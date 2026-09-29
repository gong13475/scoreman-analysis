import sqlite3
import pandas as pd
import numpy as np

from database import DB_FILE


# =========================================================
# DB 연결
# =========================================================

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


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
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()

    if df.empty:
        return df

    number_columns = [
        "initial_home",
        "initial_draw",
        "initial_away",
        "final_home",
        "final_draw",
        "final_away",
        "home_score",
        "away_score"
    ]

    for column in number_columns:

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

    # 초기배당이 정상적인 경기만
    df = df[
        (df["initial_home"] > 1) &
        (df["initial_draw"] > 1) &
        (df["initial_away"] > 1)
    ].copy()

    if df.empty:
        return df

    # =====================================================
    # 초기배당 확률
    # =====================================================

    inverse_home = 1 / df["initial_home"]
    inverse_draw = 1 / df["initial_draw"]
    inverse_away = 1 / df["initial_away"]

    total = (
        inverse_home +
        inverse_draw +
        inverse_away
    )

    df["승확률"] = (
        inverse_home / total * 100
    ).round(2)

    df["무확률"] = (
        inverse_draw / total * 100
    ).round(2)

    df["패확률"] = (
        inverse_away / total * 100
    ).round(2)

    # =====================================================
    # 최종배당 확률
    # =====================================================

    valid_final = (
        (df["final_home"] > 1) &
        (df["final_draw"] > 1) &
        (df["final_away"] > 1)
    )

    df["최종승확률"] = np.nan
    df["최종무확률"] = np.nan
    df["최종패확률"] = np.nan

    final_home = 1 / df.loc[
        valid_final,
        "final_home"
    ]

    final_draw = 1 / df.loc[
        valid_final,
        "final_draw"
    ]

    final_away = 1 / df.loc[
        valid_final,
        "final_away"
    ]

    final_total = (
        final_home +
        final_draw +
        final_away
    )

    df.loc[
        valid_final,
        "최종승확률"
    ] = (
        final_home /
        final_total *
        100
    ).round(2)

    df.loc[
        valid_final,
        "최종무확률"
    ] = (
        final_draw /
        final_total *
        100
    ).round(2)

    df.loc[
        valid_final,
        "최종패확률"
    ] = (
        final_away /
        final_total *
        100
    ).round(2)

    # =====================================================
    # 배당상 예상
    # =====================================================

    df["배당예상"] = np.select(
        [
            (
                (df["initial_home"] <= df["initial_draw"]) &
                (df["initial_home"] <= df["initial_away"])
            ),

            (
                (df["initial_draw"] < df["initial_home"]) &
                (df["initial_draw"] <= df["initial_away"])
            )
        ],
        [
            "승",
            "무"
        ],
        default="패"
    )

    df["적중"] = (
        df["배당예상"] ==
        df["result"]
    )

    return df


# =========================================================
# 경기 중복 제거
# =========================================================

def get_unique_match_data(df):

    if df is None or df.empty:
        return pd.DataFrame()

    temp = df.copy()

    return temp.drop_duplicates(
        subset=["schedule_id"]
    ).copy()


# =========================================================
# 숫자 정규화
# =========================================================

def normalize_odds(value):

    if value is None:
        return None

    try:

        value = float(value)

        # DB와 입력값의 소수점 오차 방지
        return round(value, 2)

    except Exception:

        return None


# =========================================================
# 완전 동일 배당 검색
# =========================================================

