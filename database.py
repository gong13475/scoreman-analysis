# ============================================================
# database.py
# 스코어맨 분석기
# SQLite → Supabase 영구저장 버전
#
# 기존 scoreman_crawler.py / analysis.py 호환 목적
# ============================================================

import streamlit as st
from supabase import create_client


# =========================================================
# Supabase 연결
# =========================================================

@st.cache_resource
def get_connection():

    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")

    if not url:
        raise RuntimeError(
            "SUPABASE_URL이 없습니다.\n"
            "Streamlit Secrets에 SUPABASE_URL을 입력하세요."
        )

    if not key:
        raise RuntimeError(
            "SUPABASE_KEY가 없습니다.\n"
            "Streamlit Secrets에 SUPABASE_KEY를 입력하세요."
        )

    return create_client(
        url,
        key
    )


# =========================================================
# DB 초기화 / 연결 확인
# =========================================================

def init_database():

    try:

        supabase = get_connection()

        supabase.table(
            "matches"
        ).select(
            "schedule_id"
        ).limit(
            1
        ).execute()

        return True

    except Exception as e:

        print("Supabase 연결 오류:", e)

        return False


# =========================================================
# DB 상태
# =========================================================

def get_database_status():

    supabase = get_connection()

    # 경기 수
    match_result = (
        supabase
        .table("matches")
        .select(
            "schedule_id",
            count="exact"
        )
        .execute()
    )

    match_count = (
        match_result.count
        if match_result.count is not None
        else 0
    )

    # 배당 수
    odds_result = (
        supabase
        .table("odds")
        .select(
            "id",
            count="exact"
        )
        .execute()
    )

    odds_count = (
        odds_result.count
        if odds_result.count is not None
        else 0
    )

    # 업체 목록
    bookmaker_result = (
        supabase
        .table("odds")
        .select("bookmaker")
        .execute()
    )

    companies = set()

    for row in bookmaker_result.data or []:

        name = row.get("bookmaker")

        if name:
            companies.add(
                str(name)
            )

    return {
        "matches": int(match_count),
        "odds": int(odds_count),
        "bookmakers": len(companies),
        "db_exists": True,
        "db_file": "Supabase PostgreSQL"
    }


# =========================================================
# 경기 저장
# =========================================================

def save_match(
    schedule_id,
    match_date,
    home_team,
    away_team,
    home_score,
    away_score,
    result,
    source="Scoreman"
):

    supabase = get_connection()

    data = {
        "schedule_id": str(schedule_id),
        "match_date": match_date,
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
        "result": result,
        "source": source
    }

    return (
        supabase
        .table("matches")
        .upsert(
            data,
            on_conflict="schedule_id"
        )
        .execute()
    )


# =========================================================
# 단일 배당 저장
#
# 기존 함수명 유지
# =========================================================

def save_odds(
    schedule_id,
    company_id,
    company_name,
    final_home,
    final_draw,
    final_away
):

    supabase = get_connection()

    data = {
        "schedule_id": str(schedule_id),
        "bookmaker": str(
            company_name or ""
        ),
        "home_odds": (
            float(final_home)
            if final_home is not None
            else None
        ),
        "draw_odds": (
            float(final_draw)
            if final_draw is not None
            else None
        ),
        "away_odds": (
            float(final_away)
            if final_away is not None
            else None
        ),
        "odds_type": "final"
    }

    return (
        supabase
        .table("odds")
        .upsert(
            data,
            on_conflict=(
                "schedule_id,"
                "bookmaker,"
                "odds_type"
            )
        )
        .execute()
    )


# =========================================================
# 경기 + 배당 일괄 저장
#
# 스코어맨 크롤러 핵심 저장 함수
# =========================================================

