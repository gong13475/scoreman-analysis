# ============================================================
# collector.py
# Scoreman 백그라운드 수집기 - 전체 교체본
#
# 주요 기능
# 1. Scoreman 경기 페이지 수집
# 2. 홈팀 / 원정팀 이름 추출 및 검증
# 3. 실제 경기 점수 추출 및 승무패 계산
# 4. 해외업체 최종배당 자동 수집
# 5. 경기 / 배당 / 완료 상태 저장
# 6. 수집 시작 / 중지 / 이어받기
# 7. 진행률 / 로그
# 8. 팀명 추출 실패 시 HTML 진단
# 9. 실패 자동 재시도 없음
# 10. 검증 실패 경기 완료 처리 금지
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
# 버전
# ============================================================

COLLECTOR_VERSION = "RESULT_CHECK_20261009"


# ============================================================
# 설정
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

        if len(job["log"]) > MAX_LOGS:

            job["log"] = job["log"][-MAX_LOGS:]

    print(line, flush=True)


def get_job_status():

    with lock:

        return dict(job)


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

    except Exception:

        return None


def score_int(value):

    try:

        if value is None:

            return None

        value = html_lib.unescape(
            str(value)
        )

        value = value.replace("\\", "")

        value = re.sub(
            r"<[^>]+>",
            "",
            value,
        )

        value = value.strip()

        if not re.fullmatch(
            r"\d{1,2}",
            value,
        ):

            return None

        number = int(value)

        if 0 <= number <= 99:

            return number

    except Exception:

        pass

    return None


# ============================================================
# 텍스트 정리
# ============================================================

def clean_text(value):

    if value is None:

        return ""

    value = html_lib.unescape(
        str(value)
    )

    value = value.replace(
        "\\/",
        "/",
    )

    value = value.replace(
        "\\u0026",
        "&",
    )

    value = re.sub(
        r"<script.*?</script>",
        " ",
        value,
        flags=re.I | re.S,
    )

    value = re.sub(
        r"<style.*?</style>",
        " ",
        value,
        flags=re.I | re.S,
    )

    value = re.sub(
        r"<[^>]+>",
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
# 팀 이름 검증
# ============================================================

def valid_team_name(name):

    if not isinstance(name, str):

        return False

    name = clean_text(name)

    if not name:

        return False

    if len(name) > 100:

        return False

    normalized = name.strip().lower()

    invalid_names = {

        "",

        "home",

        "away",

        "home team",

        "away team",

        "hometeam",

        "awayteam",

        "상대팀",

        "홈팀",

        "원정팀",

        "unknown",

        "undefined",

        "null",

        "none",

        "n/a",

        "tbd",

    }

    if normalized in invalid_names:

        return False

    if re.fullmatch(
        r"[\d\s.,:/\-]+",
        name,
    ):

        return False

    if re.search(
        r"\bID\s*\d+\b",
        name,
        re.I,
    ):

        return False

    if re.search(
        r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}$",
        name,
    ):

        return False

    return True


def valid_team_names(home_team, away_team):

    if not valid_team_name(home_team):

        return False

    if not valid_team_name(away_team):

        return False

    home = clean_text(
        home_team
    ).lower()

    away = clean_text(
        away_team
    ).lower()

    if home == away:

        return False

    return True


# ============================================================
# 점수로 승무패 계산
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
# 경기 페이지 가져오기
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
# JSON 파싱
# ============================================================

def parse_json(text):

    if not text:

        return None

    try:

        return json.loads(text)

    except Exception:

        pass

    # JSON 앞뒤에 다른 문자열이 포함된 경우
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
# HTML 내부 JSON 탐색
# ============================================================

def extract_json_blocks(page):

    blocks = []

    patterns = [

        r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',

        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',

    ]

    for pattern in patterns:

        found = re.findall(
            pattern,
            page,
            re.I | re.S,
        )

        blocks.extend(found)

    return blocks


# ============================================================
# JSON 키 정규화
# ============================================================

def normalize_key(value):

    return re.sub(
        r"[^a-z0-9]",
        "",
        str(value).lower(),
    )


# ============================================================
# JSON에서 팀 이름 재귀 검색
# ============================================================

