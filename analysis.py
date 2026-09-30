import database


def normalize_company_name(name):
    if name is None:
        return ""

    value = str(name).strip().lower()

    for char in [" ", "_", "-", "."]:
        value = value.replace(char, "")

    return value


def get_company_list():
    database.init_database()

    result = list(
        database.get_company_names()
    )

    preferred = [
        "Bet365",
        "William Hill",
        "10Bet"
    ]

    existing = {
        normalize_company_name(x)
        for x in result
    }

    for company in preferred:
        key = normalize_company_name(company)

        if key not in existing:
            result.append(company)
            existing.add(key)

    return sorted(
        result,
        key=lambda x: str(x).lower()
    )


def validate_company_odds(
    selected_companies,
    input_odds
):
    if not selected_companies:
        return False, "업체를 하나 이상 선택하세요."

    if not input_odds:
        return False, "배당값을 입력하세요."

    for company in selected_companies:
        if company not in input_odds:
            return False, f"{company} 배당값이 없습니다."

        odds = input_odds[company]

        for key in ["home", "draw", "away"]:
            try:
                value = float(odds[key])

                if value <= 0:
                    return False, (
                        f"{company} 배당값은 "
                        "0보다 커야 합니다."
                    )

            except Exception:
                return False, (
                    f"{company}의 {key} 배당값이 "
                    "올바르지 않습니다."
                )

    return True, ""


def calculate_implied_probabilities(
    home,
    draw,
    away
):
    try:
        home = float(home)
        draw = float(draw)
        away = float(away)

        raw = [
            1 / home,
            1 / draw,
            1 / away
        ]

        total = sum(raw)

        return {
            "home": raw[0] / total * 100,
            "draw": raw[1] / total * 100,
            "away": raw[2] / total * 100
        }

    except Exception:
        return {
            "home": 0,
            "draw": 0,
            "away": 0
        }


def calculate_result_counts(matches):
    result = {
        "total": len(matches),
        "win": 0,
        "draw": 0,
        "lose": 0
    }

    for match in matches:
        value = str(
            match.get("result", "")
        ).strip()

        if value == "승":
            result["win"] += 1
        elif value == "무":
            result["draw"] += 1
        elif value == "패":
            result["lose"] += 1

    return result


def calculate_actual_percentages(counts):
    total = counts["total"]

    if total == 0:
        return {
            "home": 0,
            "draw": 0,
            "away": 0
        }

    return {
        "home": counts["win"] / total * 100,
        "draw": counts["draw"] / total * 100,
        "away": counts["lose"] / total * 100
    }


def run_search(
    selected_companies,
    input_odds
):
    valid, message = validate_company_odds(
        selected_companies,
        input_odds
    )

    if not valid:
        return {
            "success": False,
            "message": message,
            "results": [],
            "statistics": {}
        }

    company_odds = {
        company: {
            "home": float(input_odds[company]["home"]),
            "draw": float(input_odds[company]["draw"]),
            "away": float(input_odds[company]["away"])
        }
        for company in selected_companies
    }

    try:
        matches = database.search_multiple_final_odds(
            company_odds
        )
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "results": [],
            "statistics": {}
        }

    normalized = {
        normalize_company_name(company): company
        for company in selected_companies
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
                row["company_name"]
            )

            selected_name = normalized.get(key)

            if selected_name:
                item["company_odds"][selected_name] = {
                    "home": row["final_home"],
                    "draw": row["final_draw"],
                    "away": row["final_away"]
                }

        results.append(item)

    statistics = {}

    for company in selected_companies:
        probabilities = calculate_implied_probabilities(
            input_odds[company]["home"],
            input_odds[company]["draw"],
            input_odds[company]["away"]
        )

        counts = calculate_result_counts(results)
        actual = calculate_actual_percentages(counts)

        statistics[company] = {
            "total": counts["total"],
            "win_count": counts["win"],
            "draw_count": counts["draw"],
            "lose_count": counts["lose"],
            "win_probability": probabilities["home"],
            "draw_probability": probabilities["draw"],
            "lose_probability": probabilities["away"],
            "win_actual": actual["home"],
            "draw_actual": actual["draw"],
            "lose_actual": actual["away"],
            "win_shortage": (
                probabilities["home"] - actual["home"]
            ),
            "draw_shortage": (
                probabilities["draw"] - actual["draw"]
            ),
            "lose_shortage": (
                probabilities["away"] - actual["away"]
            )
        }

    return {
        "success": True,
        "message": "",
        "results": results,
        "statistics": statistics
    }