def save_match_with_odds(
    match,
    odds_list
):

    supabase = get_connection()

    schedule_id = str(
        match["schedule_id"]
    )

    # -----------------------------------------------------
    # 경기 저장
    # -----------------------------------------------------

    match_data = {
        "schedule_id": schedule_id,
        "match_date": match.get(
            "match_date",
            ""
        ),
        "home_team": match.get(
            "home_team",
            ""
        ),
        "away_team": match.get(
            "away_team",
            ""
        ),
        "home_score": match.get(
            "home_score"
        ),
        "away_score": match.get(
            "away_score"
        ),
        "result": match.get(
            "result",
            ""
        ),
        "source": "Scoreman"
    }

    (
        supabase
        .table("matches")
        .upsert(
            match_data,
            on_conflict="schedule_id"
        )
        .execute()
    )

    # -----------------------------------------------------
    # 배당 저장
    # -----------------------------------------------------

    rows = []

    for odds in odds_list:

        company_name = str(
            odds.get(
                "company_name",
                ""
            )
            or ""
        )

        if not company_name:
            continue

        rows.append({

            "schedule_id":
                schedule_id,

            "bookmaker":
                company_name,

            "home_odds":
                odds.get(
                    "final_home"
                ),

            "draw_odds":
                odds.get(
                    "final_draw"
                ),

            "away_odds":
                odds.get(
                    "final_away"
                ),

            "odds_type":
                "final"
        })

    # -----------------------------------------------------
    # 배당 일괄 저장
    # -----------------------------------------------------

    if rows:

        (
            supabase
            .table("odds")
            .upsert(
                rows,
                on_conflict=(
                    "schedule_id,"
                    "bookmaker,"
                    "odds_type"
                )
            )
            .execute()
        )

    return len(rows)


# =========================================================
# 경기 조회
# =========================================================

def get_match(
    schedule_id
):

    supabase = get_connection()

    result = (
        supabase
        .table("matches")
        .select("*")
        .eq(
            "schedule_id",
            str(schedule_id)
        )
        .limit(1)
        .execute()
    )

    if result.data:

        return result.data[0]

    return None


# =========================================================
# 전체 경기
# =========================================================

def get_all_matches():

    supabase = get_connection()

    result = (
        supabase
        .table("matches")
        .select("*")
        .order(
            "match_date",
            desc=True
        )
        .execute()
    )

    return result.data or []


# =========================================================
# 전체 배당
# =========================================================

def get_all_odds():

    supabase = get_connection()

    result = (
        supabase
        .table("odds")
        .select("*")
        .order(
            "schedule_id",
            desc=True
        )
        .execute()
    )

    return result.data or []


# =========================================================
# 특정 경기 배당
# =========================================================

def get_match_final_odds(
    schedule_id
):

    supabase = get_connection()

    result = (
        supabase
        .table("odds")
        .select("*")
        .eq(
            "schedule_id",
            str(schedule_id)
        )
        .eq(
            "odds_type",
            "final"
        )
        .order(
            "bookmaker"
        )
        .execute()
    )

    return result.data or []


# =========================================================
# 경기 수
# =========================================================

def get_match_count():

    supabase = get_connection()

    result = (
        supabase
        .table("matches")
        .select(
            "schedule_id",
            count="exact"
        )
        .execute()
    )

    return int(
        result.count or 0
    )


# =========================================================
# 배당 수
# =========================================================

def get_odds_count():

    supabase = get_connection()

    result = (
        supabase
        .table("odds")
        .select(
            "id",
            count="exact"
        )
        .execute()
    )

    return int(
        result.count or 0
    )


# =========================================================
# 업체 목록
#
# 기존 company_name 함수 유지
# =========================================================

def get_company_names():

    supabase = get_connection()

    result = (
        supabase
        .table("odds")
        .select("bookmaker")
        .execute()
    )

    names = set()

    for row in result.data or []:

        name = row.get(
            "bookmaker"
        )

        if name:

            names.add(
                str(name)
            )

    return sorted(names)


# =========================================================
# 업체별 저장량
# =========================================================

