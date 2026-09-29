import sqlite3
import pandas as pd

from database import DB_FILE


# =========================================================
# DB 연결
# =========================================================

def get_connection():

    return sqlite3.connect(DB_FILE)


# =========================================================
# 전체 분석 데이터
# =========================================================

def get_all_analysis_data():

    conn = get_connection()

    query = """
        SELECT
            m.schedule_id,
            m.match_date,
            m.home_team,
            m.away_team,
            m.home_score,
            m.away_score,
            m.result,
            m.source,

            o.company_id,
            o.company_name,

            o.initial_home,
            o.initial_draw,
            o.initial_away,

            o.final_home,
            o.final_draw,
            o.final_away

        FROM matches m

        INNER JOIN odds o
            ON m.schedule_id = o.schedule_id

        WHERE m.result IN ('승', '무', '패')

        ORDER BY m.match_date DESC
    """

    try:

        df = pd.read_sql_query(
            query,
            conn
        )

    finally:

        conn.close()

    if df.empty:
        return df

    numeric_columns = [

        "initial_home",
        "initial_draw",
        "initial_away",

        "final_home",
        "final_draw",
        "final_away",

        "home_score",
        "away_score"

    ]

    for column in numeric_columns:

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

    return df


# =========================================================
# 회사 목록
# =========================================================

def get_company_list():

    conn = get_connection()

    query = """
        SELECT
            company_id,
            company_name,
            COUNT(*) AS match_count

        FROM odds

        WHERE company_name IS NOT NULL
        AND TRIM(company_name) != ''

        GROUP BY
            company_id,
            company_name

        ORDER BY
            company_name
    """

    try:

        df = pd.read_sql_query(
            query,
            conn
        )

    finally:

        conn.close()

    return df


# =========================================================
# 회사명 목록
# =========================================================

def get_company_names():

    df = get_company_list()

    if df.empty:
        return []

    return (
        df["company_name"]
        .dropna()
        .astype(str)
        .drop_duplicates()
        .tolist()
    )


# =========================================================
# 경기 중복 제거
# =========================================================

def get_unique_match_data(df):

    if df is None or df.empty:

        return pd.DataFrame()

    return (
        df
        .drop_duplicates(
            subset=["schedule_id"]
        )
        .copy()
    )


# =========================================================
# 숫자 정규화
#
# 1.50과 1.5를 같은 값으로 처리
# =========================================================

def normalize_odds(value):

    if value is None:
        return None

    try:

        return round(
            float(value),
            2
        )

    except Exception:

        return None


# =========================================================
# 완전 동일배당 검색
# =========================================================

def find_exact_odds(
    df,
    company_name,
    initial_home,
    initial_draw,
    initial_away,
    final_home,
    final_draw,
    final_away
):

    if df is None or df.empty:

        return pd.DataFrame()

    required_columns = [

        "company_name",

        "initial_home",
        "initial_draw",
        "initial_away",

        "final_home",
        "final_draw",
        "final_away"

    ]

    for column in required_columns:

        if column not in df.columns:

            return pd.DataFrame()

    target_initial_home = normalize_odds(
        initial_home
    )

    target_initial_draw = normalize_odds(
        initial_draw
    )

    target_initial_away = normalize_odds(
        initial_away
    )

    target_final_home = normalize_odds(
        final_home
    )

    target_final_draw = normalize_odds(
        final_draw
    )

    target_final_away = normalize_odds(
        final_away
    )

    temp = df.copy()

    # =====================================================
    # 회사명 정확히 일치
    # =====================================================

    temp = temp[
        temp["company_name"]
        .astype(str)
        .str.strip()
        ==
        str(company_name).strip()
    ].copy()

    if temp.empty:

        return pd.DataFrame()

    # =====================================================
    # 배당 숫자 정규화
    # =====================================================

    odds_columns = [

        "initial_home",
        "initial_draw",
        "initial_away",

        "final_home",
        "final_draw",
        "final_away"

    ]

    for column in odds_columns:

        temp[column] = pd.to_numeric(
            temp[column],
            errors="coerce"
        ).round(2)

    # =====================================================
    # 완전 동일
    #
    # 초기 3개
    # +
    # 최종 3개
    #
    # 총 6개 모두 일치
    # =====================================================

    condition = (

        (temp["initial_home"] == target_initial_home)

        &

        (temp["initial_draw"] == target_initial_draw)

        &

        (temp["initial_away"] == target_initial_away)

        &

        (temp["final_home"] == target_final_home)

        &

        (temp["final_draw"] == target_final_draw)

        &

        (temp["final_away"] == target_final_away)

    )

    result = temp[
        condition
    ].copy()

    return result.sort_values(
        "match_date",
        ascending=False
    )


# =========================================================
# 여러 회사의 완전 동일배당 검색
#
# 선택한 모든 회사가
# 같은 경기에서 각각 입력값과 완전히 일치해야 함
# =========================================================

