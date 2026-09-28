import sqlite3
import os
import pandas as pd


DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "scoreman_test.db"
)


# =========================================================
# DB 연결
# =========================================================

def get_connection():

    return sqlite3.connect(DB_PATH)


# =========================================================
# 전체 경기 + 배당 데이터
# =========================================================

def get_all_analysis_data():

    conn = get_connection()

    try:

        query = """
        SELECT
            m.schedule_id,
            m.home_team,
            m.away_team,
            m.home_score,
            m.away_score,
            m.result,

            o.company_id,
            o.company_name,

            o.euro_f_home AS initial_home,
            o.euro_f_draw AS initial_draw,
            o.euro_f_away AS initial_away,

            o.euro_l_home AS final_home,
            o.euro_l_draw AS final_draw,
            o.euro_l_away AS final_away

        FROM matches m

        INNER JOIN odds o
        ON m.schedule_id = o.schedule_id

        ORDER BY m.id DESC
        """

        return pd.read_sql_query(
            query,
            conn
        )

    finally:

        conn.close()


# =========================================================
# 배당 평균
# =========================================================

def calculate_average_odds(df):

    if df.empty:
        return None

    columns = [
        "initial_home",
        "initial_draw",
        "initial_away",
        "final_home",
        "final_draw",
        "final_away"
    ]

    result = {}

    for column in columns:

        result[column] = round(
            pd.to_numeric(
                df[column],
                errors="coerce"
            ).mean(),
            3
        )

    return result


# =========================================================
# 배당 변동
# =========================================================

def calculate_odds_change(df):

    if df.empty:
        return None

    result = {}

    for side in [
        "home",
        "draw",
        "away"
    ]:

        initial = pd.to_numeric(
            df[f"initial_{side}"],
            errors="coerce"
        ).mean()

        final = pd.to_numeric(
            df[f"final_{side}"],
            errors="coerce"
        ).mean()

        result[side] = round(
            final - initial,
            3
        )

    return result


# =========================================================
# 결과 통계
# =========================================================

def calculate_result_stats(df):

    if df.empty:

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

    total = len(df)

    result = {}

    for value in ["승", "무", "패"]:

        count = int(
            (df["result"] == value).sum()
        )

        percent = round(
            count / total * 100,
            1
        ) if total > 0 else 0

        result[value] = {
            "count": count,
            "percent": percent
        }

    return result


# =========================================================
# 초기 승배당 구간 통계
# =========================================================

def get_odds_range_stats(
    df,
    side="home",
    min_odds=1.50,
    max_odds=1.60
):

    if df.empty:

        return {
            "total": 0,
            "승": 0,
            "무": 0,
            "패": 0
        }

    column = f"initial_{side}"

    temp = df.copy()

    temp[column] = pd.to_numeric(
        temp[column],
        errors="coerce"
    )

    temp = temp[
        (temp[column] >= min_odds) &
        (temp[column] < max_odds)
    ]

    total = len(temp)

    if total == 0:

        return {
            "total": 0,
            "승": 0,
            "무": 0,
            "패": 0
        }

    return {
        "total": total,

        "승": round(
            (temp["result"] == "승").sum()
            / total * 100,
            1
        ),

        "무": round(
            (temp["result"] == "무").sum()
            / total * 100,
            1
        ),

        "패": round(
            (temp["result"] == "패").sum()
            / total * 100,
            1
        )
    }


# =========================================================
# 업체별 통계
# =========================================================

def get_company_stats(df):

    if df.empty:

        return pd.DataFrame()

    result = []

    for company, group in df.groupby(
        "company_name"
    ):

        total = len(group)

        wins = int(
            (group["result"] == "승").sum()
        )

        draws = int(
            (group["result"] == "무").sum()
        )

        losses = int(
            (group["result"] == "패").sum()
        )

        result.append({

            "업체": company,

            "경기수": total,

            "승": wins,

            "무": draws,

            "패": losses,

            "승률": round(
                wins / total * 100,
                1
            ) if total else 0,

            "무율": round(
                draws / total * 100,
                1
            ) if total else 0,

            "패율": round(
                losses / total * 100,
                1
            ) if total else 0

        })

    return pd.DataFrame(result)


# =========================================================
# 배당구간 전체 통계
# =========================================================

def make_odds_range_table(
    df,
    side="home"
):

    ranges = [
        (1.00, 1.19),
        (1.20, 1.29),
        (1.30, 1.39),
        (1.40, 1.49),
        (1.50, 1.59),
        (1.60, 1.69),
        (1.70, 1.79),
        (1.80, 1.89),
        (1.90, 1.99),
        (2.00, 2.19),
        (2.20, 2.49),
        (2.50, 2.99),
        (3.00, 3.49),
        (3.50, 3.99),
        (4.00, 4.99),
        (5.00, 6.99),
        (7.00, 9.99),
        (10.00, 999.0)
    ]

    rows = []

    for minimum, maximum in ranges:

        stats = get_odds_range_stats(
            df,
            side=side,
            min_odds=minimum,
            max_odds=maximum
        )

        rows.append({

            "배당구간":
                f"{minimum:.2f} ~ {maximum:.2f}",

            "경기수":
                stats["total"],

            "승%":
                stats["승"],

            "무%":
                stats["무"],

            "패%":
                stats["패"]

        })

    return pd.DataFrame(rows)
