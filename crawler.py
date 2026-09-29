# crawler.py

import time
import re
import json
import html as html_lib
import requests

import database


# =========================================================
# 기본 설정
# =========================================================

BASE_URL = "https://www.scoreman123.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; K) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36"
    ),
    "Referer": BASE_URL + "/"
}

session = requests.Session()
session.headers.update(HEADERS)


# =========================================================
# 변환
# =========================================================

def to_float(value):

    try:

        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        return float(
            value.replace(",", "")
        )

    except Exception:

        return None


def to_int(value):

    try:

        if value is None:
            return None

        return int(float(value))

    except Exception:

        return None


def clean_text(value):

    if value is None:
        return ""

    value = str(value)

    value = html_lib.unescape(value)

    value = value.replace("\\/", "/")
    value = value.replace('\\"', '"')
    value = value.replace("\\'", "'")

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


# =========================================================
# 결과 계산
# =========================================================

def calculate_result(
    home_score,
    away_score
):

    if (
        home_score is None
        or away_score is None
    ):

        return ""

    if home_score > away_score:
        return "승"

    if home_score < away_score:
        return "패"

    return "무"


# =========================================================
# 경기 페이지
# =========================================================

def get_match_page(schedule_id):

    url = (
        f"{BASE_URL}/match/data-{schedule_id}"
    )

    try:

        response = session.get(
            url,
            timeout=20
        )

        print(
            f"[페이지] ID={schedule_id} "
            f"HTTP={response.status_code} "
            f"길이={len(response.text):,}",
            flush=True
        )

        if response.status_code != 200:

            return None

        if len(response.text) < 300:

            return None

        return response.text

    except Exception as e:

        print(
            f"[페이지 오류] "
            f"ID={schedule_id}: {e}",
            flush=True
        )

        return None


# =========================================================
# 일반 값 찾기
# =========================================================

def find_value(
    html,
    keys
):

    for key in keys:

        patterns = [

            rf'"{re.escape(key)}"\s*:\s*"([^"]*)"',

            rf'"{re.escape(key)}"\s*:\s*([^,}}\s]+)',

            rf"'{re.escape(key)}'\s*:\s*'([^']*)'",

            rf"{re.escape(key)}\s*=\s*[\"']([^\"']+)[\"']"

        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                html,
                re.I | re.S
            )

            if match:

                value = clean_text(
                    match.group(1)
                )

                if value:

                    return value

    return ""


# =========================================================
# JSON 객체 탐색
# =========================================================

def search_json_objects(html):

    objects = []

    scripts = re.findall(
        r"<script[^>]*>(.*?)</script>",
        html,
        re.I | re.S
    )

    for script in scripts:

        script = script.strip()

        if not script:
            continue

        try:

            obj = json.loads(script)

            objects.append(obj)

        except Exception:

            pass

        for match in re.finditer(
            r"\{[^{}]{20,5000}\}",
            script,
            re.S
        ):

            value = match.group(0)

            try:

                obj = json.loads(value)

                objects.append(obj)

            except Exception:

                continue

    return objects


# =========================================================
# JSON 재귀 검색
# =========================================================

def recursive_find(
    obj,
    wanted_keys
):

    if isinstance(obj, dict):

        for key, value in obj.items():

            key_lower = str(key).lower()

            if key_lower in wanted_keys:

                if isinstance(
                    value,
                    (str, int, float)
                ):

                    value = clean_text(
                        value
                    )

                    if value:

                        return value

            result = recursive_find(
                value,
                wanted_keys
            )

            if result:

                return result

    elif isinstance(obj, list):

        for item in obj:

            result = recursive_find(
                item,
                wanted_keys
            )

            if result:

                return result

    return ""


# =========================================================
# 팀명
# =========================================================

def find_team_names(html):

    home_keys = {
        "hometeamname",
        "home_team_name",
        "hometeam",
        "home_team",
        "homename",
        "hname",
        "hometeamnamecn"
    }

    away_keys = {
        "awayteamname",
        "away_team_name",
        "awayteam",
        "away_team",
        "awayname",
        "aname",
        "awayteamnamecn"
    }

    home = find_value(
        html,
        list(home_keys)
    )

    away = find_value(
        html,
        list(away_keys)
    )

    if not home or not away:

        objects = search_json_objects(
            html
        )

        for obj in objects:

            if not home:

                home = recursive_find(
                    obj,
                    home_keys
                )

            if not away:

                away = recursive_find(
                    obj,
                    away_keys
                )

            if home and away:

                break

    # -----------------------------------------------------
    # data-home
    # -----------------------------------------------------

    if not home:

        patterns = [

            r'data-home(?:team|name)?=["\']([^"\']+)',

            r'data-hname=["\']([^"\']+)',

            r'data-home-team=["\']([^"\']+)'

        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                html,
                re.I
            )

            if match:

                home = clean_text(
                    match.group(1)
                )

                break

    # -----------------------------------------------------
    # data-away
    # -----------------------------------------------------

    if not away:

        patterns = [

            r'data-away(?:team|name)?=["\']([^"\']+)',

            r'data-aname=["\']([^"\']+)',

            r'data-away-team=["\']([^"\']+)'

        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                html,
                re.I
            )

            if match:

                away = clean_text(
                    match.group(1)
                )

                break

    return (
        clean_text(home),
        clean_text(away)
    )


