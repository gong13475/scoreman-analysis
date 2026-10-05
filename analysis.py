import database


# =========================================================
# 업체
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
    home = float(home)
    draw = float(draw)
    away = float(away)

    if home <= 0 or draw <= 0 or away <= 0:
        return {
            "home": 0,
            "draw": 0,
            "away": 0
        }

    raw_h = 1 / home
    raw_d = 1 / draw
    raw_a = 1 / away

    total = raw_h + raw_d + raw_a

    return {
        "home": raw_h / total * 100,
        "draw": raw_d / total * 100,
        "away": raw_a / total * 100
    }


# =========================================================
# 검색
# =========================================================

def run_search(
    companies,
    odds_input,
    tolerance=0.001
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

    # 여러 업체를 입력하면
    # 각 업체의 조건을 OR 검색
    all_results = []

    for company in companies:
        value = odds_input.get(company)

        if not value:
            continue

        rows = database.search_odds(
            value["home"],
            value["draw"],
            value["away"],
            companies=[company],
            tolerance=tolerance
        )

        for row in rows:
            row["검색업체"] = company
            all_results.append(row)

    # 중복 경기/업체 제거
    unique = {}

    for row in all_results:
        key = (
            str(row["schedule_id"]),
            str(row["bookmaker"])
        )

        unique[key] = row

    results = list(
        unique.values()
    )

    statistics = calculate_statistics(
        results
    )

    return {
        "success": True,
        "message": "",
        "results": results,
        "statistics": statistics
    }


# =========================================================
# 통계
# =========================================================

def calculate_statistics(results):
    if not results:
        return None

    total = len(results)

    home_count = sum(
        1
        for x in results
        if x.get("result") == "승"
    )

    draw_count = sum(
        1
        for x in results
        if x.get("result") == "무"
    )

    away_count = sum(
        1
        for x in results
        if x.get("result") == "패"
    )

    actual = {
        "home": home_count / total * 100,
        "draw": draw_count / total * 100,
        "away": away_count / total * 100
    }

    # 검색된 실제 배당의 평균 내재확률
    p_home = []
    p_draw = []
    p_away = []

    for row in results:
        try:
            p = odds_to_probability(
                row["home_odds"],
                row["draw_odds"],
                row["away_odds"]
            )

            p_home.append(p["home"])
            p_draw.append(p["draw"])
            p_away.append(p["away"])

        except Exception:
            pass

    if p_home:
        probability = {
            "home":
                sum(p_home) / len(p_home),

            "draw":
                sum(p_draw) / len(p_draw),

            "away":
                sum(p_away) / len(p_away)
        }
    else:
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
        "count": total,
        "actual": actual,
        "probability": probability,
        "shortage": shortage
    }


# =========================================================
# 가장 큰 차이
# =========================================================

def get_highest_shortage(stats):
    if not stats:
        return ""

    values = stats["shortage"]

    key = max(
        values,
        key=lambda x: values[x]
    )

    names = {
        "home": "승",
        "draw": "무",
        "away": "패"
    }

    return names[key]
