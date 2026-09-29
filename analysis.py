import sqlite3
import pandas as pd
import numpy as np

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

    # =====================================================
    # 정상적인 1X2 초기배당만 사용
    # =====================================================

    df = df[
        (df["initial_home"] > 1) &
        (df["initial_draw"] > 1) &
        (df["initial_away"] > 1)
    ].copy()

    if df.empty:
        return df

    # =====================================================
    # 초기배당 이론 확률
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
    # 최종배당 이론 확률
    # =====================================================

    valid_final = (
        (df["final_home"] > 1) &
        (df["final_draw"] > 1) &
        (df["final_away"] > 1)
    )

    df["최종승확률"] = np.nan
    df["최종무확률"] = np.nan
    df["최종패확률"] = np.nan

    final_home = 1 / df.loc[valid_final, "final_home"]
    final_draw = 1 / df.loc[valid_final, "final_draw"]
    final_away = 1 / df.loc[valid_final, "final_away"]

    final_total = (
        final_home +
        final_draw +
        final_away
    )

    df.loc[valid_final, "최종승확률"] = (
        final_home / final_total * 100
    ).round(2)

    df.loc[valid_final, "최종무확률"] = (
        final_draw / final_total * 100
    ).round(2)

    df.loc[valid_final, "최종패확률"] = (
        final_away / final_total * 100
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

    # =====================================================
    # 배당상 예상 적중
    # =====================================================

    df["적중"] = (
        df["배당예상"] == df["result"]
    )

    # =====================================================
    # 배당 구간
    # =====================================================

    df["승배당구간"] = df[
        "initial_home"
    ].apply(get_odds_range)

    df["무배당구간"] = df[
        "initial_draw"
    ].apply(get_odds_range)

    df["패배당구간"] = df[
        "initial_away"
    ].apply(get_odds_range)

    return df


# =========================================================
# 경기별 중복 제거
# =========================================================

def get_unique_match_data(df):

    if df is None or df.empty:
        return pd.DataFrame()

    temp = df.copy()

    temp = temp.drop_duplicates(
        subset=["schedule_id"]
    ).copy()

    return temp


# =========================================================
# 배당 구간
# =========================================================

def get_odds_range(odds):

    if pd.isna(odds):
        return "-"

    odds = float(odds)

    if odds < 1.20:
        return "1.01~1.19"

    elif odds < 1.30:
        return "1.20~1.29"

    elif odds < 1.40:
        return "1.30~1.39"

    elif odds < 1.50:
        return "1.40~1.49"

    elif odds < 1.60:
        return "1.50~1.59"

    elif odds < 1.70:
        return "1.60~1.69"

    elif odds < 1.80:
        return "1.70~1.79"

    elif odds < 1.90:
        return "1.80~1.89"

    elif odds < 2.00:
        return "1.90~1.99"

    elif odds < 2.10:
        return "2.00~2.09"

    elif odds < 2.20:
        return "2.10~2.19"

    elif odds < 2.30:
        return "2.20~2.29"

    elif odds < 2.40:
        return "2.30~2.39"

    elif odds < 2.50:
        return "2.40~2.49"

    elif odds < 2.75:
        return "2.50~2.74"

    elif odds < 3.00:
        return "2.75~2.99"

    elif odds < 3.50:
        return "3.00~3.49"

    elif odds < 4.00:
        return "3.50~3.99"

    elif odds < 5.00:
        return "4.00~4.99"

    elif odds < 7.00:
        return "5.00~6.99"

    else:
        return "7.00+"


# =========================================================
# 전체 승무패 통계
# =========================================================

def calculate_result_stats(df):

    if df is None or df.empty:

        return {
            "승": {"count": 0, "percent": 0},
            "무": {"count": 0, "percent": 0},
            "패": {"count": 0, "percent": 0}
        }

    unique_df = get_unique_match_data(df)

    result_series = (
        unique_df["result"]
        .dropna()
        .astype(str)
    )

    total = len(result_series)

    stats = {}

    for result in ["승", "무", "패"]:

        count = int(
            (result_series == result).sum()
        )

        percent = round(
            count / total * 100,
            2
        ) if total else 0

        stats[result] = {
            "count": count,
            "percent": percent
        }

    return stats


# =========================================================
# 배당 구간별 통계
# =========================================================

def make_odds_range_table(df, side="home"):

    if df is None or df.empty:
        return pd.DataFrame()

    temp = get_unique_match_data(df)

    column_map = {
        "home": "initial_home",
        "draw": "initial_draw",
        "away": "initial_away"
    }

    result_map = {
        "home": "승",
        "draw": "무",
        "away": "패"
    }

    if side not in column_map:
        raise ValueError(
            "side는 home/draw/away만 가능합니다."
        )

    odds_column = column_map[side]
    target_result = result_map[side]

    temp["배당구간"] = temp[
        odds_column
    ].apply(get_odds_range)

    ranges = [
        "1.01~1.19",
        "1.20~1.29",
        "1.30~1.39",
        "1.40~1.49",
        "1.50~1.59",
        "1.60~1.69",
        "1.70~1.79",
        "1.80~1.89",
        "1.90~1.99",
        "2.00~2.09",
        "2.10~2.19",
        "2.20~2.29",
        "2.30~2.39",
        "2.40~2.49",
        "2.50~2.74",
        "2.75~2.99",
        "3.00~3.49",
        "3.50~3.99",
        "4.00~4.99",
        "5.00~6.99",
        "7.00+"
    ]

    rows = []

    for odds_range in ranges:

        group = temp[
            temp["배당구간"] == odds_range
        ]

        count = len(group)

        if count == 0:
            continue

        target_count = int(
            (group["result"] == target_result).sum()
        )

        target_percent = round(
            target_count / count * 100,
            2
        )

        home_count = int(
            (group["result"] == "승").sum()
        )

        draw_count = int(
            (group["result"] == "무").sum()
        )

        away_count = int(
            (group["result"] == "패").sum()
        )

        rows.append({
            "배당구간": odds_range,
            "경기수": count,

            f"{target_result} 적중":
                target_count,

            f"{target_result} 적중률":
                f"{target_percent:.2f}% "
                f"({target_count}경기)",

            "승":
                f"{home_count / count * 100:.2f}% "
                f"({home_count}경기)",

            "무":
                f"{draw_count / count * 100:.2f}% "
                f"({draw_count}경기)",

            "패":
                f"{away_count / count * 100:.2f}% "
                f"({away_count}경기)"
        })

    return pd.DataFrame(rows)


# =========================================================
# 배당업체별 통계
# =========================================================

def get_company_stats(df):

    if df is None or df.empty:
        return pd.DataFrame()

    rows = []

    for company, group in df.groupby(
        "company_name",
        dropna=False
    ):

        company = (
            str(company)
            if company
            else "알 수 없음"
        )

        group = group.drop_duplicates(
            subset=["schedule_id"]
        ).copy()

        total = len(group)

        if total == 0:
            continue

        home_count = int(
            (group["result"] == "승").sum()
        )

        draw_count = int(
            (group["result"] == "무").sum()
        )

        away_count = int(
            (group["result"] == "패").sum()
        )

        home_percent = round(
            home_count / total * 100,
            2
        )

        draw_percent = round(
            draw_count / total * 100,
            2
        )

        away_percent = round(
            away_count / total * 100,
            2
        )

        hit_count = int(
            group["적중"].sum()
        )

        hit_percent = round(
            hit_count / total * 100,
            2
        )

        rows.append({
            "배당업체": company,
            "경기수": total,

            "승":
                f"{home_percent:.2f}% "
                f"({home_count}경기)",

            "무":
                f"{draw_percent:.2f}% "
                f"({draw_count}경기)",

            "패":
                f"{away_percent:.2f}% "
                f"({away_count}경기)",

            "배당상 예상 적중":
                f"{hit_percent:.2f}% "
                f"({hit_count}경기)"
        })

    result = pd.DataFrame(rows)

    if not result.empty:

        result = result.sort_values(
            "경기수",
            ascending=False
        )

    return result


# =========================================================
# 특정 배당구간 통계
# =========================================================

def get_range_result_stats(
    df,
    odds_column,
    min_odds,
    max_odds
):

    if df is None or df.empty:

        return {
            "경기수": 0,
            "승": 0,
            "무": 0,
            "패": 0
        }

    temp = get_unique_match_data(df)

    group = temp[
        (temp[odds_column] >= min_odds) &
        (temp[odds_column] <= max_odds)
    ]

    total = len(group)

    if total == 0:

        return {
            "경기수": 0,
            "승": 0,
            "무": 0,
            "패": 0
        }

    return {
        "경기수": total,

        "승":
            int((group["result"] == "승").sum()),

        "무":
            int((group["result"] == "무").sum()),

        "패":
            int((group["result"] == "패").sum())
    }


# =========================================================
# 요약
# =========================================================

def get_summary(df):

    if df is None or df.empty:

        return {
            "경기수": 0,
            "업체수": 0,
            "승": 0,
            "무": 0,
            "패": 0
        }

    unique_df = get_unique_match_data(df)

    return {
        "경기수": len(unique_df),

        "업체수":
            df["company_name"].nunique(),

        "승":
            int((unique_df["result"] == "승").sum()),

        "무":
            int((unique_df["result"] == "무").sum()),

        "패":
            int((unique_df["result"] == "패").sum())
    }


# =========================================================
# ★ 완전 동일 초기배당 검색
# =========================================================
#
# 유사배당이 아닙니다.
#
# 승 / 무 / 패 초기배당 3개가
# 모두 정확히 동일한 경기만 검색합니다.
#
# 예:
#
# 1.85 / 3.40 / 4.20  → 포함
# 1.85 / 3.40 / 4.20  → 포함
#
# 1.86 / 3.40 / 4.20  → 제외
# 1.85 / 3.41 / 4.20  → 제외
# 1.85 / 3.40 / 4.21  → 제외
#
# 경기 수가 부족해도 범위를 확대하지 않습니다.
# =========================================================

def find_similar_odds(
    df,
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.0,
    minimum_games=0,
    maximum_tolerance=0.0
):

    if df is None or df.empty:
        return pd.DataFrame(), 0.0

    temp = df.copy()

    # 경기 중복 제거
    temp = get_unique_match_data(temp)

    required_columns = [
        "initial_home",
        "initial_draw",
        "initial_away"
    ]

    for column in required_columns:

        if column not in temp.columns:
            return pd.DataFrame(), 0.0

        temp[column] = pd.to_numeric(
            temp[column],
            errors="coerce"
        )

    # 입력값 숫자 변환
    try:

        home_odds = float(home_odds)
        draw_odds = float(draw_odds)
        away_odds = float(away_odds)

    except (TypeError, ValueError):

        return pd.DataFrame(), 0.0

    # =====================================================
    # ★ 완전 동일 조건
    # =====================================================

    similar = temp[
        (temp["initial_home"] == home_odds) &
        (temp["initial_draw"] == draw_odds) &
        (temp["initial_away"] == away_odds)
    ].copy()

    # =====================================================
    # 차이값
    # =====================================================

    if not similar.empty:

        similar["승차이"] = (
            similar["initial_home"] -
            home_odds
        ).abs()

        similar["무차이"] = (
            similar["initial_draw"] -
            draw_odds
        ).abs()

        similar["패차이"] = (
            similar["initial_away"] -
            away_odds
        ).abs()

        similar["총차이"] = (
            similar["승차이"] +
            similar["무차이"] +
            similar["패차이"]
        )

        similar = similar.sort_values(
            "총차이",
            ascending=True
        )

    return similar, 0.0


# =========================================================
# 완전 동일 초기배당 승무패 통계
# =========================================================

def calculate_similar_result_stats(similar_df):

    if similar_df is None or similar_df.empty:

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

    temp = get_unique_match_data(
        similar_df
    )

    total = len(temp)

    stats = {
        "전체": total
    }

    for result in ["승", "무", "패"]:

        count = int(
            (temp["result"] == result).sum()
        )

        percent = round(
            count / total * 100,
            2
        ) if total else 0

        stats[result] = {
            "count": count,
            "percent": percent
        }

    return stats


# =========================================================
# 입력 배당 이론확률
# =========================================================

def calculate_market_probability(
    home_odds,
    draw_odds,
    away_odds
):

    try:

        values = [
            float(home_odds),
            float(draw_odds),
            float(away_odds)
        ]

    except (TypeError, ValueError):

        return None

    if any(
        value <= 0
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
                inverse[0] / total * 100,
                2
            ),

        "무":
            round(
                inverse[1] / total * 100,
                2
            ),

        "패":
            round(
                inverse[2] / total * 100,
                2
            )
    }


