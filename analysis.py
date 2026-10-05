import database


# =========================================================
# 업체 목록
# =========================================================

def get_company_list():
    """
    DB에 실제 저장된 업체 목록을 반환
    """

    try:
        return database.get_company_names() or []

    except Exception:
        return []


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

        if home <= 0 or draw <= 0 or away <= 0:
            return {
                "home": 0,
                "draw": 0,
                "away": 0
            }

        inv_home = 1 / home
        inv_draw = 1 / draw
        inv_away = 1 / away

        total = (
            inv_home
            + inv_draw
            + inv_away
        )

        if total <= 0:
            return {
                "home": 0,
                "draw": 0,
                "away": 0
            }

        return {
            "home":
                inv_home / total * 100,

            "draw":
                inv_draw / total * 100,

            "away":
                inv_away / total * 100
        }

    except Exception:
        return {
            "home": 0,
            "draw": 0,
            "away": 0
        }


# =========================================================
# 결과 변환
# =========================================================

def result_to_key(result):

    result = str(
        result or ""
    ).strip()

    if result == "승":
        return "home"

    if result == "무":
        return "draw"

    if result == "패":
        return "away"

    return None


# =========================================================
# 입력 배당 비교
# =========================================================

def _odds_match(
    actual,
    target,
    tolerance=0.001
):

    try:
        return (
            abs(
                float(actual)
                - float(target)
            )
            <= tolerance
        )

    except Exception:
        return False


# =========================================================
# 경기 필터
# =========================================================

def _match_selected_companies(
    odds_rows,
    companies,
    odds_input
):

    if not odds_rows:
        return False

    by_company = {}

    for row in odds_rows:

        name = str(
            row.get(
                "bookmaker",
                ""
            )
        ).strip().lower()

        by_company[name] = row


    for company in companies:

        company_key = str(
            company
        ).strip().lower()

        row = by_company.get(
            company_key
        )

        if not row:
            return False

        target = odds_input.get(
            company
        )

        if not target:
            return False

        if not _odds_match(
            row.get("home_odds"),
            target.get("home")
        ):
            return False

        if not _odds_match(
            row.get("draw_odds"),
            target.get("draw")
        ):
            return False

        if not _odds_match(
            row.get("away_odds"),
            target.get("away")
        ):
            return False

    return True


# =========================================================
# 경기 검색 및 분석
# =========================================================

def run_search(
    companies,
    odds_input
):

    try:

        companies = list(
            companies or []
        )

        if not companies:

            return {
                "success": False,
                "message": "분석 업체를 선택하세요.",
                "results": [],
                "statistics": None
            }


        matches = (
            database.get_all_matches()
            or []
        )


        if not matches:

            return {
                "success": False,
                "message": "저장된 경기가 없습니다.",
                "results": [],
                "statistics": None
            }


        results = []


        for match in matches:

            schedule_id = str(
                match.get(
                    "schedule_id",
                    ""
                )
            )


            if not schedule_id:
                continue


            result = str(
                match.get(
                    "result",
                    ""
                )
            ).strip()


            if result not in {
                "승",
                "무",
                "패"
            }:
                continue


            odds_rows = (
                database.get_odds_by_match(
                    schedule_id
                )
                or []
            )


            if not odds_rows:
                continue


            if not _match_selected_companies(
                odds_rows,
                companies,
                odds_input
            ):
                continue


            probability_values = []


            for company in companies:

                target = odds_input.get(
                    company
                )

                if not target:
                    continue


                probability = odds_to_probability(

                    target.get("home"),
                    target.get("draw"),
                    target.get("away")
                )


                probability_values.append(
                    probability
                )


            if not probability_values:
                continue


            avg_probability = {

                "home":
                    sum(
                        x["home"]
                        for x in probability_values
                    )
                    / len(probability_values),

                "draw":
                    sum(
                        x["draw"]
                        for x in probability_values
                    )
                    / len(probability_values),

                "away":
                    sum(
                        x["away"]
                        for x in probability_values
                    )
                    / len(probability_values)
            }


            results.append({

                "schedule_id":
                    schedule_id,

                "match_date":
                    match.get(
                        "match_date",
                        ""
                    ),

                "home_team":
                    match.get(
                        "home_team",
                        ""
                    ),

                "away_team":
                    match.get(
                        "away_team",
                        ""
                    ),

                "home_score":
                    match.get(
                        "home_score"
                    ),

                "away_score":
                    match.get(
                        "away_score"
                    ),

                "result":
                    result,

                "prob_home":
                    round(
                        avg_probability["home"],
                        2
                    ),

                "prob_draw":
                    round(
                        avg_probability["draw"],
                        2
                    ),

                "prob_away":
                    round(
                        avg_probability["away"],
                        2
                    )
            })


        if not results:

            return {
                "success": True,
                "message": "조건에 맞는 경기가 없습니다.",
                "results": [],
                "statistics": None
            }


        # =====================================================
        # 실제 결과
        # =====================================================

        total = len(results)

        home_count = sum(
            1
            for row in results
            if row["result"] == "승"
        )

        draw_count = sum(
            1
            for row in results
            if row["result"] == "무"
        )

        away_count = sum(
            1
            for row in results
            if row["result"] == "패"
        )


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


        # =====================================================
        # 배당 확률
        # =====================================================

        probability = {

            "home":
                sum(
                    row["prob_home"]
                    for row in results
                )
                / total,

            "draw":
                sum(
                    row["prob_draw"]
                    for row in results
                )
                / total,

            "away":
                sum(
                    row["prob_away"]
                    for row in results
                )
                / total
        }


        # =====================================================
        # 실제 결과 - 배당 확률
        # =====================================================

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


        statistics = {

            "count":
                total,

            "actual":
                actual,

            "probability":
                probability,

            "shortage":
                shortage
        }


        return {

            "success":
                True,

            "message":
                "",

            "results":
                results,

            "statistics":
                statistics
        }


    except Exception as e:

        return {

            "success":
                False,

            "message":
                str(e),

            "results":
                [],

            "statistics":
                None
        }


# =========================================================
# 가장 부족한 결과
# =========================================================

def get_highest_shortage(
    stats
):

    if not stats:
        return ""


    shortage = stats.get(
        "shortage",
        {}
    )


    values = {

        "승":
            float(
                shortage.get(
                    "home",
                    0
                )
            ),

        "무":
            float(
                shortage.get(
                    "draw",
                    0
                )
            ),

        "패":
            float(
                shortage.get(
                    "away",
                    0
                )
            )
    }


    return max(
        values,
        key=values.get
            )
