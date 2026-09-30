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
    value = value.replace("·", "")

    return value


# =========================================================
# 업체명 비교
# =========================================================

def company_names_match(
    name1,
    name2
):

    a = normalize_company_name(name1)
    b = normalize_company_name(name2)

    if not a or not b:
        return False

    if a == b:
        return True

    if a in b:
        return True

    if b in a:
        return True

    return False


# =========================================================
# 업체 목록
# =========================================================

def get_company_list():

    database.init_database()

    companies = database.get_company_names()

    result = []

    # -----------------------------------------------------
    # DB에 저장된 업체 전부 가져오기
    # -----------------------------------------------------

    for company in companies:

        if company is None:
            continue

        company = str(company).strip()

        if not company:
            continue

        result.append(company)

    # -----------------------------------------------------
    # 주요 해외업체
    #
    # DB에 아직 없어도 선택창에서 선택 가능
    # -----------------------------------------------------

    preferred_companies = [

        "Bet365",

        "William Hill",

        "10Bet",

        "마카오"

    ]

    existing_normalized = set()

    for company in result:

        existing_normalized.add(
            normalize_company_name(
                company
            )
        )

    for company in preferred_companies:

        normalized = normalize_company_name(
            company
        )

        if normalized not in existing_normalized:

            result.append(company)

            existing_normalized.add(
                normalized
            )

    # -----------------------------------------------------
    # 중복 제거
    # -----------------------------------------------------

    unique = {}

    for company in result:

        normalized = normalize_company_name(
            company
        )

        if not normalized:
            continue

        if normalized not in unique:

            unique[normalized] = company

    result = list(
        unique.values()
    )

    # -----------------------------------------------------
    # 정렬
    # -----------------------------------------------------

    result.sort(
        key=lambda x: str(x).lower()
    )

    return result


# =========================================================
# 배당 입력값 검증
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

        odds = input_odds[
            company
        ]

        for key in [
            "home",
            "draw",
            "away"
        ]:

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

