# ============================================================
# collector.py
# Scoreman 해외 최종배당 백그라운드 수집기
#
# 기능
# 1. 경기 페이지 수집
# 2. 실제 홈팀 / 원정팀 이름 검증
# 3. 실제 점수 및 승무패 검증
# 4. 해외업체 최종배당 수집
# 5. 전체 업체 / 선택 업체 수집
# 6. 경기 / 배당 / 완료상태 저장
# 7. 실패 경기 완료 처리 방지
# 8. 백그라운드 수집 / 중지 / 이어받기
# 9. 진행률 / 로그 / 통계
# 10. 자동 재시도 없음
# 11. API 응답 구조 진단
# 12. 잘못된 팀명 저장 방지
# ============================================================

import re
import time
import json
import html as html_lib
import threading

from datetime import datetime
from html.parser import HTMLParser

import requests
import database


# ============================================================
# 기본 설정
# ============================================================

BASE_URL = "https://www.scoreman123.com"

MATCH_URL = (
    BASE_URL
    + "/match/data-{schedule_id}"
)

ODDS_URL = (
    BASE_URL
    + "/ajax/soccerajax?type=14&t=1&id={schedule_id}&h=0"
)

REQUEST_TIMEOUT = 25
DEFAULT_DELAY = 0.5
MAX_LOGS = 1500

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; K) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/130.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    "Referer": BASE_URL + "/",
})


# ============================================================
# 작업 상태
# ============================================================

job = {
    "running": False,
    "finished": False,

    "current": 0,
    "total": 0,

    "success": 0,
    "exists": 0,
    "failed": 0,
    "odds": 0,

    "start_id": 0,
    "end_id": 0,

    "last_completed_id": None,

    "selected_companies": [],
    "delay": DEFAULT_DELAY,

    "start_time": None,
    "end_time": None,

    "log": [],
    "result": "",
    "error": "",
}

lock = threading.RLock()


# ============================================================
# 로그
# ============================================================

def add_log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {message}"

    with lock:
        job["log"].append(line)

        if len(job["log"]) > MAX_LOGS:
            job["log"] = job["log"][-MAX_LOGS:]

    print(line, flush=True)


def get_job_status():
    with lock:
        return {
            **job,
            "log": list(job["log"]),
            "selected_companies": list(
                job["selected_companies"]
            ),
        }


def get_logs():
    with lock:
        return list(job["log"])


def clear_logs():
    with lock:
        job["log"] = []


def is_running():
    with lock:
        return bool(job["running"])


# ============================================================
# 중지
# ============================================================

def stop_collection():
    with lock:
        if not job["running"]:
            return False

        job["running"] = False

    add_log("🛑 수집 중지 요청")
    return True


# ============================================================
# 문자열 정리
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    value = html_lib.unescape(str(value))

    value = value.replace("\\/", "/")

    value = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    value = re.sub(
        r"[\r\n\t]+",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


# ============================================================
# 대소문자를 구분하지 않는 딕셔너리 조회
# ============================================================

def get_ci(data, key, default=None):
    """
    JSON 키의 대소문자가 다른 경우에도 조회한다.
    """

    if not isinstance(data, dict):
        return default

    wanted = str(key).lower()

    for current_key, value in data.items():
        if str(current_key).lower() == wanted:
            return value

    return default


# ============================================================
# 숫자 변환
# ============================================================

def to_float(value):
    try:
        if value is None:
            return None

        if isinstance(value, bool):
            return None

        value = str(value).strip()
        value = value.replace(",", "")

        if not value:
            return None

        number = float(value)

        if number <= 0:
            return None

        return number

    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None


def score_int(value):
    """
    실제 점수 변환.
    임의의 HTML 숫자를 점수로 간주하지 않는다.
    """

    try:
        if value is None:
            return None

        if isinstance(value, bool):
            return None

        if isinstance(value, int):
            number = value

        elif isinstance(value, float):
            if not value.is_integer():
                return None

            number = int(value)

        else:
            value = html_lib.unescape(
                str(value)
            ).strip()

            if not re.fullmatch(
                r"\d{1,2}",
                value,
            ):
                return None

            number = int(value)

        if 0 <= number <= 30:
            return number

    except Exception:
        pass

    return None


# ============================================================
# 승무패 계산
# ============================================================

def calculate_result(home_score, away_score):
    home = score_int(home_score)
    away = score_int(away_score)

    if home is None or away is None:
        return None

    if home > away:
        return "승"

    if home == away:
        return "무"

    return "패"


# ============================================================
# 경기 페이지 요청
# ============================================================

def fetch_match_page(schedule_id):
    url = MATCH_URL.format(
        schedule_id=schedule_id
    )

    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT,
    )

    add_log(
        f"[페이지] ID={schedule_id} "
        f"HTTP={response.status_code} "
        f"SIZE={len(response.text):,}"
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"경기 페이지 HTTP={response.status_code}"
        )

    if not response.text.strip():
        raise RuntimeError(
            "경기 페이지 내용이 비어 있습니다."
        )

    return response.text