def recursive_team_search(obj):

    if isinstance(obj, dict):

        normalized = {

            normalize_key(key): value

            for key, value in obj.items()

        }

        pairs = [

            (
                "hometeam",
                "awayteam",
            ),

            (
                "hometeamname",
                "awayteamname",
            ),

            (
                "hometeamtext",
                "awayteamtext",
            ),

            (
                "hometeamfullname",
                "awayteamfullname",
            ),

            (
                "hometeamnameen",
                "awayteamnameen",
            ),

            (
                "hometeamnamecn",
                "awayteamnamecn",
            ),

            (
                "hometeamnamedisplay",
                "awayteamnamedisplay",
            ),

            (
                "hometeamnamezh",
                "awayteamnamezh",
            ),

            (
                "hometeamnameko",
                "awayteamnameko",
            ),

            (
                "hometeamnamejp",
                "awayteamnamejp",
            ),

            (
                "home_team",
                "away_team",
            ),

            (
                "home_team_name",
                "away_team_name",
            ),

            (
                "hteam",
                "ateam",
            ),

            (
                "hometeamname",
                "guestteamname",
            ),

            (
                "hostname",
                "guestname",
            ),

            (
                "hometeam",
                "guestteam",
            ),

        ]

        for home_key, away_key in pairs:

            home_key = normalize_key(
                home_key
            )

            away_key = normalize_key(
                away_key
            )

            if (
                home_key in normalized
                and away_key in normalized
            ):

                home = normalized[
                    home_key
                ]

                away = normalized[
                    away_key
                ]

                if isinstance(home, (str, int)) and isinstance(away, (str, int)):

                    home = clean_text(home)

                    away = clean_text(away)

                    if valid_team_names(
                        home,
                        away,
                    ):

                        return home, away

        # 하위 객체 탐색
        for value in obj.values():

            found = recursive_team_search(
                value
            )

            if found:

                return found

    elif isinstance(obj, list):

        for value in obj:

            found = recursive_team_search(
                value
            )

            if found:

                return found

    return None


# ============================================================
# HTML / JavaScript에서 팀 이름 검색
# ============================================================