# =========================================================
# 추천 결과
# =========================================================

def get_recommendation(stats):

    if not stats:
        return None

    values = {
        "승":
            stats.get("승", {}).get(
                "percent",
                0
            ),

        "무":
            stats.get("무", {}).get(
                "percent",
                0
            ),

        "패":
            stats.get("패", {}).get(
                "percent",
                0
            )
    }

    return max(
        values,
        key=values.get
    )


# =========================================================
# 신뢰도
# =========================================================

def get_confidence(total):

    total = int(total or 0)

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

    temp = get_unique_match_data(
        df
    ).copy()

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
# 배당 하락 적중률
# =========================================================

def get_movement_result_stats(
    df,
    movement_column,
    target_result
):

    if df is None or df.empty:

        return {
            "경기수": 0,
            "적중": 0,
            "적중률": 0
        }

    group = df[
        df[movement_column] == "하락"
    ].copy()

    total = len(group)

    if total == 0:

        return {
            "경기수": 0,
            "적중": 0,
            "적중률": 0
        }

    hit = int(
        (group["result"] == target_result).sum()
    )

    percent = round(
        hit / total * 100,
        2
    )

    return {
        "경기수": total,
        "적중": hit,
        "적중률": percent
    }


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
            if row["initial_home"] ==
            min(
                row["initial_home"],
                row["initial_draw"],
                row["initial_away"]
            )

            else (

                "무"
                if row["initial_draw"] ==
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

    upset_df = get_upset_analysis(df)

    if upset_df.empty:

        return {
            "전체경기": 0,
            "역배경기": 0,
            "역배율": 0
        }

    total = len(upset_df)

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
        "전체경기": total,
        "역배경기": upset_count,
        "역배율": upset_percent
    }


# =========================================================
# 실행 테스트
# =========================================================

if __name__ == "__main__":

    df = get_all_analysis_data()

    print(
        "전체 배당 행:",
        len(df)
    )

    unique_df = get_unique_match_data(df)

    print(
        "실제 경기 수:",
        len(unique_df)
    )

    print(
        "승무패:",
        calculate_result_stats(df)
    )

    print("\n승 배당구간:")

    print(
        make_odds_range_table(
            df,
            side="home"
        )
    )

    print("\n업체별:")

    print(
        get_company_stats(df)
    )

    print("\n역배:")

    print(
        get_upset_stats(df)
    )
