import sqlite3
import pandas as pd
import numpy as np

from database import DB_FILE


# =========================================================
# DB 연결
# =========================================================

def get_connection():

    conn = sqlite3.connect(
        DB_FILE
    )

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

        WHERE m.result IN (
            '승',
            '무',
            '패'
        )

        ORDER BY
            m.match_date DESC
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

    return df


# =========================================================
# 경기 중복 제거
# =========================================================

def get_unique_match_data(df):

    if df is None or df.empty:

        return pd.DataFrame()

    temp = df.copy()

    temp = temp.drop_duplicates(
        subset=[
            "schedule_id"
        ]
    )

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
                result_series == result
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
# 배당区間 통계
# =========================================================

def make_odds_range_table(
    df,
    side="home"
):

    if df is None or df.empty:

        return pd.DataFrame()

    temp = get_unique_match_data(
        df
    ).copy()

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
            temp["배당구간"]
            ==
            odds_range
        ]

        count = len(
            group
        )

        if count == 0:
            continue

        target_count = int(
            (
                group["result"]
                ==
                target_result
            ).sum()
        )

        rows.append({

            "배당구간":
                odds_range,

            "경기수":
                count,

            f"{target_result} 적중":
                target_count,

            f"{target_result} 적중률":
                f"{target_count / count * 100:.2f}% "
                f"({target_count}경기)",

            "승":
                f"{(group['result'] == '승').sum() / count * 100:.2f}% "
                f"({(group['result'] == '승').sum()}경기)",

            "무":
                f"{(group['result'] == '무').sum() / count * 100:.2f}% "
                f"({(group['result'] == '무').sum()}경기)",

            "패":
                f"{(group['result'] == '패').sum() / count * 100:.2f}% "
                f"({(group['result'] == '패').sum()}경기)"

        })

    return pd.DataFrame(
        rows
    )


# =========================================================
# 업체별统计
# =========================================================