# ============================================================
# 홈 / 원정 구분
# ============================================================

def classify_side(class_text):
    value = str(
        class_text or ""
    ).lower()

    value = value.replace("_", "-")

    away_markers = (
        "away-team",
        "awayteam",
        "team-away",
        "teamaway",
        "guest-team",
        "guestteam",
        "team-right",
        "team-r",
        "away",
        "guest",
        "team2",
    )

    home_markers = (
        "home-team",
        "hometeam",
        "team-home",
        "teamhome",
        "host-team",
        "hostteam",
        "team-left",
        "team-l",
        "home",
        "host",
        "team1",
    )

    for marker in away_markers:
        if marker in value:
            return "away"

    for marker in home_markers:
        if marker in value:
            return "home"

    return None


# ============================================================
# 팀명 검증
# ============================================================

def valid_team_name(value):
    value = clean_text(value)

    if not value:
        return False

    if len(value) < 2 or len(value) > 100:
        return False

    # 숫자나 점수만 있는 이름 제외
    if re.fullmatch(
        r"[\d\s:./-]+",
        value,
    ):
        return False

    lowered = value.lower().strip()

    # 실제 팀명이 아닌 화면 표시 문구
    invalid_exact = {
        "홈",
        "원정",
        "홈팀",
        "원정팀",
        "홈 팀",
        "원정 팀",
        "home",
        "away",
        "host",
        "guest",
        "home team",
        "away team",
        "home_team",
        "away_team",
        "홈팀명",
        "원정팀명",
        "미정",
        "알수없음",
        "unknown",
        "undefined",
        "null",
        "none",
        "n/a",
        "loading",
        "scoreman",
    }

    if lowered in invalid_exact:
        return False

    if re.search(
        r"\b\d{1,2}\s*[-:]\s*\d{1,2}\b",
        value,
    ):
        return False

    if any(
        word in lowered
        for word in (
            "javascript",
            "function",
            "undefined",
        )
    ):
        return False

    return True


# ============================================================
# HTML 팀명 / 점수 파서
# ============================================================

class MatchHTMLParser(HTMLParser):

    VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self):
        super().__init__(
            convert_charrefs=True
        )

        self.stack = []

        self.team_candidates = {
            "home": [],
            "away": [],
        }

        self.score_candidates = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        attrs_dict = dict(attrs)

        class_text = (
            str(attrs_dict.get("class", ""))
            + " "
            + str(attrs_dict.get("id", ""))
        ).lower()

        side = classify_side(class_text)

        is_score = (
            "score" in class_text
            or "result-score" in class_text
        )

        node = {
            "tag": tag,
            "side": side,
            "is_score": is_score,
            "parts": [],
        }

        if tag not in self.VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

        if tag.lower() not in self.VOID_TAGS:
            self.handle_endtag(tag)

    def handle_data(self, data):
        if not data:
            return

        for node in self.stack:
            if node["side"] or node["is_score"]:
                node["parts"].append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()

        index = None

        for i in range(
            len(self.stack) - 1,
            -1,
            -1,
        ):
            if self.stack[i]["tag"] == tag:
                index = i
                break

        if index is None:
            return

        popped = self.stack[index:]

        self.stack = self.stack[:index]

        for node in reversed(popped):
            text = clean_text(
                " ".join(node["parts"])
            )

            if not text:
                continue

            if node["side"]:
                if valid_team_name(text):
                    self.team_candidates[
                        node["side"]
                    ].append(text)

            if node["is_score"]:
                self.score_candidates.append(text)


# ============================================================
# JSON 스크립트 추출
# ============================================================

def extract_json_scripts(page_html):
    results = []

    pattern = (
        r"<script\b([^>]*)>(.*?)</script\s*>"
    )

    matches = re.findall(
        pattern,
        page_html,
        re.I | re.S,
    )

    for attrs, body in matches:
        attrs = str(attrs or "")

        body = html_lib.unescape(
            body or ""
        ).strip()

        if not body:
            continue

        is_json = bool(
            re.search(
                r'application/(?:ld\+)?json',
                attrs,
                re.I,
            )
        )

        if is_json:
            try:
                results.append(
                    json.loads(body)
                )
            except Exception:
                pass

            continue

        # 스크립트 본문 자체가 JSON인 경우
        if body.startswith("{") or body.startswith("["):
            try:
                results.append(
                    json.loads(body)
                )
            except Exception:
                pass

    return results


