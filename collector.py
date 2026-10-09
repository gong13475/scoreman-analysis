# ============================================================
# collector.py
# Scoreman 백그라운드 수집기 - 결과 검증 강화판
#
# 주요 기능
# 1. Scoreman 경기 페이지 자동 수집
# 2. 실제 홈팀 / 원정팀 이름 추출
# 3. 명시적인 경기 점수 데이터만 사용
# 4. 실제 점수로 승 / 무 / 패 계산
# 5. 전체 해외 배당업체 자동 수집
# 6. 최종배당만 저장
# 7. SQLite / Turso 등 database.py 기존 기능 사용
# 8. 백그라운드 수집 / 중지 / 이어받기
# 9. 실패 / 결과 미확인 / 배당 없음은 완료 처리하지 않음
# 10. 자동 재시도 없음
# 11. 부분 수집 데이터의 완료 처리 방지
# ============================================================

import re
import time
import json
import html as html_lib
import threading

from datetime import datetime

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

REQUEST_TIMEOUT = 20

DEFAULT_DELAY = 0.5


# ============================================================
# HTTP 세션
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; K) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/130.0 Mobile Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": (
        "ko-KR,ko;q=0.9,en-US;q=0.8"
    ),
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

    timestamp = datetime.now().strftime(
        "%H:%M:%S"
    )

    line = f"[{timestamp}] {message}"

    with lock:

        job["log"].append(line)

        if len(job["log"]) > 1500:
            job["log"] = job["log"][-1500:]

    print(line)


def get_job_status():

    with lock:
        result = dict(job)

        result["log"] = list(job["log"])
        result["selected_companies"] = list(
            job["selected_companies"]
        )

        return result


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

    add_log("🛑 수집 중지 요청")

    return True


# ============================================================
# 텍스트 정리
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    value = html_lib.unescape(
        str(value)
    )

    value = value.replace("\\/", "/")

    value = re.sub(
        r"<[^>]+>",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# ============================================================
# 숫자 변환
# ============================================================

def to_float(value):

    try:

        if value is None:
            return None

        value = str(value).strip()

        value = value.replace(",", "")

        if not value:
            return None

        number = float(value)

        if number <= 0:
            return None

        return number

    except (ValueError, TypeError, OverflowError):

        return None


# ============================================================
# 점수 변환
#
# 중요:
# 임의의 문자열에서 첫 번째 숫자를 뽑지 않는다.
# 점수 숫자 또는 점수 숫자로만 구성된 문자열만 허용.
# ============================================================

def score_int(value):

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, int):

        if 0 <= value <= 30:
            return value

        return None

    if isinstance(value, float):

        if (
            value.is_integer()
            and 0 <= value <= 30
        ):
            return int(value)

        return None

    value = html_lib.unescape(
        str(value)
    ).strip()

    # 점수 필드에 "0-10" 등이 들어오면
    # 단일 점수로 잘못 해석하지 않는다.
    if not re.fullmatch(
        r"\d{1,2}",
        value
    ):
        return None

    number = int(value)

    if 0 <= number <= 30:
        return number

    return None


# ============================================================
# 승 / 무 / 패 계산
# ============================================================

def calculate_result(
    home_score,
    away_score
):

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
# HTTP 응답
# ============================================================

def fetch_match_page(schedule_id):

    url = MATCH_URL.format(
        schedule_id=schedule_id
    )

    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT
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

    return response.text


# ============================================================
# JSON 파싱
# ============================================================

def parse_json(text):

    if not text:
        return None

    text = html_lib.unescape(
        str(text)
    ).strip()

    try:
        return json.loads(text)

    except Exception:
        pass

    # JSONP 또는 JSON 앞뒤에 다른 내용이 있는 경우
    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:

        try:

            return json.loads(
                text[start:end + 1]
            )

        except Exception:
            pass

    return None


# ============================================================
# 페이지 안의 JSON 블록 찾기
# ============================================================

