# analysis.py

import database


# =========================================================
# 업체 목록
# =========================================================

def get_company_list():
    """
    DB에 실제 저장된 모든 업체명을 반환합니다.
    """

    try:

        companies = database.get_company_names()

        if not companies:
            return []

        # 중복 제거 + 정렬
        result = sorted(
            set(
                str(company).strip()
                for company in companies
                if company
                and str(company).strip()
            ),
            key=lambda x: x.lower()
        )

        return result

    except Exception as e:

        print(
            f"[업체 목록 오류] {e}",
            flush=True
        )

        return []


# =========================================================
# 업체별 저장 개수
# =========================================================

def get_company_counts():
    """
    업체별 최종배당 저장 개수를 반환합니다.

    예:
    {
        "Bet365": 100,
        "WilliamHill": 80,
        "10Bet": 50
    }
    """

    database.init_database()

    conn = database.get_connection()

    try:

        rows = conn.execute(
            """
            SELECT
                company_name,
                COUNT(*) AS count
            FROM odds
            WHERE
                company_name IS NOT NULL
                AND TRIM(company_name) <> ''
            GROUP BY
                company_name
            ORDER BY
                company_name
            """
        ).fetchall()

        result = {}

        for row in rows:

            company = str(
                row["company_name"]
            ).strip()

            if not company:
                continue

            result[company] = int(
                row["count"]
            )

        return result

    finally:

        conn.close()


# =========================================================
# 특정 업체 저장 개수
# =========================================================

def get_company_count(company_name):

    database.init_database()

    conn = database.get_connection()

    try:

        row = conn.execute(
            """
            SELECT
                COUNT(*) AS count
            FROM odds
            WHERE
                LOWER(TRIM(company_name))
                =
                LOWER(TRIM(?))
            """,
            (
                str(company_name),
            )
        ).fetchone()

        if row is None:
            return 0

        return int(
            row["count"]
        )

    finally:

        conn.close()


# =========================================================
# 선택 업체 저장 개수
# =========================================================

def get_selected_company_counts(
    companies
):

    if not companies:
        return {}

    counts = (
        get_company_counts()
    )

    result = {}

    for company in companies:

        company = str(
            company
        ).strip()

        if not company:
            continue

        # 대소문자 차이까지 대응
        count = 0

        for db_company, db_count in counts.items():

            if (
                db_company.strip().lower()
                ==
                company.lower()
            ):

                count = db_count
                break

        result[company] = count

    return result


# =========================================================
# 업체명 정규화
# =========================================================

def normalize_company_name(
    company_name
):

    if company_name is None:
        return ""

    return (
        str(company_name)
        .strip()
        .lower()
    )


# =========================================================
# 배당값 정규화
# =========================================================

def normalize_odds(
    odds
):

    if not isinstance(
        odds,
        dict
    ):
        return None

    try:

        home = float(
            odds["home"]
        )

        draw = float(
            odds["draw"]
        )

        away = float(
            odds["away"]
        )

    except Exception:

        return None

    return {

        "home": home,

        "draw": draw,

        "away": away
    }


# =========================================================
# 검색 조건 생성
# =========================================================

def build_company_odds(
    selected_companies,
    input_odds
):

    if not selected_companies:
        return {}

    if not isinstance(
        input_odds,
        dict
    ):
        return {}

    company_odds = {}

    for company in selected_companies:

        company_name = str(
            company
        ).strip()

        if not company_name:
            continue

        odds = input_odds.get(
            company
        )

        if odds is None:

            # 대소문자 차이 대응
            target = normalize_company_name(
                company
            )

            for key, value in input_odds.items():

                if (
                    normalize_company_name(
                        key
                    )
                    ==
                    target
                ):

                    odds = value
                    break

        normalized = normalize_odds(
            odds
        )

        if normalized is None:
            continue

        company_odds[
            company_name
        ] = normalized

    return company_odds


# =========================================================
# 최종배당 검색
# =========================================================