def odds_to_probability(
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

        inv_home = 1.0 / home
        inv_draw = 1.0 / draw
        inv_away = 1.0 / away

        total = (
            inv_home
            + inv_draw
            + inv_away
        )

        if total <= 0:

            return {
                "home": 0.0,
                "draw": 0.0,
                "away": 0.0
            }

        return {

            "home":
                inv_home / total,

            "draw":
                inv_draw / total,

            "away":
                inv_away / total

        }

    except Exception:

        return {

            "home": 0.0,

            "draw": 0.0,

            "away": 0.0

        }


# =========================================================
# app.py에서 사용하는 함수
#
# 결과를 퍼센트로 반환
# =========================================================

def calculate_implied_probabilities(
    home,
    draw,
    away
):

    probability = odds_to_probability(

        home,

        draw,

        away

    )

    return {

        "home":
            probability["home"] * 100,

        "draw":
            probability["draw"] * 100,

        "away":
            probability["away"] * 100

    }


# =========================================================
# 결과 → 승무패
# =========================================================

def result_to_key(result):

    if result is None:
        return ""

    value = str(
        result
    ).strip().lower()

    if value in [

        "승",
        "win",
        "home"

    ]:

        return "home"

    if value in [

        "무",
        "draw",
        "tie"

    ]:

        return "draw"

    if value in [

        "패",
        "loss",
        "away"

    ]:

        return "away"

    return ""


# =========================================================
# 결과 건수
# =========================================================

def calculate_result_counts(
    results
):

    counts = {

        "home": 0,

        "draw": 0,

        "away": 0

    }

    for row in results:

        result = result_to_key(

            row.get(
                "result"
            )

        )

        if result in counts:

            counts[result] += 1

    total = (

        counts["home"]

        + counts["draw"]

        + counts["away"]

    )

    return {

        "total":
            total,

        "home":
            counts["home"],

        "draw":
            counts["draw"],

        "away":
            counts["away"]

    }


# =========================================================
# 실제 결과 비율
# =========================================================

def calculate_actual_percentages(
    results
):

    counts = calculate_result_counts(
        results
    )

    total = counts["total"]

    if total <= 0:

        return {

            "home": 0.0,

            "draw": 0.0,

            "away": 0.0

        }

    return {

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


# =========================================================
# 부족확률
# =========================================================

def calculate_shortage_percent(
    expected_probability,
    actual_probability
):

    try:

        expected = float(
            expected_probability
        )

        actual = float(
            actual_probability
        )

    except Exception:

        return 0.0

    shortage = (
        expected
        - actual
    )

    if shortage < 0:

        shortage = 0.0

    return shortage


# =========================================================
# 전체 분석 통계
# =========================================================

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

    odds_values = []

    for company, odds in input_odds.items():

        try:

            odds_values.append({

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

            })

        except Exception:

            continue

    if not odds_values:

        return {

            "total":
                counts["total"],

            "counts":
                counts,

            "actual":
                actual,

            "probability": {

                "home": 0.0,

                "draw": 0.0,

                "away": 0.0

            },

            "shortage": {

                "home": 0.0,

                "draw": 0.0,

                "away": 0.0

            },

            "average_odds": {

                "home": 0.0,

                "draw": 0.0,

                "away": 0.0

            }

        }

    avg_home = sum(

        x["home"]

        for x in odds_values

    ) / len(odds_values)

    avg_draw = sum(

        x["draw"]

        for x in odds_values

    ) / len(odds_values)

    avg_away = sum(

        x["away"]

        for x in odds_values

    ) / len(odds_values)

    probability = (
        odds_to_probability(

            avg_home,

            avg_draw,

            avg_away

        )
    )

    probability_percent = {

        "home":
            probability["home"]
            * 100,

        "draw":
            probability["draw"]
            * 100,

        "away":
            probability["away"]
            * 100

    }

    shortage = {

        "home":
            calculate_shortage_percent(

                probability_percent[
                    "home"
                ],

                actual[
                    "home"
                ]

            ),

        "draw":
            calculate_shortage_percent(

                probability_percent[
                    "draw"
                ],

                actual[
                    "draw"
                ]

            ),

        "away":
            calculate_shortage_percent(

                probability_percent[
                    "away"
                ],

                actual[
                    "away"
                ]

            )

    }

    return {

        "total":
            counts["total"],

        "counts":
            counts,

        "actual":
            actual,

        "probability":
            probability_percent,

        "shortage":
            shortage,

        "average_odds": {

            "home":
                avg_home,

            "draw":
                avg_draw,

            "away":
                avg_away

        }

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
                None

        }

    # -----------------------------------------------------
    # DB 검색용 배당
    # -----------------------------------------------------

    company_odds = {}

    for company in selected_companies:

        odds = input_odds[
            company
        ]

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

    # -----------------------------------------------------
    # DB 검색
    # -----------------------------------------------------

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
                f"DB 검색 오류: {e}",

            "results":
                [],

            "statistics":
                None

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
    # 경기별 업체 배당
    # -----------------------------------------------------

    for match in matches:

        item = dict(
            match
        )

        item[
            "company_odds"
        ] = {}

        rows = (
            database.get_match_final_odds(
                match[
                    "schedule_id"
                ]
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

            # -------------------------------------------------
            # 정확히 같은 정규화 이름이 없어도 부분 매칭
            # -------------------------------------------------

            if not selected_name:

                for normalized_key, original_name in normalized_selected.items():

                    if (
                        normalized
                        and normalized_key
                        and (
                            normalized in normalized_key
                            or normalized_key in normalized
                        )
                    ):

                        selected_name = (
                            original_name
                        )

                        break

            if selected_name:

                item[
                    "company_odds"
                ][
                    selected_name
                ] = {

                    "home":
                        row[
                            "final_home"
                        ],

                    "draw":
                        row[
                            "final_draw"
                        ],

                    "away":
                        row[
                            "final_away"
                        ]

                }

        # -------------------------------------------------
        # 선택 업체가 실제로 존재하는 경기만 유지
        # -------------------------------------------------

        if item["company_odds"]:

            results.append(
                item
            )

    # -----------------------------------------------------
    # 통계
    # -----------------------------------------------------

    statistics = calculate_statistics(

        results,

        input_odds

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
# 업체별 개별 통계
# =========================================================

def calculate_company_statistics(
    results,
    company
):

    company_results = []

    for row in results:

        company_odds = row.get(

            "company_odds",

            {}

        )

        if company in company_odds:

            company_results.append(
                row
            )

    return calculate_result_counts(
        company_results
    )


# =========================================================
# 업체별 상세 통계
# =========================================================

def calculate_company_detailed_statistics(
    results,
    company
):

    data = []

    for row in results:

        odds = (
            row.get(
                "company_odds",
                {}
            ).get(
                company
            )
        )

        if not odds:
            continue

        probability = (
            calculate_implied_probabilities(

                odds["home"],

                odds["draw"],

                odds["away"]

            )
        )

        data.append({

            "probability":
                probability,

            "result":
                row.get(
                    "result",
                    ""
                )

        })

    if not data:

        return {

            "count":
                0,

            "probability": {

                "home": 0.0,

                "draw": 0.0,

                "away": 0.0

            },

            "actual": {

                "home": 0.0,

                "draw": 0.0,

                "away": 0.0

            },

            "shortage": {

                "home": 0.0,

                "draw": 0.0,

                "away": 0.0

            }

        }

    total = len(data)

    avg_probability = {

        "home":
            sum(
                x["probability"]["home"]
                for x in data
            ) / total,

        "draw":
            sum(
                x["probability"]["draw"]
                for x in data
            ) / total,

        "away":
            sum(
                x["probability"]["away"]
                for x in data
            ) / total

    }

    actual = {

        "home":
            sum(
                x["result"] == "승"
                for x in data
            ) / total * 100,

        "draw":
            sum(
                x["result"] == "무"
                for x in data
            ) / total * 100,

        "away":
            sum(
                x["result"] == "패"
                for x in data
            ) / total * 100

    }

    shortage = {

        "home":
            max(
                0.0,
                avg_probability["home"]
                - actual["home"]
            ),

        "draw":
            max(
                0.0,
                avg_probability["draw"]
                - actual["draw"]
            ),

        "away":
            max(
                0.0,
                avg_probability["away"]
                - actual["away"]
            )

    }

    return {

        "count":
            total,

        "probability":
            avg_probability,

        "actual":
            actual,

        "shortage":
            shortage

    }


# =========================================================
# 부족확률이 가장 큰 결과
# =========================================================

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

    if not values:
        return ""

    return max(
        values,
        key=values.get
    )


# =========================================================
# 분석 요약
# =========================================================

def get_summary(
    statistics
):

    if not statistics:
        return {}

    counts = statistics.get(
        "counts",
        {}
    )

    probability = statistics.get(
        "probability",
        {}
    )

    actual = statistics.get(
        "actual",
        {}
    )

    shortage = statistics.get(
        "shortage",
        {}
    )

    return {

        "전체경기수":
            counts.get(
                "total",
                0
            ),

        "승건수":
            counts.get(
                "home",
                0
            ),

        "무건수":
            counts.get(
                "draw",
                0
            ),

        "패건수":
            counts.get(
                "away",
                0
            ),

        "승배당확률":
            probability.get(
                "home",
                0
            ),

        "무배당확률":
            probability.get(
                "draw",
                0
            ),

        "패배당확률":
            probability.get(
                "away",
                0
            ),

        "실제승률":
            actual.get(
                "home",
                0
            ),

        "실제무승률":
            actual.get(
                "draw",
                0
            ),

        "실제패율":
            actual.get(
                "away",
                0
            ),

        "승부족확률":
            shortage.get(
                "home",
                0
            ),

        "무부족확률":
            shortage.get(
                "draw",
                0
            ),

        "패부족확률":
            shortage.get(
                "away",
                0
            ),

        "가장부족한결과":
            get_highest_shortage(
                statistics
            )

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
        "Scoreman Analysis"
    )

    print(
        "========================================"
    )

    print(
        "현재 등록 업체"
    )

    companies = get_company_list()

    for company in companies:

        print(
            "-",
            company
        )

    print(
        "========================================"
    )

    print(
        f"총 업체 수: {len(companies)}"
            )