# ============================================================
# JSON 파싱
# ============================================================

def parse_json(text):
    if not isinstance(text, str):
        return None

    text = text.strip()

    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        pass

    # 응답 앞뒤에 다른 문자가 붙어 있는 경우
    decoder = json.JSONDecoder()

    for index, char in enumerate(text):
        if char not in "{[":
            continue

        try:
            data, _ = decoder.raw_decode(
                text[index:]
            )

            if isinstance(data, (dict, list)):
                return data

        except Exception:
            continue

    # JSON 문자열이 한 번 더 인코딩된 경우
    try:
        decoded = json.loads(text)

        if isinstance(decoded, str):
            return parse_json(decoded)

    except Exception:
        pass

    return None


# ============================================================
# JSON 팀명 추출
# ============================================================

def name_from_value(value):
    if isinstance(value, str):
        value = clean_text(value)

        if valid_team_name(value):
            return value

        return ""

    if isinstance(value, dict):
        preferred = (
            "name",
            "teamName",
            "team_name",
            "teamname",
            "cn",
            "en",
            "shortName",
            "short_name",
            "value",
        )

        for key in preferred:
            result = name_from_value(
                get_ci(value, key)
            )

            if result:
                return result

    return ""


def recursive_team_search(obj):
    if isinstance(obj, dict):
        lower = {
            str(key).lower(): value
            for key, value in obj.items()
        }

        pairs = [
            ("hometeam", "awayteam"),
            ("home_team", "away_team"),
            ("home_team_name", "away_team_name"),
            ("hometeamname", "awayteamname"),
            ("home_name", "away_name"),
            ("hteam", "ateam"),
            ("home", "away"),
            ("hostname", "guestname"),
            ("host", "guest"),
            ("team1", "team2"),
        ]

        for home_key, away_key in pairs:
            if (
                home_key not in lower
                or away_key not in lower
            ):
                continue

            home = name_from_value(
                lower[home_key]
            )

            away = name_from_value(
                lower[away_key]
            )

            if (
                valid_team_name(home)
                and valid_team_name(away)
                and home != away
            ):
                return home, away

        for value in obj.values():
            found = recursive_team_search(value)

            if found:
                return found

    elif isinstance(obj, list):
        for value in obj:
            found = recursive_team_search(value)

            if found:
                return found

    return None


# ============================================================
# 제목 / 메타 태그 팀명 추출
# ============================================================

def extract_title_candidates(page_html):
    values = []

    patterns = [
        r"<title[^>]*>(.*?)</title>",
        (
            r'<meta[^>]+property=["\']og:title["\']'
            r'[^>]+content=["\']([^"\']+)["\']'
        ),
        (
            r'<meta[^>]+content=["\']([^"\']+)["\']'
            r'[^>]+property=["\']og:title["\']'
        ),
    ]

    for pattern in patterns:
        found = re.findall(
            pattern,
            page_html,
            re.I | re.S,
        )

        for value in found:
            value = clean_text(value)

            if value:
                values.append(value)

    return values


def teams_from_title(page_html):
    patterns = [
        r"\s+vs\.?\s+",
        r"\s+v\s+",
        r"\s+对阵\s+",
        r"\s+对\s+",
    ]

    for title in extract_title_candidates(page_html):
        for pattern in patterns:
            parts = re.split(
                pattern,
                title,
                maxsplit=1,
                flags=re.I,
            )

            if len(parts) != 2:
                continue

            home = clean_text(parts[0])
            away = clean_text(parts[1])

            # 사이트 이름이나 경기 외 설명 제거
            away = re.split(
                r"\s+[|｜]\s+|\s+-\s+",
                away,
                maxsplit=1,
            )[0].strip()

            if (
                valid_team_name(home)
                and valid_team_name(away)
                and home != away
            ):
                return home, away

    return None


# ============================================================
# 팀명 추출
# ============================================================

def extract_team_names(page_html):

    # 1. JSON 데이터
    for data in extract_json_scripts(page_html):
        found = recursive_team_search(data)

        if found:
            home, away = found

            if (
                valid_team_name(home)
                and valid_team_name(away)
            ):
                return home, away

    # 2. HTML 클래스 기반
    parser = MatchHTMLParser()

    try:
        parser.feed(page_html)
        parser.close()
    except Exception:
        pass

    home_candidates = sorted(
        set(
            clean_text(value)
            for value in parser.team_candidates["home"]
            if valid_team_name(value)
        ),
        key=len,
    )

    away_candidates = sorted(
        set(
            clean_text(value)
            for value in parser.team_candidates["away"]
            if valid_team_name(value)
        ),
        key=len,
    )

    for home in home_candidates:
        for away in away_candidates:
            if (
                valid_team_name(home)
                and valid_team_name(away)
                and home != away
            ):
                return home, away

    # 3. 제목 기반
    found = teams_from_title(page_html)

    if found:
        return found

    # 팀명을 모르면 임의로 지정하지 않는다.
    return "", ""


