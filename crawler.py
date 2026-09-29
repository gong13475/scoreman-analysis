import time
import re
import json
import requests
from html import unescape

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
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": BASE_URL + "/",
    "Connection": "keep-alive",
}

session = requests.Session()
session.headers.update(HEADERS)


# =========================================================
# 변환
# =========================================================

def to_float(value):

    if value is None:
        return None

    try:

        value = str(value).strip()

        value = value.replace(",", "")

        if value == "":
            return None

        return float(value)

    except Exception:

        return None


def to_int(value):

    if value is None:
        return None

    try:

        return int(float(str(value).strip()))

    except Exception:

        return None


def clean_text(value):

    if value is None:
        return ""

    value = unescape(str(value))

    value = value.replace("\\/", "/")
    value = value.replace('\\"', '"')

    return value.strip()


# =========================================================
# 결과 계산
# =========================================================

def calculate_result(home_score, away_score):

    if home_score is None or away_score is None:
        return ""

    if home_score > away_score:
        return "승"

    if home_score < away_score:
        return "패"

    return "무"


# =========================================================
# 페이지 요청
# =========================================================

def get_match_page(schedule_id):

    url = f"{BASE_URL}/match/data-{schedule_id}"

    try:

        response = session.get(
            url,
            timeout=20
        )

        if response.status_code != 200:
            return None

        if not response.text:
            return None

        return response.text

    except Exception:

        return None


# =========================================================
# 정규식 JSON 값
# =========================================================

