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
# 경기 페이지
# =========================================================

def get_match_page(schedule_id):

    url = (
        f"{BASE_URL}/match/data-{schedule_id}"
    )

    try:

        response = requests.get(
            url,
            headers=HEADERS,
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
# 경기 정보 파싱
# =========================================================

def parse_match_info(
    html,
    schedule_id
):

    if not html:

        return None


    home_team = ""

    away_team = ""

    home_score = None

    away_score = None

    match_date = ""


    # =====================================================
    # 홈팀
    # =====================================================

    home_patterns = [

        r'"homeTeamName"\s*:\s*"([^"]+)"',

        r'"home_team"\s*:\s*"([^"]+)"',

        r'"homeTeam"\s*:\s*"([^"]+)"',

        r'"HomeTeam"\s*:\s*"([^"]+)"'

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


    # =====================================================
    # 원정팀
    # =====================================================

    away_patterns = [

        r'"awayTeamName"\s*:\s*"([^"]+)"',

        r'"away_team"\s*:\s*"([^"]+)"',

        r'"awayTeam"\s*:\s*"([^"]+)"',

        r'"AwayTeam"\s*:\s*"([^"]+)"'

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


    # =====================================================
    # 홈팀 / 원정팀 보완
    # =====================================================

    if not home_team or not away_team:

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

            title_match_2 = re.search(
                r"(.+?)\s+vs\.?\s+(.+?)(?:\s+-|\s+\||$)",
                title,
                re.I
            )

            if title_match_2:

                if not home_team:

                    home_team = (
                        title_match_2.group(1)
                        .strip()
                    )

                if not away_team:

                    away_team = (
                        title_match_2.group(2)
                        .strip()
                    )


    # =====================================================
    # 스코어
    # =====================================================

    score_patterns = [

        r'"homeScore"\s*:\s*(\d+).*?'
        r'"awayScore"\s*:\s*(\d+)',

        r'"home_score"\s*:\s*(\d+).*?'
        r'"away_score"\s*:\s*(\d+)',

        r'"hscore"\s*:\s*(\d+).*?'
        r'"ascore"\s*:\s*(\d+)'

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


    # =====================================================
    # 일반 HTML 스코어
    # =====================================================

    if home_score is None:

        score_matches = re.findall(
            r">\s*(\d{1,2})\s*-\s*(\d{1,2})\s*<",
            html
        )

        if score_matches:

            home_score = to_int(
                score_matches[-1][0]
            )

            away_score = to_int(
                score_matches[-1][1]
            )


    # =====================================================
    # 날짜
    # =====================================================

    date_patterns = [

        r'"matchTime"\s*:\s*"([^"]+)"',

        r'"matchDate"\s*:\s*"([^"]+)"',

        r'"startTime"\s*:\s*"([^"]+)"',

        r'"date"\s*:\s*"([^"]+)"'

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


    # =====================================================
    # 경기 자체가 없으면
    # =====================================================

    if not home_team or not away_team:

        return None


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
            result

    }


# =========================================================
# 스코어맨 배당 API
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


            # =================================================
            # 정상적인 1X2 배당
            # =================================================

            if initial_home is None:
                continue

            if initial_draw is None:
                continue

            if initial_away is None:
                continue


            if initial_home <= 1:
                continue

            if initial_draw <= 1:
                continue

            if initial_away <= 1:
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


        except Exception:

            continue


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


    saved = 0


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

        saved += 1


    return saved


# =========================================================
# ID 범위 자동 수집
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

            "odds": 0

        }


    total = (
        end_id
        -
        start_id
        +
        1
    )


    success = 0

    failed = 0

    odds_count = 0


    for index, schedule_id in enumerate(

        range(
            start_id,
            end_id + 1
        ),

        start=1

    ):


        # =================================================
        # 진행률
        # =================================================

        if progress_callback:

            progress_callback(
                index / total
            )


        # =================================================
        # 경기 페이지
        # =================================================

        html = get_match_page(
            schedule_id
        )


        if not html:

            failed += 1

            if log_callback:

                log_callback(
                    f"{schedule_id} : 경기 없음"
                )

            time.sleep(
                delay
            )

            continue


        # =================================================
        # 경기 정보
        # =================================================

        match = parse_match_info(

            html,

            schedule_id

        )


        if match is None:

            failed += 1

            if log_callback:

                log_callback(
                    f"{schedule_id} : "
                    f"경기 정보 없음"
                )

            time.sleep(
                delay
            )

            continue


        # =================================================
        # 완료 경기만 저장
        # =================================================

        if match["result"] not in [

            "승",

            "무",

            "패"

        ]:

            failed += 1

            if log_callback:

                log_callback(

                    f"{schedule_id} : "

                    f"미완료 경기 → 건너뜀"

                )

            time.sleep(
                delay
            )

            continue


        # =================================================
        # 배당
        # =================================================

        odds_list = get_scoreman_odds(

            schedule_id

        )


        if not odds_list:

            failed += 1

            if log_callback:

                log_callback(

                    f"{schedule_id} : "

                    f"1X2 배당 없음"

                )

            time.sleep(
                delay
            )

            continue


        # =================================================
        # DB 저장
        # =================================================

        try:

            saved = save_match_data(

                match,

                odds_list

            )


            success += 1

            odds_count += saved


            if log_callback:

                log_callback(

                    f"{schedule_id} | "

                    f"{match['home_team']} "
                    f"vs "
                    f"{match['away_team']} | "

                    f"{match['result']} | "

                    f"배당 {saved}개"

                )


        except Exception as e:

            failed += 1

            if log_callback:

                log_callback(

                    f"{schedule_id} : "

                    f"DB 오류 - {e}"

                )


        time.sleep(
            delay
        )


    if progress_callback:

        progress_callback(
            1.0
        )


    return {

        "success":
            success,

        "failed":
            failed,

        "odds":
            odds_count

    }


# =========================================================
# 자동 수집
# =========================================================

def auto_collect_database(

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

        delay=
            delay

    )


# =========================================================
# 테스트
# =========================================================

if __name__ == "__main__":

    database.init_database()


    result = build_database_progress(

        2716480,

        2716580,

        delay=0.5

    )


    print(
        result
        )