def run_search(
    selected_companies,
    input_odds
):

    try:

        # -------------------------------------------------
        # 업체 확인
        # -------------------------------------------------

        if not selected_companies:

            return {

                "success": False,

                "message":
                    "검색할 업체를 하나 이상 선택하세요.",

                "results": []
            }

        # -------------------------------------------------
        # 검색 조건
        # -------------------------------------------------

        company_odds = (
            build_company_odds(
                selected_companies,
                input_odds
            )
        )

        if not company_odds:

            return {

                "success": False,

                "message":
                    "검색할 최종배당 값이 없습니다.",

                "results": []
            }

        # -------------------------------------------------
        # DB 완전일치 검색
        # -------------------------------------------------

        rows = (
            database.search_multiple_final_odds(
                company_odds
            )
        )

        results = []

        # -------------------------------------------------
        # 검색 결과에 업체별 배당 붙이기
        # -------------------------------------------------

        for row in rows:

            item = dict(
                row
            )

            item[
                "company_odds"
            ] = {}

            match_odds = (
                database.get_match_final_odds(
                    row["schedule_id"]
                )
            )

            for odds_row in match_odds:

                company_name = str(
                    odds_row["company_name"]
                ).strip()

                item[
                    "company_odds"
                ][company_name] = {

                    "home":
                        odds_row[
                            "final_home"
                        ],

                    "draw":
                        odds_row[
                            "final_draw"
                        ],

                    "away":
                        odds_row[
                            "final_away"
                        ]
                }

            results.append(
                item
            )

        return {

            "success": True,

            "message":
                f"{len(results):,}경기 검색 완료",

            "results": results,

            "count":
                len(results),

            "companies":
                list(company_odds.keys())
        }

    except Exception as e:

        return {

            "success": False,

            "message":
                f"검색 오류: {e}",

            "results": []
        }


# =========================================================
# 단일 업체 검색
# =========================================================

def search_company(
    company_name,
    home,
    draw,
    away
):

    try:

        rows = (
            database.search_final_odds(
                company_name=company_name,
                final_home=home,
                final_draw=draw,
                final_away=away
            )
        )

        results = []

        for row in rows:

            item = dict(
                row
            )

            results.append(
                item
            )

        return results

    except Exception as e:

        print(
            f"[단일 업체 검색 오류] {e}",
            flush=True
        )

        return []


# =========================================================
# 여러 업체 검색
# =========================================================

def search_companies(
    company_odds
):

    try:

        if not company_odds:
            return []

        normalized = {}

        for company, odds in (
            company_odds.items()
        ):

            value = normalize_odds(
                odds
            )

            if value is None:
                continue

            normalized[
                str(company).strip()
            ] = value

        if not normalized:
            return []

        rows = (
            database.search_multiple_final_odds(
                normalized
            )
        )

        results = []

        for row in rows:

            item = dict(
                row
            )

            item[
                "company_odds"
            ] = {}

            odds_rows = (
                database.get_match_final_odds(
                    row["schedule_id"]
                )
            )

            for odds_row in odds_rows:

                name = str(
                    odds_row[
                        "company_name"
                    ]
                ).strip()

                item[
                    "company_odds"
                ][name] = {

                    "home":
                        odds_row[
                            "final_home"
                        ],

                    "draw":
                        odds_row[
                            "final_draw"
                        ],

                    "away":
                        odds_row[
                            "final_away"
                        ]
                }

            results.append(
                item
            )

        return results

    except Exception as e:

        print(
            f"[다중 업체 검색 오류] {e}",
            flush=True
        )

        return []


# =========================================================
# 전체 업체 + 저장 개수
# =========================================================

def get_company_summary():

    counts = (
        get_company_counts()
    )

    result = []

    for company in sorted(
        counts.keys(),
        key=lambda x: x.lower()
    ):

        result.append({

            "company_name":
                company,

            "count":
                counts[company]
        })

    return result


# =========================================================
# 업체별 저장 경기 수
# =========================================================

def get_company_match_count(
    company_name
):

    database.init_database()

    conn = database.get_connection()

    try:

        row = conn.execute(
            """
            SELECT
                COUNT(
                    DISTINCT schedule_id
                ) AS count
            FROM odds
            WHERE
                LOWER(
                    TRIM(company_name)
                )
                =
                LOWER(
                    TRIM(?)
                )
            """,
            (
                str(company_name),
            )
        ).fetchone()

        if row is None:
            return 0

        return int(
            row["count"]
        )

    finally:

        conn.close()


# =========================================================
# 업체별 저장 현황
# =========================================================

def get_company_statistics():

    database.init_database()

    conn = database.get_connection()

    try:

        rows = conn.execute(
            """
            SELECT

                company_name,

                COUNT(*) AS odds_count,

                COUNT(
                    DISTINCT schedule_id
                ) AS match_count

            FROM odds

            WHERE
                company_name IS NOT NULL
                AND TRIM(company_name) <> ''

            GROUP BY
                company_name

            ORDER BY
                company_name
            """
        ).fetchall()

        result = []

        for row in rows:

            result.append({

                "company_name":
                    row["company_name"],

                "odds_count":
                    int(
                        row["odds_count"]
                    ),

                "match_count":
                    int(
                        row["match_count"]
                    )
            })

        return result

    finally:

        conn.close()


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
        "최종배당 분석"
    )

    print(
        "========================================"
    )

    print(
        "업체 목록"
    )

    companies = (
        get_company_list()
    )

    for company in companies:

        count = (
            get_company_count(
                company
            )
        )

        match_count = (
            get_company_match_count(
                company
            )
        )

        print(
            f" - {company}: "
            f"배당 {count:,}개 / "
            f"경기 {match_count:,}개"
        )

    print(
        "========================================"
        )