def get_company_stats(df):

    if df is None or df.empty:

        return pd.DataFrame()

    rows = []

    for company, group in df.groupby(
        "company_name",
        dropna=False
    ):

        group = group.copy()

        group = group.drop_duplicates(
            subset=[
                "schedule_id"
            ]
        )

        total = len(
            group
        )

        if total == 0:
            continue

        win = int(
            (
                group["result"] == "승"
            ).sum()
        )

        draw = int(
            (
                group["result"] == "무"
            ).sum()
        )

        lose = int(
            (
                group["result"] == "패"
            ).sum()
        )

        rows.append({

            "배당업체":
                company,

            "경기수":
                total,

            "승":
                f"{win / total * 100:.2f}% "
                f"({win}경기)",

            "무":
                f"{draw / total * 100:.2f}% "
                f"({draw}경기)",

            "패":
                f"{lose / total * 100:.2f}% "
                f"({lose}경기)"

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
# 배당 확률
# =========================================================

def calculate_market_probability(
    home_odds,
    draw_odds,
    away_odds
):

    values = [

        float(home_odds),
        float(draw_odds),
        float(away_odds)

    ]

    if any(
        value <= 0
        for value in values
    ):

        return None

    inverse = [

        1 / value
        for value in values

    ]

    total = sum(
        inverse
    )

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
# 완전 동일배당 검색
# =========================================================
#
# 선택한 업체별로
#
# 초기:
# 승 / 무 / 패
#
# 최종:
# 승 / 무 / 패
#
# 6개 값이 모두 완전히 같은
# 과거 경기만 반환
#
# =========================================================

def find_exact_odds_matches(
    df,
    selected_companies,
    initial_home,
    initial_draw,
    initial_away,
    final_home,
    final_draw,
    final_away
):

    if df is None or df.empty:

        return pd.DataFrame()

    if not selected_companies:

        return pd.DataFrame()

    temp = df.copy()

    # -----------------------------------------------------
    # 숫자 변환
    # -----------------------------------------------------

    numeric_columns = [

        "initial_home",
        "initial_draw",
        "initial_away",

        "final_home",
        "final_draw",
        "final_away"

    ]

    for column in numeric_columns:

        temp[column] = pd.to_numeric(
            temp[column],
            errors="coerce"
        )

    # -----------------------------------------------------
    # 입력값 숫자화
    # -----------------------------------------------------

    target_values = {

        "initial_home":
            float(initial_home),

        "initial_draw":
            float(initial_draw),

        "initial_away":
            float(initial_away),

        "final_home":
            float(final_home),

        "final_draw":
            float(final_draw),

        "final_away":
            float(final_away)

    }

    # -----------------------------------------------------
    # 선택 업체만
    # -----------------------------------------------------

    temp = temp[
        temp["company_name"]
        .isin(
            selected_companies
        )
    ].copy()

    if temp.empty:

        return pd.DataFrame()

    # -----------------------------------------------------
    # 완전 동일 배당
    # -----------------------------------------------------

    mask = (

        temp["initial_home"]
        ==
        target_values[
            "initial_home"
        ]

    ) & (

        temp["initial_draw"]
        ==
        target_values[
            "initial_draw"
        ]

    ) & (

        temp["initial_away"]
        ==
        target_values[
            "initial_away"
        ]

    ) & (

        temp["final_home"]
        ==
        target_values[
            "final_home"
        ]

    ) & (

        temp["final_draw"]
        ==
        target_values[
            "final_draw"
        ]

    ) & (

        temp["final_away"]
        ==
        target_values[
            "final_away"
        ]

    )

    matched = temp[
        mask
    ].copy()

    if matched.empty:

        return pd.DataFrame()

    # -----------------------------------------------------
    # 선택한 업체가 여러 개일 경우
    #
    # 같은 경기에 선택 업체가 모두 존재해야 함
    # -----------------------------------------------------

    company_count = len(
        selected_companies
    )

    match_company_count = (
        matched
        .groupby(
            "schedule_id"
        )["company_name"]
        .nunique()
    )

    valid_schedule_ids = (
        match_company_count[
            match_company_count
            ==
            company_count
        ]
        .index
    )

    matched = matched[
        matched["schedule_id"]
        .isin(
            valid_schedule_ids
        )
    ].copy()

    if matched.empty:

        return pd.DataFrame()

    # -----------------------------------------------------
    # 업체별 행 → 경기 하나로 변환
    # -----------------------------------------------------

    result_rows = []

    for schedule_id, group in matched.groupby(
        "schedule_id"
    ):

        first = group.iloc[0]

        companies = list(
            group[
                "company_name"
            ]
            .dropna()
            .astype(str)
            .unique()
        )

        result_rows.append({

            "schedule_id":
                schedule_id,

            "match_date":
                first["match_date"],

            "home_team":
                first["home_team"],

            "away_team":
                first["away_team"],

            "home_score":
                first["home_score"],

            "away_score":
                first["away_score"],

            "result":
                first["result"],

            "선택업체":
                ", ".join(
                    sorted(companies)
                ),

            "업체수":
                len(companies),

            "initial_home":
                first["initial_home"],

            "initial_draw":
                first["initial_draw"],

            "initial_away":
                first["initial_away"],

            "final_home":
                first["final_home"],

            "final_draw":
                first["final_draw"],

            "final_away":
                first["final_away"]

        })

    result = pd.DataFrame(
        result_rows
    )

    if not result.empty:

        result = result.sort_values(
            "match_date",
            ascending=False
        )

    return result


# =========================================================
# 정확히 일치한 경기의 승무패 통계
# =========================================================

def calculate_exact_result_stats(
    exact_df
):

    if (
        exact_df is None
        or exact_df.empty
    ):

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

    temp = exact_df.drop_duplicates(
        subset=[
            "schedule_id"
        ]
    ).copy()

    total = len(
        temp
    )

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
# 추천
# =========================================================

def get_recommendation(
    stats
):

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

    return max(
        values,
        key=values.get
    )


# =========================================================
# 신뢰도
# =========================================================

def get_confidence(
    total
):

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

def calculate_odds_movement(
    df
):

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
        temp["final_home"]
        -
        temp["initial_home"]
    ).round(2)

    temp["무변동"] = (
        temp["final_draw"]
        -
        temp["initial_draw"]
    ).round(2)

    temp["패변동"] = (
        temp["final_away"]
        -
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

def get_upset_analysis(
    df
):

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

        (
            "승"
            if row["initial_home"]
            ==
            min(
                row["initial_home"],
                row["initial_draw"],
                row["initial_away"]
            )

            else

            (
                "무"
                if row["initial_draw"]
                ==
                min(
                    row["initial_home"],
                    row["initial_draw"],
                    row["initial_away"]
                )

                else "패"
            )
        ),

        axis=1
    )

    temp["역배"] = (

        temp["예상"]
        !=
        temp["result"]

    )

    return temp


# =========================================================
# 역배 통계
# =========================================================

def get_upset_stats(
    df
):

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
# 특정 연도 데이터
# =========================================================

def get_year_data(
    df,
    year
):

    if df is None or df.empty:

        return pd.DataFrame()

    temp = df.copy()

    temp["match_date"] = (
        temp["match_date"]
        .astype(str)
    )

    return temp[
        temp["match_date"]
        .str.startswith(
            str(year)
        )
    ].copy()


# =========================================================
# 연도별 통계
# =========================================================

def get_year_stats(
    df
):

    if df is None or df.empty:

        return pd.DataFrame()

    temp = get_unique_match_data(
        df
    ).copy()

    temp["연도"] = (
        temp["match_date"]
        .astype(str)
        .str[:4]
    )

    rows = []

    for year, group in temp.groupby(
        "연도"
    ):

        total = len(
            group
        )

        if total == 0:
            continue

        win = int(
            (
                group["result"]
                ==
                "승"
            ).sum()
        )

        draw = int(
            (
                group["result"]
                ==
                "무"
            ).sum()
        )

        lose = int(
            (
                group["result"]
                ==
                "패"
            ).sum()
        )

        rows.append({

            "연도":
                year,

            "경기수":
                total,

            "승":
                f"{win / total * 100:.2f}% ({win})",

            "무":
                f"{draw / total * 100:.2f}% ({draw})",

            "패":
                f"{lose / total * 100:.2f}% ({lose})"

        })

    return pd.DataFrame(
        rows
    ).sort_values(
        "연도",
        ascending=False
    )


# =========================================================
# 테스트
# =========================================================

if __name__ == "__main__":

    print(
        "================================"
    )

    print(
        "Analysis 테스트"
    )

    df = get_all_analysis_data()

    print(
        "전체 배당 행:",
        len(df)
    )

    if not df.empty:

        print(
            "전체 경기:",
            len(
                get_unique_match_data(
                    df
                )
            )
        )

        print(
            "업체:"
        )

        print(
            get_company_stats(
                df
            )
        )

    print(
        "================================"
    )
