import sqlite3
import pandas as pd
import numpy as np

from database import DB_FILE


# =========================================================
# DB 연결
# =========================================================

def get_connection():

    conn = sqlite3.connect(DB_FILE)

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

        df = pd.read_sql_query(
            query,
            conn
        )

    finally:

        conn.close()


    if df.empty:

        return df


    # =====================================================
    # 숫자 변환
    # =====================================================

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
    # 정상적인 1X2 배당만
    # =====================================================

    df = df[
        (df["initial_home"] > 1) &
        (df["initial_draw"] > 1) &
        (df["initial_away"] > 1)
    ].copy()


    if df.empty:

        return df


    # =====================================================
    # 배당 확률
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
        inverse_home /
        total *
        100
    ).round(2)


    df["무확률"] = (
        inverse_draw /
        total *
        100
    ).round(2)


    df["패확률"] = (
        inverse_away /
        total *
        100
    ).round(2)


    # =====================================================
    # 배당상 예상
    # =====================================================

    df["배당예상"] = np.select(

        [

            (
                (df["initial_home"] <= df["initial_draw"])
                &
                (df["initial_home"] <= df["initial_away"])
            ),

            (
                (df["initial_draw"] < df["initial_home"])
                &
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
        df["배당예상"] ==
        df["result"]
    )


    # =====================================================
    # 배당구간
    # =====================================================

    df["승배당구간"] = df[
        "initial_home"
    ].apply(
        get_odds_range
    )

    df["무배당구간"] = df[
        "initial_draw"
    ].apply(
        get_odds_range
    )

    df["패배당구간"] = df[
        "initial_away"
    ].apply(
        get_odds_range
    )


    return df


# =========================================================
# 경기 중복 제거
# =========================================================

def get_unique_match_data(df):

    if df is None or df.empty:

        return pd.DataFrame()


    temp = df.copy()


    # -----------------------------------------------------
    # schedule_id 기준으로 1경기 1행
    # -----------------------------------------------------

    temp = temp.drop_duplicates(
        subset=["schedule_id"]
    ).copy()


    return temp


# =========================================================
# 배당구간
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


    # =====================================================
    # 핵심: 경기 ID 중복 제거
    # =====================================================

    unique_df = get_unique_match_data(
        df
    )


    result_series = (
        unique_df["result"]
        .dropna()
        .astype(str)
    )


    total = len(
        result_series
    )


    stats = {}


    for result in [
        "승",
        "무",
        "패"
    ]:

        count = int(
            (
                result_series ==
                result
            ).sum()
        )


        percent = round(
            count /
            total *
            100,
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
# 배당구간별 통계
# =========================================================

def make_odds_range_table(
    df,
    side="home"
):

    if df is None or df.empty:

        return pd.DataFrame()


    # =====================================================
    # 경기별 중복 제거
    # =====================================================

    temp = get_unique_match_data(
        df
    )


    column_map = {

        "home":
            "initial_home",

        "draw":
            "initial_draw",

        "away":
            "initial_away"

    }


    result_map = {

        "home":
            "승",

        "draw":
            "무",

        "away":
            "패"

    }


    if side not in column_map:

        raise ValueError(
            "side는 home/draw/away만 가능합니다."
        )


    odds_column = column_map[
        side
    ]


    target_result = result_map[
        side
    ]


    temp["배당구간"] = temp[
        odds_column
    ].apply(
        get_odds_range
    )


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
            temp["배당구간"] ==
            odds_range
        ]


        count = len(
            group
        )


        if count == 0:

            continue


        win_count = int(
            (
                group["result"] ==
                target_result
            ).sum()
        )


        percent = round(
            win_count /
            count *
            100,
            2
        )


        home_count = int(
            (
                group["result"] ==
                "승"
            ).sum()
        )


        draw_count = int(
            (
                group["result"] ==
                "무"
            ).sum()
        )


        away_count = int(
            (
                group["result"] ==
                "패"
            ).sum()
        )


        rows.append({

            "배당구간":
                odds_range,

            "경기수":
                count,

            f"{target_result} 적중":
                win_count,

            f"{target_result} 적중률":
                f"{percent:.2f}% ({win_count}경기)",

            "승":
                f"{home_count / count * 100:.2f}% ({home_count}경기)",

            "무":
                f"{draw_count / count * 100:.2f}% ({draw_count}경기)",

            "패":
                f"{away_count / count * 100:.2f}% ({away_count}경기)"

        })


    return pd.DataFrame(
        rows
    )


# =========================================================
# 배당업체별 통계
# =========================================================

def get_company_stats(df):

    if df is None or df.empty:

        return pd.DataFrame()


    rows = []


    # =====================================================
    # 업체별로 계산
    # =====================================================

    for company, group in df.groupby(
        "company_name",
        dropna=False
    ):


        company = (
            str(company)
            if company
            else "알 수 없음"
        )


        # -------------------------------------------------
        # 업체 안에서도 같은 경기 중복 제거
        # -------------------------------------------------

        group = group.drop_duplicates(
            subset=["schedule_id"]
        ).copy()


        total = len(
            group
        )


        if total == 0:

            continue


        home_count = int(
            (
                group["result"] ==
                "승"
            ).sum()
        )


        draw_count = int(
            (
                group["result"] ==
                "무"
            ).sum()
        )


        away_count = int(
            (
                group["result"] ==
                "패"
            ).sum()
        )


        home_percent = round(
            home_count /
            total *
            100,
            2
        )


        draw_percent = round(
            draw_count /
            total *
            100,
            2
        )


        away_percent = round(
            away_count /
            total *
            100,
            2
        )


        # -------------------------------------------------
        # 배당상 예상 적중
        # -------------------------------------------------

        if "적중" in group.columns:

            hit_count = int(
                group["적중"].sum()
            )

        else:

            hit_count = 0


        hit_percent = round(
            hit_count /
            total *
            100,
            2
        )


        rows.append({

            "배당업체":
                company,

            "경기수":
                total,

            "승":
                f"{home_percent:.2f}% ({home_count}경기)",

            "무":
                f"{draw_percent:.2f}% ({draw_count}경기)",

            "패":
                f"{away_percent:.2f}% ({away_count}경기)",

            "배당상 예상 적중":
                f"{hit_percent:.2f}% ({hit_count}경기)"

        })


    result = pd.DataFrame(
        rows
    )


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


    temp = get_unique_match_data(
        df
    )


    group = temp[
        (temp[odds_column] >= min_odds)
        &
        (temp[odds_column] <= max_odds)
    ]


    total = len(
        group
    )


    if total == 0:

        return {

            "경기수": 0,
            "승": 0,
            "무": 0,
            "패": 0

        }


    return {

        "경기수":
            total,

        "승":
            int(
                (
                    group["result"] ==
                    "승"
                ).sum()
            ),

        "무":
            int(
                (
                    group["result"] ==
                    "무"
                ).sum()
            ),

        "패":
            int(
                (
                    group["result"] ==
                    "패"
                ).sum()
            )

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


    unique_df = get_unique_match_data(
        df
    )


    return {

        "경기수":
            len(unique_df),

        "업체수":
            df["company_name"].nunique(),

        "승":
            int(
                (
                    unique_df["result"] ==
                    "승"
                ).sum()
            ),

        "무":
            int(
                (
                    unique_df["result"] ==
                    "무"
                ).sum()
            ),

        "패":
            int(
                (
                    unique_df["result"] ==
                    "패"
                ).sum()
            )

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


    unique_df = get_unique_match_data(
        df
    )


    print(
        "실제 경기 수:",
        len(unique_df)
    )


    print(
        "승무패:",
        calculate_result_stats(df)
    )


    print(
        "\n승 배당구간:"
    )


    print(
        make_odds_range_table(
            df,
            side="home"
        )
    )


    print(
        "\n업체별:"
    )


    print(
        get_company_stats(df)
    )