def find_exact_odds_matches(
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

    temp = df.copy()

    # -----------------------------------------------------
    # 업체명 필터
    # -----------------------------------------------------

    if company_name:

        temp = temp[
            temp["company_name"].astype(str).str.strip()
            ==
            str(company_name).strip()
        ].copy()

    if temp.empty:

        return pd.DataFrame()

    # -----------------------------------------------------
    # 숫자 정규화
    # -----------------------------------------------------

    columns = [
        "initial_home",
        "initial_draw",
        "initial_away",
        "final_home",
        "final_draw",
        "final_away"
    ]

    for column in columns:

        temp[column] = pd.to_numeric(
            temp[column],
            errors="coerce"
        ).round(2)

    targets = {

        "initial_home":
            normalize_odds(initial_home),

        "initial_draw":
            normalize_odds(initial_draw),

        "initial_away":
            normalize_odds(initial_away),

        "final_home":
            normalize_odds(final_home),

        "final_draw":
            normalize_odds(final_draw),

        "final_away":
            normalize_odds(final_away)
    }

    # -----------------------------------------------------
    # 완전 동일 조건
    # -----------------------------------------------------

    condition = pd.Series(
        True,
        index=temp.index
    )

    for column, value in targets.items():

        if value is None:

            return pd.DataFrame()

        condition &= (
            temp[column] == value
        )

    result = temp[
        condition
    ].copy()

    # 같은 경기가 업체별 중복으로 잡히지 않도록
    result = result.drop_duplicates(
        subset=["schedule_id"]
    )

    return result.sort_values(
        "match_date",
        ascending=False
    )


# =========================================================
# 여러 업체 완전 동일 검색
# =========================================================

def find_exact_matches_multiple_companies(
    df,
    company_inputs
):

    if df is None or df.empty:
        return pd.DataFrame()

    if not company_inputs:
        return pd.DataFrame()

    result_frames = []

    for item in company_inputs:

        company_name = item.get(
            "company_name"
        )

        matches = find_exact_odds_matches(

            df=df,

            company_name=company_name,

            initial_home=item.get(
                "initial_home"
            ),

            initial_draw=item.get(
                "initial_draw"
            ),

            initial_away=item.get(
                "initial_away"
            ),

            final_home=item.get(
                "final_home"
            ),

            final_draw=item.get(
                "final_draw"
            ),

            final_away=item.get(
                "final_away"
            )
        )

        if matches.empty:
            continue

        matches = matches.copy()

        matches["검색업체"] = company_name

        result_frames.append(
            matches
        )

    if not result_frames:

        return pd.DataFrame()

    result = pd.concat(
        result_frames,
        ignore_index=True
    )

    return result


# =========================================================
# 여러 업체가 모두 완전 동일한 경기만 찾기
# =========================================================

def find_matches_matching_all_companies(
    df,
    company_inputs
):

    if df is None or df.empty:
        return pd.DataFrame()

    if not company_inputs:
        return pd.DataFrame()

    # 업체별 완전일치 결과
    result_sets = []

    for item in company_inputs:

        matches = find_exact_odds_matches(

            df=df,

            company_name=item.get(
                "company_name"
            ),

            initial_home=item.get(
                "initial_home"
            ),

            initial_draw=item.get(
                "initial_draw"
            ),

            initial_away=item.get(
                "initial_away"
            ),

            final_home=item.get(
                "final_home"
            ),

            final_draw=item.get(
                "final_draw"
            ),

            final_away=item.get(
                "final_away"
            )
        )

        if matches.empty:

            return pd.DataFrame()

        result_sets.append(
            set(
                matches["schedule_id"].astype(str)
            )
        )

    # 모든 업체의 교집합
    common_ids = result_sets[0]

    for ids in result_sets[1:]:

        common_ids &= ids

    if not common_ids:

        return pd.DataFrame()

    result = df[
        df["schedule_id"].astype(str).isin(
            common_ids
        )
    ].copy()

    # 업체별 자료가 여러 줄이므로 경기 단위로 표시
    result = result.drop_duplicates(
        subset=["schedule_id"]
    )

    return result.sort_values(
        "match_date",
        ascending=False
    )


# =========================================================
# 업체 목록
# =========================================================

def get_company_list(df=None):

    if df is None:

        df = get_all_analysis_data()

    if df is None or df.empty:

        return []

    companies = (
        df["company_name"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    companies = [
        x for x in companies.unique()
        if x
    ]

    return sorted(
        companies,
        key=lambda x: x.lower()
    )


# =========================================================
# 완전일치 상세 결과
# =========================================================

def get_exact_match_details(
    df,
    schedule_id
):

    if df is None or df.empty:

        return pd.DataFrame()

    result = df[
        df["schedule_id"].astype(str)
        ==
        str(schedule_id)
    ].copy()

    if result.empty:

        return result

    columns = [

        "schedule_id",
        "match_date",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "result",

        "company_name",

        "initial_home",
        "initial_draw",
        "initial_away",

        "final_home",
        "final_draw",
        "final_away"

    ]

    columns = [
        column
        for column in columns
        if column in result.columns
    ]

    return result[columns].copy()


# =========================================================
# 입력 배당 확률
# =========================================================

def calculate_market_probability(
    home_odds,
    draw_odds,
    away_odds
):

    values = [

        normalize_odds(home_odds),
        normalize_odds(draw_odds),
        normalize_odds(away_odds)

    ]

    if any(
        value is None or value <= 0
        for value in values
    ):

        return None

    inverse = [
        1 / value
        for value in values
    ]

    total = sum(inverse)

    if total <= 0:
        return None

    return {

        "승":
            round(
                inverse[0] /
                total *
                100,
                2
            ),

        "무":
            round(
                inverse[1] /
                total *
                100,
                2
            ),

        "패":
            round(
                inverse[2] /
                total *
                100,
                2
            )
    }


# =========================================================
# 완전일치 결과 통계
# =========================================================

def calculate_exact_result_stats(
    result_df
):

    if result_df is None or result_df.empty:

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

    temp = result_df.drop_duplicates(
        subset=["schedule_id"]
    ).copy()

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
                temp["result"] ==
                result
            ).sum()
        )

        percent = round(
            count / total * 100,
            2
        ) if total else 0

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

def get_recommendation(stats):

    if not stats:

        return None

    values = {

        "승":
            stats.get(
                "승",
                {}
            ).get(
                "percent",
                0
            ),

        "무":
            stats.get(
                "무",
                {}
            ).get(
                "percent",
                0
            ),

        "패":
            stats.get(
                "패",
                {}
            ).get(
                "percent",
                0
            )
    }

    if not values:
        return None

    return max(
        values,
        key=values.get
    )


# =========================================================
# 신뢰도
# =========================================================

def get_confidence(total):

    total = int(
        total or 0
    )

    if total >= 100:
        return "높음"

    if total >= 50:
        return "보통"

    if total >= 20:
        return "낮음"

    return "매우 낮음"


# =========================================================
# 배당 변동 분석
# =========================================================

def calculate_odds_movement(df):

    if df is None or df.empty:

        return pd.DataFrame()

    temp = df.copy()

    required = [

        "initial_home",
        "initial_draw",
        "initial_away",

        "final_home",
        "final_draw",
        "final_away"

    ]

    for column in required:

        if column not in temp.columns:

            return pd.DataFrame()

    temp["승변동"] = (
        temp["final_home"] -
        temp["initial_home"]
    ).round(2)

    temp["무변동"] = (
        temp["final_draw"] -
        temp["initial_draw"]
    ).round(2)

    temp["패변동"] = (
        temp["final_away"] -
        temp["initial_away"]
    ).round(2)

    temp["승변동방향"] = np.select(

        [
            temp["승변동"] < -0.03,
            temp["승변동"] > 0.03
        ],

        [
            "하락",
            "상승"
        ],

        default="유지"
    )

    temp["무변동방향"] = np.select(

        [
            temp["무변동"] < -0.03,
            temp["무변동"] > 0.03
        ],

        [
            "하락",
            "상승"
        ],

        default="유지"
    )

    temp["패변동방향"] = np.select(

        [
            temp["패변동"] < -0.03,
            temp["패변동"] > 0.03
        ],

        [
            "하락",
            "상승"
        ],

        default="유지"
    )

    return temp


# =========================================================
# 역배 분석
# =========================================================

def get_upset_analysis(df):

    if df is None or df.empty:

        return pd.DataFrame()

    temp = get_unique_match_data(
        df
    ).copy()

    required = [

        "initial_home",
        "initial_draw",
        "initial_away",
        "result"

    ]

    for column in required:

        if column not in temp.columns:

            return pd.DataFrame()

    temp["예상"] = temp.apply(

        lambda row:

            "승"
            if row["initial_home"]
            ==
            min(
                row["initial_home"],
                row["initial_draw"],
                row["initial_away"]
            )

            else (

                "무"

                if row["initial_draw"]
                ==
                min(
                    row["initial_home"],
                    row["initial_draw"],
                    row["initial_away"]
                )

                else "패"

            ),

        axis=1
    )

    temp["역배"] = (
        temp["예상"] !=
        temp["result"]
    )

    return temp


# =========================================================
# 역배 통계
# =========================================================

def get_upset_stats(df):

    upset_df = get_upset_analysis(
        df
    )

    if upset_df.empty:

        return {

            "전체경기": 0,
            "역배경기": 0,
            "역배율": 0

        }

    total = len(
        upset_df
    )

    upset_count = int(
        upset_df["역배"].sum()
    )

    upset_percent = round(
        upset_count /
        total *
        100,
        2
    ) if total else 0

    return {

        "전체경기":
            total,

        "역배경기":
            upset_count,

        "역배율":
            upset_percent

    }


# =========================================================
# 실행 테스트
# =========================================================

if __name__ == "__main__":

    df = get_all_analysis_data()

    print(
        "전체 배당 데이터:",
        len(df)
    )

    print(
        "업체:",
        get_company_list(df)
    )

    print(
        "경기:",
        len(
            get_unique_match_data(df)
        )
        )
