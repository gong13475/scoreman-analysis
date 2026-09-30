import database


# =========================================================
# 업체명 정규화
# =========================================================

def normalize_company_name(name):

    if name is None:
        return ""

    value = str(name).strip().lower()

    value = value.replace(" ", "")
    value = value.replace("_", "")
    value = value.replace("-", "")
    value = value.replace(".", "")

    return value


# =========================================================
# 업체 목록
# =========================================================

def get_company_list():

    database.init_database()

    companies = database.get_company_names()

    result = list(companies)

    preferred = [
        "Bet365",
        "William Hill",
        "10Bet",
        "12bet",
        "마카오"
    ]

    existing = {
        normalize_company_name(x)
        for x in result
    }

    for company in preferred:

        normalized = normalize_company_name(
            company
        )

        if normalized not in existing:

            result.append(company)

            existing.add(
                normalized
            )

    return sorted(
        result,
        key=lambda x: str(x).lower()
    )


# =========================================================
# 배당 검증
# =========================================================

def validate_company_odds(
    selected_companies,
    input_odds
):

    if not selected_companies:

        return (
            False,
            "업체를 하나 이상 선택하세요."
        )

    if not input_odds:

        return (
            False,
            "배당값을 입력하세요."
        )

    for company in selected_companies:

        if company not in input_odds:

            return (
                False,
                f"{company} 배당값이 없습니다."
            )

        odds = input_odds[company]

        for key in (
            "home",
            "draw",
            "away"
        ):

            if key not in odds:

                return (
                    False,
                    f"{company}의 "
                    f"{key} 배당값이 없습니다."
                )

            try:

                value = float(
                    odds[key]
                )

                if value <= 0:

                    return (
                        False,
                        f"{company} 배당값은 "
                        f"0보다 커야 합니다."
                    )

            except Exception:

                return (
                    False,
                    f"{company} 배당값이 "
                    f"올바르지 않습니다."
                )

    return True, ""


# =========================================================
# 배당 → 확률
# =========================================================

def calculate_implied_probabilities(
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

            return {
                "home": 0.0,
                "draw": 0.0,
                "away": 0.0
            }

        ih = 1.0 / home
        idraw = 1.0 / draw
        ia = 1.0 / away

        total = (
            ih
            + idraw
            + ia
        )

        if total <= 0:

            return {
                "home": 0.0,
                "draw": 0.0,
                "away": 0.0
            }

        return {
            "home": ih / total * 100,
            "draw": idraw / total * 100,
            "away": ia / total * 100
        }

    except Exception:

        return {
            "home": 0.0,
            "draw": 0.0,
            "away": 0.0
        }


def odds_to_probability(
    home,
    draw,
    away
):

    return calculate_implied_probabilities(
        home,
        draw,
        away
    )


# =========================================================
# 결과 변환
# =========================================================

def result_to_key(result):

    if result is None:
        return ""

    value = str(
        result
    ).strip().lower()

    if value in (
        "승",
        "win",
        "home"
    ):
        return "home"

    if value in (
        "무",
        "draw",
        "tie"
    ):
        return "draw"

    if value in (
        "패",
        "loss",
        "away"
    ):
        return "away"

    return ""


# =========================================================
# 동일배당 분석
# =========================================================

def calculate_same_odds_statistics(
    company,
    home,
    draw,
    away
):

    rows = database.get_same_odds_matches(
        company,
        home,
        draw,
        away
    )

    total = len(rows)

    counts = {
        "home": 0,
        "draw": 0,
        "away": 0
    }

    for row in rows:

        key = result_to_key(
            row["result"]
        )

        if key in counts:
            counts[key] += 1

    if total:

        actual = {
            "home":
                counts["home"]
                / total
                * 100,

            "draw":
                counts["draw"]
                / total
                * 100,

            "away":
                counts["away"]
                / total
                * 100
        }

    else:

        actual = {
            "home": 0.0,
            "draw": 0.0,
            "away": 0.0
        }

    expected = calculate_implied_probabilities(
        home,
        draw,
        away
    )

    difference = {
        "home":
            actual["home"]
            - expected["home"],

        "draw":
            actual["draw"]
            - expected["draw"],

        "away":
            actual["away"]
            - expected["away"]
    }

    return {
        "company": company,
        "odds": {
            "home": float(home),
            "draw": float(draw),
            "away": float(away)
        },
        "total": total,
        "counts": counts,
        "actual": actual,
        "expected": expected,
        "difference": difference,
        "rows": rows
    }


# =========================================================
# 검색
# =========================================================

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
            "statistics": None,
            "same_odds": {}
        }

    company_odds = {}

    for company in selected_companies:

        odds = input_odds[company]

        company_odds[company] = {
            "home": float(
                odds["home"]
            ),
            "draw": float(
                odds["draw"]
            ),
            "away": float(
                odds["away"]
            )
        }

    try:

        matches = (
            database.search_multiple_final_odds(
                company_odds
            )
        )

    except Exception as e:

        return {
            "success": False,
            "message": f"DB 검색 오류: {e}",
            "results": [],
            "statistics": None,
            "same_odds": {}
        }

    results = []

    normalized_selected = {}

    for company in selected_companies:

        normalized_selected[
            normalize_company_name(
                company
            )
        ] = company

    for match in matches:

        item = dict(match)

        item["company_odds"] = {}

        rows = (
            database.get_match_final_odds(
                match["schedule_id"]
            )
        )

        for row in rows:

            actual_name = row[
                "company_name"
            ]

            normalized = (
                normalize_company_name(
                    actual_name
                )
            )

            selected_name = (
                normalized_selected.get(
                    normalized
                )
            )

            if selected_name:

                item["company_odds"][
                    selected_name
                ] = {
                    "home": row["final_home"],
                    "draw": row["final_draw"],
                    "away": row["final_away"]
                }

        results.append(item)

    same_odds = {}

    for company in selected_companies:

        odds = input_odds[company]

        same_odds[company] = (
            calculate_same_odds_statistics(
                company,
                odds["home"],
                odds["draw"],
                odds["away"]
            )
        )

    return {
        "success": True,
        "message": "",
        "results": results,
        "statistics": None,
        "same_odds": same_odds
    }


# =========================================================
# 업체별 통계
# =========================================================

def calculate_company_statistics(
    results,
    company
):

    counts = {
        "home": 0,
        "draw": 0,
        "away": 0
    }

    for row in results:

        if company not in row.get(
            "company_odds",
            {}
        ):
            continue

        key = result_to_key(
            row.get("result")
        )

        if key in counts:
            counts[key] += 1

    total = sum(
        counts.values()
    )

    return {
        "total": total,
        **counts
    }


def get_highest_difference(
    statistics
):

    if not statistics:
        return ""

    values = statistics.get(
        "difference",
        {}
    )

    if not values:
        return ""

    keys = {
        "home": "승",
        "draw": "무",
        "away": "패"
    }

    key = max(
        values,
        key=values.get
    )

    return keys.get(
        key,
        ""
    )


def get_summary(
    statistics
):

    if not statistics:
        return {}

    return {
        "동일배당경기수":
            statistics.get(
                "total",
                0
            ),
        "승건수":
            statistics.get(
                "counts",
                {}
            ).get("home", 0),
        "무건수":
            statistics.get(
                "counts",
                {}
            ).get("draw", 0),
        "패건수":
            statistics.get(
                "counts",
                {}
            ).get("away", 0)
            }