def extract_json_blocks(page):

    blocks = []

    patterns = [
        (
            r'<script[^>]*type=["\']'
            r'application/json["\'][^>]*>'
            r'(.*?)</script>'
        ),
        (
            r'<script[^>]*>'
            r'(.*?)</script>'
        ),
    ]

    for pattern in patterns:

        found = re.findall(
            pattern,
            page,
            re.I | re.S
        )

        blocks.extend(found)

    return blocks


# ============================================================
# JSON의 실제 점수 검색
#
# 일반적인 페이지 숫자 조합은 검색하지 않는다.
# 명시적인 점수 필드 쌍만 인정한다.
# ============================================================

def recursive_score_search(obj):

    if isinstance(obj, dict):

        pairs = [
            ("homeScore", "awayScore"),
            ("home_score", "away_score"),
            ("homescore", "awayscore"),

            ("home_score1", "away_score1"),

            ("HomeScore", "AwayScore"),

            ("HScore", "AScore"),
            ("hscore", "ascore"),

            ("score_home", "score_away"),

            ("homeGoals", "awayGoals"),
            ("home_goals", "away_goals"),

            ("homegoal", "awaygoal"),
            ("home_goal", "away_goal"),
        ]

        # 대소문자 차이를 허용하되
        # 동일 객체 내부의 필드만 비교한다.
        normalized = {
            str(key).lower(): value
            for key, value in obj.items()
        }

        for home_key, away_key in pairs:

            hk = home_key.lower()
            ak = away_key.lower()

            if hk not in normalized:
                continue

            if ak not in normalized:
                continue

            home = score_int(
                normalized[hk]
            )

            away = score_int(
                normalized[ak]
            )

            if home is not None and away is not None:

                return home, away

        # 명시적인 score 필드
        for key, value in obj.items():

            if str(key).lower() != "score":
                continue

            if not isinstance(value, str):
                continue

            match = re.fullmatch(
                r"\s*(\d{1,2})\s*[-:]\s*"
                r"(\d{1,2})\s*",
                value
            )

            if match:

                home = score_int(
                    match.group(1)
                )

                away = score_int(
                    match.group(2)
                )

                if home is not None and away is not None:

                    return home, away

        # 하위 객체 탐색
        for value in obj.values():

            found = recursive_score_search(
                value
            )

            if found is not None:
                return found

    elif isinstance(obj, list):

        for value in obj:

            found = recursive_score_search(
                value
            )

            if found is not None:
                return found

    return None


# ============================================================
# HTML의 명시적 점수 필드 검색
#
# 서로 관계없는 숫자 두 개를 조합하지 않는다.
# ============================================================

def extract_explicit_score_fields(page):

    key_pairs = [
        ("homeScore", "awayScore"),
        ("home_score", "away_score"),
        ("homescore", "awayscore"),
        ("HomeScore", "AwayScore"),
        ("HScore", "AScore"),
        ("hscore", "ascore"),
        ("score_home", "score_away"),
        ("homeGoals", "awayGoals"),
        ("home_goals", "away_goals"),
    ]

    for home_key, away_key in key_pairs:

        def make_pattern(first, second):

            return (
                r"""["']?"""
                + re.escape(first)
                + r"""["']?\s*:\s*["']?"""
                + r"""(\d{1,2})"""
                + r"""["']?"""
                + r"""[^{}]{0,250}?"""
                + r"""["']?"""
                + re.escape(second)
                + r"""["']?\s*:\s*["']?"""
                + r"""(\d{1,2})"""
                + r"""["']?"""
            )

        patterns = [
            make_pattern(
                home_key,
                away_key
            ),
            make_pattern(
                away_key,
                home_key
            ),
        ]

        for index, pattern in enumerate(patterns):

            matches = re.finditer(
                pattern,
                page,
                re.I | re.S
            )

            for match in matches:

                first = score_int(
                    match.group(1)
                )

                second = score_int(
                    match.group(2)
                )

                if first is None or second is None:
                    continue

                if index == 0:
                    return first, second

                return second, first

    # 명시적인 data-score 속성
    patterns = [
        (
            r"""data-score\s*=\s*["']"""
            r"""(\d{1,2})\s*[-:]\s*"""
            r"""(\d{1,2})["']"""
        ),
        (
            r"""data-match-score\s*=\s*["']"""
            r"""(\d{1,2})\s*[-:]\s*"""
            r"""(\d{1,2})["']"""
        ),
    ]

    for pattern in patterns:

        found = re.search(
            pattern,
            page,
            re.I
        )

        if found:

            home = score_int(
                found.group(1)
            )

            away = score_int(
                found.group(2)
            )

            if home is not None and away is not None:

                return home, away

    return None