def regex_value(html, names):

    for name in names:

        patterns = [

            rf'"{re.escape(name)}"\s*:\s*"([^"]*)"',
            rf'"{re.escape(name)}"\s*:\s*([^,\}}\s]+)',
            rf"'{re.escape(name)}'\s*:\s*'([^']*)'",
            rf"'{re.escape(name)}'\s*:\s*([^,\}}\s]+)"

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
# 팀명 추출
# =========================================================

def find_home_team(html):

    names = [

        "homeTeamName",
        "home_team",
        "homeTeam",
        "HomeTeam",
        "hname",
        "HomeName",
        "homeName",
        "HomeTeamName",
        "teamHome",
        "home"

    ]

    value = regex_value(
        html,
        names
    )

    if value:
        return value

    # HTML class 보완
    patterns = [

        r'class="[^"]*(?:home|Home)[^"]*"[^>]*>\s*([^<]{2,80})<',

        r'<[^>]+class="[^"]*(?:home|Home)[^"]*"[^>]*>'
        r'\s*([^<]{2,80})\s*</',

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


def find_away_team(html):

    names = [

        "awayTeamName",
        "away_team",
        "awayTeam",
        "AwayTeam",
        "aname",
        "AwayName",
        "awayName",
        "AwayTeamName",
        "teamAway",
        "away"

    ]

    value = regex_value(
        html,
        names
    )

    if value:
        return value

    patterns = [

        r'class="[^"]*(?:away|Away)[^"]*"[^>]*>\s*([^<]{2,80})<',

        r'<[^>]+class="[^"]*(?:away|Away)[^"]*"[^>]*>'
        r'\s*([^<]{2,80})\s*</',

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
# 스코어 추출
# =========================================================

def find_score(html):

    score_pairs = [

        (
            "homeScore",
            "awayScore"
        ),

        (
            "home_score",
            "away_score"
        ),

        (
            "hscore",
            "ascore"
        ),

        (
            "HomeScore",
            "AwayScore"
        ),

        (
            "home_score_full",
            "away_score_full"
        ),

    ]


    for home_key, away_key in score_pairs:

        home = regex_value(
            html,
            [home_key]
        )

        away = regex_value(
            html,
            [away_key]
        )

        hs = to_int(home)
        aws = to_int(away)

        if hs is not None and aws is not None:

            return hs, aws


    # -----------------------------------------------------
    # JSON 형태의 score 객체
    # -----------------------------------------------------

    patterns = [

        r'"score"\s*:\s*\{\s*'
        r'"home"\s*:\s*(\d+).*?'
        r'"away"\s*:\s*(\d+)',

        r'"score"\s*:\s*\[\s*'
        r'(\d+)\s*,\s*(\d+)\s*\]',

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


    # -----------------------------------------------------
    # HTML 2 - 1 형태
    # -----------------------------------------------------

    patterns = [

        r'>\s*(\d{1,2})\s*-\s*(\d{1,2})\s*<',

        r'(\d{1,2})\s*-\s*(\d{1,2})',

    ]


    candidates = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            html
        )

        for hs, aws in matches:

            h = to_int(hs)
            a = to_int(aws)

            if h is not None and a is not None:

                candidates.append(
                    (h, a)
                )


    if candidates:

        return candidates[-1]


    return None, None


# =========================================================
# 날짜
# =========================================================

def find_match_date(html):

    names = [

        "matchTime",
        "matchDate",
        "startTime",
        "date",
        "MatchTime",
        "MatchDate",
        "gameTime",
        "eventTime"

    ]

    value = regex_value(
        html,
        names
    )

    if value:
        return value

    # 날짜 문자열 보완
    patterns = [

        r'(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}'
        r'\s+\d{1,2}:\d{2})',

        r'(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})',

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html
        )

        if match:

            return clean_text(
                match.group(1)
            )

    return ""


# =========================================================
# 경기정보
# =========================================================

def parse_match_info(
    html,
    schedule_id
):

    if not html:
        return None


    home_team = find_home_team(
        html
    )

    away_team = find_away_team(
        html
    )

    home_score, away_score = find_score(
        html
    )

    match_date = find_match_date(
        html
    )


    result = calculate_result(
        home_score,
        away_score
    )


    # -----------------------------------------------------
    # 최소한 팀명이 없으면 실패
    # -----------------------------------------------------

    if not home_team and not away_team:

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
# 배당 API
# =========================================================

def get_odds(schedule_id):

    urls = [

        (
            f"{BASE_URL}/ajax/soccerajax"
            f"?type=14&t=1&id={schedule_id}&h=0"
        ),

        (
            f"{BASE_URL}/ajax/soccerajax"
            f"?type=14&t=1&id={schedule_id}"
        ),

    ]


    data = None


    for url in urls:

        try:

            response = session.get(
                url,
                timeout=20,
                headers={
                    "X-Requested-With":
                        "XMLHttpRequest",
                    "Referer":
                        f"{BASE_URL}/match/data-{schedule_id}"
                }
            )

            if response.status_code != 200:
                continue

            try:

                data = response.json()

            except Exception:

                text = response.text.strip()

                if text.startswith("{"):

                    data = json.loads(text)

            if isinstance(data, dict):

                break

        except Exception:

            continue


    if not isinstance(data, dict):

        return []


    # -----------------------------------------------------
    # Data
    # -----------------------------------------------------

    data_block = data.get(
        "Data",
        {}
    )


    if not isinstance(data_block, dict):

        return []


    mixodds = data_block.get(
        "mixodds",
        []
    )


    if not isinstance(mixodds, list):

        return []


    result = []


    for item in mixodds:

        if not isinstance(item, dict):
            continue


        company_id = (
            item.get("cid")
            or item.get("company_id")
            or item.get("id")
        )


        company_name = (
            item.get("cn")
            or item.get("company_name")
            or item.get("name")
            or ""
        )


        euro = item.get(
            "euro",
            {}
        )


        if not isinstance(euro, dict):
            euro = {}


        initial = (
            euro.get("f")
            or euro.get("first")
            or {}
        )


        final = (
            euro.get("l")
            or euro.get("last")
            or {}
        )


        if not isinstance(initial, dict):
            initial = {}


        if not isinstance(final, dict):
            final = {}


        initial_home = to_float(
            initial.get("u")
            or initial.get("home")
        )


        initial_draw = to_float(
            initial.get("g")
            or initial.get("draw")
        )


        initial_away = to_float(
            initial.get("d")
            or initial.get("away")
        )


        final_home = to_float(
            final.get("u")
            or final.get("home")
        )


        final_draw = to_float(
            final.get("g")
            or final.get("draw")
        )


        final_away = to_float(
            final.get("d")
            or final.get("away")
        )


        # 초기 3개가 없으면 업체 제외
        if (
            initial_home is None
            or initial_draw is None
            or initial_away is None
        ):

            continue


        result.append({

            "company_id":
                company_id,

            "company_name":
                clean_text(
                    company_name
                ),

            "initial_home":
                initial_home,

            "initial_draw":
                initial_draw,

            "initial_away":
                initial_away,

            "final_home":
                final_home,

            "final_draw":
                final_draw,

            "final_away":
                final_away

        })


    return result


# =========================================================
# 저장
# =========================================================

def save_match_data(
    match,
    odds_list
):

    database.save_match(

        schedule_id=
            match["schedule_id"],

        match_date=
            match["match_date"],

        home_team=
            match["home_team"],

        away_team=
            match["away_team"],

        home_score=
            match["home_score"],

        away_score=
            match["away_score"],

        result=
            match["result"],

        source=
            "Scoreman"

    )


    for odds in odds_list:

        database.save_odds(

            schedule_id=
                match["schedule_id"],

            company_id=
                odds["company_id"],

            company_name=
                odds["company_name"],

            initial_home=
                odds["initial_home"],

            initial_draw=
                odds["initial_draw"],

            initial_away=
                odds["initial_away"],

            final_home=
                odds["final_home"],

            final_draw=
                odds["final_draw"],

            final_away=
                odds["final_away"]

        )


# =========================================================
# 존재 여부
# =========================================================

def match_exists(schedule_id):

    try:

        return (
            database.get_match(
                schedule_id
            )
            is not None
        )

    except Exception:

        return False


# =========================================================
# ID 하나 수집
# =========================================================

def collect_one(
    schedule_id,
    log_callback=None
):

    schedule_id = str(
        schedule_id
    )


    # -----------------------------------------------------
    # 이미 존재하는 경우
    # -----------------------------------------------------

    if match_exists(schedule_id):

        if log_callback:

            log_callback(
                f"[기존] {schedule_id}"
            )

        return {

            "status":
                "exists",

            "odds":
                0

        }


    # -----------------------------------------------------
    # 페이지
    # -----------------------------------------------------

    html = get_match_page(
        schedule_id
    )


    if not html:

        if log_callback:

            log_callback(
                f"[실패] {schedule_id} "
                f"페이지 요청 실패"
            )

        return {

            "status":
                "skip",

            "reason":
                "page",

            "odds":
                0

        }


    # -----------------------------------------------------
    # 경기정보
    # -----------------------------------------------------

    match = parse_match_info(
        html,
        schedule_id
    )


    if not match:

        if log_callback:

            log_callback(
                f"[실패] {schedule_id} "
                f"경기정보 파싱 실패"
            )

        return {

            "status":
                "skip",

            "reason":
                "match_parse",

            "odds":
                0

        }


    # -----------------------------------------------------
    # 결과가 아직 없으면 저장하지 않음
    # -----------------------------------------------------

    if match["result"] not in (
        "승",
        "무",
        "패"
    ):

        if log_callback:

            log_callback(
                f"[미완료] {schedule_id} "
                f"{match['home_team']} vs "
                f"{match['away_team']} "
                f"/ score="
                f"{match['home_score']}-"
                f"{match['away_score']}"
            )

        return {

            "status":
                "skip",

            "reason":
                "unfinished",

            "odds":
                0

        }


    # -----------------------------------------------------
    # 배당
    # -----------------------------------------------------

    odds_list = get_odds(
        schedule_id
    )


    if not odds_list:

        if log_callback:

            log_callback(
                f"[실패] {schedule_id} "
                f"배당 데이터 없음"
            )

        return {

            "status":
                "skip",

            "reason":
                "odds",

            "odds":
                0

        }


    # -----------------------------------------------------
    # 저장
    # -----------------------------------------------------

    save_match_data(
        match,
        odds_list
    )


    if log_callback:

        log_callback(
            f"[저장완료] {schedule_id} "
            f"{match['home_team']} vs "
            f"{match['away_team']} "
            f"/ {match['home_score']}-"
            f"{match['away_score']} "
            f"/ 결과 {match['result']} "
            f"/ 업체 {len(odds_list)}"
        )


        for odds in odds_list:

            log_callback(

                f"    └ {odds['company_name']} "
                f"| 초기 "
                f"{odds['initial_home']} / "
                f"{odds['initial_draw']} / "
                f"{odds['initial_away']} "
                f"| 최종 "
                f"{odds['final_home']} / "
                f"{odds['final_draw']} / "
                f"{odds['final_away']}"

            )


    return {

        "status":
            "success",

        "odds":
            len(odds_list),

        "home":
            match["home_team"],

        "away":
            match["away_team"],

        "result":
            match["result"]

    }


# =========================================================
# 범위 수집
# =========================================================

def build_database_progress(

    start_id,
    end_id,

    progress_callback=None,

    log_callback=None,

    delay=0.5

):

    database.init_database()


    start_id = int(
        start_id
    )

    end_id = int(
        end_id
    )


    if end_id < start_id:

        raise ValueError(
            "마지막 ID가 시작 ID보다 작습니다."
        )


    total = (
        end_id -
        start_id +
        1
    )


    success = 0
    failed = 0
    exists = 0
    odds_total = 0


    for index, schedule_id in enumerate(

        range(
            start_id,
            end_id + 1
        ),

        start=1

    ):

        try:

            result = collect_one(

                schedule_id,

                log_callback=
                    log_callback

            )


            status = result.get(
                "status",
                "skip"
            )


            if status == "success":

                success += 1

                odds_total += int(
                    result.get(
                        "odds",
                        0
                    )
                )


            elif status == "exists":

                exists += 1


            else:

                failed += 1


        except Exception as e:

            failed += 1

            if log_callback:

                log_callback(
                    f"[오류] {schedule_id}: {e}"
                )


        if progress_callback:

            progress_callback(
                index / total
            )


        if delay:

            time.sleep(
                float(delay)
            )


    return {

        "success":
            success,

        "failed":
            failed,

        "exists":
            exists,

        "odds":
            odds_total,

        "total":
            total

    }


# =========================================================
# 자동 수집
# =========================================================

def auto_collect(

    start_id,
    end_id,

    progress_callback=None,

    log_callback=None,

    delay=0.5

):

    return build_database_progress(

        start_id=start_id,

        end_id=end_id,

        progress_callback=
            progress_callback,

        log_callback=
            log_callback,

        delay=delay

    )


# =========================================================
# 단일 경기 테스트
# =========================================================

if __name__ == "__main__":

    database.init_database()


    print()
    print(
        "================================"
    )
    print(
        "Scoreman 단일 경기 테스트"
    )
    print(
        "================================"
    )


    schedule_id = input(
        "경기 ID: "
    ).strip()


    if not schedule_id:

        print(
            "경기 ID가 없습니다."
        )

        raise SystemExit


    result = collect_one(

        schedule_id,

        log_callback=print

    )


    print()
    print(
        "================================"
    )
    print(
        "결과"
    )
    print(
        result
    )
    print(
        "================================"
        )
