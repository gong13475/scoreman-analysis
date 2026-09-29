import database


# =========================================================
# 기본 업체
# =========================================================

DEFAULT_COMPANIES = [
    "Bet365",
    "William Hill",
    "10Bet",
]


# =========================================================
# 숫자 변환
# =========================================================

def to_float(value):

    if value is None:
        return None

    if isinstance(
        value,
        (int, float)
    ):
        return float(value)

    value = str(value).strip()

    if not value:
        return None

    try:
        return float(
            value.replace(",", "")
        )
    except Exception:
        return None


# =========================================================
# 배당 비교
#
# 1.5 == 1.50
# =========================================================

def odds_equal(
    value1,
    value2
):

    value1 = to_float(value1)
    value2 = to_float(value2)

    if value1 is None or value2 is None:
        return False

    return abs(
        value1 - value2
    ) < 0.000001


# =========================================================
# 업체 목록
# =========================================================

def get_company_list():

    companies = []

    # -----------------------------------------------------
    # 기본 업체
    # -----------------------------------------------------

    for company in DEFAULT_COMPANIES:

        if company not in companies:

            companies.append(
                company
            )

    # -----------------------------------------------------
    # DB 업체
    # -----------------------------------------------------

    try:

        db_companies = (
            database.get_company_names()
        )

    except Exception:

        db_companies = []

    for company in db_companies:

        if not company:
            continue

        company = str(
            company
        ).strip()

        if not company:
            continue

        if company not in companies:

            companies.append(
                company
            )

    return companies


# =========================================================
# 업체명 정규화
# =========================================================

def normalize_company_name(
    name
):

    if name is None:
        return ""

    name = str(
        name
    ).strip()

    aliases = {

        "bet365":
            "Bet365",

        "Bet365":
            "Bet365",

        "williamhill":
            "William Hill",

        "william hill":
            "William Hill",

        "WilliamHill":
            "William Hill",

        "10bet":
            "10Bet",

        "10 bet":
            "10Bet",

        "10Bet":
            "10Bet",
    }

    key = name.lower()

    if key in aliases:

        return aliases[key]

    return name


# =========================================================
# 입력값 정리
# =========================================================

def normalize_company_odds(
    company_odds
):

    result = {}

    if not isinstance(
        company_odds,
        dict
    ):
        return result

    for company_name, odds in company_odds.items():

        company_name = (
            normalize_company_name(
                company_name
            )
        )

        if not company_name:
            continue

        if not isinstance(
            odds,
            dict
        ):
            continue

        home = to_float(
            odds.get("home")
        )

        draw = to_float(
            odds.get("draw")
        )

        away = to_float(
            odds.get("away")
        )

        # 세 값 모두 입력되어야 검색
        if (
            home is None
            or draw is None
            or away is None
        ):
            continue

        result[
            company_name
        ] = {

            "home": home,

            "draw": draw,

            "away": away
        }

    return result


# =========================================================
# 최종배당 검색
# =========================================================

def search_final_odds(
    company_odds
):

    company_odds = (
        normalize_company_odds(
            company_odds
        )
    )

    if not company_odds:

        return []

    # -----------------------------------------------------
    # database.py의 다중 업체 검색 사용
    # -----------------------------------------------------

    try:

        rows = (
            database.search_multiple_final_odds(
                company_odds
            )
        )

        return rows

    except Exception as e:

        print(
            f"[검색 오류] {e}"
        )

        return []


# =========================================================
# 특정 경기의 업체별 배당 가져오기
# =========================================================

def get_match_odds(
    schedule_id
):

    try:

        rows = (
            database.get_match_final_odds(
                schedule_id
            )
        )

        result = {}

        for row in rows:

            company_name = row[
                "company_name"
            ]

            result[
                company_name
            ] = {

                "home":
                    row["final_home"],

                "draw":
                    row["final_draw"],

                "away":
                    row["final_away"]
            }

        return result

    except Exception:

        return {}


# =========================================================
# 검색 결과에 업체별 배당 붙이기
# =========================================================

def enrich_results(
    rows,
    company_odds
):

    results = []

    for row in rows:

        try:

            item = dict(row)

        except Exception:

            item = {
                key: row[key]
                for key in row.keys()
            }

        schedule_id = (
            item.get(
                "schedule_id"
            )
        )

        item[
            "company_odds"
        ] = get_match_odds(
            schedule_id
        )

        results.append(
            item
        )

    return results


# =========================================================
# 최종 검색
# =========================================================

def run_search(
    selected_companies,
    input_odds
):

    if not selected_companies:

        return {

            "success":
                False,

            "message":
                "검색할 업체를 하나 이상 선택하세요.",

            "results":
                []
        }

    company_odds = {}

    for company in selected_companies:

        company = normalize_company_name(
            company
        )

        odds = input_odds.get(
            company,
            {}
        )

        home = to_float(
            odds.get("home")
        )

        draw = to_float(
            odds.get("draw")
        )

        away = to_float(
            odds.get("away")
        )

        if (
            home is None
            or draw is None
            or away is None
        ):

            return {

                "success":
                    False,

                "message":
                    f"{company}의 "
                    "최종 승/무/패 배당을 "
                    "모두 입력하세요.",

                "results":
                    []
            }

        company_odds[
            company
        ] = {

            "home":
                home,

            "draw":
                draw,

            "away":
                away
        }

    # -----------------------------------------------------
    # DB 검색
    # -----------------------------------------------------

    rows = search_final_odds(
        company_odds
    )

    results = enrich_results(
        rows,
        company_odds
    )

    return {

        "success":
            True,

        "message":
            f"{len(results)}경기 검색됨",

        "results":
            results
    }