# ============================================================
# 점수 문자열 추출
# ============================================================

def score_pair_from_string(value):
    if not isinstance(value, str):
        return None

    value = clean_text(value)

    match = re.fullmatch(
        r"\s*(\d{1,2})\s*[-:]\s*(\d{1,2})\s*",
        value,
    )

    if not match:
        return None

    home = score_int(match.group(1))
    away = score_int(match.group(2))

    if home is None or away is None:
        return None

    return home, away


# ============================================================
# JSON 점수 검색
# ============================================================

def recursive_score_search(obj):
    if isinstance(obj, dict):
        lower = {
            str(key).lower(): value
            for key, value in obj.items()
        }

        pairs = [
            ("homescore", "awayscore"),
            ("home_score", "away_score"),
            ("home_score1", "away_score1"),
            ("hscore", "ascore"),
            ("h_score", "a_score"),
            ("homescore1", "awayscore1"),
            ("homegoals", "awaygoals"),
            ("home_goal", "away_goal"),
            ("hs", "as"),
        ]

        for home_key, away_key in pairs:
            if (
                home_key in lower
                and away_key in lower
            ):
                home = score_int(
                    lower[home_key]
                )

                away = score_int(
                    lower[away_key]
                )

                if (
                    home is not None
                    and away is not None
                ):
                    return home, away

        score_keys = (
            "score",
            "matchscore",
            "match_score",
            "fullscore",
            "full_score",
            "finalscore",
            "final_score",
            "ftscore",
            "ft_score",
        )

        for key in score_keys:
            if key in lower:
                found = score_pair_from_string(
                    lower[key]
                )

                if found:
                    return found

        for value in obj.values():
            found = recursive_score_search(value)

            if found:
                return found

    elif isinstance(obj, list):
        for value in obj:
            found = recursive_score_search(value)

            if found:
                return found

    return None


# ============================================================
# HTML 점수 추출
# ============================================================

def extract_score(page_html):

    # 1. JSON
    for data in extract_json_scripts(page_html):
        found = recursive_score_search(data)

        if found:
            home, away = found

            return (
                home,
                away,
                calculate_result(home, away),
            )

    # 2. 명시적인 점수 필드
    patterns = [
        (
            r'"homeScore"\s*:\s*["\']?(\d{1,2})',
            r'"awayScore"\s*:\s*["\']?(\d{1,2})',
        ),
        (
            r'"home_score"\s*:\s*["\']?(\d{1,2})',
            r'"away_score"\s*:\s*["\']?(\d{1,2})',
        ),
        (
            r'"homescore"\s*:\s*["\']?(\d{1,2})',
            r'"awayscore"\s*:\s*["\']?(\d{1,2})',
        ),
        (
            r'"hscore"\s*:\s*["\']?(\d{1,2})',
            r'"ascore"\s*:\s*["\']?(\d{1,2})',
        ),
    ]

    for home_pattern, away_pattern in patterns:
        home_values = re.findall(
            home_pattern,
            page_html,
            re.I,
        )

        away_values = re.findall(
            away_pattern,
            page_html,
            re.I,
        )

        if not home_values or not away_values:
            continue

        home = score_int(home_values[-1])
        away = score_int(away_values[-1])

        if (
            home is not None
            and away is not None
        ):
            return (
                home,
                away,
                calculate_result(home, away),
            )

    # 3. 명시적인 score HTML
    parser = MatchHTMLParser()

    try:
        parser.feed(page_html)
        parser.close()
    except Exception:
        pass

    for value in reversed(
        parser.score_candidates
    ):
        found = score_pair_from_string(value)

        if found:
            home, away = found

            return (
                home,
                away,
                calculate_result(home, away),
            )

    # 4. data-score
    data_scores = re.findall(
        r'data-score\s*=\s*["\']([^"\']+)["\']',
        page_html,
        re.I,
    )

    for value in reversed(data_scores):
        found = score_pair_from_string(value)

        if found:
            home, away = found

            return (
                home,
                away,
                calculate_result(home, away),
            )

    return None, None, None


# ============================================================
# 경기 날짜 추출
# ============================================================

def extract_match_date(page_html):
    patterns = [
        r'"matchDate"\s*:\s*"([^"]+)"',
        r'"match_date"\s*:\s*"([^"]+)"',
        r'"matchTime"\s*:\s*"([^"]+)"',
        r'"match_time"\s*:\s*"([^"]+)"',
    ]

    for pattern in patterns:
        found = re.findall(
            pattern,
            page_html,
            re.I,
        )

        for value in reversed(found):
            value = clean_text(value)

            if value:
                return value

    dates = re.findall(
        r"(?<!\d)"
        r"(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})"
        r"(?!\d)",
        page_html,
    )

    if dates:
        return clean_text(dates[0])

    return None


