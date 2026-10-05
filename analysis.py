import database


def normalize_company_name(name):

    if name is None:
        return ""

    return (
        str(name)
        .strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace(".", "")
    )


def get_company_list():

    database.init_database()

    companies = list(
        database.get_company_names()
    )

    preferred = [
        "Bet365",
        "William Hill",
        "10Bet",
        "마카오"
    ]

    existing = {
        normalize_company_name(x)
        for x in companies
    }

    for company in preferred:

        key = normalize_company_name(
            company
        )

        if key not in existing:

            companies.append(
                company
            )

            existing.add(key)

    return sorted(
        companies,
        key=lambda x: str(x).lower()
    )


def odds_to_probability(
    home,
    draw,
    away
):

    try:

        h = float(home)
        d = float(draw)
        a = float(away)

        if h <= 0 or d <= 0 or a <= 0:
            raise ValueError

        ih = 1 / h
        idraw = 1 / d
        ia = 1 / a

        total = ih + idraw + ia

        return {
            "home": ih / total,
            "draw": idraw / total,
            "away": ia / total
        }

    except Exception:

        return {
            "home": 0,
            "draw": 0,
            "away": 0
        }


def result_to_key(result):

    value = str(
        result or ""
    ).strip().lower()

    if value in ["승", "win", "home"]:
        return "home"

    if value in ["무", "draw", "tie"]:
        return "draw"

    if value in ["패", "loss", "away"]:
        return "away"

    return ""


def calculate_result_counts(results):

    counts = {
        "home": 0,
        "draw": 0,
        "away": 0
    }

    for row in results:

        key = result_to_key(
            row.get("result")
        )

        if key:
            counts[key] += 1

    total = sum(
        counts.values()
    )

    return {
        "total": total,
        **counts
    }


def calculate_actual_percentages(
    results
):

    counts = calculate_result_counts(
        results
    )

    total = counts["total"]

    if total == 0:

        return {
            "home": 0,
            "draw": 0,
            "away": 0
        }

    return {
        "home":
            counts["home"] / total * 100,

        "draw":
            counts["draw"] / total * 100,

        "away":
            counts["away"] / total * 100
    }


def calculate_statistics(
    results,
    input_odds
):

    counts = calculate_result_counts(
        results
    )

    actual = calculate_actual_percentages(
        results
    )

    values = []

    for odds in input_odds.values():

        try:

            values.append({
                "home": float(odds["home"]),
                "draw": float(odds["draw"]),
                "away": float(odds["away"])
            })

        except Exception:
            pass

    if not values:

        probability = {
            "home": 0,
            "draw": 0,
            "away": 0
        }

        average = {
            "home": 0,
            "draw": 0,
            "away": 0
        }

    else:

        average = {
            "home":
                sum(x["home"] for x in values)
                / len(values),

            "draw":
                sum(x["draw"] for x in values)
                / len(values),

            "away":
                sum(x["away"] for x in values)
                / len(values)
        }

        p = odds_to_probability(
            average["home"],
            average["draw"],
            average["away"]
        )

        probability = {
            "home": p["home"] * 100,
            "draw": p["draw"] * 100,
            "away": p["away"] * 100
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
        "total": counts["total"],
        "counts": counts,
        "actual": actual,
        "probability": probability,
        "shortage": shortage,
        "average_odds": average
    }


def run_search(
    selected_companies,
    input_odds
):

    if not selected_companies:
        return {
            "success": False,
            "message": "업체를 선택하세요.",
            "results": [],
            "statistics": None
        }

    if not input_odds:
        return {
            "success": False,
            "message": "배당값을 입력하세요.",
            "results": [],
            "statistics": None
        }

    for company in selected_companies:

        if company not in input_odds:
            return {
                "success": False,
                "message":
                    f"{company} 배당값이 없습니다.",
                "results": [],
                "statistics": None
            }

    matches = database.search_multiple_final_odds(
        input_odds
    )

    normalized = {
        normalize_company_name(c): c
        for c in selected_companies
    }

    results = []

    for match in matches:

        item = dict(match)

        item["company_odds"] = {}

        rows = database.get_match_final_odds(
            match["schedule_id"]
        )

        for row in rows:

            key = normalize_company_name(
                row["bookmaker"]
            )

            company = normalized.get(key)

            if company:

                item["company_odds"][company] = {
                    "home": row["final_home"],
                    "draw": row["final_draw"],
                    "away": row["final_away"]
                }

        results.append(item)

    statistics = calculate_statistics(
        results,
        input_odds
    )

    return {
        "success": True,
        "message": "",
        "results": results,
        "statistics": statistics
    }


def get_highest_shortage(
    statistics
):

    if not statistics:
        return ""

    shortage = statistics.get(
        "shortage",
        {}
    )

    values = {
        "승": shortage.get("home", 0),
        "무": shortage.get("draw", 0),
        "패": shortage.get("away", 0)
    }

    return max(
        values,
        key=values.get
    )


def get_summary(statistics):

    if not statistics:
        return {}

    c = statistics["counts"]
    p = statistics["probability"]
    a = statistics["actual"]
    s = statistics["shortage"]

    return {
        "전체경기수": c["total"],
        "승건수": c["home"],
        "무건수": c["draw"],
        "패건수": c["away"],

        "승배당확률": p["home"],
        "무배당확률": p["draw"],
        "패배당확률": p["away"],

        "실제승률": a["home"],
        "실제무승률": a["draw"],
        "실제패율": a["away"],

        "승부족확률": s["home"],
        "무부족확률": s["draw"],
        "패부족확률": s["away"],

        "가장부족한결과":
            get_highest_shortage(statistics)
    }
