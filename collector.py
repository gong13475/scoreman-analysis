# ============================================================
# collector.py
# Scoreman 해외 최종배당 수집기
#
# 기능
# 1. 경기 페이지 수집
# 2. 홈팀 / 원정팀 추출
# 3. 실제 점수 및 승무패 검증
# 4. 해외업체 최종배당 euro.l만 추출
# 5. 경기 및 배당 저장
# 6. 전체 및 업체별 수집 상태 저장
# 7. 중지 / 이어받기
# 8. 진행률 / 로그
# 9. 자동 재시도 없음
# 10. 점수 추출 진단 강화
# 11. 선택 업체 수집 시 부분 완료 처리
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

MATCH_URL = BASE_URL + "/match/data-{schedule_id}"

ODDS_URL = (
    BASE_URL
    + "/ajax/soccerajax?type=14&t=1&id={schedule_id}&h=0"
)

REQUEST_TIMEOUT = 25
DEFAULT_DELAY = 0.5
MAX_LOGS = 1500


# ============================================================
# HTTP 세션
# ============================================================

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
# 수집 중지
# ============================================================

def stop_collection():

    with lock:

        if not job["running"]:
            return False

        job["running"] = False

    add_log("수집 중지 요청")

    return True


# ============================================================
# 문자열 정리
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    value = html_lib.unescape(str(value))

    value = value.replace("\\/", "/")

    value = re.sub(r"<[^>]+>", " ", value)

    value = re.sub(r"[\r\n\t]+", " ", value)

    value = re.sub(r"\s+", " ", value)

    return value.strip()


# ============================================================
# 대소문자 구분 없는 JSON 키 조회
# ============================================================

def get_ci(data, key, default=None):

    if not isinstance(data, dict):
        return default

    wanted = str(key).lower()

    for current_key, value in data.items():

        if str(current_key).lower() == wanted:
            return value

    return default


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

    return None


# ============================================================
# JSON 스크립트 추출
# ============================================================

def extract_json_scripts(page_html):

    results = []

    pattern = r"<script\b([^>]*)>(.*?)</script\s*>"

    for attrs, body in re.findall(
        pattern,
        page_html,
        re.I | re.S,
    ):

        body = html_lib.unescape(
            body or ""
        ).strip()

        if not body:
            continue

        is_json = bool(
            re.search(
                r'application/(?:ld\+)?json',
                attrs or "",
                re.I,
            )
        )

        if (
            is_json
            or body.startswith(("{", "["))
            or re.search(
                r"\b(?:homeScore|home_score|hscore|matchscore)\b",
                body,
                re.I,
            )
        ):

            data = parse_json(body)

            if data is not None:
                results.append(data)

    return results


# ============================================================
# 숫자 변환
# ============================================================

def to_float(value):

    try:

        if value is None or isinstance(value, bool):
            return None

        if isinstance(value, (dict, list, tuple)):
            return None

        value = str(value).strip().replace(",", "")

        if not value:
            return None

        number = float(value)

        if not 0 < number <= 1000:
            return None

        return number

    except Exception:
        return None


# ============================================================
# 점수 정수 변환
# ============================================================

def score_int(value):

    try:

        if value is None or isinstance(value, bool):
            return None

        if isinstance(value, float):

            if not value.is_integer():
                return None

            value = int(value)

        elif isinstance(value, str):

            value = value.strip()

            if not re.fullmatch(r"\d{1,2}", value):
                return None

            value = int(value)

        else:
            value = int(value)

        if 0 <= value <= 30:
            return value

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
# 팀명 검증
# ============================================================

def valid_team_name(value):

    value = clean_text(value)

    if not value:
        return False

    if len(value) < 2 or len(value) > 100:
        return False

    if re.fullmatch(r"[\d\s:./-]+", value):
        return False

    lowered = value.lower()

    invalid = {
        "홈",
        "원정",
        "홈팀",
        "원정팀",
        "home",
        "away",
        "host",
        "guest",
        "home team",
        "away team",
        "unknown",
        "undefined",
        "null",
        "none",
        "loading",
        "scoreman",
    }

    if lowered in invalid:
        return False

    if any(
        item in lowered
        for item in (
            "javascript",
            "function",
            "undefined",
        )
    ):
        return False

    return True


# ============================================================
# JSON 팀명 추출
# ============================================================

