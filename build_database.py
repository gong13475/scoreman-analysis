import requests
import re
import time
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

        if not value:
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

def calculate_result(
    home_score,
    away_score
):

    if (
        home_score is None
        or
        away_score is None
    ):

        return ""


    if home_score > away_score:

        return "승"


    if home_score < away_score:

        return "패"


    return "무"


# =========================================================
# 경기 페이지 요청
# =========================================================

def get_match_page(
    schedule_id
):

    url = (
        f"{BASE_URL}/match/data-"
        f"{schedule_id}"
    )


    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        if response.status_code != 200:

            return None


        return response


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
    # 팀명
    # -----------------------------------------------------

    home_patterns = [

        r'"homeTeamName"\s*:\s*"([^"]+)"',

        r'"home_team"\s*:\s*"([^"]+)"',

        r'"homeTeam"\s*:\s*"([^"]+)"',

        r'"homeName"\s*:\s*"([^"]+)"'

    ]


    away_patterns = [

        r'"awayTeamName"\s*:\s*"([^"]+)"',

        r'"away_team"\s*:\s*"([^"]+)"',

        r'"awayTeam"\s*:\s*"([^"]+)"',

        r'"awayName"\s*:\s*"([^"]+)"'

    ]


    for pattern in home_patterns:

        match = re.search(
            pattern,
            html,
            re.I
        )

        if match:

            home_team = (
                match.group(1)
                .strip()
            )

            break


    for pattern in away_patterns:

        match = re.search(
            pattern,
            html,
            re.I
        )

        if match:

            away_team = (
                match.group(1)
                .strip()
            )

            break


    # -----------------------------------------------------
    # 제목에서 팀명 보완
    # -----------------------------------------------------

    title_match = re.search(
        r"<title>(.*?)</title>",
        html,
        re.I | re.S
    )


    title = ""


    if title_match:

        title = re.sub(
            r"\s+",
            " ",
            title_match.group(1)
        ).strip()


    if not home_team or not away_team:

        patterns = [

            r"(.+?)\s+vs\s+(.+?)\s*(?:-|</title>)",

            r"(.+?)\s+VS\s+(.+?)\s*(?:-|</title>)"

        ]


        for pattern in patterns:

            match = re.search(
                pattern,
                title,
                re.I
            )

            if match:

                if not home_team:

                    home_team = (
                        match.group(1)
                        .strip()
                    )


                if not away_team:

                    away_team = (
                        match.group(2)
                        .strip()
                    )


                break


    # -----------------------------------------------------
    # 스코어
    # -----------------------------------------------------

    score_patterns = [

        (
            r'"homeScore"\s*:\s*'
            r'(\d+).*?'
            r'"awayScore"\s*:\s*'
            r'(\d+)'
        ),

        (
            r'"home_score"\s*:\s*'
            r'(\d+).*?'
            r'"away_score"\s*:\s*'
            r'(\d+)'
        ),

        (
            r'"hscore"\s*:\s*'
            r'(\d+).*?'
            r'"ascore"\s*:\s*'
            r'(\d+)'
        ),

        (
            r'"homeGoals"\s*:\s*'
            r'(\d+).*?'
            r'"awayGoals"\s*:\s*'
            r'(\d+)'
        )

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
    # HTML 스코어
    # -----------------------------------------------------

    if home_score is None:

        scores = re.findall(

            r">\s*"
            r"(\d{1,2})"
            r"\s*-\s*"
            r"(\d{1,2})"
            r"\s*<",

            html
        )


        if scores:

            home_score = to_int(
                scores[-1][0]
            )

            away_score = to_int(
                scores[-1][1]
            )


    # -----------------------------------------------------
    # 날짜
    # -----------------------------------------------------

    date_patterns = [

        r'"matchTime"\s*:\s*"([^"]+)"',

        r'"matchDate"\s*:\s*"([^"]+)"',

        r'"startTime"\s*:\s*"([^"]+)"',

        r'"gameTime"\s*:\s*"([^"]+)"'

    ]


    for pattern in date_patterns:

        match = re.search(
            pattern,
            html,
            re.I
        )

        if match:

            match_date = (
                match.group(1)
                .strip()
            )

            break


    result = calculate_result(
        home_score,
        away_score
    )


    return {

        "schedule_id":
            str(schedule_id),

        "title":
            title,

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

        "match_date":
            match_date

    }


# =========================================================
# 배당 API
# =========================================================

def get_scoreman_odds(
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

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )


        if response.status_code != 200:

            return None


        return response


    except Exception:

        return None


# =========================================================
# 배당 파싱
# =========================================================

def parse_odds_json(
    data
):

    companies = []


    if not isinstance(
        data,
        dict
    ):

        return companies


    if data.get(
        "ErrCode"
    ) not in (
        0,
        "0",
        None
    ):

        return companies


    data_block = data.get(
        "Data",
        {}
    )


    if not isinstance(
        data_block,
        dict
    ):

        return companies


    mixodds = data_block.get(
        "mixodds",
        []
    )


    if not isinstance(
        mixodds,
        list
    ):

        return companies


    for item in mixodds:

        if not isinstance(
            item,
            dict
        ):

            continue


        try:

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


            # -----------------------------------------
            # 실제 1X2 배당이 하나라도 있는 경우만
            # -----------------------------------------

            values = [

                row["initial_home"],

                row["initial_draw"],

                row["initial_away"],

                row["final_home"],

                row["final_draw"],

                row["final_away"]

            ]


            if not any(
                value is not None
                and value > 1
                for value in values
            ):

                continue


            companies.append(
                row
            )


        except Exception:

            continue


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
# 한 경기 수집
# =========================================================

def collect_one_match(
    schedule_id
):

    result = {

        "success":
            False,

        "schedule_id":
            str(schedule_id),

        "reason":
            "",

        "companies":
            0

    }


    # -----------------------------------------------------
    # 경기 페이지
    # -----------------------------------------------------

    response = get_match_page(
        schedule_id
    )


    if response is None:

        result["reason"] = (
            "경기 페이지 요청 실패"
        )

        return result


    match = parse_match_info(
        response.text,
        schedule_id
    )


    # -----------------------------------------------------
    # 완료된 경기인지 확인
    # -----------------------------------------------------

    if not match["result"]:

        result["reason"] = (
            "최종 경기결과를 확인하지 못함"
        )

        return result


    if not match["home_team"]:

        result["reason"] = (
            "홈팀 확인 실패"
        )

        return result


    if not match["away_team"]:

        result["reason"] = (
            "원정팀 확인 실패"
        )

        return result


    # -----------------------------------------------------
    # 배당
    # -----------------------------------------------------

    odds_response = get_scoreman_odds(
        schedule_id
    )


    if odds_response is None:

        result["reason"] = (
            "배당 API 요청 실패"
        )

        return result


    try:

        odds_json = (
            odds_response.json()
        )

    except Exception:

        result["reason"] = (
            "배당 JSON 변환 실패"
        )

        return result


    odds_list = parse_odds_json(
        odds_json
    )


    if not odds_list:

        result["reason"] = (
            "1X2 배당 없음"
        )

        return result


    # -----------------------------------------------------
    # DB 저장
    # -----------------------------------------------------

    try:

        save_match_data(
            match,
            odds_list
        )

    except Exception as e:

        result["reason"] = (
            f"DB 저장 실패: {e}"
        )

        return result


    result["success"] = True

    result["companies"] = len(
        odds_list
    )


    return result


# =========================================================
# 경기 ID 범위 수집
# =========================================================

def build_database(
    start_id,
    end_id,
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

        start_id, end_id = (
            end_id,
            start_id
        )


    total = (
        end_id -
        start_id +
        1
    )


    success_count = 0

    fail_count = 0

    odds_count = 0


    print(
        "================================"
    )

    print(
        "스코어맨 과거 DB 수집 시작"
    )

    print(
        f"ID 범위: {start_id} ~ {end_id}"
    )

    print(
        f"총 ID: {total}"
    )

    print(
        "================================"
    )


    for index, schedule_id in enumerate(

        range(
            start_id,
            end_id + 1
        ),

        start=1

    ):

        result = collect_one_match(
            schedule_id
        )


        if result["success"]:

            success_count += 1

            odds_count += (
                result["companies"]
            )


            print(

                f"[{index}/{total}] "
                f"성공 "
                f"ID={schedule_id} "
                f"업체={result['companies']}"

            )


        else:

            fail_count += 1


            print(

                f"[{index}/{total}] "
                f"실패 "
                f"ID={schedule_id} "
                f"{result['reason']}"

            )


        time.sleep(
            delay
        )


    print(
        "================================"
    )

    print(
        "수집 완료"
    )

    print(
        f"성공 경기: {success_count}"
    )

    print(
        f"실패 경기: {fail_count}"
    )

    print(
        f"저장 배당업체: {odds_count}"
    )

    print(
        f"DB 경기 수: "
        f"{database.get_match_count()}"
    )

    print(
        f"DB 배당 수: "
        f"{database.get_odds_count()}"
    )

    print(
        "================================"
    )


    return {

        "success":
            success_count,

        "failed":
            fail_count,

        "odds":
            odds_count

    }


# =========================================================
# Streamlit용 함수
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

        start_id, end_id = (
            end_id,
            start_id
        )


    total = (
        end_id -
        start_id +
        1
    )


    success_count = 0

    fail_count = 0

    odds_count = 0


    for index, schedule_id in enumerate(

        range(
            start_id,
            end_id + 1
        ),

        start=1

    ):

        result = collect_one_match(
            schedule_id
        )


        if result["success"]:

            success_count += 1

            odds_count += (
                result["companies"]
            )

            message = (

                f"✅ ID {schedule_id} "
                f"저장 완료 / "
                f"배당업체 "
                f"{result['companies']}개"

            )

        else:

            fail_count += 1

            message = (

                f"❌ ID {schedule_id} "
                f"{result['reason']}"

            )


        if log_callback:

            log_callback(
                message
            )


        if progress_callback:

            progress_callback(
                index / total
            )


        time.sleep(
            delay
        )


    return {

        "success":
            success_count,

        "failed":
            fail_count,

        "odds":
            odds_count

    }


# =========================================================
# 직접 실행
# =========================================================

if __name__ == "__main__":

    print()
    print(
        "스코어맨 과거 DB 수집기"
    )
    print()

    start = input(
        "시작 경기 ID: "
    ).strip()

    end = input(
        "마지막 경기 ID: "
    ).strip()


    if not start or not end:

        print(
            "경기 ID를 입력하세요."
        )

        raise SystemExit


    build_database(
        start,
        end
    )