def extract_team_names(page):

    # --------------------------------------------------------
    # 1. JSON 블록
    # --------------------------------------------------------

    for block in extract_json_blocks(page):

        data = parse_json(
            html_lib.unescape(block)
        )

        if data is None:

            continue

        found = recursive_team_search(
            data
        )

        if found:

            return found

    # --------------------------------------------------------
    # 2. JavaScript 변수 / JSON 속성
    # --------------------------------------------------------

    patterns = [

        (
            r'["\']homeTeamName["\']\s*:\s*["\']([^"\']+)["\']',

            r'["\']awayTeamName["\']\s*:\s*["\']([^"\']+)["\']',

        ),

        (
            r'["\']homeTeam["\']\s*:\s*["\']([^"\']+)["\']',

            r'["\']awayTeam["\']\s*:\s*["\']([^"\']+)["\']',

        ),

        (
            r'["\']home_team["\']\s*:\s*["\']([^"\']+)["\']',

            r'["\']away_team["\']\s*:\s*["\']([^"\']+)["\']',

        ),

        (
            r'["\']home_team_name["\']\s*:\s*["\']([^"\']+)["\']',

            r'["\']away_team_name["\']\s*:\s*["\']([^"\']+)["\']',

        ),

        (
            r'["\']hteam["\']\s*:\s*["\']([^"\']+)["\']',

            r'["\']ateam["\']\s*:\s*["\']([^"\']+)["\']',

        ),

        (
            r'["\']HomeTeam["\']\s*:\s*["\']([^"\']+)["\']',

            r'["\']AwayTeam["\']\s*:\s*["\']([^"\']+)["\']',

        ),

        (
            r'["\']homeName["\']\s*:\s*["\']([^"\']+)["\']',

            r'["\']awayName["\']\s*:\s*["\']([^"\']+)["\']',

        ),

        (
            r'["\']HomeName["\']\s*:\s*["\']([^"\']+)["\']',

            r'["\']AwayName["\']\s*:\s*["\']([^"\']+)["\']',

        ),

        (
            r'["\']hostTeam["\']\s*:\s*["\']([^"\']+)["\']',

            r'["\']guestTeam["\']\s*:\s*["\']([^"\']+)["\']',

        ),

    ]

    for home_pattern, away_pattern in patterns:

        home_matches = re.findall(
            home_pattern,
            page,
            re.I,
        )

        away_matches = re.findall(
            away_pattern,
            page,
            re.I,
        )

        if home_matches and away_matches:

            for home, away in zip(
                home_matches,
                away_matches,
            ):

                home = clean_text(home)

                away = clean_text(away)

                if valid_team_names(
                    home,
                    away,
                ):

                    return home, away

    # --------------------------------------------------------
    # 3. HTML data 속성
    # --------------------------------------------------------

    attribute_pairs = [

        (
            r'data-home-team\s*=\s*["\']([^"\']+)["\']',

            r'data-away-team\s*=\s*["\']([^"\']+)["\']',

        ),

        (
            r'data-home-name\s*=\s*["\']([^"\']+)["\']',

            r'data-away-name\s*=\s*["\']([^"\']+)["\']',

        ),

        (
            r'data-hometeam\s*=\s*["\']([^"\']+)["\']',

            r'data-awayteam\s*=\s*["\']([^"\']+)["\']',

        ),

    ]

    for home_pattern, away_pattern in attribute_pairs:

        home_matches = re.findall(
            home_pattern,
            page,
            re.I,
        )

        away_matches = re.findall(
            away_pattern,
            page,
            re.I,
        )

        if home_matches and away_matches:

            for home, away in zip(
                home_matches,
                away_matches,
            ):

                home = clean_text(home)

                away = clean_text(away)

                if valid_team_names(
                    home,
                    away,
                ):

                    return home, away

    # --------------------------------------------------------
    # 4. HTML class / id
    # --------------------------------------------------------

    def find_html_team(pattern):

        tag_pattern = re.compile(

            r'<(?P<tag>div|span|a|strong|p|td|b)\b'

            r'(?=[^>]*(?:class|id)\s*=\s*["\'][^"\']*'

            + pattern +

            r'[^"\']*["\'])'

            r'[^>]*>(.*?)</(?P=tag)\s*>',

            re.I | re.S,

        )

        values = []

        for match in tag_pattern.finditer(page):

            value = clean_text(
                match.group(2)
            )

            if valid_team_name(value):

                values.append(value)

        return values

    home_patterns = [

        r'home[^"\']*team',

        r'team[^"\']*home',

        r'home[^"\']*name',

        r'name[^"\']*home',

        r'host[^"\']*team',

        r'team[^"\']*host',

    ]

    away_patterns = [

        r'away[^"\']*team',

        r'team[^"\']*away',

        r'away[^"\']*name',

        r'name[^"\']*away',

        r'guest[^"\']*team',

        r'team[^"\']*guest',

    ]

    home_candidates = []

    away_candidates = []

    for pattern in home_patterns:

        home_candidates.extend(
            find_html_team(pattern)
        )

    for pattern in away_patterns:

        away_candidates.extend(
            find_html_team(pattern)
        )

    for home in home_candidates:

        for away in away_candidates:

            if valid_team_names(
                home,
                away,
            ):

                return home, away

    # --------------------------------------------------------
    # 5. 페이지 제목
    # --------------------------------------------------------

    title_match = re.search(

        r"<title[^>]*>(.*?)</title>",

        page,

        re.I | re.S,

    )

    if title_match:

        title = clean_text(
            title_match.group(1)
        )

        title_patterns = [

            r"(.+?)\s+(?:vs\.?|VS|v)\s+(.+?)(?:\s*[|｜\-]\s*|$)",

            r"(.+?)\s*-\s*(.+?)\s*\|\s*Scoreman",

        ]

        for pattern in title_patterns:

            match = re.search(
                pattern,
                title,
                re.I,
            )

            if match:

                home = clean_text(
                    match.group(1)
                )

                away = clean_text(
                    match.group(2)
                )

                if valid_team_names(
                    home,
                    away,
                ):

                    return home, away

    return "", ""


# ============================================================
# 팀 이름 진단
# ============================================================