def name_from_value(value):

    if isinstance(value, str):

        value = clean_text(value)

        return value if valid_team_name(value) else ""

    if isinstance(value, dict):

        for key in (
            "name",
            "teamName",
            "team_name",
            "teamname",
            "cn",
            "en",
            "shortName",
            "short_name",
            "value",
        ):

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
# HTML 팀명 / 점수 파서
# ============================================================

def classify_side(value):

    value = str(value or "").lower()

    away_markers = (
        "away-team",
        "awayteam",
        "team-away",
        "guest-team",
        "guestteam",
        "team-right",
        "away",
        "guest",
        "team2",
    )

    home_markers = (
        "home-team",
        "hometeam",
        "team-home",
        "host-team",
        "hostteam",
        "team-left",
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


def score_priority(class_text):

    value = str(class_text or "").lower()

    if any(
        marker in value
        for marker in (
            "half-time",
            "halftime",
            "half_time",
            "first-half",
            "firsthalf",
            "1st-half",
            "ht-score",
        )
    ):
        return -10

    if any(
        marker in value
        for marker in (
            "full-time",
            "fulltime",
            "full_time",
            "final-score",
            "finalscore",
            "ft-score",
            "result-score",
        )
    ):
        return 10

    return 0


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

        self.teams = {
            "home": [],
            "away": [],
        }

        self.scores = []

        self.score_sides = {
            "home": [],
            "away": [],
        }

    def handle_starttag(self, tag, attrs):

        tag = tag.lower()

        attrs = dict(attrs)

        class_text = (
            str(attrs.get("class", ""))
            + " "
            + str(attrs.get("id", ""))
            + " "
            + str(attrs.get("data-testid", ""))
        ).lower()

        node = {
            "tag": tag,
            "class_text": class_text,
            "side": classify_side(class_text),
            "score": (
                "score" in class_text
                or "result-score" in class_text
            ),
            "priority": score_priority(class_text),
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

            if node["side"] or node["score"]:
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

            value = clean_text(
                " ".join(node["parts"])
            )

            if not value:
                continue

            if node["side"] and not node["score"]:

                if valid_team_name(value):

                    self.teams[node["side"]].append(
                        value
                    )

            if node["score"]:

                self.scores.append(value)

                if node["side"]:

                    number = score_int(value)

                    if number is not None:

                        self.score_sides[
                            node["side"]
                        ].append(
                            (
                                node["priority"],
                                number,
                            )
                        )


# ============================================================
# 제목에서 팀명 추출
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

    for title in extract_title_candidates(page_html):

        title = re.split(
            r"\s+[|｜]\s+",
            title,
            maxsplit=1,
        )[0]

        parts = re.split(
            r"\s+(?:vs\.?|v|对阵|对)\s+",
            title,
            maxsplit=1,
            flags=re.I,
        )

        if len(parts) != 2:
            continue

        home = clean_text(parts[0])

        away = clean_text(parts[1])

        away = re.split(
            r"\s+-\s+",
            away,
            maxsplit=1,
        )[0]

        if (
            valid_team_name(home)
            and valid_team_name(away)
            and home != away
        ):

            return home, away

    return None


def extract_team_names(page_html):

    for data in extract_json_scripts(page_html):

        found = recursive_team_search(data)

        if found:
            return found

    parser = MatchHTMLParser()

    try:

        parser.feed(page_html)

        parser.close()

    except Exception:
        pass

    homes = sorted(
        set(parser.teams["home"]),
        key=len,
    )

    aways = sorted(
        set(parser.teams["away"]),
        key=len,
    )

    for home in homes:

        for away in aways:

            if (
                valid_team_name(home)
                and valid_team_name(away)
                and home != away
            ):

                return home, away

    found = teams_from_title(page_html)

    if found:
        return found

    return "", ""


# ============================================================
# 점수 문자열
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
# JSON 점수 추출
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
                home_key not in lower
                or away_key not in lower
            ):
                continue

            home = score_int(lower[home_key])

            away = score_int(lower[away_key])

            if home is not None and away is not None:
                return home, away

        for key in (
            "score",
            "matchscore",
            "match_score",
            "fullscore",
            "full_score",
            "finalscore",
            "final_score",
            "ftscore",
            "ft_score",
        ):

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
# HTML / JavaScript 점수 추출 보조
# ============================================================

def extract_score_from_named_fields(page_html):

    home_keys = (
        r"homeScore|home_score|home_score1|"
        r"hscore|h_score|homeGoals|home_goal"
    )

    away_keys = (
        r"awayScore|away_score|away_score1|"
        r"ascore|a_score|awayGoals|away_goal"
    )

    patterns = [

        rf"""["']?(?:{home_keys})["']?\s*[:=]\s*
        ["']?(\d{{1,2}})["']?
        [\s\S]{{0,250}}?
        ["']?(?:{away_keys})["']?\s*[:=]\s*
        ["']?(\d{{1,2}})["']?""",

        rf"""["']?(?:{away_keys})["']?\s*[:=]\s*
        ["']?(\d{{1,2}})["']?
        [\s\S]{{0,250}}?
        ["']?(?:{home_keys})["']?\s*[:=]\s*
        ["']?(\d{{1,2}})["']?""",
    ]

    for index, pattern in enumerate(patterns):

        for match in re.finditer(
            pattern,
            page_html,
            re.I | re.X,
        ):

            first = score_int(match.group(1))

            second = score_int(match.group(2))

            if first is None or second is None:
                continue

            if index == 0:
                return first, second

            return second, first

    return None


def extract_score_from_data_attributes(page_html):

    home_patterns = [
        r'data-home-score\s*=\s*["\'](\d{1,2})["\']',
        r'data-hscore\s*=\s*["\'](\d{1,2})["\']',
    ]

    away_patterns = [
        r'data-away-score\s*=\s*["\'](\d{1,2})["\']',
        r'data-ascore\s*=\s*["\'](\d{1,2})["\']',
    ]

    home_values = []

    away_values = []

    for pattern in home_patterns:

        home_values.extend(
            re.findall(
                pattern,
                page_html,
                re.I,
            )
        )

    for pattern in away_patterns:

        away_values.extend(
            re.findall(
                pattern,
                page_html,
                re.I,
            )
        )

    if not home_values or not away_values:
        return None

    home = score_int(home_values[0])

    away = score_int(away_values[0])

    if home is None or away is None:
        return None

    return home, away


# ============================================================
# 실제 점수 추출
# ============================================================

def extract_score(page_html):

    # 1. JSON 데이터
    for data in extract_json_scripts(page_html):

        found = recursive_score_search(data)

        if found:

            home, away = found

            return (
                home,
                away,
                calculate_result(home, away),
            )

    # 2. 홈팀 / 원정팀 점수 분리 HTML
    parser = MatchHTMLParser()

    try:

        parser.feed(page_html)

        parser.close()

    except Exception:
        pass

    home_candidates = parser.score_sides["home"]

    away_candidates = parser.score_sides["away"]

    if home_candidates and away_candidates:

        home = max(
            enumerate(home_candidates),
            key=lambda item: (
                item[1][0],
                item[0],
            ),
        )[1][1]

        away = max(
            enumerate(away_candidates),
            key=lambda item: (
                item[1][0],
                item[0],
            ),
        )[1][1]

        return (
            home,
            away,
            calculate_result(home, away),
        )

    # 3. 하나의 문자열로 표시된 점수
    for value in reversed(parser.scores):

        found = score_pair_from_string(value)

        if found:

            home, away = found

            return (
                home,
                away,
                calculate_result(home, away),
            )

    # 4. data-score="0-1"
    for value in re.findall(
        r'data-score\s*=\s*["\']([^"\']+)["\']',
        page_html,
        re.I,
    ):

        found = score_pair_from_string(value)

        if found:

            home, away = found

            return (
                home,
                away,
                calculate_result(home, away),
            )

    # 5. 홈 / 원정 점수 속성
    found = extract_score_from_data_attributes(
        page_html
    )

    if found:

        home, away = found

        return (
            home,
            away,
            calculate_result(home, away),
        )

    # 6. JavaScript 점수 필드
    found = extract_score_from_named_fields(
        page_html
    )

    if found:

        home, away = found

        return (
            home,
            away,
            calculate_result(home, away),
        )

    return None, None, None


# ============================================================
# 경기 날짜
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
        return dates[0]

    return None


# ============================================================
# HTTP 요청
# ============================================================

def _fetch(url, schedule_id, label):

    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT,
    )

    add_log(
        f"[{label}] ID={schedule_id} "
        f"HTTP={response.status_code} "
        f"SIZE={len(response.text):,}"
    )

    if response.status_code != 200:

        raise RuntimeError(
            f"{label} HTTP={response.status_code}"
        )

    if not response.text.strip():

        raise RuntimeError(
            f"{label} 응답이 비어 있습니다."
        )

    return response.text


