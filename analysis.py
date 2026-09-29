import database


# =========================================================
# 업체 목록
# =========================================================

def get_company_list():

    database.init_database()

    companies = database.get_company_names()

    # -----------------------------------------------------
    # DB에 실제 저장된 업체가 우선
    # -----------------------------------------------------

    result = list(
        companies
    )

    # -----------------------------------------------------
    # 요청한 주요 업체가 아직 DB에 없어도
    # 선택창에서 보이도록 추가
    #
    # 실제 데이터가 없으면 검색 결과는 나오지 않음.
    # 크롤링 후 실제 업체명이 DB에 저장되면
    # 중복 없이 정리됨.
    # -----------------------------------------------------

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

            result.append(
                company
            )

            existing_normalized.add(
                normalized
            )

    return sorted(
        result,
        key=lambda x: str(x).lower()
    )


# =========================================================
# 업체명 정규화
# =========================================================

def normalize_company_name(
    name
):

    if name is None:
        return ""

    value = str(
        name
    ).strip().lower()

    value = value.replace(
        " ",
        ""
    )

    value = value.replace(
        "_",
        ""
    )

    value = value.replace(
        "-",
        ""
    )

    value = value.replace(
        ".",
        ""
    )

    return value


# =========================================================
# 입력값 검증
# =========================================================

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

            return False, (
                f"{company} 배당값이 없습니다."
            )

        odds = input_odds[company]

        for key in [
            "home",
            "draw",
            "away"
        ]:

            if key not in odds:

                return False, (
                    f"{company}의 {key} 배당값이 없습니다."
                )

            try:

                value = float(
                    odds[key]
                )

                if value <= 0:

                    return False, (
                        f"{company} 배당값은 "
                        f"0보다 커야 합니다."
                    )

            except Exception:

                return False, (
                    f"{company} 배당값이 올바르지 않습니다."
                )

    return True, ""


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
                []
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
                []
        }

    results = []

    # -----------------------------------------------------
    # 검색 결과에 업체별 배당 추가
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

        # 정규화 업체명 -> 실제 DB 업체명
        normalized_selected = {}

        for company in selected_companies:

            normalized_selected[
                normalize_company_name(
                    company
                )
            ] = company

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

    return {

        "success":
            True,

        "message":
            "",

        "results":
            results
    }


# =========================================================
# 테스트
# =========================================================

if __name__ == "__main__":

    database.init_database()

    print(
        "업체 목록"
    )

    for company in get_company_list():

        print(
            "-",
            company
        )