def find_exact_multi_company(
    df,
    company_inputs
):

    if df is None or df.empty:

        return pd.DataFrame()

    if not company_inputs:

        return pd.DataFrame()

    all_matches = []

    # =====================================================
    # 회사별 검색
    # =====================================================

    for company_name, values in company_inputs.items():

        company_result = find_exact_odds(

            df=df,

            company_name=company_name,

            initial_home=
                values["initial_home"],

            initial_draw=
                values["initial_draw"],

            initial_away=
                values["initial_away"],

            final_home=
                values["final_home"],

            final_draw=
                values["final_draw"],

            final_away=
                values["final_away"]

        )

        if company_result.empty:

            return pd.DataFrame()

        all_matches.append(
            company_result
        )

    # =====================================================
    # 첫 번째 회사 결과
    # =====================================================

    base = all_matches[0].copy()

    # =====================================================
    # 나머지 회사와 경기ID 교집합
    # =====================================================

    for other in all_matches[1:]:

        common_ids = set(
            base["schedule_id"]
        ).intersection(
            set(other["schedule_id"])
        )

        base = base[
            base["schedule_id"].isin(
                common_ids
            )
        ].copy()

        if base.empty:

            return pd.DataFrame()

    # =====================================================
    # 회사별 배당 정보 표시
    # =====================================================

    result = base.copy()

    for index, company_df in enumerate(
        all_matches
    ):

        company_name = str(
            company_df.iloc[0]["company_name"]
        )

        if index == 0:

            continue

        # 해당 회사 데이터와 경기ID 기준 병합
        extra = company_df[
            [
                "schedule_id",

                "initial_home",
                "initial_draw",
                "initial_away",

                "final_home",
                "final_draw",
                "final_away"

            ]
        ].copy()

        suffix = (
            "_"
            +
            str(index + 1)
        )

        result = result.merge(

            extra,

            on="schedule_id",

            how="inner",

            suffixes=(
                "",
                suffix
            )
        )

    return result.sort_values(
        "match_date",
        ascending=False
    )


# =========================================================
# 입력 배당과 완전 동일한 경기 찾기
#
# 단일 회사용 편의 함수
# =========================================================

def find_exact_match(
    df,
    company_name,
    initial_home,
    initial_draw,
    initial_away,
    final_home,
    final_draw,
    final_away
):

    return find_exact_odds(

        df=df,

        company_name=company_name,

        initial_home=initial_home,
        initial_draw=initial_draw,
        initial_away=initial_away,

        final_home=final_home,
        final_draw=final_draw,
        final_away=final_away

    )


# =========================================================
# 완전 동일배당 결과 통계
# =========================================================

def calculate_exact_result_stats(
    exact_df
):

    if exact_df is None or exact_df.empty:

        return {

            "전체": 0,

            "승": {
                "count": 0,
                "percent": 0
            },

            "무": {
                "count": 0,
                "percent": 0
            },

            "패": {
                "count": 0,
                "percent": 0
            }

        }

    temp = (
        exact_df
        .drop_duplicates(
            subset=["schedule_id"]
        )
        .copy()
    )

    total = len(temp)

    stats = {
        "전체": total
    }

    for result in [
        "승",
        "무",
        "패"
    ]:

        count = int(
            (
                temp["result"]
                ==
                result
            ).sum()
        )

        percent = (

            round(
                count /
                total *
                100,
                2
            )

            if total

            else 0

        )

        stats[result] = {

            "count":
                count,

            "percent":
                percent
        }

    return stats


# =========================================================
# 추천
# =========================================================

def get_recommendation(
    stats
):

    if not stats:

        return None

    values = {

        "승":
            stats["승"]["percent"],

        "무":
            stats["무"]["percent"],

        "패":
            stats["패"]["percent"]

    }

    return max(
        values,
        key=values.get
    )


# =========================================================
# 완전 동일 여부 확인
# =========================================================

def is_exact_odds_match(
    row,
    initial_home,
    initial_draw,
    initial_away,
    final_home,
    final_draw,
    final_away
):

    try:

        return (

            normalize_odds(
                row["initial_home"]
            )
            ==
            normalize_odds(
                initial_home
            )

            and

            normalize_odds(
                row["initial_draw"]
            )
            ==
            normalize_odds(
                initial_draw
            )

            and

            normalize_odds(
                row["initial_away"]
            )
            ==
            normalize_odds(
                initial_away
            )

            and

            normalize_odds(
                row["final_home"]
            )
            ==
            normalize_odds(
                final_home
            )

            and

            normalize_odds(
                row["final_draw"]
            )
            ==
            normalize_odds(
                final_draw
            )

            and

            normalize_odds(
                row["final_away"]
            )
            ==
            normalize_odds(
                final_away
            )

        )

    except Exception:

        return False


# =========================================================
# 실행 테스트
# =========================================================

if __name__ == "__main__":

    print(
        "================================"
    )

    print(
        "완전 동일배당 분석"
    )

    print(
        "================================"
    )

    df = get_all_analysis_data()

    print(
        "전체 배당 행:",
        len(df)
    )

    companies = get_company_names()

    print(
        "배당 업체:",
        len(companies)
    )

    for company in companies:

        print(
            "-",
            company
        )

    print(
        "================================"
    )