def fetch_match_page(schedule_id):

    return _fetch(
        MATCH_URL.format(
            schedule_id=schedule_id
        ),
        schedule_id,
        "경기 페이지",
    )


def fetch_odds(schedule_id):

    return _fetch(
        ODDS_URL.format(
            schedule_id=schedule_id
        ),
        schedule_id,
        "배당 API",
    )


# ============================================================
# 최종배당 읽기
# ============================================================

def read_final_prices(final_odds):

    if isinstance(final_odds, str):
        final_odds = parse_json(final_odds)

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

    return home, draw, away


# ============================================================
# 업체 목록 추출
# ============================================================

def get_mixodds_container(data):

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

        if isinstance(mixodds, str):
            mixodds = parse_json(mixodds)

        if mixodds is not None:
            return mixodds

    if isinstance(container, list):
        return container

    mixodds = get_ci(data, "mixodds")

    if isinstance(mixodds, str):
        mixodds = parse_json(mixodds)

    return mixodds


def extract_bookmakers(data):

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

        # 초기배당 euro.f는 사용하지 않는다.
        # 최종배당 euro.l만 사용한다.
        final_odds = get_ci(euro, "l")

        prices = read_final_prices(final_odds)

        if prices is None:
            continue

        home, draw, away = prices

        unique_key = str(cid).strip()

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
# 업체 필터
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

        if cid in selected or name in selected:
            result.append(item)

    return result