# ============================================================
# 배당 API 요청
# ============================================================

def fetch_odds(schedule_id):
    url = ODDS_URL.format(
        schedule_id=schedule_id
    )

    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT,
    )

    add_log(
        f"[배당 API] ID={schedule_id} "
        f"HTTP={response.status_code} "
        f"SIZE={len(response.text):,}"
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"배당 API HTTP={response.status_code}"
        )

    if not response.text.strip():
        raise RuntimeError(
            "배당 API 응답이 비어 있습니다."
        )

    return response.text


# ============================================================
# 최종배당 숫자 구조 읽기
# ============================================================

def read_final_prices(final_odds):
    """
    최종배당만 읽는다.

    표준 구조:
        {"u": 홈승, "g": 무승부, "d": 원정승}

    euro.f 등의 초기배당은 절대 사용하지 않는다.
    """

    if isinstance(final_odds, dict):
        home = to_float(
            get_ci(final_odds, "u")
        )

        draw = to_float(
            get_ci(final_odds, "g")
        )

        away = to_float(
            get_ci(final_odds, "d")
        )

    elif isinstance(final_odds, (list, tuple)):
        if len(final_odds) < 3:
            return None

        home = to_float(final_odds[0])
        draw = to_float(final_odds[1])
        away = to_float(final_odds[2])

    else:
        return None

    if (
        home is None
        or draw is None
        or away is None
    ):
        return None

    if (
        home > 1000
        or draw > 1000
        or away > 1000
    ):
        return None

    return home, draw, away


# ============================================================
# 업체 목록 구조 읽기
# ============================================================

def get_mixodds_container(data):
    """
    API 구조가 조금 달라도 Data.mixodds를 찾는다.
    """

    if not isinstance(data, dict):
        return None

    container = get_ci(data, "Data")

    if isinstance(container, str):
        container = parse_json(container)

    if isinstance(container, dict):
        mixodds = get_ci(
            container,
            "mixodds",
        )

        if mixodds is not None:
            if isinstance(mixodds, str):
                mixodds = parse_json(mixodds)

            return mixodds

    # 일부 응답은 최상위에 mixodds가 존재한다.
    mixodds = get_ci(data, "mixodds")

    if isinstance(mixodds, str):
        mixodds = parse_json(mixodds)

    if mixodds is not None:
        return mixodds

    # Data 자체가 업체 목록인 구조
    if isinstance(container, list):
        return container

    return None


# ============================================================
# 배당 API 응답 진단
# ============================================================

def diagnose_odds_response(schedule_id, data):
    """
    최종배당을 추출하지 못한 이유를 확인할 수 있도록
    JSON 구조를 간단히 로그에 남긴다.
    """

    if not isinstance(data, dict):
        add_log(
            f"[배당 진단] ID={schedule_id} "
            f"최상위 JSON이 dict가 아닙니다. "
            f"type={type(data).__name__}"
        )
        return

    add_log(
        f"[배당 진단] ID={schedule_id} "
        f"최상위 키={list(data.keys())[:20]}"
    )

    container = get_ci(data, "Data")

    if isinstance(container, dict):
        add_log(
            f"[배당 진단] ID={schedule_id} "
            f"Data 키={list(container.keys())[:20]}"
        )

    mixodds = get_mixodds_container(data)

    if isinstance(mixodds, list):
        add_log(
            f"[배당 진단] ID={schedule_id} "
            f"업체 목록 개수={len(mixodds)}"
        )

        for item in mixodds[:2]:
            if not isinstance(item, dict):
                continue

            euro = get_ci(item, "euro")

            if isinstance(euro, str):
                euro = parse_json(euro)

            if isinstance(euro, dict):
                final_data = get_ci(euro, "l")

                add_log(
                    f"[배당 진단] ID={schedule_id} "
                    f"업체={get_ci(item, 'cn', '이름없음')} "
                    f"euro 키={list(euro.keys())[:15]} "
                    f"최종배당 구조="
                    f"{type(final_data).__name__}"
                )

                if isinstance(final_data, dict):
                    add_log(
                        f"[배당 진단] ID={schedule_id} "
                        f"최종배당 키="
                        f"{list(final_data.keys())[:10]}"
                    )

    elif isinstance(mixodds, dict):
        add_log(
            f"[배당 진단] ID={schedule_id} "
            f"업체 목록이 dict 형태입니다. "
            f"키={list(mixodds.keys())[:20]}"
        )

    else:
        add_log(
            f"[배당 진단] ID={schedule_id} "
            f"mixodds를 찾지 못했습니다. "
            f"type={type(mixodds).__name__}"
        )


