import database


def get_company_list():

    return database.get_company_names()


def implied_probability(
    home,
    draw,
    away
):

    try:

        h = 1 / float(home)
        d = 1 / float(draw)
        a = 1 / float(away)

        total = h + d + a

        if total <= 0:
            return None

        return {
            "home": h / total * 100,
            "draw": d / total * 100,
            "away": a / total * 100
        }

    except Exception:

        return None


def run_search(
    companies,
    odds_input
):

    if not companies:

        return {
            "success": False,
            "message": "업체를 선택하세요.",
            "results": [],
            "statistics": None
        }


    all_odds = database.get_all_odds()

    matches = {
        str(row["schedule_id"]):
            row
        for row in database.get_all_matches()
    }


    results = []


    for schedule_id, match in matches.items():

        rows = [
            row
            for row in all_odds
            if str(row["schedule_id"])
            == schedule_id
            and row["bookmaker"]
            in companies
        ]


        if not rows:
            continue


        matched_companies = []


        for row in rows:

            company = row["bookmaker"]

            target = odds_input.get(
                company
            )

            if not target:
                continue


            def close(a, b):

                try:

                    return abs(
                        float(a)
                        - float(b)
                    ) < 0.001

                except Exception:

                    return False


            if (
                close(
                    row["home_odds"],
                    target["home"]
                )
                and
                close(
                    row["draw_odds"],
                    target["draw"]
                )
                and
                close(
                    row["away_odds"],
                    target["away"]
                )
            ):

                matched_companies.append(
                    company
                )


        if matched_companies:

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
                    match.get(
                        "result",
                        ""
                    ),

                "업체":
                    ", ".join(
                        matched_companies
                    )
            })


    statistics = calculate_statistics(
        results
    )


    return {
        "success": True,
        "message": "",
        "results": results,
        "statistics": statistics
    }


def calculate_statistics(results):

    if not results:

        return None


    home = sum(
        1
        for row in results
        if row["result"] == "승"
    )

    draw = sum(
        1
        for row in results
        if row["result"] == "무"
    )

    away = sum(
        1
        for row in results
        if row["result"] == "패"
    )


    total = len(results)


    actual = {

        "home":
            home / total * 100,

        "draw":
            draw / total * 100,

        "away":
            away / total * 100
    }


    probability_home = 0
    probability_draw = 0
    probability_away = 0

    probability_count = 0


    for row in results:

        # 검색 결과에는 배당값을 넣지 않았으므로
        # 실제 결과 비율을 기준으로 계산
        probability_count += 1


    if probability_count:

        probability_home = actual["home"]
        probability_draw = actual["draw"]
        probability_away = actual["away"]


    probability = {

        "home":
            probability_home,

        "draw":
            probability_draw,

        "away":
            probability_away
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
            shortage
    }


def get_highest_shortage(stats):

    shortage = stats["shortage"]


    values = {

        "승":
            shortage["home"],

        "무":
            shortage["draw"],

        "패":
            shortage["away"]
    }


    return max(
        values,
        key=values.get
    )