# ============================================================
# HTML 요소의 클래스에서 값 추출
# ============================================================

def extract_class_values(
    page,
    class_patterns
):

    values = []

    element_pattern = re.compile(
        r"<(?P<tag>[a-zA-Z][a-zA-Z0-9]*)"
        r"\b(?P<attrs>[^>]*)>"
        r"(?P<body>.*?)"
        r"</(?P=tag)\s*>",
        re.I | re.S
    )

    for element in element_pattern.finditer(page):

        attrs = element.group("attrs")

        classes = re.search(
            r"""class\s*=\s*["']([^"']*)["']""",
            attrs,
            re.I
        )

        if not classes:
            continue

        class_text = classes.group(1).lower()

        matched = any(
            re.search(
                pattern,
                class_text,
                re.I
            )
            for pattern in class_patterns
        )

        if not matched:
            continue

        value = clean_text(
            element.group("body")
        )

        if value and len(value) <= 120:

            values.append(value)

    return values


# ============================================================
# 실제 점수 추출
#
# 기존의 위험한 전체 HTML 숫자 검색 제거.
# ============================================================

def extract_score(page):

    # --------------------------------------------------------
    # 1. JSON 블록
    # --------------------------------------------------------

    for block in extract_json_blocks(page):

        data = parse_json(block)

        if data is None:
            continue

        found = recursive_score_search(
            data
        )

        if found is not None:

            home, away = found

            return (
                home,
                away,
                calculate_result(home, away)
            )

    # --------------------------------------------------------
    # 2. 명시적인 HTML / JavaScript 필드
    # --------------------------------------------------------

    found = extract_explicit_score_fields(
        page
    )

    if found is not None:

        home, away = found

        return (
            home,
            away,
            calculate_result(home, away)
        )

    # --------------------------------------------------------
    # 3. 명시적인 홈 / 원정 점수 클래스
    # --------------------------------------------------------

    home_values = extract_class_values(
        page,
        [
            r"\bhome-score\b",
            r"\bhome_score\b",
            r"\bhomescore\b",
            r"\bscore-home\b",
            r"\bscore_home\b",
        ]
    )

    away_values = extract_class_values(
        page,
        [
            r"\baway-score\b",
            r"\baway_score\b",
            r"\bawayscore\b",
            r"\bscore-away\b",
            r"\bscore_away\b",
        ]
    )

    if home_values and away_values:

        home = score_int(
            home_values[-1]
        )

        away = score_int(
            away_values[-1]
        )

        if home is not None and away is not None:

            return (
                home,
                away,
                calculate_result(home, away)
            )

    # --------------------------------------------------------
    # 4. 확인 불가
    #
    # 페이지 전체에서 임의의 숫자 조합을 찾지 않는다.
    # --------------------------------------------------------

    return None, None, None


# ============================================================
# 팀 이름 검색 - JSON
# ============================================================