# ============================================================
# 해외업체 최종배당 추출
# ============================================================

def extract_bookmakers(data):
    """
    최종배당 euro.l만 수집한다.
    """

    mixodds = get_mixodds_container(data)

    if isinstance(mixodds, dict):
        items = list(mixodds.values())

    elif isinstance(mixodds, list):
        items = mixodds

    else:
        return []

    result = []
    seen = set()

    for item in items:
        if not isinstance(item, dict):
            continue

        cid = (
            get_ci(item, "cid")
            or get_ci(item, "company_id")
            or get_ci(item, "companyId")
            or get_ci(item, "id")
        )

        if cid is None:
            continue

        name = (
            get_ci(item, "cn")
            or get_ci(item, "company_name")
            or get_ci(item, "companyName")
            or get_ci(item, "name")
            or ""
        )

        name = clean_text(name)

        euro = get_ci(item, "euro")

        if isinstance(euro, str):
            euro = parse_json(euro)

        if not isinstance(euro, dict):
            continue

        # 최종배당만 사용
        final_odds = get_ci(euro, "l")

        prices = read_final_prices(final_odds)

        if prices is None:
            continue

        home, draw, away = prices

        unique_key = (
            str(cid).strip(),
            name.lower(),
        )

        if unique_key in seen:
            continue

        seen.add(unique_key)

        result.append({
            "cid": str(cid),
            "name": name or str(cid),
            "home": home,
            "draw": draw,
            "away": away,
        })

    return result


# ============================================================
# 업체 선택 필터
# ============================================================

def filter_bookmakers(
    bookmakers,
    selected_companies=None,
):
    if not selected_companies:
        return bookmakers

    selected = {
        str(value).strip().lower()
        for value in selected_companies
        if str(value).strip()
    }

    result = []

    for item in bookmakers:
        cid = str(
            item["cid"]
        ).strip().lower()

        name = str(
            item["name"]
        ).strip().lower()

        if (
            cid in selected
            or name in selected
        ):
            result.append(item)

    return result


# ============================================================
# 단일 경기 수집
# ============================================================

def collect_one_match(
    schedule_id,
    selected_companies=None,
):
    schedule_id = int(schedule_id)

    # --------------------------------------------------------
    # 1. 완료된 경기 확인
    # --------------------------------------------------------

    if database.is_collection_completed(schedule_id):
        add_log(
            f"[중복] ID={schedule_id}"
        )

        return "exists"

    # --------------------------------------------------------
    # 2. 경기 페이지
    # --------------------------------------------------------

    page_html = fetch_match_page(schedule_id)

    if not is_running():
        return "stopped"

    # --------------------------------------------------------
    # 3. 실제 팀명
    # --------------------------------------------------------

    home_team, away_team = extract_team_names(
        page_html
    )

    if (
        not valid_team_name(home_team)
        or not valid_team_name(away_team)
        or home_team == away_team
    ):
        add_log(
            f"[팀명 미확인] ID={schedule_id} "
            f"홈={home_team!r} "
            f"원정={away_team!r}"
        )

        raise RuntimeError(
            "실제 홈팀 / 원정팀 이름 추출 실패"
        )

    # --------------------------------------------------------
    # 4. 실제 점수 및 승무패
    # --------------------------------------------------------

    home_score, away_score, result = extract_score(
        page_html
    )

    match_date = extract_match_date(
        page_html
    )

    if (
        home_score is None
        or away_score is None
        or result not in ("승", "무", "패")
    ):
        add_log(
            f"[결과 미확인] ID={schedule_id} "
            f"{home_team} vs {away_team}"
        )

        # 결과 미확인 경기와 임의 점수를 저장하지 않는다.
        # 완료 상태도 기록하지 않는다.
        raise RuntimeError(
            "실제 경기 점수 확인 실패"
        )

    verified_result = calculate_result(
        home_score,
        away_score,
    )

    if verified_result != result:
        raise RuntimeError(
            "실제 점수와 승무패 결과가 일치하지 않습니다."
        )

    add_log(
        f"[경기결과] ID={schedule_id} "
        f"{home_team} "
        f"{home_score}-{away_score} "
        f"{away_team} "
        f"결과={result}"
    )

    # --------------------------------------------------------
    # 5. 배당 API
    # --------------------------------------------------------

    if not is_running():
        return "stopped"

    odds_text = fetch_odds(schedule_id)

    odds_data = parse_json(odds_text)

    if odds_data is None:
        add_log(
            f"[배당 진단] ID={schedule_id} "
            f"JSON 파싱 실패 "
            f"응답 앞부분={odds_text[:250]!r}"
        )

        raise RuntimeError(
            "배당 API JSON 파싱 실패"
        )

    bookmakers = extract_bookmakers(
        odds_data
    )

    bookmakers = filter_bookmakers(
        bookmakers,
        selected_companies,
    )

    add_log(
        f"[배당 추출] ID={schedule_id} "
        f"업체={len(bookmakers)}"
    )

    if not bookmakers:
        diagnose_odds_response(
            schedule_id,
            odds_data,
        )

        raise RuntimeError(
            "최종배당 없음 또는 추출 가능한 업체 없음"
        )

    if not is_running():
        return "stopped"

    # --------------------------------------------------------
    # 6. 경기 저장
    # --------------------------------------------------------

    saved_match = database.save_match(
        schedule_id,
        match_date,
        home_team,
        away_team,
        home_score,
        away_score,
        result,
        "scoreman",
    )

    if saved_match is False:
        raise RuntimeError(
            "경기 저장 실패"
        )

    # --------------------------------------------------------
    # 7. 업체별 최종배당 저장
    # --------------------------------------------------------

    saved_odds = 0

    for item in bookmakers:
        if not is_running():
            add_log(
                f"[중지] ID={schedule_id} "
                "배당 저장 도중 중지되었습니다."
            )

            return "stopped"

        ok = database.save_odds(
            schedule_id,
            item["cid"],
            item["name"],
            item["home"],
            item["draw"],
            item["away"],
        )

        if ok is False:
            raise RuntimeError(
                f"배당 저장 실패: {item['name']}"
            )

        saved_odds += 1

        add_log(
            f"[배당 저장] ID={schedule_id} "
            f"업체={item['name']} "
            f"승={item['home']} "
            f"무={item['draw']} "
            f"패={item['away']}"
        )

    if saved_odds <= 0:
        raise RuntimeError(
            "저장된 최종배당 없음"
        )

    # --------------------------------------------------------
    # 8. 모든 저장 성공 후 완료 상태
    # --------------------------------------------------------

    if not is_running():
        return "stopped"

    state_saved = database.save_collection_state(
        schedule_id,
        "completed",
    )

    if state_saved is False:
        raise RuntimeError(
            "완료 상태 저장 실패"
        )

    add_log(
        f"[수집 성공] ID={schedule_id} "
        f"업체={saved_odds} "
        f"결과={result}"
    )

    return {
        "status": "success",
        "odds": saved_odds,
        "result": result,
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
    }