def get_company_counts():

    supabase = get_connection()

    result = (
        supabase
        .table("odds")
        .select("bookmaker")
        .execute()
    )

    counts = {}

    for row in result.data or []:

        name = row.get(
            "bookmaker"
        )

        if not name:
            continue

        name = str(name)

        counts[name] = (
            counts.get(name, 0) + 1
        )

    return dict(
        sorted(
            counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
    )


# =========================================================
# 동일 배당 검색
#
# 여러 업체가 같은 배당을 가진 경기 검색
# =========================================================

def search_multiple_final_odds(
    company_odds
):

    if not company_odds:

        return []

    supabase = get_connection()

    schedule_ids = None

    tolerance = 0.00001

    # -----------------------------------------------------
    # 업체별 검색
    # -----------------------------------------------------

    for company_name, odds in (
        company_odds.items()
    ):

        home = float(
            odds["home"]
        )

        draw = float(
            odds["draw"]
        )

        away = float(
            odds["away"]
        )

        home_min = (
            home - tolerance
        )

        home_max = (
            home + tolerance
        )

        draw_min = (
            draw - tolerance
        )

        draw_max = (
            draw + tolerance
        )

        away_min = (
            away - tolerance
        )

        away_max = (
            away + tolerance
        )

        result = (
            supabase
            .table("odds")
            .select("schedule_id")
            .eq(
                "bookmaker",
                company_name
            )
            .gte(
                "home_odds",
                home_min
            )
            .lte(
                "home_odds",
                home_max
            )
            .gte(
                "draw_odds",
                draw_min
            )
            .lte(
                "draw_odds",
                draw_max
            )
            .gte(
                "away_odds",
                away_min
            )
            .lte(
                "away_odds",
                away_max
            )
            .eq(
                "odds_type",
                "final"
            )
            .execute()
        )

        ids = {
            str(row["schedule_id"])
            for row in (
                result.data or []
            )
        }

        if schedule_ids is None:

            schedule_ids = ids

        else:

            schedule_ids &= ids

        if not schedule_ids:

            return []

    # -----------------------------------------------------
    # 경기 정보 가져오기
    # -----------------------------------------------------

    if not schedule_ids:

        return []

    result = (
        supabase
        .table("matches")
        .select("*")
        .in_(
            "schedule_id",
            list(schedule_ids)
        )
        .order(
            "match_date",
            desc=True
        )
        .execute()
    )

    return result.data or []


# =========================================================
# DB 초기화
#
# 기존 clear_database 함수 유지
# =========================================================

def clear_database():

    supabase = get_connection()

    # 배당 먼저 삭제
    (
        supabase
        .table("odds")
        .delete()
        .neq(
            "id",
            0
        )
        .execute()
    )

    # 경기 삭제
    (
        supabase
        .table("matches")
        .delete()
        .neq(
            "id",
            0
        )
        .execute()
    )


# =========================================================
# 경기 존재 확인
# =========================================================

def match_exists(
    schedule_id
):

    return (
        get_match(schedule_id)
        is not None
    )


# =========================================================
# 배당 존재 확인
# =========================================================

def odds_exists(
    schedule_id,
    company_name
):

    supabase = get_connection()

    result = (
        supabase
        .table("odds")
        .select("id")
        .eq(
            "schedule_id",
            str(schedule_id)
        )
        .eq(
            "bookmaker",
            str(company_name)
        )
        .eq(
            "odds_type",
            "final"
        )
        .limit(1)
        .execute()
    )

    return bool(
        result.data
    )


# =========================================================
# 결과별 경기 조회
# =========================================================

def get_matches_by_result(
    result_value
):

    supabase = get_connection()

    result = (
        supabase
        .table("matches")
        .select("*")
        .eq(
            "result",
            result_value
        )
        .order(
            "match_date",
            desc=True
        )
        .execute()
    )

    return result.data or []


# =========================================================
# 특정 업체 배당
# =========================================================

def get_odds_by_company(
    company_name
):

    supabase = get_connection()

    result = (
        supabase
        .table("odds")
        .select("*")
        .eq(
            "bookmaker",
            company_name
        )
        .eq(
            "odds_type",
            "final"
        )
        .order(
            "schedule_id",
            desc=True
        )
        .execute()
    )

    return result.data or []


# =========================================================
# 테스트
# =========================================================

if __name__ == "__main__":

    try:

        ok = init_database()

        if ok:

            print(
                "Supabase 연결 성공"
            )

            print(
                get_database_status()
            )

        else:

            print(
                "Supabase 연결 실패"
            )

    except Exception as e:

        print(
            "오류:",
            e
            )