# ============================================================
# 배당 진단
# ============================================================

def diagnose_odds_response(schedule_id, data):

    add_log(
        f"[배당 진단] ID={schedule_id} "
        f"ErrCode={get_ci(data, 'ErrCode')!r}"
    )

    if not isinstance(data, dict):

        add_log(
            "[배당 진단] JSON 객체가 아닙니다."
        )

        return

    mixodds = get_mixodds_container(data)

    if isinstance(mixodds, dict):

        items = list(mixodds.values())

    elif isinstance(mixodds, list):

        items = mixodds

    else:

        add_log(
            "[배당 진단] 업체 목록을 찾지 못했습니다."
        )

        return

    add_log(
        f"[배당 진단] 업체 항목={len(items)}"
    )

    for item in items[:5]:

        if not isinstance(item, dict):
            continue

        name = (
            get_ci(item, "cn")
            or get_ci(item, "name")
            or "이름 없음"
        )

        euro = get_ci(item, "euro")

        if isinstance(euro, str):
            euro = parse_json(euro)

        final_odds = (
            get_ci(euro, "l")
            if isinstance(euro, dict)
            else None
        )

        add_log(
            f"[배당 진단] 업체={clean_text(name)} "
            f"최종배당={final_odds!r}"
        )


# ============================================================
# 업체별 상태 저장
# ============================================================

def save_company_state(
    schedule_id,
    company_name,
    status,
):

    function = getattr(
        database,
        "save_company_collection_state",
        None,
    )

    if not callable(function):

        raise RuntimeError(
            "database.py에 "
            "save_company_collection_state() 함수가 없습니다."
        )

    return function(
        int(schedule_id),
        str(company_name),
        str(status),
    )


# ============================================================
# 단일 경기 수집
# ============================================================