# ============================================================
# 백그라운드 작업
# ============================================================

def _worker():

    with lock:
        start_id = int(job["start_id"])
        end_id = int(job["end_id"])
        delay = float(job["delay"])

        selected = list(
            job["selected_companies"]
        )

        job["start_time"] = datetime.now().isoformat(
            timespec="seconds"
        )

        job["total"] = end_id - start_id + 1

    add_log("=" * 50)
    add_log("⚽ Scoreman 백그라운드 수집 시작")

    add_log(
        f"범위: {start_id:,} ~ {end_id:,}"
    )

    add_log(
        "팀명 / 실제 점수 / 승무패 검증 후 저장"
    )

    add_log(
        "실패 / 결과미확인 / 배당없음은 "
        "완료 ID로 저장하지 않음"
    )

    add_log("자동 재시도: 없음")

    add_log(
        f"요청 간격: {delay:.2f}초"
    )

    if selected:
        add_log(
            "수집 업체: "
            + ", ".join(map(str, selected))
        )
    else:
        add_log(
            "수집 업체: 전체 업체 자동수집"
        )

    add_log("=" * 50)

    try:
        for index, schedule_id in enumerate(
            range(start_id, end_id + 1),
            start=1,
        ):
            if not is_running():
                break

            with lock:
                job["current"] = index

            try:
                result = collect_one_match(
                    schedule_id,
                    selected,
                )

                if isinstance(result, dict):
                    with lock:
                        job["success"] += 1

                        job["odds"] += int(
                            result.get("odds", 0)
                        )

                        job["last_completed_id"] = int(
                            schedule_id
                        )

                elif result == "exists":
                    with lock:
                        job["exists"] += 1

                        job["last_completed_id"] = int(
                            schedule_id
                        )

                elif result == "stopped":
                    break

            except Exception as error:
                with lock:
                    job["failed"] += 1

                    job["error"] = (
                        f"ID={schedule_id}: "
                        f"{type(error).__name__}: {error}"
                    )

                add_log(
                    f"[수집 실패] ID={schedule_id} "
                    f"오류={type(error).__name__}: "
                    f"{error}"
                )

            if (
                delay > 0
                and is_running()
                and schedule_id < end_id
            ):
                time.sleep(delay)

    except Exception as error:
        with lock:
            job["error"] = (
                f"{type(error).__name__}: {error}"
            )

        add_log(
            f"[작업 오류] "
            f"{type(error).__name__}: {error}"
        )

    finally:
        with lock:
            job["running"] = False
            job["finished"] = True

            job["end_time"] = datetime.now().isoformat(
                timespec="seconds"
            )

            job["result"] = (
                f"성공 {job['success']} / "
                f"중복 {job['exists']} / "
                f"실패 {job['failed']} / "
                f"배당 {job['odds']}"
            )

            success = job["success"]
            exists = job["exists"]
            failed = job["failed"]
            odds = job["odds"]

        add_log("=" * 50)
        add_log("🏁 Scoreman 수집 종료")

        add_log(
            f"성공={success} "
            f"중복={exists} "
            f"실패={failed} "
            f"배당={odds}"
        )

        add_log("=" * 50)


