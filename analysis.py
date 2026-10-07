# ============================================================
# analysis.py
# 동일배당 검색 / 승무패 확률 / 부족확률
# ============================================================

import database


# ============================================================
# 업체 목록
# ============================================================

def get_company_list():

    return database.get_company_list()


# ============================================================
# 배당 비교
# 소수점 2자리 기준
# ============================================================

def _same_odds(a, b):

    try:
        return round(float(a), 2) == round(float(b), 2)
    except Exception:
        return False


# ============================================================
# 동일배당 검색
# ============================================================

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

    if not odds_input:
        return {
            "success": False,
            "message": "배당을 입력하세요.",
            "results": [],
            "statistics": None
        }

    rows = database._execute("""
        SELECT
            m.schedule_id,
            m.match_date,
            m.home_team,
            m.away_team,
            m.home_score,
            m.away_score,
            m.result,
            o.company_name AS bookmaker,
            o.final_home AS home_odds,
            o.final_draw AS draw_odds,
            o.final_away AS away_odds
        FROM matches m
        JOIN odds o
          ON m.schedule_id = o.schedule_id
        ORDER BY CAST(m.schedule_id AS INTEGER) DESC
    """, fetch=True)

    results = []

    for row in rows:

        company = row.get("bookmaker")

        if company not in companies:
            continue

        target = odds_input.get(company)

        if not target:
            continue

        if not _same_odds(
            row.get("home_odds"),
            target.get("home")
        ):
            continue

        if not _same_odds(
            row.get("draw_odds"),
            target.get("draw")
        ):
            continue

        if not _same_odds(
            row.get("away_odds"),
            target.get("away")
        ):
            continue

        results.append(row)

    statistics = calculate_statistics(
        results,
        odds_input
    )

    return {
        "success": True,
        "message": "검색 완료",
        "results": results,
        "statistics": statistics
    }


# ============================================================
# 확률 계산
# ============================================================

def _odds_probability(
    home,
    draw,
    away
):

    try:

        h = 1 / float(home)
        d = 1 / float(draw)
        a = 1 / float(away)

        total = h + d + a

        return {
            "home": h / total * 100,
            "draw": d / total * 100,
            "away": a / total * 100
        }

    except Exception:

        return {
            "home": 0,
            "draw": 0,
            "away": 0
        }


# ============================================================
# 통계
# ============================================================

def calculate_statistics(
    results,
    odds_input
):

    total = len(results)

    home_count = sum(
        1
        for row in results
        if row.get("result") == "승"
    )

    draw_count = sum(
        1
        for row in results
        if row.get("result") == "무"
    )

    away_count = sum(
        1
        for row in results
        if row.get("result") == "패"
    )

    if total:

        actual = {
            "home":
                home_count / total * 100,

            "draw":
                draw_count / total * 100,

            "away":
                away_count / total * 100
        }

    else:

        actual = {
            "home": 0,
            "draw": 0,
            "away": 0
        }

    # --------------------------------------------------------
    # 여러 업체를 선택했을 경우
    # 각 업체 입력배당 확률을 평균
    # --------------------------------------------------------

    probability_list = []

    for company in odds_input:

        values = odds_input[company]

        probability_list.append(
            _odds_probability(
                values["home"],
                values["draw"],
                values["away"]
            )
        )

    if probability_list:

        probability = {
            "home":
                sum(
                    x["home"]
                    for x in probability_list
                ) / len(probability_list),

            "draw":
                sum(
                    x["draw"]
                    for x in probability_list
                ) / len(probability_list),

            "away":
                sum(
                    x["away"]
                    for x in probability_list
                ) / len(probability_list)
        }

    else:

        probability = {
            "home": 0,
            "draw": 0,
            "away": 0
        }

    shortage = {
        "home":
            actual["home"] - probability["home"],

        "draw":
            actual["draw"] - probability["draw"],

        "away":
            actual["away"] - probability["away"]
    }

    return {
        "total": total,

        "counts": {
            "home": home_count,
            "draw": draw_count,
            "away": away_count
        },

        "actual": actual,

        "probability": probability,

        "shortage": shortage
    }


# ============================================================
# 가장 큰 부족확률
# ============================================================

def get_highest_shortage(stats):

    if not stats:
        return ""

    shortage = stats.get(
        "shortage",
        {}
    )

    values = {
        "승": float(
            shortage.get("home", 0)
        ),

        "무": float(
            shortage.get("draw", 0)
        ),

        "패": float(
            shortage.get("away", 0)
        )
    }

    return max(
        values,
        key=values.get
            )