def recursive_team_search(obj):

    if isinstance(obj, dict):

        normalized = {
            str(key).lower(): value
            for key, value in obj.items()
        }

        pairs = [
            ("hometeam", "awayteam"),
            ("home_team", "away_team"),

            ("hteam", "ateam"),

            ("hometeamname", "awayteamname"),
            ("home_team_name", "away_team_name"),

            ("homename", "awayname"),
            ("home_name", "away_name"),

            ("teamhome", "teamaway"),

            ("hostteam", "guestteam"),
            ("hostname", "guestname"),
        ]

        for home_key, away_key in pairs:

            hk = home_key.lower()
            ak = away_key.lower()

            if hk not in normalized:
                continue

            if ak not in normalized:
                continue

            home = clean_text(
                normalized[hk]
            )

            away = clean_text(
                normalized[ak]
            )

            if valid_team_names(home, away):

                return home, away

        # generic home / away는 무조건 사용하지 않는다.
        # 점수 필드도 같이 있는 객체에 한해서만 허용한다.
        score_pairs = [
            ("homescore", "awayscore"),
            ("home_score", "away_score"),
            ("hscore", "ascore"),
        ]

        has_score_pair = any(
            hk in normalized and ak in normalized
            for hk, ak in score_pairs
        )

        if (
            has_score_pair
            and "home" in normalized
            and "away" in normalized
        ):

            home = clean_text(
                normalized["home"]
            )

            away = clean_text(
                normalized["away"]
            )

            if valid_team_names(home, away):

                return home, away

        for value in obj.values():

            found = recursive_team_search(
                value
            )

            if found is not None:
                return found

    elif isinstance(obj, list):

        for value in obj:

            found = recursive_team_search(
                value
            )

            if found is not None:
                return found

    return None


# ============================================================
# 팀 이름 유효성 검사
# ============================================================

def valid_team_names(home, away):

    home = clean_text(home)
    away = clean_text(away)

    if not home or not away:
        return False

    if home.lower() == away.lower():
        return False

    invalid_names = {
        "home",
        "away",
        "hometeam",
        "awayteam",
        "상대팀",
        "홈팀",
        "원정팀",
        "unknown",
        "null",
        "none",
    }

    if home.lower() in invalid_names:
        return False

    if away.lower() in invalid_names:
        return False

    if re.fullmatch(
        r"ID\s*\d+",
        home,
        re.I
    ):
        return False

    if re.fullmatch(
        r"ID\s*\d+",
        away,
        re.I
    ):
        return False

    return True


# ============================================================
# HTML에서 팀 이름 추출
# ============================================================

def extract_team_names(page):

    # --------------------------------------------------------
    # 1. JSON
    # --------------------------------------------------------

    for block in extract_json_blocks(page):

        data = parse_json(block)

        if data is None:
            continue

        found = recursive_team_search(
            data
        )

        if found is not None:

            home, away = found

            if valid_team_names(home, away):

                return home, away

    # --------------------------------------------------------
    # 2. data-home-team / data-away-team
    # --------------------------------------------------------

    home_match = re.search(
        r"""data-home-team\s*=\s*["']([^"']+)["']""",
        page,
        re.I
    )

    away_match = re.search(
        r"""data-away-team\s*=\s*["']([^"']+)["']""",
        page,
        re.I
    )

    if home_match and away_match:

        home = clean_text(
            home_match.group(1)
        )

        away = clean_text(
            away_match.group(1)
        )

        if valid_team_names(home, away):

            return home, away

    # --------------------------------------------------------
    # 3. HTML 클래스
    # --------------------------------------------------------

    home_values = extract_class_values(
        page,
        [
            r"\bhome-team\b",
            r"\bhome_team\b",
            r"\bhometeam\b",
            r"\bteam-home\b",
            r"\bteam_home\b",
            r"\bhome-name\b",
            r"\bhome_name\b",
        ]
    )

    away_values = extract_class_values(
        page,
        [
            r"\baway-team\b",
            r"\baway_team\b",
            r"\bawayteam\b",
            r"\bteam-away\b",
            r"\bteam_away\b",
            r"\baway-name\b",
            r"\baway_name\b",
        ]
    )

    if home_values and away_values:

        home = home_values[-1]
        away = away_values[-1]

        if valid_team_names(home, away):

            return home, away

    # --------------------------------------------------------
    # 4. 확인 불가
    # --------------------------------------------------------

    return "", ""


# ============================================================
# 날짜 추출
# ============================================================

