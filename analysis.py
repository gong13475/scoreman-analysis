import database


# =========================================================
# 업체 목록
# =========================================================

def get_company_list():

    return database.get_company_names()


# =========================================================
# 배당 → 확률
# =========================================================

def odds_to_probability(
    home,
    draw,
    away
):

    try:

        home = float(home)
        draw = float(draw)
        away = float(away)

        if (
            home <= 0
            or draw <= 0
            or away <= 0
        ):

            return None

        h = 1 / home
        d = 1 / draw
        a = 1 / away

        total = (
            h + d + a
        )

        if total <= 0:
            return None

        return {

            "home":
                h / total * 100,

            "draw":
                d / total * 100,

            "away":
                a / total * 100
        }

    except Exception:

        return None


# =========================================================
# 입력 배당 평균
# =========================================================

def average_input_probability(
    odds_input,
    companies
):

    values = []

    for company in companies:

        data = odds_input.get(
            company
        )

        if not data:
            continue

        probability = odds_to_probability(

            data.get("home"),
            data.get("draw"),
            data.get("away")
        )

        if probability:

            values.append(
                probability
            )

    if not values:
        return None

    return {

        "home":
            sum(
                x["home"]
                for x in values
            ) / len(values),

        "draw":
            sum(
                x["draw"]
                for x in values
            ) / len(values),

        "away":
            sum(
                x["away"]
                for x in values
            ) / len(values)
    }


# =========================================================
# 저장 배당과 입력값 비교
# =========================================================

def _matches_odds(
    row,
    target,
    tolerance=0.005
):

    try:

        rh = float(
            row["home_odds"]
        )

        rd = float(
            row["draw_odds"]
        )

        ra = float(
            row["away_odds"]
        )

        th = float(
            target["home"]
        )

        td = float(
            target["draw"]
        )

        ta = float(
            target["away"]
        )

        return (

            abs(rh - th) <= tolerance

            and

            abs(rd - td) <= tolerance

            and

            abs(ra - ta) <= tolerance
        )

    except Exception:

        return False


# =========================================================
# 검색
# =========================================================

def run_search(
    companies,
    odds_input
):

    if not companies:

        return {

            "success": False,

            "message":
                "분석 업체를 선택하세요.",

            "results": [],

            "statistics": None
        }

    all_matches = database.get_all_matches()

    if not all_matches:

        return {

            "success": False,

            "message":
                "저장된 경기가 없습니다.",

            "results": [],

            "statistics": None
        }

    results = []

    for match in all_matches:

        schedule_id = str(
            match["schedule_id"]
        )

        odds_rows = database.get_odds_by_match(
            schedule_id
        )

        if not odds_rows:
            continue

        matched_companies = []

        matched_odds = []

        for company in companies:

            target = odds_input.get(
                company
            )

            if not target:
                continue

            for row in odds_rows:

                if (
                    str(
                        row["bookmaker"]
                    ).strip().lower()
                    !=
                    str(
                        company
                    ).strip().lower()
                ):

                    continue

                if _matches_odds(
                    row,
                    target
                ):

                    matched_companies.append(
                        company
                    )

                    matched_odds.append(
                        row
                    )

                    break

        if not matched_companies:
            continue

        results.append({

            "경기ID":
                match["schedule_id"],

            "경기일":
                match["match_date"],

            "홈팀":
                match["home_team"],

            "원정팀":
                match["away_team"],

            "홈점수":
                match["home_score"],

            "원정점수":
                match["away_score"],

            "실제결과":
                match["result"],

            "매칭업체":
                ", ".join(
                    matched_companies
                )
        })

    statistics = calculate_statistics(
        results,
        odds_input,
        companies
    )

    return {

        "success": True,

        "message":
            "",

        "results":
            results,

        "statistics":
            statistics
    }


# =========================================================
# 통계
# =========================================================

def calculate_statistics(
    results,
    odds_input,
    companies
):

    if not results:

        return None

    total = len(
        results
    )

    home_count = 0
    draw_count = 0
    away_count = 0

    for row in results:

        result = row.get(
            "실제결과"
        )

        if result == "승":

            home_count += 1

        elif result == "무":

            draw_count += 1

        elif result == "패":

            away_count += 1

    actual = {

        "home":
            home_count
            / total
            * 100,

        "draw":
            draw_count
            / total
            * 100,

        "away":
            away_count
            / total
            * 100
    }

    probability = (
        average_input_probability(
            odds_input,
            companies
        )
    )

    if probability is None:

        probability = {

            "home": 0,
            "draw": 0,
            "away": 0
        }

    shortage = {

        "home":
            actual["home"]
            - probability["home"],

        "draw":
            actual["draw"]
            - probability["draw"],

        "away":
            actual["away"]
            - probability["away"]
    }

    return {

        "actual":
            actual,

        "probability":
            probability,

        "shortage":
            shortage,

        "count":
            total
    }


# =========================================================
# 가장 부족한 결과
# =========================================================

def get_highest_shortage(stats):

    if not stats:
        return ""

    shortage = stats.get(
        "shortage",
        {}
    )

    values = {

        "승":
            shortage.get(
                "home",
                0
            ),

        "무":
            shortage.get(
                "draw",
                0
            ),

        "패":
            shortage.get(
                "away",
                0
            )
    }

    return min(
        values,
        key=values.get
    )
