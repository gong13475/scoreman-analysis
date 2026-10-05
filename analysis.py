import database


# =========================================================
# 업체
# =========================================================

def get_company_list():
    return database.get_company_names() or []


# =========================================================
# 배당 → 정규화 확률
# =========================================================

def odds_to_probability(home, draw, away):
    try:
        home = float(home)
        draw = float(draw)
        away = float(away)
    except Exception:
        return {
            "home": 0.0,
            "draw": 0.0,
            "away": 0.0
        }

    if home <= 0 or draw <= 0 or away <= 0:
        return {
            "home": 0.0,
            "draw": 0.0,
            "away": 0.0
        }

    raw_home = 1.0 / home
    raw_draw = 1.0 / draw
    raw_away = 1.0 / away

    total = raw_home + raw_draw + raw_away

    return {
        "home": raw_home / total * 100,
        "draw": raw_draw / total * 100,
        "away": raw_away / total * 100
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

    all_results = []

    for company in companies:

        value = odds_input.get(company)

        if not value:
            continue

        try:
            rows = database.search_odds(
                value["home"],
                value["draw"],
                value["away"],
                companies=[company],
                tolerance=tolerance
            ) or []

        except Exception:
            rows = []

        for row in rows:

            item = dict(row)

            item["검색업체"] = company

            all_results.append(item)

    # 경기 + 업체 중복 제거
    unique = {}

    for row in all_results:

        key = (
            str(row.get("schedule_id", "")),
            str(row.get("bookmaker", ""))
        )

        unique[key] = row

    results = list(unique.values())

    # 날짜순
    results.sort(
        key=lambda x: str(
            x.get("match_date", "")
        ),
        reverse=True
    )

    statistics = calculate_statistics(results)

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

    home_count = 0
    draw_count = 0
    away_count = 0

    for row in results:

        result = str(
            row.get("result", "")
        ).strip()

        if result == "승":
            home_count += 1

        elif result == "무":
            draw_count += 1

        elif result == "패":
            away_count += 1

    actual = {
        "home":
            home_count / total * 100,

        "draw":
            draw_count / total * 100,

        "away":
            away_count / total * 100
    }

    # -----------------------------------------------------
    # 검색된 실제 배당의 평균 확률
    # -----------------------------------------------------

    p_home = []
    p_draw = []
    p_away = []

    for row in results:

        try:

            p = odds_to_probability(
                row.get("home_odds"),
                row.get("draw_odds"),
                row.get("away_odds")
            )

            p_home.append(p["home"])
            p_draw.append(p["draw"])
            p_away.append(p["away"])

        except Exception:
            continue

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
            "home": 0.0,
            "draw": 0.0,
            "away": 0.0
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

    shortage = stats.get(
        "shortage",
        {}
    )

    if not shortage:
        return ""

    key = max(
        shortage,
        key=shortage.get
    )

    names = {
        "home": "승",
        "draw": "무",
        "away": "패"
    }

    return names.get(
        key,
        ""
    )