# =========================================================
# 스코어
# =========================================================

def find_scores(html):

    patterns = [

        (
            r'"homeScore"\s*:\s*["\']?(\d+)'
            r'.{0,1000}?'
            r'"awayScore"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"home_score"\s*:\s*["\']?(\d+)'
            r'.{0,1000}?'
            r'"away_score"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"hscore"\s*:\s*["\']?(\d+)'
            r'.{0,1000}?'
            r'"ascore"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"HomeScore"\s*:\s*["\']?(\d+)'
            r'.{0,1000}?'
            r'"AwayScore"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"hs"\s*:\s*["\']?(\d+)'
            r'.{0,1000}?'
            r'"as"\s*:\s*["\']?(\d+)'
        )

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.I | re.S
        )

        if match:

            return (
                to_int(match.group(1)),
                to_int(match.group(2))
            )

    patterns = [

        r">\s*(\d{1,2})\s*-\s*(\d{1,2})\s*<",

        r">\s*(\d{1,2})\s*:\s*(\d{1,2})\s*<",

        r"(\d{1,2})\s*-\s*(\d{1,2})"

    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            html,
            re.I | re.S
        )

        if matches:

            hs, aws = matches[-1]

            return (
                to_int(hs),
                to_int(aws)
            )

    return None, None


# =========================================================
# 날짜
# =========================================================

def find_match_date(html):

    keys = [

        "matchTime",
        "matchDate",
        "startTime",
        "MatchTime",
        "MatchDate",
        "date"

    ]

    value = find_value(
        html,
        keys
    )

    if value:

        return value

    match = re.search(
        r"(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}"
        r"(?:\s+\d{1,2}:\d{2})?)",
        html
    )

    if match:

        return clean_text(
            match.group(1)
        )

    return ""


# =========================================================
# 경기 파싱
# =========================================================

def parse_match_info(
    html,
    schedule_id
):

    home_team, away_team = find_team_names(
        html
    )

    home_score, away_score = find_scores(
        html
    )

    match_date = find_match_date(
        html
    )

    result = calculate_result(
        home_score,
        away_score
    )

    print(
        f"[파싱] ID={schedule_id} "
        f"홈={home_team or '-'} "
        f"원정={away_team or '-'} "
        f"스코어="
        f"{home_score if home_score is not None else '-'}-"
        f"{away_score if away_score is not None else '-'} "
        f"결과={result or '-'}",
        flush=True
    )

    if not home_team or not away_team:

        print(
            f"[파싱 실패] ID={schedule_id} "
            f"팀 정보를 찾지 못했습니다.",
            flush=True
        )

        return None

    return {

        "schedule_id":
            str(schedule_id),

        "match_date":
            match_date,

        "home_team":
            home_team,

        "away_team":
            away_team,

        "home_score":
            home_score,

        "away_score":
            away_score,

        "result":
            result
    }


# =========================================================
# 업체명 비교용
# =========================================================

def normalize_company_name(name):

    if name is None:

        return ""

    return re.sub(
        r"\s+",
        " ",
        str(name).strip().lower()
    )


# =========================================================
# 선택 업체 필터
# =========================================================

def company_is_selected(
    company_name,
    selected_companies
):

    # None = 전체 업체 저장
    if selected_companies is None:

        return True

    # 빈 리스트 = 저장 안 함
    if len(selected_companies) == 0:

        return False

    target = normalize_company_name(
        company_name
    )

    for company in selected_companies:

        if target == normalize_company_name(
            company
        ):

            return True

    return False


# =========================================================
# 최종배당 수집
#
# 중요:
# euro["f"] = 초기배당
# euro["l"] = 최종배당
#
# 초기배당은 사용하지 않음.
# =========================================================

def get_odds(schedule_id):

    url = (
        f"{BASE_URL}/ajax/soccerajax"
        f"?type=14"
        f"&t=1"
        f"&id={schedule_id}"
        f"&h=0"
    )

    try:

        response = session.get(
            url,
            timeout=20
        )

        print(
            f"[배당] ID={schedule_id} "
            f"HTTP={response.status_code}",
            flush=True
        )

  
