import time
import requests
import re

import database


# =========================================================
# Scoreman 기본 설정
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
# 경기 페이지 요청
# =========================================================

def get_match_page(
    session,
    schedule_id
):

    url = (
        f"{BASE_URL}/match/data-{schedule_id}"
    )

    try:

        response = session.get(
            url,
            timeout=15
        )

        return response

    except Exception:

        return None


# =========================================================
# 경기 정보 파싱
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
    # title
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


    # -----------------------------------------------------
    # 홈팀
    # -----------------------------------------------------

    home_patterns = [

        r'"homeTeamName"\s*:\s*"([^"]+)"',

        r'"home_team"\s*:\s*"([^"]+)"',

        r'"homeTeam"\s*:\s*"([^"]+)"',

        r'"HomeTeamName"\s*:\s*"([^"]+)"'

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


    # -----------------------------------------------------
    # 원정팀
    # -----------------------------------------------------

    away_patterns = [

        r'"awayTeamName"\s*:\s*"([^"]+)"',

        r'"away_team"\s*:\s*"([^"]+)"',

        r'"awayTeam"\s*:\s*"([^"]+)"',

        r'"AwayTeamName"\s*:\s*"([^"]+)"'

    ]


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
    # title에서 팀명 추출
    # -----------------------------------------------------

    if not home_team or not away_team:

        patterns = [

            r"<title>\s*(.*?)\s+vs\s+(.*?)\s*</title>",

            r"<title>\s*(.*?)\s+-\s+(.*?)\s*</title>"

        ]


        for pattern in patterns:

            match = re.search(
                pattern,
                html,
                re.I | re.S
            )

            if match:

                if not home_team:

                    home_team = re.sub(
                        r"\s+",
                        " ",
                        match.group(1)
                    ).strip()


                if not away_team:

                    away_team = re.sub(
                        r"\s+",
                        " ",
                        match.group(2)
                    ).strip()


                break


    # -----------------------------------------------------
    # 스코어
    # -----------------------------------------------------

    score_patterns = [

        r'"homeScore"\s*:\s*(\d+).*?"awayScore"\s*:\s*(\d+)',

        r'"home_score"\s*:\s*(\d+).*?"away_score"\s*:\s*(\d+)',

        r'"hscore"\s*:\s*(\d+).*?"ascore"\s*:\s*(\d+)',

        r'"HomeScore"\s*:\s*(\d+).*?"AwayScore"\s*:\s*(\d+)'

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
    # HTML score
    # -----------------------------------------------------

    if home_score is None:

        score_matches = re.findall(
            r">\s*(\d{1,2})\s*-\s*(\d{1,2})\s*<",
            html
        )


        if score_matches:

            hs, aws = (
                score_matches[-1]
            )

            home_score = to_int(
                hs
            )

            away_score = to_int(
                aws
            )


    # -----------------------------------------------------
    # 날짜
    # -----------------------------------------------------

    date_patterns = [

        r'"matchTime"\s*:\s*"([^"]+)"',

        r'"matchDate"\s*:\s*"([^"]+)"',

        r'"startTime"\s*:\s*"([^"]+)"',

        r'"MatchTime"\s*:\s*"([^"]+)"'

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


    # -----------------------------------------------------
    # 결과
    # -----------------------------------------------------

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

def get_scoreman_odds(
    session,
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

        return response

    except Exception:

        return None


# =========================================================
# 배당 JSON 파싱
# =========================================================

def parse_odds_json(data):

    companies = []


    if not isinstance(
        data,
        dict
    ):

        return companies


    if data.get(
        "ErrCode"
    ) != 0:

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


            # -------------------------------------------------
            # 정상적인 1X2만
            # -------------------------------------------------

            if (

                row["initial_home"] is None
                or
                row["initial_draw"] is None
                or
                row["initial_away"] is None

            ):

                continue


            if (

                row["initial_home"] <= 1
                or
                row["initial_draw"] <= 1
                or
                row["initial_away"] <= 1

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

def save_match_to_database(
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
# 자동 DB 구축
# =========================================================

def build_database_progress(

    start_id,

    end_id,

    progress_callback=None,

    log_callback=None,

    delay=0.7

):

    # -----------------------------------------------------
    # DB 초기화
    # -----------------------------------------------------

    database.init_database()


    # -----------------------------------------------------
    # Session
    # -----------------------------------------------------

    session = requests.Session()

    session.headers.update(
        HEADERS
    )


    # -----------------------------------------------------
    # 통계
    # -----------------------------------------------------

    success = 0

    failed = 0

    skipped = 0

    odds_total = 0


    total = (
        int(end_id)
        -
        int(start_id)
        +
        1
    )


    if total <= 0:

        return {

            "success": 0,
            "failed": 0,
            "skipped": 0,
            "odds": 0,
            "total": 0

        }


    # =====================================================
    # ID 순회
    # =====================================================

    for index, schedule_id in enumerate(

        range(
            int(start_id),
            int(end_id) + 1
        ),

        start=1

    ):

        try:

            # -------------------------------------------------
            # 이미 존재하는 경기
            # -------------------------------------------------

            existing = database.get_match(
                str(schedule_id)
            )


            if existing is not None:

                skipped += 1


                if log_callback:

                    log_callback(
                        f"[{index}/{total}] "
                        f"{schedule_id} "
                        f"이미 DB 존재 → 건너뜀"
                    )


                continue


            # -------------------------------------------------
            # 경기 페이지
            # -------------------------------------------------

            response = get_match_page(
                session,
                schedule_id
            )


            if response is None:

                failed += 1

                if log_callback:

                    log_callback(
                        f"[{index}/{total}] "
                        f"{schedule_id} "
                        f"페이지 요청 실패"
                    )

                continue


            if response.status_code != 200:

                failed += 1

                if log_callback:

                    log_callback(
                        f"[{index}/{total}] "
                        f"{schedule_id} "
                        f"HTTP {response.status_code}"
                    )

                continue


            # -------------------------------------------------
            # 경기 파싱
            # -------------------------------------------------

            match = parse_match_info(

                response.text,

                schedule_id

            )


            # -------------------------------------------------
            # 경기 정보 없는 ID
            # -------------------------------------------------

            if not match["home_team"]:

                skipped += 1

                if log_callback:

                    log_callback(
                        f"[{index}/{total}] "
                        f"{schedule_id} "
                        f"경기 없음"
                    )

                continue


            if not match["away_team"]:

                skipped += 1

                if log_callback:

                    log_callback(
                        f"[{index}/{total}] "
                        f"{schedule_id} "
                        f"원정팀 없음"
                    )

                continue


            # -------------------------------------------------
            # 종료 경기만 저장
            # -------------------------------------------------

            if match["result"] not in [

                "승",
                "무",
                "패"

            ]:

                skipped += 1

                if log_callback:

                    log_callback(
                        f"[{index}/{total}] "
                        f"{schedule_id} "
                        f"미완료 경기"
                    )

                continue


            # -------------------------------------------------
            # 배당 API
            # -------------------------------------------------

            odds_response = (
                get_scoreman_odds(
                    session,
                    schedule_id
                )
            )


            odds_list = []


            if odds_response is not None:

                if odds_response.status_code == 200:

                    try:

                        odds_json = (
                            odds_response.json()
                        )


                        odds_list = (
                            parse_odds_json(
                                odds_json
                            )
                        )


                    except Exception:

                        odds_list = []


            # -------------------------------------------------
            # 배당 없는 경기
            # -------------------------------------------------

            if not odds_list:

                skipped += 1

                if log_callback:

                    log_callback(
                        f"[{index}/{total}] "
                        f"{schedule_id} "
                        f"{match['home_team']} vs "
                        f"{match['away_team']} "
                        f"배당 없음 → 건너뜀"
                    )

                continue


            # -------------------------------------------------
            # DB 저장
            # -------------------------------------------------

            save_match_to_database(

                match,

                odds_list

            )


            success += 1

            odds_total += len(
                odds_list
            )


            if log_callback:

                log_callback(

                    f"[{index}/{total}] "
                    f"✅ {schedule_id} | "
                    f"{match['home_team']} vs "
                    f"{match['away_team']} | "
                    f"{match['result']} | "
                    f"배당 {len(odds_list)}개"

                )


        except Exception as e:

            failed += 1


            if log_callback:

                log_callback(
                    f"[{index}/{total}] "
                    f"❌ {schedule_id} "
                    f"오류: {e}"
                )


        finally:

            # -------------------------------------------------
            # 진행률
            # -------------------------------------------------

            if progress_callback:

                progress_callback(
                    index / total
                )


            # -------------------------------------------------
            # 요청 간격
            # -------------------------------------------------

            time.sleep(
                float(delay)
            )


    # =====================================================
    # 결과
    # =====================================================

    return {

        "success":
            success,

        "failed":
            failed,

        "skipped":
            skipped,

        "odds":
            odds_total,

        "total":
            total

    }


# =========================================================
# 단독 실행 테스트
# =========================================================

if __name__ == "__main__":

    database.init_database()

    print(
        "Scoreman DB 구축 모듈 정상"
    )

    print(
        "DB:",
        database.DB_FILE
    )
