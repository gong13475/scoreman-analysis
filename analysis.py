import database


# =========================================================
# 업체 목록
# =========================================================

def get_company_list():

    return database.get_company_names()


# =========================================================
# 배당 확률
# =========================================================

def odds_probability(
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
# 입력 배당과 저장 배당 비교
# =========================================================

def _close(
    a,
    b,
    tolerance=0.03
):

    try:

        return abs(
            float(a)
            - float(b)
        ) <= tolerance

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

            "success":
                False,

            "message":
                "분석할 업체가 없습니다.",

            "results":
                [],

            "statistics":
                None
        }


    all_odds = database.get_all_odds()

    matches = {
        str(
            x["schedule_id"]
        ): x

        for x in database.get_all_matches()
    }


    results = []


    for row in all_odds:

        bookmaker = str(
            row.get(
                "bookmaker",
                ""
            )
        )

        if bookmaker not in companies:
            continue


        wanted = odds_input.get(
            bookmaker
        )

        if not wanted:
            continue


        if not (
            _close(
                row.get("home_odds"),
                wanted.get("home")
            )
            and
            _close(
                row.get("draw_odds"),
                wanted.get("draw")
            )
            and
            _close(
                row.get("away_odds"),
                wanted.get("away")
            )
        ):
            continue


        match = matches.get(
            str(
                row.get(
                    "schedule_id"
                )
            )
        )

        if not match:
            continue


        result = match.get(
            "result",
            ""
        )


        if result not in {
            "승",
            "무",
            "패"
        }:
            continue


        results.append({

            "경기ID":
                row.get(
                    "schedule_id"
                ),

            "업체":
                bookmaker,

            "홈팀":
                match.get(
                    "home_team",
                    ""
                ),

            "원정팀":
                match.get(
                    "away_team",
                    ""
                ),

            "홈배당":
                row.get(
                    "home_odds"
                ),

            "무배당":
                row.get(
                    "draw_odds"
                ),

            "원정배당":
                row.get(
                    "away_odds"
                ),

            "실제결과":
                result
        })


    if not results:

        return {

            "success":
                True,

            "message":
                "검색 결과가 없습니다.",

            "results":
                [],

            "statistics":
                None
        }


    home_count = sum(
        1
        for x in results
        if x["실제결과"] == "승"
    )

    draw_count = sum(
        1
        for x in results
        if x["실제결과"] == "무"
    )

    away_count = sum(
        1
        for x in results
        if x["실제결과"] == "패"
    )


    total = len(
        results
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


    # 평균 배당
    home_odds = sum(
        float(x["홈배당"])
        for x in results
    ) / total

    draw_odds = sum(
        float(x["무배당"])
        for x in results
    ) / total

    away_odds = sum(
        float(x["원정배당"])
        for x in results
    ) / total


    probability = odds_probability(

        home_odds,

        draw_odds,

        away_odds
    )


    if probability:

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

    else:

        shortage = {

            "home": 0,

            "draw": 0,

            "away": 0
        }


    return {

        "success":
            True,

        "message":
            "",

        "results":
            results,

        "statistics": {

            "actual":
                actual,

            "probability":
                probability or {

                    "home": 0,

                    "draw": 0,

                    "away": 0
                },

            "shortage":
                shortage
        }
    }


# =========================================================
# 가장 부족한 결과
# =========================================================

def get_highest_shortage(
    stats
):

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
