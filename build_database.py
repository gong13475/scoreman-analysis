import time
import re
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
# 세션
# =========================================================

session = requests.Session()

session.headers.update(
    HEADERS
)


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
            timeout=15
        )

        if response.status_code != 200:

            return None

        if len(response.text) < 500:

            return None

        return response.text

    except Exception:

        return None


# =========================================================
# 경기정보 파싱
# =========================================================

def parse_match_info(
    html,
    schedule_id
):

    home_team = ""

    away_team = ""

    home_score = None

    away_score = None

    match_date = ""


    # -----------------------------------------------------
    # 홈팀
    # -----------------------------------------------------

    patterns = [

        r'"homeTeamName"\s*:\s*"([^"]+)"',

        r'"home_team"\s*:\s*"([^"]+)"',

        r'"homeTeam"\s*:\s*"([^"]+)"',

        r'"HomeTeam"\s*:\s*"([^"]+)"'

    ]


    for pattern in patterns:

        m = re.search(
            pattern,
            html,
            re.I
        )

        if m:

            home_team = m.group(1).strip()

            break


    # -----------------------------------------------------
    # 원정팀
    # -----------------------------------------------------

    patterns = [

        r'"awayTeamName"\s*:\s*"([^"]+)"',

        r'"away_team"\s*:\s*"([^"]+)"',

        r'"awayTeam"\s*:\s*"([^"]+)"',

        r'"AwayTeam"\s*:\s*"([^"]+)"'

    ]


    for pattern in patterns:

        m = re.search(
            pattern,
            html,
            re.I
        )

        if m:

            away_team = m.group(1).strip()

            break


    # -----------------------------------------------------
    # 스코어
    # -----------------------------------------------------

    patterns = [

        r'"homeScore"\s*:\s*(\d+).*?'
        r'"awayScore"\s*:\s*(\d+)',

        r'"home_score"\s*:\s*(\d+).*?'
        r'"away_score"\s*:\s*(\d+)',

        r'"hscore"\s*:\s*(\d+).*?'
        r'"ascore"\s*:\s*(\d+)'

    ]


    for pattern in patterns:

        m = re.search(
            pattern,
            html,
            re.I | re.S
        )

        if m:

            home_score = to_int(
                m.group(1)
            )

            away_score = to_int(
                m.group(2)
            )

            break


    # -----------------------------------------------------
    # HTML 스코어 보완
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

        r'"date"\s*:\s*"([^"]+)"'

    ]


    for pattern in date_patterns:

        m = re.search(
            pattern,
            html,
            re.I
        )

        if m:

            match_date = m.group(1).strip()

            break


    # -----------------------------------------------------
    # 결과
    # -----------------------------------------------------

    result = calculate_result(
        home_score,
        away_score
    )


    # -----------------------------------------------------
    # 최소 경기정보 확인
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

def get_odds(
    schedule_id
):

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
            timeout=15
        )

        if response.status_code != 200:

            return []


        data = response.json()


    except Exception:

        return []


    if not isinstance(
        data,
        dict
    ):

        return []


    if data.get(
        "ErrCode"
    ) != 0:

        return []


    data_block = data.get(
        "Data",
        {}
    )


    mixodds = data_block.get(
        "mixodds",
        []
    )


    if not isinstance(
        mixodds,
        list
    ):

        return []


    result = []


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


        initial = euro.get(
            "f",
            {}
        )


        final = euro.get(
            "l",
            {}
        )


        initial_home = to_float(
            initial.get("u")
        )

        initial_draw = to_float(
            initial.get("g")
        )

        initial_away = to_float(
            initial.get("d")
        )


        final_home = to_float(
            final.get("u")
        )

        final_draw = to_float(
            final.get("g")
        )

        final_away = to_float(
            final.get("d")
        )


        if not (
            initial_home
            and initial_draw
            and initial_away
        ):

            continue


        result.append({

            "company_id":
                company_id,

            "company_name":
                company_name,

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
# 기존 경기 확인
# =========================================================

def match_exists(
    schedule_id
):

    try:

        row = database.get_match(
            schedule_id
        )

        return row is not None

    except Exception:

        return False


# =========================================================
# ID 하나 수집
# =========================================================

def collect_one(
    schedule_id
):

    # -----------------------------------------------------
    # 기존 DB에 있으면 건너뜀
    # -----------------------------------------------------

    if match_exists(
        schedule_id
    ):

        return {

            "status":
                "exists",

            "odds":
                0

        }


    # -----------------------------------------------------
    # 경기 페이지
    # -----------------------------------------------------

    html = get_match_page(
        schedule_id
    )


    if not html:

        return {

            "status":
                "skip",

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

        return {

            "status":
                "skip",

            "odds":
                0

        }


    # -----------------------------------------------------
    # 결과가 없는 진행중/예정 경기는 제외
    # -----------------------------------------------------

    if match["result"] not in [

        "승",
        "무",
        "패"

    ]:

        return {

            "status":
                "skip",

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

        return {

            "status":
                "skip",

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


    return {

        "status":
            "success",

        "odds":
            len(odds_list)

    }


# =========================================================
# 진행률 수집
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
            "end_id가 start_id보다 작습니다."
        )


    total = (
        end_id
        -
        start_id
        +
        1
    )


    success = 0

    failed = 0

    odds_total = 0

    exists = 0


    for index, schedule_id in enumerate(

        range(
            start_id,
            end_id + 1
        ),

        start=1

    ):


        try:

            result = collect_one(
                schedule_id
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
                    or 0
                )


                if log_callback:

                    log_callback(
                        f"[성공] "
                        f"ID {schedule_id} "
                        f"/ 업체 "
                        f"{result.get('odds', 0)}"
                    )


            elif status == "exists":

                exists += 1

            else:

                failed += 1


        except Exception as e:

            failed += 1

            if log_callback:

                log_callback(
                    f"[오류] ID {schedule_id}: {e}"
                )


        # -------------------------------------------------
        # 진행률
        # -------------------------------------------------

        if progress_callback:

            progress_callback(
                index / total
            )


        # -------------------------------------------------
        # 서버 부하 방지
        # -------------------------------------------------

        if delay:

            time.sleep(
                delay
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
# 간단 실행
# =========================================================

if __name__ == "__main__":

    database.init_database()


    print(
        "스코어맨 과거 DB 수집"
    )


    start_id = int(
        input(
            "시작 ID: "
        )
    )


    end_id = int(
        input(
            "마지막 ID: "
        )
    )


    result = build_database_progress(

        start_id,

        end_id,

        log_callback=
            print

    )


    print(
        "\n=========================="
    )

    print(
        "수집 완료"
    )

    print(
        "성공:",
        result["success"]
    )

    print(
        "실패:",
        result["failed"]
    )

    print(
        "기존:",
        result["exists"]
    )

    print(
        "배당 업체:",
        result["odds"]
    )

    print(
        "=========================="
            )