def log_team_diagnostics(
    schedule_id,
    page,
):

    add_log(
        f"[팀명 진단] ID={schedule_id} "
        "HTML 구조 확인 시작"
    )

    # --------------------------------------------------------
    # 제목
    # --------------------------------------------------------

    title_match = re.search(

        r"<title[^>]*>(.*?)</title>",

        page,

        re.I | re.S,

    )

    if title_match:

        title = clean_text(
            title_match.group(1)
        )

        add_log(
            f"[팀명 진단 제목] {title[:200]}"
        )

    # --------------------------------------------------------
    # 주요 키워드
    # --------------------------------------------------------

    keywords = [

        "homeTeam",

        "awayTeam",

        "home_team",

        "away_team",

        "homeTeamName",

        "awayTeamName",

        "HomeName",

        "AwayName",

        "homename",

        "awayname",

        "hostTeam",

        "guestTeam",

        "data-home",

        "data-away",

        "team_name",

        "teamname",

        "score",

        "主队",

        "客队",

    ]

    found_count = 0

    seen_positions = set()

    for keyword in keywords:

        match = re.search(
            re.escape(keyword),
            page,
            re.I,
        )

        if not match:

            continue

        position = match.start()

        if any(

            abs(position - old) < 100

            for old in seen_positions

        ):

            continue

        seen_positions.add(
            position
        )

        start = max(
            0,
            position - 180,
        )

        end = min(
            len(page),
            position + 300,
        )

        snippet = page[
            start:end
        ]

        snippet = re.sub(
            r"\s+",
            " ",
            snippet,
        ).strip()

        add_log(
            f"[팀명 진단 HTML] "
            f"키워드={keyword} "
            f"내용={snippet[:400]}"
        )

        found_count += 1

        if found_count >= 8:

            break

    if found_count == 0:

        add_log(
            "[팀명 진단] "
            "알려진 팀명 키워드를 찾지 못했습니다."
        )

    add_log(
        f"[팀명 진단] 검색 완료: {found_count}개"
    )


# ============================================================
# JSON에서 실제 점수 재귀 검색
# ============================================================