def collect_one_match(
    schedule_id,
    selected_companies=None,
):

    schedule_id = int(schedule_id)

    selected_companies = list(
        selected_companies or []
    )

    # --------------------------------------------------------
    # 1. 이미 전체 완료된 경기 확인
    # --------------------------------------------------------

    if database.is_collection_completed(
        schedule_id
    ):

        add_log(
            f"[중복] ID={schedule_id} "
            "전체 수집 완료 경기"
        )

        return "exists"

    # --------------------------------------------------------
    # 2. 경기 페이지
    # --------------------------------------------------------

    page_html = fetch_match_page(
        schedule_id
    )

    if not is_running():
        return "stopped"

    # --------------------------------------------------------
    # 3. 팀명
    # --------------------------------------------------------

    home_team, away_team = extract_team_names(
        page_html
    )

    if (
        not valid_team_name(home_team)
        or not valid_team_name(away_team)
        or home_team == away_team
    ):

        raise RuntimeError(
            "홈팀/원정팀 추출 실패: "
            f"{home_team!r} vs {away_team!r}"
        )

    # --------------------------------------------------------
    # 4. 실제 점수 및 승무패
    # --------------------------------------------------------

    home_score, away_score, result = extract_score(
        page_html
    )

    if (
        home_score is None
        or away_score is None
        or result not in ("승", "무", "패")
    ):

        raise RuntimeError(
            "실제 경기 점수 확인 실패"
        )

    verified_result = calculate_result(
        home_score,
        away_score,
    )

    if verified_result != result:

        raise RuntimeError(
            "점수와 승무패 검증 실패"
        )

    match_date = extract_match_date(
        page_html
    )

    add_log(
        f"[경기결과] ID={schedule_id} "
        f"{home_team} "
        f"{home_score}-{away_score} "
        f"{away_team} "
        f"결과={result}"
    )

    # --------------------------------------------------------
    # 5. 최종배당 API
    # --------------------------------------------------------

    if not is_running():
        return "stopped"

    odds_text = fetch_odds(
        schedule_id
    )

    odds_data = parse_json(
        odds_text
    )

    if odds_data is None:

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
            "최종배당 없음 또는 "
            "선택 업체의 유효 배당 없음"
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

    if not saved_match:

        raise RuntimeError(
            "경기 저장 실패"
        )

    # --------------------------------------------------------
    # 7. 최종배당 저장
    #
    # 현재 경기 저장이 시작되면 모든 업체의 배당 저장을
    # 완료한 다음 완료 상태를 기록한다.
    # --------------------------------------------------------

    saved_odds = 0

    for item in bookmakers:

        ok = database.save_odds(
            schedule_id,
            item["cid"],
            item["name"],
            item["home"],
            item["draw"],
            item["away"],
        )

        if not ok:

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
    # 8. 수집 상태 저장
    #
    # 선택 업체 수집:
    #   업체별 completed
    #   경기 전체 상태 partial
    #
    # 전체 업체 수집:
    #   경기 전체 상태 completed
    # --------------------------------------------------------

    if selected_companies:

        # 선택 업체별 완료 상태 저장
        for item in bookmakers:

            state_ok = save_company_state(
                schedule_id,
                item["name"],
                "completed",
            )

            if not state_ok:

                raise RuntimeError(
                    "업체별 상태 저장 실패: "
                    f"{item['name']}"
                )

        # 일부 업체만 수집했으므로 전체 완료가 아니다.
        state_saved = database.save_collection_state(
            schedule_id,
            "partial",
        )

        add_log(
            f"[部分 완료] ID={schedule_id} "
            f"선택 업체 {saved_odds}개 저장"
        )

    else:

        # 전체 업체 수집일 때만 전체 완료 처리
        state_saved = database.save_collection_state(
            schedule_id,
            "completed",
        )

    if not state_saved:

        raise RuntimeError(
            "수집 완료 상태 저장 실패"
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

    add_log(
        "Scoreman 백그라운드 수집 시작"
    )

    add_log(
        f"범위: {start_id:,} ~ {end_id:,}"
    )

    add_log(
        "실제 점수 / 승무패 검증 후 저장"
    )

    add_log(
        "실패 경기는 전체 완료로 처리하지 않음"
    )

    add_log(
        "자동 재시도: 없음"
    )

    add_log(
        f"요청 간격: {delay:.2f}초"
    )

    add_log(
        "수집 업체: "
        + (
            ", ".join(selected)
            if selected
            else "전체 업체"
        )
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

                # 전체 완료가 아닌 경기만 진행 상태로 변경
                if not database.is_collection_completed(
                    schedule_id
                ):

                    state_ok = database.save_collection_state(
                        schedule_id,
                        "in_progress",
                    )

                    if not state_ok:

                        add_log(
                            f"[경고] ID={schedule_id} "
                            "진행 상태 저장 실패"
                        )

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

                    # ----------------------------------------
                    # 수정 3: 중복 처리
                    # ----------------------------------------

                    with lock:

                        job["exists"] += 1

                        job["last_completed_id"] = int(
                            schedule_id
                        )

                    # 전체 완료된 경기는 completed 상태를
                    # partial로 덮어쓰지 않는다.
                    #
                    # 부분 수집 중 중복 결과가 반환되는 경우에만
                    # 전체 완료 여부를 확인한 후 처리한다.

                    if selected:

                        is_completed = (
                            database.is_collection_completed(
                                schedule_id
                            )
                        )

                        if not is_completed:

                            state_ok = (
                                database.save_collection_state(
                                    schedule_id,
                                    "partial",
                                )
                            )

                            if not state_ok:

                                add_log(
                                    f"[상태 저장 경고] "
                                    f"ID={schedule_id} "
                                    "partial 저장 실패"
                                )

                elif result == "stopped":

                    add_log(
                        f"[중지] ID={schedule_id}"
                    )

                    break

            except Exception as error:

                with lock:

                    job["failed"] += 1

                    job["error"] = (
                        f"ID={schedule_id}: "
                        f"{type(error).__name__}: "
                        f"{error}"
                    )

                # 자동 재시도 없음
                # 실패한 경기는 completed로 기록하지 않는다.
                try:

                    database.save_collection_state(
                        schedule_id,
                        "failed",
                    )

                except Exception as state_error:

                    add_log(
                        f"[상태 저장 오류] "
                        f"ID={schedule_id} "
                        f"{state_error}"
                    )

                add_log(
                    f"[수집 실패] ID={schedule_id} "
                    f"{type(error).__name__}: {error}"
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

            success = job["success"]

            exists = job["exists"]

            failed = job["failed"]

            odds = job["odds"]

            job["result"] = (
                f"성공 {success} / "
                f"중복 {exists} / "
                f"실패 {failed} / "
                f"배당 {odds}"
            )

        add_log("=" * 50)

        add_log(
            "Scoreman 수집 종료"
        )

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

    if not 0 <= delay <= 10:

        return False, "요청 간격은 0~10초입니다."

    selected_companies = list(
        selected_companies or []
    )

    with lock:

        if job["running"]:

            return False, "이미 수집 중입니다."

        job.update({

            "running": True,

            "finished": False,

            "current": 0,

            "total": end_id - start_id + 1,

            "success": 0,

            "exists": 0,

            "failed": 0,

            "odds": 0,

            "start_id": start_id,

            "end_id": end_id,

            "last_completed_id": None,

            "selected_companies": selected_companies,

            "delay": delay,

            "start_time": None,

            "end_time": None,

            "log": [],

            "result": "",

            "error": "",

        })

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

            return False, str(error)

    return True, "수집을 시작했습니다."


# ============================================================
# 이어받기
# ============================================================

def resume_collection(
    end_id,
    selected_companies=None,
    delay=DEFAULT_DELAY,
    start_id=None,
):

    try:

        end_id = int(end_id)

    except Exception:

        return False, "종료 ID 오류"

    if start_id is None:
        start_id = 1

    try:

        start_id = int(start_id)

    except Exception:

        return False, "시작 ID 오류"

    if start_id <= 0:

        return False, "시작 ID 오류"

    if end_id < start_id:

        return False, "종료 ID 오류"

    pending_id = database.get_first_pending_id(
        start_id,
        end_id,
    )

    if pending_id is not None:

        next_id = int(pending_id)

    else:

        last_id = database.get_last_completed_id()

        if last_id is None:

            next_id = start_id

        else:

            next_id = max(
                start_id,
                int(last_id) + 1,
            )

    if next_id > end_id:

        return (
            False,
            "이어받을 ID가 없습니다. "
            f"마지막 완료 ID={next_id - 1:,}",
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

        total = int(
            job["total"] or 0
        )

        current = int(
            job["current"] or 0
        )

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

            "last_completed_id": (
                job["last_completed_id"]
            ),

        }


# ============================================================
# 단일 경기 수집
# ============================================================

def collect_single(
    schedule_id,
    selected_companies=None,
):

    try:

        sid = int(schedule_id)

    except Exception:

        return {

            "status": "failed",

            "error": "경기 ID가 올바르지 않습니다.",

        }

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

        if not database.is_collection_completed(sid):

            state_ok = database.save_collection_state(
                sid,
                "in_progress",
            )

            if not state_ok:

                add_log(
                    f"[경고] ID={sid} "
                    "진행 상태 저장 실패"
                )

        result = collect_one_match(
            sid,
            selected_companies or [],
        )

        return result

    except Exception as error:

        try:

            database.save_collection_state(
                sid,
                "failed",
            )

        except Exception as state_error:

            add_log(
                f"[상태 저장 오류] ID={sid} "
                f"{state_error}"
            )

        add_log(
            f"[단일 경기 실패] ID={sid} "
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