def extract_match_date(page):

    patterns = [
        r'"matchDate"\s*:\s*"([^"]+)"',
        r'"match_date"\s*:\s*"([^"]+)"',
        r'"matchTime"\s*:\s*"([^"]+)"',
        r'"match_time"\s*:\s*"([^"]+)"',
    ]

    for pattern in patterns:

        found = re.findall(
            pattern,
            page,
            re.I
        )

        if found:

            value = clean_text(
                found[0]
            )

            if value:
                return value

    # 날짜 형식 자체가 명확한 경우만 추출
    date_match = re.search(
        r"\b(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})\b",
        page
    )

    if date_match:

        return clean_text(
            date_match.group(1)
        )

    return None


# ============================================================
# 결과 추출 실패 진단
# ============================================================

def log_score_diagnostics(
    schedule_id,
    page
):

    add_log(
        f"[결과 진단] ID={schedule_id} "
        "명시적인 점수 필드를 찾지 못했습니다."
    )

    # 페이지 전체를 로그에 출력하지 않고
    # 점수 관련 키 주변의 일부 내용만 기록한다.
    patterns = [
        r"homeScore",
        r"awayScore",
        r"home_score",
        r"away_score",
        r"homeTeam",
        r"awayTeam",
        r"data-score",
        r"score_home",
        r"score_away",
    ]

    shown = 0

    for pattern in patterns:

        match = re.search(
            pattern,
            page,
            re.I
        )

        if not match:
            continue

        start = max(
            0,
            match.start() - 100
        )

        end = min(
            len(page),
            match.end() + 180
        )

        snippet = clean_text(
            page[start:end]
        )

        add_log(
            f"[결과 진단 내용] {snippet[:250]}"
        )

        shown += 1

        if shown >= 4:
            break

    if shown == 0:

        add_log(
            "[결과 진단] 알려진 점수 필드가 "
            "페이지 HTML에서 발견되지 않았습니다."
        )


# ============================================================
# 배당 API
# ============================================================

def fetch_odds(schedule_id):

    url = ODDS_URL.format(
        schedule_id=schedule_id
    )

    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT
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

    return response.text


# ============================================================
# 최종배당 업체 추출
#
# euro.l
# u = 홈 승
# g = 무승부
# d = 원정 승
#
# 초기배당 euro.f는 사용하지 않는다.
# ============================================================