def recursive_score_search(obj):

    if isinstance(obj, dict):

        normalized = {

            normalize_key(key): value

            for key, value in obj.items()

        }

        pairs = [

            (
                "homeScore",
                "awayScore",
            ),

            (
                "home_score",
                "away_score",
            ),

            (
                "homescore",
                "awayscore",
            ),

            (
                "hscore",
                "ascore",
            ),

            (
                "score_home",
                "score_away",
            ),

            (
                "homeFullScore",
                "awayFullScore",
            ),

            (
                "fullHomeScore",
                "fullAwayScore",
            ),

        ]

        for home_key, away_key in pairs:

            home_key = normalize_key(
                home_key
            )

            away_key = normalize_key(
                away_key
            )

            if (

                home_key in normalized

                and away_key in normalized

            ):

                home = score_int(
                    normalized[home_key]
                )

                away = score_int(
                    normalized[away_key]
                )

                if home is not None and away is not None:

                    return home, away

        # 명시적으로 점수를 나타내는 문자열만 탐색
        for key, value in obj.items():

            key_normalized = normalize_key(
                key
            )

            if "score" not in key_normalized:

                continue

            if any(

                word in key_normalized

                for word in [

                    "half",

                    "halftime",

                    "firsthalf",

                    "secondhalf",

                    "corner",

                    "yellow",

                    "redcard",

                ]

            ):

                continue

            if isinstance(value, str):

                match = re.fullmatch(

                    r"\s*(\d{1,2})\s*[-:：]\s*(\d{1,2})\s*",

                    value,

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

            if found:

                return found

    elif isinstance(obj, list):

        for value in obj:

            found = recursive_score_search(
                value
            )

            if found:

                return found

    return None


# ============================================================
# 실제 점수 추출
# ============================================================

def extract_score(page):

    # --------------------------------------------------------
    # 1. JSON 블록
    # --------------------------------------------------------

    for block in extract_json_blocks(page):

        data = parse_json(
            html_lib.unescape(block)
        )

        if data is None:

            continue

        found = recursive_score_search(
            data
        )

        if found:

            home, away = found

            return (
                home,
                away,
                calculate_result(home, away),
            )

    # --------------------------------------------------------
    # 2. HTML의 명시적인 홈 / 원정 점수 속성
    # --------------------------------------------------------

    score_pairs = [

        (

            r'["\']homeScore["\']\s*:\s*["\']?(\d{1,2})',

            r'["\']awayScore["\']\s*:\s*["\']?(\d{1,2})',

        ),

        (

            r'["\']home_score["\']\s*:\s*["\']?(\d{1,2})',

            r'["\']away_score["\']\s*:\s*["\']?(\d{1,2})',

        ),

        (

            r'["\']hscore["\']\s*:\s*["\']?(\d{1,2})',

            r'["\']ascore["\']\s*:\s*["\']?(\d{1,2})',

        ),

        (

            r'data-home-score\s*=\s*["\'](\d{1,2})',

            r'data-away-score\s*=\s*["\'](\d{1,2})',

        ),

    ]

    for home_pattern, away_pattern in score_pairs:

        home_matches = re.findall(

            home_pattern,

            page,

            re.I,

        )

        away_matches = re.findall(

            away_pattern,

            page,

            re.I,

        )

        if home_matches and away_matches:

            for home_value, away_value in zip(

                home_matches,

                away_matches,

            ):

                home = score_int(
                    home_value
                )

                away = score_int(
                    away_value
                )

                if home is not None and away is not None:

                    return (

                        home,

                        away,

                        calculate_result(
                            home,
                            away,
                        ),

                    )

    # --------------------------------------------------------
    # 3. 명시적인 score HTML 요소
    # --------------------------------------------------------

    score_element_pattern = re.compile(

        r'<(?P<tag>div|span|td|strong|b)\b'

        r'(?=[^>]*(?:class|id)\s*=\s*["\'][^"\']*score[^"\']*["\'])'

        r'[^>]*>(?P<content>.*?)</(?P=tag)\s*>',

        re.I | re.S,

    )

    for match in score_element_pattern.finditer(page):

        content = clean_text(
            match.group("content")
        )

        score_match = re.fullmatch(

            r"(\d{1,2})\s*[-:：]\s*(\d{1,2})",

            content,

        )

        if score_match:

            home = score_int(
                score_match.group(1)
            )

            away = score_int(
                score_match.group(2)
            )

            if home is not None and away is not None:

                return (

                    home,

                    away,

                    calculate_result(
                        home,
                        away,
                    ),

                )

    # --------------------------------------------------------
    # 4. 명시적인 JSON score 문자열
    # --------------------------------------------------------

    score_patterns = [

        r'["\'](?:matchScore|fullScore|score)["\']\s*:\s*["\'](\d{1,2})\s*[-:：]\s*(\d{1,2})["\']',

        r'data-score\s*=\s*["\'](\d{1,2})\s*[-:：]\s*(\d{1,2})["\']',

    ]

    for pattern in score_patterns:

        found = re.findall(

            pattern,

            page,

            re.I,

        )

        if found:

            for home_value, away_value in found:

                home = score_int(
                    home_value
                )

                away = score_int(
                    away_value
                )

                if home is not None and away is not None:

                    return (

                        home,

                        away,

                        calculate_result(
                            home,
                            away,
                        ),

                    )

    # --------------------------------------------------------
    # 중요:
    # HTML 전체에서 임의의 숫자-숫자 패턴을 찾아
    # 경기 점수로 사용하는 처리는 하지 않음.
    #
    # 잘못된 0-10 등의 점수 추출 방지.
    # --------------------------------------------------------

    return None, None, None


# ============================================================
# 경기 날짜
# ============================================================

def extract_match_date(page):

    patterns = [

        r'"matchDate"\s*:\s*"([^"]+)"',

        r'"match_date"\s*:\s*"([^"]+)"',

        r'"matchTime"\s*:\s*"([^"]+)"',

        r'"match_time"\s*:\s*"([^"]+)"',

        r'"date"\s*:\s*"([^"]+)"',

    ]

    for pattern in patterns:

        found = re.findall(

            pattern,

            page,

            re.I,

        )

        if found:

            for value in found:

                value = clean_text(value)

                if re.search(

                    r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}",

                    value,

                ):

                    return value

    # 날짜를 찾지 못하면 None
    return None


# ============================================================
# 배당 API
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
# 해외업체 최종배당 추출
# ============================================================

def extract_bookmakers(data):

    if not isinstance(data, dict):

        return []

    mixodds = None

    if isinstance(data.get("Data"), dict):

        mixodds = data["Data"].get(
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

        name = clean_text(name)

        if not name:

            name = f"업체_{cid}"

        key = str(cid)

        # 업체 ID 중복 방지
        if key in seen:

            continue

        seen.add(key)

        result.append({

            "cid": str(cid),

            "name": name,

            "home": home,

            "draw": draw,

            "away": away,

        })

    return result


# ============================================================
# 업체 선택
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
        ).lower()

        name = str(
            item["name"]
        ).lower()

        if (

            cid in selected

            or name in selected

        ):

            result.append(item)

    return result