# ============================================================
# 수집 시작
# ============================================================

def start_background_collection(
    start_id,
    end_id,
    selected_companies=None,
    delay=DEFAULT_DELAY,
):

    try:
        start_id = int(start_id)
        end_id = int(end_id)

    except Exception:
        return False, "ID는 숫자로 입력하세요."

    if start_id <= 0:
        return False, "시작 ID 오류"

    if end_id < start_id:
        return False, "종료 ID 오류"

    try:
        delay = float(delay)
    except Exception:
        delay = DEFAULT_DELAY

    if delay < 0:
        delay = 0

    if delay > 10:
        delay = 10

    selected_companies = (
        selected_companies or []
    )

    with lock:
        if job["running"]:
            return False, "이미 수집 중입니다."

        job["running"] = True
        job["finished"] = False

        job["current"] = 0
        job["total"] = end_id - start_id + 1

        job["success"] = 0
        job["exists"] = 0
        job["failed"] = 0
        job["odds"] = 0

        job["start_id"] = start_id
        job["end_id"] = end_id

        job["last_completed_id"] = None

        job["selected_companies"] = list(
            selected_companies
        )

        job["delay"] = delay

        job["start_time"] = None
        job["end_time"] = None

        job["log"] = []
        job["result"] = ""
        job["error"] = ""

        try:
            thread = threading.Thread(
                target=_worker,
                daemon=True,
                name="ScoremanCollector",
            )

            thread.start()

        except Exception as error:
            job["running"] = False
            job["finished"] = True
            job["error"] = str(error)

            return (
                False,
                f"수집 스레드 시작 실패: {error}",
            )

    return True, "수집을 시작했습니다."


# ============================================================
# 이어받기
# ============================================================

def resume_collection(
    end_id,
    selected_companies=None,
    delay=DEFAULT_DELAY,
):

    try:
        last_id = database.get_last_completed_id()

    except Exception as error:
        return (
            False,
            f"완료 ID 조회 실패: {error}",
        )

    if last_id is None:
        return (
            False,
            "저장된 완료 ID가 없습니다.",
        )

    try:
        end_id = int(end_id)
        last_id = int(last_id)

    except Exception:
        return False, "ID 오류"

    next_id = last_id + 1

    if next_id > end_id:
        return (
            False,
            f"이어받을 ID가 없습니다. "
            f"마지막 완료 ID={last_id:,}",
        )

    return start_background_collection(
        next_id,
        end_id,
        selected_companies or [],
        delay,
    )


# ============================================================
# 진행률
# ============================================================

def get_progress():
    with lock:
        total = int(job["total"] or 0)
        current = int(job["current"] or 0)

        percent = (
            current / total * 100
            if total > 0
            else 0.0
        )

        return {
            "current": current,
            "total": total,
            "percent": percent,

            "success": job["success"],
            "exists": job["exists"],
            "failed": job["failed"],
            "odds": job["odds"],

            "running": job["running"],
            "finished": job["finished"],

            "last_completed_id":
                job["last_completed_id"],
        }


# ============================================================
# 단일 경기 수집
# ============================================================

def collect_single(
    schedule_id,
    selected_companies=None,
):

    with lock:
        if job["running"]:
            return {
                "status": "failed",
                "error": "이미 수집 작업이 실행 중입니다.",
            }

        job["running"] = True
        job["finished"] = False
        job["error"] = ""

    try:
        result = collect_one_match(
            int(schedule_id),
            selected_companies or [],
        )

        return result

    except Exception as error:
        add_log(
            f"[단일 경기 실패] "
            f"ID={schedule_id} "
            f"{type(error).__name__}: {error}"
        )

        return {
            "status": "failed",
            "error": str(error),
        }

    finally:
        with lock:
            job["running"] = False
            job["finished"] = True

            job["end_time"] = datetime.now().isoformat(
                timespec="seconds"
            )