def extract_bookmakers(data):

    if not isinstance(data, dict):
        return []

    mixodds = None

    data_block = data.get("Data")

    if isinstance(data_block, dict):

        mixodds = data_block.get(
            "mixodds"
        )

    if mixodds is None:

        mixodds = data.get(
            "mixodds"
        )

    if not isinstance(mixodds, list):
        return []

    result = []

    seen = set()

    for item in mixodds:

        if not isinstance(item, dict):
            continue

        cid = (
            item.get("cid")
            or item.get("company_id")
            or item.get("id")
        )

        name = (
            item.get("cn")
            or item.get("company_name")
            or item.get("name")
            or ""
        )

        if cid is None:
            continue

        euro = item.get("euro")

        if not isinstance(euro, dict):
            continue

        # 최종배당만 사용
        final_odds = euro.get("l")

        if not isinstance(final_odds, dict):
            continue

        home = to_float(
            final_odds.get("u")
        )

        draw = to_float(
            final_odds.get("g")
        )

        away = to_float(
            final_odds.get("d")
        )

        if (
            home is None
            or draw is None
            or away is None
        ):
            continue

        # 업체 중복 제거
        unique_key = str(cid).strip()

        if unique_key in seen:
            continue

        seen.add(unique_key)

        result.append({
            "cid": str(cid).strip(),
            "name": str(name).strip(),
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
    selected_companies=None
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
# 한 경기 수집
# ============================================================

def collect_one_match(
    schedule_id,
    selected_companies=None
):

    schedule_id = str(
        schedule_id
    ).strip()

    # --------------------------------------------------------
    # 1. 이미 완료된 경기인지 확인
    # --------------------------------------------------------

    if database.is_collection_completed(
        schedule_id
    ):

        add_log(
            f"[중복] ID={schedule_id}"
        )

        return "exists"

    # --------------------------------------------------------
    # 2. 경기 페이지
    # --------------------------------------------------------

    page = fetch_match_page(
        schedule_id
    )

    # --------------------------------------------------------
    # 3. 팀 이름
    # --------------------------------------------------------

    home_team, away_team = extract_team_names(
        page
    )

    if not valid_team_names(
        home_team,
        away_team
    ):

        add_log(
            f"[팀명 미확인] ID={schedule_id} "
            "실제 홈팀 / 원정팀 이름을 추출하지 못했습니다."
        )

        raise RuntimeError(
            "실제 팀 이름 추출 실패"
        )

    # --------------------------------------------------------
    # 4. 실제 점수
    # --------------------------------------------------------

    home_score, away_score, result = extract_score(
        page
    )

    if (
        home_score is None
        or away_score is None
        or result not in ("승", "무", "패")
    ):

        log_score_diagnostics(
            schedule_id,
            page
        )

        add_log(
            f"[결과 미확인] ID={schedule_id} "
            f"홈팀={home_team} "
            f"원정팀={away_team} "
            f"홈점수={home_score} "
            f"원정점수={away_score}"
        )

        # 잘못된 임시 경기 정보를 저장하지 않는다.
        # 완료 상태도 저장하지 않는다.
        raise RuntimeError(
            "실제 경기결과 / 스코어 확인 실패"
        )

    match_date = extract_match_date(
        page
    )

    add_log(
        f"[경기결과 검증] ID={schedule_id} "
        f"{home_team} "
        f"{home_score}-{away_score} "
        f"{away_team} "
        f"결과={result}"
    )

    # --------------------------------------------------------
    # 5. 배당 API
    # --------------------------------------------------------

    odds_text = fetch_odds(
        schedule_id
    )

    odds_data = parse_json(
        odds_text
    )

    if odds_data is None:

        raise RuntimeError(
            "배당 JSON 파싱 실패"
        )

    bookmakers = extract_bookmakers(
        odds_data
    )

    bookmakers = filter_bookmakers(
        bookmakers,
        selected_companies
    )

    add_log(
        f"[배당 추출] ID={schedule_id} "
        f"업체={len(bookmakers)}"
    )

    if not bookmakers:

        raise RuntimeError(
            "최종배당 없음"
        )

    # --------------------------------------------------------
    # 6. 경기 저장
    #
    # 팀 이름 / 점수 / 결과 검증을 통과한 경기만 저장.
    # --------------------------------------------------------

    saved_match = database.save_match(
        schedule_id,
        match_date,
        home_team,
        away_team,
        home_score,
        away_score,
        result,
        "scoreman"
    )

    if not saved_match:

        raise RuntimeError(
            "경기 저장 실패"
        )

    # --------------------------------------------------------
    # 7. 최종배당 저장
    # --------------------------------------------------------

    saved_odds = 0

    for item in bookmakers:

        if not is_running():

            add_log(
                f"[수집 중지] ID={schedule_id} "
                "배당 저장 도중 중지 요청"
            )

            return "stopped"

        saved = database.save_odds(
            schedule_id,
            item["cid"],
            item["name"],
            item["home"],
            item["draw"],
            item["away"]
        )

        if not saved:

            raise RuntimeError(
                f"배당 저장 실패: {item['name']}"
            )

        saved_odds += 1

        add_log(
            f"[배당 저장] "
            f"ID={schedule_id} "
            f"업체={item['name']} "
            f"승={item['home']} "
            f"무={item['draw']} "
            f"패={item['away']}"
        )

    if saved_odds <= 0:

        raise RuntimeError(
            "저장된 배당 없음"
        )

    # --------------------------------------------------------
    # 8. 완료 상태 저장
    #
    # 경기 + 배당 저장이 끝난 후에만 완료 처리.
    # --------------------------------------------------------

    if not is_running():

        return "stopped"

    state_saved = database.save_collection_state(
        schedule_id,
        "completed"
    )

    if not state_saved:

        raise RuntimeError(
            "완료 상태 저장 실패"
        )

    add_log(
        f"[수집 성공] ID={schedule_id} "
        f"홈팀={home_team} "
        f"원정팀={away_team} "
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

        start_id = int(
            job["start_id"]
        )

        end_id = int(
            job["end_id"]
        )

        delay = float(
            job["delay"]
        )

        selected = list(
            job["selected_companies"]
        )

        job["start_time"] = datetime.now().isoformat(
            timespec="seconds"
        )

    add_log("=" * 50)

    add_log(
        "⚽ Scoreman 백그라운드 수집 시작"
    )

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

    add_log(
        "자동 재시도: 없음"
    )

    add_log(
        f"요청 간격: {delay:.2f}초"
    )

    if selected:

        add_log(
            "수집 업체: "
            + ", ".join(
                map(str, selected)
            )
        )

    else:

        add_log(
            "수집 업체: 전체 업체 자동수집"
        )

    add_log("=" * 50)

    for index, schedule_id in enumerate(
        range(start_id, end_id + 1),
        1
    ):

        if not is_running():
            break

        with lock:

            job["current"] = index

        try:

            result = collect_one_match(
                schedule_id,
                selected
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

            add_log(
                f"[수집 실패] "
                f"ID={schedule_id} "
                f"오류={type(error).__name__}: {error}"
            )

        if (
            delay > 0
            and is_running()
            and schedule_id < end_id
        ):

            time.sleep(delay)

    # --------------------------------------------------------
    # 종료 상태
    # --------------------------------------------------------

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

    add_log("=" * 50)

    add_log(
        "🏁 Scoreman 수집 종료"
    )

    add_log(
        f"성공={job['success']} "
        f"중복={job['exists']} "
        f"실패={job['failed']} "
        f"배당={job['odds']}"
    )

    add_log("=" * 50)


# ============================================================
# 백그라운드 수집 시작
# ============================================================

def start_background_collection(
    start_id,
    end_id,
    selected_companies=None,
    delay=DEFAULT_DELAY
):

    with lock:

        if job["running"]:

            return (
                False,
                "이미 수집 중입니다."
            )

    try:

        start_id = int(
            start_id
        )

        end_id = int(
            end_id
        )

    except Exception:

        return (
            False,
            "ID는 숫자로 입력하세요."
        )

    if start_id <= 0:

        return (
            False,
            "시작 ID 오류"
        )

    if end_id < start_id:

        return (
            False,
            "종료 ID 오류"
        )

    try:

        delay = float(
            delay
        )

    except Exception:

        delay = DEFAULT_DELAY

    delay = max(
        0.0,
        delay
    )

    selected_companies = (
        selected_companies or []
    )

    with lock:

        job["running"] = True

        job["finished"] = False

        job["current"] = 0

        job["total"] = (
            end_id - start_id + 1
        )

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

    thread = threading.Thread(
        target=_worker,
        daemon=True
    )

    thread.start()

    return (
        True,
        "수집을 시작했습니다."
    )


# ============================================================
# 이어받기
# ============================================================

def resume_collection(
    end_id,
    selected_companies=None,
    delay=DEFAULT_DELAY
):

    last_id = database.get_last_completed_id()

    if last_id is None:

        return (
            False,
            "저장된 완료 ID가 없습니다."
        )

    try:

        end_id = int(
            end_id
        )

    except Exception:

        return (
            False,
            "종료 ID 오류"
        )

    next_id = int(last_id) + 1

    if next_id > end_id:

        return (
            False,
            f"이어받을 ID가 없습니다. "
            f"마지막 완료 ID={last_id:,}"
        )

    return start_background_collection(
        next_id,
        end_id,
        selected_companies or [],
        delay
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

            "last_completed_id":
                job["last_completed_id"],
        }


# ============================================================
# 단일 경기 수집
# ============================================================

def collect_single(
    schedule_id,
    selected_companies=None
):

    with lock:

        if job["running"]:

            return {
                "status": "failed",
                "error": "이미 수집 중입니다."
            }

        job["running"] = True

    try:

        result = collect_one_match(
            int(schedule_id),
            selected_companies
        )

        return result

    except Exception as error:

        return {
            "status": "failed",
            "error": str(error)
        }

    finally:

        with lock:

            job["running"] = False