# ============================================================
# 경기 하나 수집
# ============================================================

def collect_one_match(

    schedule_id,

    selected_companies=None,

):

    schedule_id = str(
        schedule_id
    )

    # --------------------------------------------------------
    # 이미 완료된 경기
    # --------------------------------------------------------

    if database.is_collection_completed(
        schedule_id
    ):

        add_log(
            f"[중복] ID={schedule_id}"
        )

        return "exists"

    # --------------------------------------------------------
    # 경기 페이지
    # --------------------------------------------------------

    page = fetch_match_page(
        schedule_id
    )

    # --------------------------------------------------------
    # 팀 이름
    # --------------------------------------------------------

    home_team, away_team = extract_team_names(
        page
    )

    if not valid_team_names(

        home_team,

        away_team,

    ):

        add_log(

            f"[팀명 미확인] ID={schedule_id} "

            "실제 홈팀 / 원정팀 이름을 추출하지 못했습니다."

        )

        # 진단 로그 출력
        log_team_diagnostics(

            schedule_id,

            page,

        )

        # 임의 팀 이름으로 저장하지 않음
        raise RuntimeError(

            "실제 팀 이름 추출 실패"

        )

    # --------------------------------------------------------
    # 점수 / 결과
    # --------------------------------------------------------

    home_score, away_score, result = extract_score(
        page
    )

    match_date = extract_match_date(
        page
    )

    # --------------------------------------------------------
    # 결과 검증
    # --------------------------------------------------------

    if (

        home_score is None

        or away_score is None

        or result not in ("승", "무", "패")

    ):

        add_log(

            f"[결과 미확인] ID={schedule_id} "

            f"홈팀={home_team} "

            f"원정팀={away_team} "

            f"홈점수={home_score} "

            f"원정점수={away_score}"

        )

        # 실제 팀 이름이 확인된 경우에만
        # 미확인 경기로 임시 저장
        try:

            database.save_match(

                schedule_id,

                match_date,

                home_team,

                away_team,

                None,

                None,

                None,

                "scoreman",

            )

        except Exception as save_error:

            add_log(

                f"[미확인 경기 임시저장 오류] "

                f"ID={schedule_id} "

                f"{save_error}"

            )

        # 완료 ID는 저장하지 않음
        raise RuntimeError(

            "실제 경기결과 / 점수 확인 실패"

        )

    # --------------------------------------------------------
    # 최종 점수 검증
    # --------------------------------------------------------

    calculated_result = calculate_result(

        home_score,

        away_score,

    )

    if calculated_result != result:

        raise RuntimeError(

            "승무패 계산 검증 실패"

        )

    add_log(

        f"[경기결과 검증] ID={schedule_id} "

        f"{home_team} "

        f"{home_score}-{away_score} "

        f"{away_team} "

        f"결과={result}"

    )

    # --------------------------------------------------------
    # 배당 API
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

        selected_companies,

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
    # 경기 저장
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
    # 배당 저장
    # --------------------------------------------------------

    saved_odds = 0

    for item in bookmakers:

        if not is_running():

            add_log(

                f"[중지] ID={schedule_id} "

                "배당 저장 도중 중지 요청"

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

        if not ok:

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
    # 모든 데이터 저장 후 완료 상태 저장
    # --------------------------------------------------------

    if not is_running():

        add_log(

            f"[중지] ID={schedule_id} "

            "완료 상태 저장 전 중지"

        )

        return "stopped"

    state_saved = database.save_collection_state(

        schedule_id,

        "completed",

    )

    if not state_saved:

        raise RuntimeError(

            "완료 상태 저장 실패"

        )

    # --------------------------------------------------------
    # 성공
    # --------------------------------------------------------

    add_log(

        f"[수집 성공] ID={schedule_id} "

        f"업체={saved_odds} "

        f"결과={result}"

    )

    return {

        "status": "success",

        "odds": saved_odds,

        "result": result,

    }


# ============================================================
# 백그라운드 수집
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
        f"[실행 코드 확인] "
        f"collector 버전={COLLECTOR_VERSION}"
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

    total = end_id - start_id + 1

    for index, schedule_id in enumerate(

        range(
            start_id,
            end_id + 1,
        ),

        1,

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

                job["error"] = str(
                    error
                )

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

      
