import requests
import re
import time
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

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


# =========================================================
# 숫자 변환
# =========================================================

def to_float(value):

    try:

        if value is None:
            return None

        value = str(value).strip()

        if value == "":
            return None

        return float(value)

    except Exception:

        return None


def to_int(value):

    try:

        if value is None:
            return None

        return int(value)

    except Exception:

        return None


# =========================================================
# 경기 결과
# =========================================================

def calculate_result(home_score, away_score):

    if home_score is None:
        return ""

    if away_score is None:
        return ""

    if home_score > away_score:
        return "승"

    if home_score < away_score:
        return "패"

    return "무"


# =========================================================
# HTTP 요청
# =========================================================

def get(url, timeout=15):

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=timeout
        )

        if response.status_code != 200:
            return None

        return response

    except Exception:

        return None


# =========================================================
# 경기 상세 페이지
# =========================================================

def get_match_page(schedule_id):

    url = (
        f"{BASE_URL}/match/data-{schedule_id}"
    )

    return get(url)


# =========================================================
# 경기 정보 파싱
# =========================================================

def parse_match_info(html, schedule_id):

    home_team = ""
    away_team = ""

    home_score = None
    away_score = None

    match_date = ""

    # -----------------------------------------------------
    # 홈팀
    # -----------------------------------------------------

    home_patterns = [

        r'"homeTeamName"\s*:\s*"([^"]+)"',

        r'"home_team"\s*:\s*"([^"]+)"',

        r'"homeTeam"\s*:\s*"([^"]+)"',

        r'"HomeTeamName"\s*:\s*"([^"]+)"',

        r'"HomeTeam"\s*:\s*"([^"]+)"'

    ]

    for pattern in home_patterns:

        match = re.search(
            pattern,
            html,
            re.I
        )

        if match:

            home_team = match.group(1).strip()

            break


    # -----------------------------------------------------
    # 원정팀
    # -----------------------------------------------------

    away_patterns = [

        r'"awayTeamName"\s*:\s*"([^"]+)"',

        r'"away_team"\s*:\s*"([^"]+)"',

        r'"awayTeam"\s*:\s*"([^"]+)"',

        r'"AwayTeamName"\s*:\s*"([^"]+)"',

        r'"AwayTeam"\s*:\s*"([^"]+)"'

    ]

    for pattern in away_patterns:

        match = re.search(
            pattern,
            html,
            re.I
        )

        if match:

            away_team = match.group(1).strip()

            break


    # -----------------------------------------------------
    # 스코어
    # -----------------------------------------------------

    score_patterns = [

        r'"homeScore"\s*:\s*(\d+).*?'
        r'"awayScore"\s*:\s*(\d+)',

        r'"home_score"\s*:\s*(\d+).*?'
        r'"away_score"\s*:\s*(\d+)',

        r'"hscore"\s*:\s*(\d+).*?'
        r'"ascore"\s*:\s*(\d+)',

        r'"HomeScore"\s*:\s*(\d+).*?'
        r'"AwayScore"\s*:\s*(\d+)'

    ]

    for pattern in score_patterns:

        match = re.search(
            pattern,
            html,
            re.I | re.S
        )

        if match:

            home_score = to_int(
                match.group(1)
            )

            away_score = to_int(
                match.group(2)
            )

            break


    # -----------------------------------------------------
    # HTML 일반 스코어
    # -----------------------------------------------------

    if home_score is None:

        scores = re.findall(
            r">\s*(\d{1,2})\s*-\s*(\d{1,2})\s*<",
            html
        )

        if scores:

            hs, aws = scores[-1]

            home_score = to_int(hs)

            away_score = to_int(aws)


    # -----------------------------------------------------
    # 날짜
    # -----------------------------------------------------

    date_patterns = [

        r'"matchTime"\s*:\s*"([^"]+)"',

        r'"matchDate"\s*:\s*"([^"]+)"',

        r'"startTime"\s*:\s*"([^"]+)"',

        r'"MatchTime"\s*:\s*"([^"]+)"',

        r'"MatchDate"\s*:\s*"([^"]+)"'

    ]

    for pattern in date_patterns:

        match = re.search(
            pattern,
            html,
            re.I
        )

        if match:

            match_date = match.group(1).strip()

            break


    # -----------------------------------------------------
    # 제목
    # -----------------------------------------------------

    title = ""

    title_match = re.search(
        r"<title>(.*?)</title>",
        html,
        re.I | re.S
    )

    if title_match:

        title = re.sub(
            r"\s+",
            " ",
            title_match.group(1)
        ).strip()


    # -----------------------------------------------------
    # 제목으로 팀명 보완
    # -----------------------------------------------------

    if not home_team or not away_team:

        title_team = re.search(
            r"(.+?)\s+vs\s+(.+?)(?:\s+\||$)",
            title,
            re.I
        )

        if title_team:

            if not home_team:

                home_team = (
                    title_team.group(1)
                    .strip()
                )

            if not away_team:

                away_team = (
                    title_team.group(2)
                    .strip()
                )


    result = calculate_result(
        home_score,
        away_score
    )


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
            result,

        "title":
            title

    }


