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
# 업체명 정규화
# =========================================================

def normalize_company_name(name):

    if name is None:
        return ""

    name = str(name).strip()

    if not name:
        return ""

    key = name.lower()

    aliases = {

        "bet365":
            "Bet365",

        "williamhill":
            "William Hill",

        "william hill":
            "William Hill",

        "william-hill":
            "William Hill",

        "10bet":
            "10Bet",

        "10 bet":
            "10Bet",
    }

    return aliases.get(
        key,
        name
    )


# =========================================================
# 업체 목록
#
# 기본 3개 + DB에 존재하는 모든 업체
# =========================================================

def get_company_list():

    companies = []

    # -----------------------------------------------------
    # 기본 업체 먼저
    # -----------------------------------------------------

    for company in DEFAULT_COMPANIES:

        company = normalize_company_name(
            company
        )

        if (
            company
            and company not in companies
        ):

            companies.append(
                company
            )

    # -----------------------------------------------------
    # DB에서 업체 전부 가져오기
    # -----------------------------------------------------

    try:

        # 가장 정확한 방법:
        # DB의 업체명 DISTINCT 목록 사용

        db_companies = (
            database.get_company_names()
        )

        if db_companies:

            for company in db_companies:

                company = (
                    normalize_company_name(
                        company
                    )
                )

                if (
                    company
                    and company not in companies
                ):

                    companies.append(
                        company
                    )

    except Exception as e:

        print(
            f"[업체 목록 오류] {e}"
        )

        # -------------------------------------------------
        # 혹시 get_company_names()가 없는 구버전 DB라면
        # 전체 배당에서 업체를 직접 추출
        # -------------------------------------------------

        try:

            rows = (
                database.get_all_odds()
            )

            for row in rows:

                try:

                    company = row[
                        "company_name"
                    ]

                except Exception:

                    company = ""

                company = (
                    normalize_company_name(
                        company
                    )
                )

                if (
                    company
                    and company not in companies
                ):

                    companies.append(
                        company
                    )

        except Exception as e2:

            print(
                f"[전체 업체 추출 오류] {e2}"
            )

    return companies


# =========================================================
# 최종배당 숫자 변환
# =========================================================

def to_float(value):

    if value is None:
        return None

    try:

        return float(
            str(value)
            .strip()
            .replace(",", "")
        )

    except Exception:

        return None


# =========================================================
# 배당 동일 여부
# =========================================================

def odds_equal(
    value1,
    value2
):

    value1 = to_float(
        value1
    )

    value2 = to_float(
        value2
    )

    if (
        value1 is None
        or value2 is None
    ):

        return False

    return abs(
        value1 - value2
    ) < 0.000001


# =========================================================
# 입력 배당 정리
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

    for company, odds in (
        company_odds.items()
    ):

        company = (
            normalize_company_name(
                company
            )
        )

        if not company:
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

        if (
            home is None
            or draw is None
            or away is None
        ):

            continue

        result[
            company
        ] = {

            "home":
                home,

            "draw":
                draw,

            "away":
                away
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

    try:

        return (
            database.search_multiple_final_odds(
                company_odds
            )
        )

    except Exception as e:

        print(
            f"[최종배당 검색 오류] {e}"
        )

        return []


# =========================================================
# 경기의 업체별 최종배당
# =========================================================

def get_match_odds(
    schedule_id
):

    result = {}

    try:

        rows = (
            database.get_match_final_odds(
                schedule_id
            )
        )

    except Exception:

        return result

    for row in rows:

        company = (
            normalize_company_name(
                row["company_name"]
            )
        )

        if not company:
            continue

        result[
            company
        ] = {

            "home":
                row["final_home"],

            "draw":
                row["final_draw"],

            "away":
                row["final_away"]
        }

    return result


# =========================================================
# 검색 결과에 업체별 배당 추가
# =========================================================

def enrich_results(
    rows,
    company_odds
):

    results = []

    for row in rows:

        item = dict(
            row
        )

        item[
            "company_odds"
        ] = get_match_odds(
            row["schedule_id"]
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

        company = (
            normalize_company_name(
                company
            )
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
# DB 전체 경기
# =========================================================

def get_all_matches():

    try:

        return database.get_all_matches()

    except Exception as e:

        print(
            f"[전체 경기 조회 오류] {e}"
        )

        return []


# =========================================================
# DB 전체 배당
# =========================================================

def get_all_odds():

    try:

        return database.get_all_odds()

    except Exception as e:

        print(
            f"[전체 배당 조회 오류] {e}"
        )

        return []


# =========================================================
# DB 현황
# =========================================================

def get_database_status():

    try:

        matches = (
            database.get_match_count()
        )

    except Exception:

        matches = 0

    try:

        odds = (
            database.get_odds_count()
        )

    except Exception:

        odds = 0

    companies = (
        get_company_list()
    )

    return {

        "matches":
            matches,

        "odds":
            odds,

        "companies":
            companies,

        "company_count":
            len(companies)
    }


# =========================================================
# 검색 화면용 업체 데이터
# =========================================================

def get_search_companies():

    companies = (
        get_company_list()
    )

    return [

        {
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
        }

        for company in companies
    ]


# =========================================================
# 빈 배당 입력 생성
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
                f"{company}: "
                f"{odds.get('home')} / "
                f"{odds.get('draw')} / "
                f"{odds.get('away')}"
            )


# =========================================================
# 직접 테스트
# =========================================================

if __name__ == "__main__":

    database.init_database()

    print(
        "========================================"
    )

    print(
        "현재 검색 업체 전체 목록"
    )

    print(
        "========================================"
    )

    companies = (
        get_company_list()
    )

    for index, company in enumerate(
        companies,
        start=1
    ):

        print(
            f"{index}. {company}"
        )

    print(
        "========================================"
    )

    print(
        f"총 업체: {len(companies)}개"
        )