# =========================================================
# 결과를 보기 좋은 형태로 변환
# =========================================================

def format_result(
    row
):

    result = {}

    result[
        "schedule_id"
    ] = row.get(
        "schedule_id",
        ""
    )

    result[
        "match_date"
    ] = row.get(
        "match_date",
        ""
    )

    result[
        "home_team"
    ] = row.get(
        "home_team",
        ""
    )

    result[
        "away_team"
    ] = row.get(
        "away_team",
        ""
    )

    result[
        "home_score"
    ] = row.get(
        "home_score"
    )

    result[
        "away_score"
    ] = row.get(
        "away_score"
    )

    result[
        "result"
    ] = row.get(
        "result",
        ""
    )

    result[
        "company_odds"
    ] = row.get(
        "company_odds",
        {}
    )

    return result


# =========================================================
# 검색 결과 전체 포맷
# =========================================================

def format_results(
    rows
):

    return [
        format_result(row)
        for row in rows
    ]


# =========================================================
# 전체 경기 조회
# =========================================================

def get_all_matches():

    try:

        return database.get_all_matches()

    except Exception as e:

        print(
            f"[경기 조회 오류] {e}"
        )

        return []


# =========================================================
# 전체 배당 조회
# =========================================================

def get_all_odds():

    try:

        return database.get_all_odds()

    except Exception as e:

        print(
            f"[배당 조회 오류] {e}"
        )

        return []


# =========================================================
# DB 현황
# =========================================================

def get_database_status():

    try:

        match_count = (
            database.get_match_count()
        )

    except Exception:

        match_count = 0

    try:

        odds_count = (
            database.get_odds_count()
        )

    except Exception:

        odds_count = 0

    try:

        companies = (
            database.get_company_names()
        )

    except Exception:

        companies = []

    return {

        "matches":
            match_count,

        "odds":
            odds_count,

        "companies":
            companies,

        "company_count":
            len(companies)
    }


# =========================================================
# 검색용 업체 정보
# =========================================================

def get_search_companies():

    companies = (
        get_company_list()
    )

    result = []

    for company in companies:

        result.append({

            "name":
                company,

            "selected":
                False,

            "home":
                "",

            "draw":
                "",

            "away":
                ""
        })

    return result


# =========================================================
# 업체 입력 데이터 생성
# =========================================================

def create_empty_odds(
    selected_companies
):

    result = {}

    for company in selected_companies:

        company = (
            normalize_company_name(
                company
            )
        )

        result[
            company
        ] = {

            "home":
                "",

            "draw":
                "",

            "away":
                ""
        }

    return result


# =========================================================
# 검색 결과 출력
# =========================================================

def print_results(
    rows
):

    if not rows:

        print(
            "검색 결과가 없습니다."
        )

        return

    print()
    print(
        "========================================"
    )
    print(
        f"검색 결과: {len(rows)}경기"
    )
    print(
        "========================================"
    )

    for index, row in enumerate(
        rows,
        start=1
    ):

        print()

        print(
            f"[{index}] "
            f"{row.get('schedule_id', '')}"
        )

        print(
            f"날짜: "
            f"{row.get('match_date', '')}"
        )

        print(
            f"{row.get('home_team', '')}"
            f" vs "
            f"{row.get('away_team', '')}"
        )

        print(
            f"스코어: "
            f"{row.get('home_score', '-')}"
            f"-"
            f"{row.get('away_score', '-')}"
        )

        print(
            f"결과: "
            f"{row.get('result', '-')}"
        )

        company_odds = (
            row.get(
                "company_odds",
                {}
            )
        )

        for company, odds in (
            company_odds.items()
        ):

            print(
                f"  {company}: "
                f"{odds.get('home', '-')}"
                f" / "
                f"{odds.get('draw', '-')}"
                f" / "
                f"{odds.get('away', '-')}"
            )

    print()
    print(
        "========================================"
    )


# =========================================================
# 직접 실행 테스트
# =========================================================

if __name__ == "__main__":

    database.init_database()

    print(
        "========================================"
    )

    print(
        "Scoreman 최종배당 검색 테스트"
    )

    print(
        "========================================"
    )

    companies = (
        get_company_list()
    )

    print(
        "검색 가능 업체:"
    )

    for company in companies:

        print(
            f" - {company}"
        )

    print()

    print(
        "DB 경기:",
        database.get_match_count()
    )

    print(
        "DB 배당:",
        database.get_odds_count()
    )

    print()

    # -----------------------------------------------------
    # 테스트
    # -----------------------------------------------------

    test_companies = [
        "Bet365"
    ]

    test_odds = {

        "Bet365": {

            "home":
                1.50,

            "draw":
                3.50,

            "away":
                5.00
        }
    }

    result = run_search(
        test_companies,
        test_odds
    )

    print(
        result["message"]
    )

    print_results(
        result["results"]
        )