# =========================================================
# 배당 API
# =========================================================

def get_scoreman_odds(schedule_id):

    url = (
        f"{BASE_URL}/ajax/soccerajax"
        f"?type=14"
        f"&t=1"
        f"&id={schedule_id}"
        f"&h=0"
    )

    response = get(url)

    if response is None:

        return []

    try:

        data = response.json()

    except Exception:

        return []


    if not isinstance(data, dict):

        return []


    if data.get("ErrCode") != 0:

        return []


    data_block = data.get(
        "Data",
        {}
    )


    if not isinstance(
        data_block,
        dict
    ):

        return []


    mixodds = data_block.get(
        "mixodds",
        []
    )


    if not isinstance(
        mixodds,
        list
    ):

        return []


    companies = []


    for item in mixodds:

        if not isinstance(
            item,
            dict
        ):

            continue


        company_id = item.get(
            "cid"
        )


        company_name = item.get(
            "cn",
            ""
        )


        euro = item.get(
            "euro",
            {}
        )


        if not isinstance(
            euro,
            dict
        ):

            continue


        initial = euro.get(
            "f",
            {}
        )


        final = euro.get(
            "l",
            {}
        )


        if not isinstance(
            initial,
            dict
        ):

            initial = {}


        if not isinstance(
            final,
            dict
        ):

            final = {}


        row = {

            "company_id":
                company_id,

            "company_name":
                company_name,

            "initial_home":
                to_float(
                    initial.get("u")
                ),

            "initial_draw":
                to_float(
                    initial.get("g")
                ),

            "initial_away":
                to_float(
                    initial.get("d")
                ),

            "final_home":
                to_float(
                    final.get("u")
                ),

            "final_draw":
                to_float(
                    final.get("g")
                ),

            "final_away":
                to_float(
                    final.get("d")
                )

        }


        # -------------------------------------------------
        # 최소 1개라도 배당이 있으면 저장
        # -------------------------------------------------

        valid = [

            row["initial_home"],

            row["initial_draw"],

            row["initial_away"]

        ]


        if any(
            x is not None and x > 1
            for x in valid
        ):

            companies.append(row)


    return companies


# =========================================================
# DB 저장
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

        source="Scoreman"

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
# 기존 DB ID 확인
# =========================================================

def get_existing_ids():

    conn = database.get_connection()

    cursor = conn.cursor()

    try:

        cursor.execute(
            "SELECT schedule_id FROM matches"
        )

        rows = cursor.fetchall()

        return {
            str(row[0])
            for row in rows
        }

    finally:

        conn.close()


# =========================================================
# ID 자동 탐색
#
# Scoreman 경기 ID는 연속 숫자이지만
# 모든 ID가 축구 경기인 것은 아니므로
# 상세 페이지를 실제 확인한다.
# =========================================================

def find_scoreman_ids(
    start_id,
    end_id,
    progress_callback=None,
    log_callback=None,
    delay=0.3
):

    found = []

    total = (
        end_id -
        start_id +
        1
    )


    if total <= 0:

        return found


    for index, schedule_id in enumerate(
        range(start_id, end_id + 1),
        start=1
    ):

        response = get_match_page(
            schedule_id
        )


        if response is not None:

            text = response.text


            # -------------------------------------------------
            # 실제 경기 페이지인지 확인
            # -------------------------------------------------

            has_match_data = (

                "homeTeam"
                in text

                or

                "home_team"
                in text

                or

                "homeTeamName"
                in text

                or

                "HomeTeam"
                in text

            )


            if has_match_data:

                match = parse_match_info(
                    text,
                    schedule_id
                )


                # -------------------------------------------------
                # 완료 경기만
                # -------------------------------------------------

                if (

                    match["home_team"]

                    and

                    match["away_team"]

                    and

                    match["result"]

                ):

                    found.append(match)


                    if log_callback:

                        log_callback(
                            f"발견: "
                            f'{schedule_id} | '
                            f'{match["home_team"]} '
                            f'vs '
                            f'{match["away_team"]} | '
                            f'{match["result"]}'
                        )


        if progress_callback:

            progress_callback(
                index / total
            )


        if delay > 0:

            time.sleep(delay)


    return found


# =========================================================
# 날짜 필터
# =========================================================

