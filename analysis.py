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

    # DB에 실제 저장된 업체 우선
    result = list(companies)

    # 주요 해외 업체
    preferred_companies = [

        "Bet365",
        "William Hill",
        "10Bet"

    ]

    existing_normalized = set()

    for company in result:

        existing_normalized.add(
            normalize_company_name(
                company
            )
        )

    for company in preferred_companies:

        normalized = (
            normalize_company_name(
                company
            )
        )

        if normalized not in existing_normalized:

            result.append(company)

            existing_normalized.add(
                normalized
            )

    return sorted(
        result,
        key=lambda x: str(x).lower()
    )


# =========================================================
# 배당값 검증
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

        for key in [
            "home",
            "draw",
            "away"
        ]:

            if key not in odds:

                return (
                    False,
                    f"{company}의 {key} 배당값이 없습니다."
                )

            try:

                value = float(
                    odds[key]
                )

                if value <= 0:

                    return (
                        False,
                        f"{company} 배당값은 0보다 커야 합니다."
                    )

            except Exception:

                return (
                    False,
                    f"{company} 배당값이 올바르지 않습니다."
                )

    return True, ""


# =========================================================
# 배당 → 암시적 확률
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
                "home": 0,
                "draw": 0,
                "away": 0
            }

        raw_home = 1 / home
        raw_draw = 1 / draw
        raw_away = 1 / away

        total = (
            raw_home
            +
            raw_draw
            +
            raw_away
        )

        if total <= 0:

            return {
                "home": 0,
                "draw": 0,
                "away": 0
            }

        return {

            "home":
                raw_home / total * 100,

            "draw":
                raw_draw / total * 100,

            "away":
                raw_away / total * 100

        }

    except Exception:

        return {

            "home": 0,
            "draw": 0,
            "away": 0

        }


# =========================================================
# 실제 결과 건수
# =========================================================

def calculate_result_counts(
    matches
):

    total = len(matches)

    win = 0
    draw = 0
    lose = 0

    for match in matches:

        result = str(
            match.get(
                "result",
                ""
            )
        ).strip()

        if result == "승":

            win += 1

        elif result == "무":

            draw += 1

        elif result == "패":

            lose += 1

    return {

        "total":
            total,

        "win":
            win,

        "draw":
            draw,

        "lose":
            lose

    }


# =========================================================
# 실제 결과 비율
# =========================================================

def calculate_actual_percentages(
    counts
):

    total = int(
        counts.get(
            "total",
            0
        )
    )

    if total <= 0:

        return {

            "home": 0,
            "draw": 0,
            "away": 0

        }

    return {

        "home":
            counts["win"]
            /
            total
            *
            100,

        "draw":
            counts["draw"]
            /
            total
            *
            100,

        "away":
            counts["lose"]
            /
            total
            *
            100

    }


# =========================================================
# 부족확률
#
# 예상확률 - 실제결과비율
#
# 양수:
# 예상보다 실제 결과가 부족
#
# 음수:
# 예상보다 실제 결과가 많이 발생
# =========================================================

def calculate_shortage_percent(
    probabilities,
    actual_percentages
):

    return {

        "home":
            probabilities["home"]
            -
            actual_percentages["home"],

        "draw":
            probabilities["draw"]
            -
            actual_percentages["draw"],

        "away":
            probabilities["away"]
            -
            actual_percentages["away"]

    }


# =========================================================
# 업체별 통계
# =========================================================

def analyze_company_results(
    matches,
    company_name,
    input_odds
):

    counts = calculate_result_counts(
        matches
    )

    actual = calculate_actual_percentages(
        counts
    )

    probabilities = (
        calculate_implied_probabilities(

            input_odds["home"],
            input_odds["draw"],
            input_odds["away"]

        )
    )

    shortage = (
        calculate_shortage_percent(
            probabilities,
            actual
        )
    )

    return {

        "company":
            company_name,

        "total":
            counts["total"],

        "win_count":
            counts["win"],

        "draw_count":
            counts["draw"],

        "lose_count":
            counts["lose"],

        "win_probability":
            probabilities["home"],

        "draw_probability":
            probabilities["draw"],

        "lose_probability":
            probabilities["away"],

        "win_actual":
            actual["home"],

        "draw_actual":
            actual["draw"],

        "lose_actual":
            actual["away"],

        "win_shortage":
            shortage["home"],

        "draw_shortage":
            shortage["draw"],

        "lose_shortage":
            shortage["away"]

    }


# =========================================================
# 검색
# =========================================================

def run_search(
    selected_companies,
    input_odds
):

    valid, message = (
        validate_company_odds(
            selected_companies,
            input_odds
        )
    )

    if not valid:

        return {

            "success":
                False,

            "message":
                message,

            "results":
                [],

            "statistics":
                {}

        }

    # -----------------------------------------------------
    # DB 검색용
    # -----------------------------------------------------

    company_odds = {}

    for company in selected_companies:

        odds = input_odds[company]

        company_odds[company] = {

            "home":
                float(
                    odds["home"]
                ),

            "draw":
                float(
                    odds["draw"]
                ),

            "away":
                float(
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

            "success":
                False,

            "message":
                str(e),

            "results":
                [],

            "statistics":
                {}

        }

    results = []

    # -----------------------------------------------------
    # 선택 업체 정규화
    # -----------------------------------------------------

    normalized_selected = {}

    for company in selected_companies:

        normalized_selected[
            normalize_company_name(
                company
            )
        ] = company

    # -----------------------------------------------------
    # 경기별 데이터
    # -----------------------------------------------------

    for match in matches:

        item = dict(
            match
        )

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

                item[
                    "company_odds"
                ][
                    selected_name
                ] = {

                    "home":
                        row["final_home"],

                    "draw":
                        row["final_draw"],

                    "away":
                        row["final_away"]

                }

        results.append(
            item
        )

    # =====================================================
    # 업체별 통계
    # =====================================================

    statistics = {}

    for company in selected_companies:

        statistics[company] = (
            analyze_company_results(

                results,

                company,

                input_odds[company]

            )
        )

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


# =========================================================
# 전체 검색 결과 통계
# =========================================================

def get_overall_statistics(
    results
):

    counts = calculate_result_counts(
        results
    )

    actual = calculate_actual_percentages(
        counts
    )

    return {

        "total":
            counts["total"],

        "win_count":
            counts["win"],

        "draw_count":
            counts["draw"],

        "lose_count":
            counts["lose"],

        "win_percent":
            actual["home"],

        "draw_percent":
            actual["draw"],

        "lose_percent":
            actual["away"]

    }


# =========================================================
# 테스트
# =========================================================

if __name__ == "__main__":

    database.init_database()

    print(
        "========================================"
    )

    print(
        "Scoreman 배당 분석"
    )

    print(
        "========================================"
    )

    print(
        "업체 목록"
    )

    for company in get_company_list():

        print(
            "-",
            company
        )