def date_in_range(
    match_date,
    start_date,
    end_date
):

    if not match_date:

        return True


    # -----------------------------------------------------
    # 날짜 문자열에서 YYYY-MM-DD 추출
    # -----------------------------------------------------

    match = re.search(
        r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})",
        match_date
    )


    if not match:

        return True


    try:

        current = datetime(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3))
        ).date()


        return (
            start_date
            <=
            current
            <=
            end_date
        )

    except Exception:

        return True


# =========================================================
# 자동 DB 구축
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

        return {

            "success": 0,

            "failed": 0,

            "odds": 0,

            "found": 0

        }


    existing_ids = (
        get_existing_ids()
    )


    success = 0

    failed = 0

    odds_count = 0

    found = 0


    total = (
        end_id -
        start_id +
        1
    )


    for index, schedule_id in enumerate(

        range(
            start_id,
            end_id + 1
        ),

        start=1

    ):

        sid = str(
            schedule_id
        )


        # -----------------------------------------------------
        # 이미 존재
        # -----------------------------------------------------

        if sid in existing_ids:

            if progress_callback:

                progress_callback(
                    index / total
                )

            continue


        try:

            # -------------------------------------------------
            # 경기 페이지
            # -------------------------------------------------

            response = get_match_page(
                schedule_id
            )


            if response is None:

                failed += 1

                continue


            # -------------------------------------------------
            # 경기 파싱
            # -------------------------------------------------

            match = parse_match_info(

                response.text,

                schedule_id

            )


            # -------------------------------------------------
            # 경기 아닌 ID
            # -------------------------------------------------

            if not match["home_team"]:

                failed += 1

                continue


            if not match["away_team"]:

                failed += 1

                continue


            # -------------------------------------------------
            # 완료 경기만 저장
            # -------------------------------------------------

            if match["result"] not in [

                "승",
                "무",
                "패"

            ]:

                failed += 1

                continue


            found += 1


            # -------------------------------------------------
            # 배당
            # -------------------------------------------------

            odds_list = (
                get_scoreman_odds(
                    schedule_id
                )
            )


            # -------------------------------------------------
            # 저장
            # -------------------------------------------------

            save_match_data(

                match,

                odds_list

            )


            success += 1

            odds_count += len(
                odds_list
            )


            existing_ids.add(
                sid
            )


            if log_callback:

                log_callback(

                    f"저장 완료 | "
                    f"{sid} | "
                    f"{match['home_team']} "
                    f"vs "
                    f"{match['away_team']} | "
                    f"{match['result']} | "
                    f"배당 {len(odds_list)}개"

                )


        except Exception as e:

            failed += 1


            if log_callback:

                log_callback(

                    f"오류 | "
                    f"{sid} | "
                    f"{e}"

                )


        finally:

            if progress_callback:

                progress_callback(
                    index / total
                )


            if delay > 0:

                time.sleep(
                    delay
                )


    return {

        "success":
            success,

        "failed":
            failed,

        "odds":
            odds_count,

        "found":
            found

    }


# =========================================================
# 2020~2026 자동 수집
# =========================================================
#
# 주의:
# Scoreman의 내부 경기 ID는 날짜 ID가 아니므로
# 2020~2026 전체를 직접 날짜로 변환할 수 없다.
#
# 따라서 현재 알려진 ID 범위를 탐색하는 방식으로
# 구현한다.
# =========================================================

def auto_collect_scoreman(

    start_id,

    end_id,

    progress_callback=None,

    log_callback=None,

    delay=0.5

):

    return build_database_progress(

        start_id,

        end_id,

        progress_callback=
            progress_callback,

        log_callback=
            log_callback,

        delay=delay

    )


# =========================================================
# ID 자동 범위 확장
# =========================================================

def scan_id_range(

    center_id,

    radius,

    progress_callback=None,

    log_callback=None,

    delay=0.3

):

    start_id = max(
        1,
        int(center_id) -
        int(radius)
    )


    end_id = (
        int(center_id) +
        int(radius)
    )


    return find_scoreman_ids(

        start_id,

        end_id,

        progress_callback=
            progress_callback,

        log_callback=
            log_callback,

        delay=delay

    )


# =========================================================
# 테스트
# =========================================================

if __name__ == "__main__":

    database.init_database()


    print(
        "================================"
    )

    print(
        "Scoreman DB 수집 테스트"
    )

    print(
        "DB:",
        database.DB_FILE
    )

    print(
        "현재 경기:",
        database.get_match_count()
    )

    print(
        "현재 배당:",
        database.get_odds_count()
    )

    print(
        "================================"
    )


    result = build_database_progress(

        2716480,

        2716580,

        delay=0.5

    )


    print(
        result
        )
