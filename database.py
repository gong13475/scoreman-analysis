import sqlite3
import os


# =========================================================
# DB 경로
# =========================================================

DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "scoreman_test.db"
)


# =========================================================
# DB 연결
# =========================================================

def get_connection():

    return sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )


# =========================================================
# DB 초기화
# =========================================================

def init_database():

    conn = None

    try:

        conn = get_connection()
        cur = conn.cursor()

        # -----------------------------------------------
        # 경기 데이터
        # -----------------------------------------------

        cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            schedule_id TEXT,

            home_team TEXT,

            away_team TEXT,

            match_date TEXT,

            home_score INTEGER,

            away_score INTEGER,

            result TEXT,

            page_url TEXT,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP

        )
        """)

        # -----------------------------------------------
        # 배당 데이터
        # -----------------------------------------------

        cur.execute("""
        CREATE TABLE IF NOT EXISTS odds (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            schedule_id TEXT,

            company_id INTEGER,

            company_name TEXT,

            euro_f_home REAL,

            euro_f_draw REAL,

            euro_f_away REAL,

            euro_l_home REAL,

            euro_l_draw REAL,

            euro_l_away REAL,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP

        )
        """)

        conn.commit()

        return True

    except Exception as e:

        raise RuntimeError(
            "SQLite 초기화 실패: "
            + repr(e)
            + "\nDB 경로: "
            + DB_PATH
        )

    finally:

        if conn is not None:
            conn.close()


# =========================================================
# 경기 저장
# =========================================================

def save_match(
    schedule_id,
    home_team,
    away_team,
    match_date="",
    home_score=None,
    away_score=None,
    result="",
    page_url=""
):

    conn = get_connection()

    try:

        cur = conn.cursor()

        # 같은 경기 ID가 있으면 삭제
        cur.execute(
            """
            DELETE FROM matches
            WHERE schedule_id = ?
            """,
            (str(schedule_id),)
        )

        # 경기 저장
        cur.execute(
            """
            INSERT INTO matches (

                schedule_id,
                home_team,
                away_team,
                match_date,
                home_score,
                away_score,
                result,
                page_url

            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(schedule_id),
                home_team,
                away_team,
                match_date,
                home_score,
                away_score,
                result,
                page_url
            )
        )

        conn.commit()

    finally:

        conn.close()


# =========================================================
# 숫자 변환
# =========================================================

def to_float(value):

    try:

        if value is None:
            return None

        value = str(value).strip()

        if value == "":
            return None

        return float(value)

    except Exception:

        return None


# =========================================================
# 승무패 배당 저장
#
# initial = 초기배당
# final   = 최종배당
# =========================================================

def save_odds(

    schedule_id,

    company_id,

    company_name,

    initial_home=None,
    initial_draw=None,
    initial_away=None,

    final_home=None,
    final_draw=None,
    final_away=None

):

    conn = get_connection()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO odds (

                schedule_id,

                company_id,

                company_name,

                euro_f_home,
                euro_f_draw,
                euro_f_away,

                euro_l_home,
                euro_l_draw,
                euro_l_away

            )

            VALUES (

                ?,
                ?,
                ?,

                ?,
                ?,
                ?,

                ?,
                ?,
                ?

            )
            """,
            (

                str(schedule_id),

                company_id,

                company_name,

                to_float(initial_home),
                to_float(initial_draw),
                to_float(initial_away),

                to_float(final_home),
                to_float(final_draw),
                to_float(final_away)

            )
        )

        conn.commit()

    finally:

        conn.close()


# =========================================================
# 스코어맨 JSON의 12개 업체 저장
# =========================================================

def save_all_odds(schedule_id, mixodds):

    count = 0

    if not mixodds:

        return 0

    for item in mixodds:

        try:

            euro = item.get(
                "euro",
                {}
            )

            initial = euro.get(
                "f",
                {}
            )

            final = euro.get(
                "l",
                {}
            )

            save_odds(

                schedule_id=schedule_id,

                company_id=item.get(
                    "cid"
                ),

                company_name=item.get(
                    "cn",
                    ""
                ),

                # 초기 승
                initial_home=initial.get(
                    "u"
                ),

                # 초기 무
                initial_draw=initial.get(
                    "g"
                ),

                # 초기 패
                initial_away=initial.get(
                    "d"
                ),

                # 최종 승
                final_home=final.get(
                    "u"
                ),

                # 최종 무
                final_draw=final.get(
                    "g"
                ),

                # 최종 패
                final_away=final.get(
                    "d"
                )
            )

            count += 1

        except Exception as e:

            print(
                "배당 저장 오류:",
                item.get("cn", ""),
                str(e)
            )

    return count


# =========================================================
# 경기 1개 조회
# =========================================================

def get_match(schedule_id):

    conn = get_connection()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT *
            FROM matches
            WHERE schedule_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (str(schedule_id),)
        )

        row = cur.fetchone()

        if row is None:

            return None

        columns = [
            column[0]
            for column in cur.description
        ]

        return dict(
            zip(
                columns,
                row
            )
        )

    finally:

        conn.close()


# =========================================================
# 경기의 배당 조회
# =========================================================

def get_odds(schedule_id):

    conn = get_connection()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT *
            FROM odds
            WHERE schedule_id = ?
            ORDER BY id
            """,
            (str(schedule_id),)
        )

        rows = cur.fetchall()

        columns = [
            column[0]
            for column in cur.description
        ]

        result = []

        for row in rows:

            result.append(
                dict(
                    zip(
                        columns,
                        row
                    )
                )
            )

        return result

    finally:

        conn.close()


# =========================================================
# 경기 데이터 개수
# =========================================================

def get_match_count():

    conn = get_connection()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT COUNT(*)
            FROM matches
            """
        )

        return cur.fetchone()[0]

    finally:

        conn.close()


# =========================================================
# 배당 데이터 개수
# =========================================================

def get_odds_count():

    conn = get_connection()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT COUNT(*)
            FROM odds
            """
        )

        return cur.fetchone()[0]

    finally:

        conn.close()


# =========================================================
# DB 전체 통계
# =========================================================

def get_database_stats():

    return {

        "matches": get_match_count(),

        "odds": get_odds_count()

    }
def get_all_matches():

    conn = get_connection()

    try:

        cur = conn.cursor()

        cur.execute("""
            SELECT *
            FROM matches
            ORDER BY id DESC
        """)

        rows = cur.fetchall()

        columns = [
            column[0]
            for column in cur.description
        ]

        return [
            dict(zip(columns, row))
            for row in rows
        ]

    finally:

        conn.close()


def get_all_odds():

    conn = get_connection()

    try:

        cur = conn.cursor()

        cur.execute("""
            SELECT
                id,
                schedule_id,
                company_id,
                company_name,

                euro_f_home AS initial_home,
                euro_f_draw AS initial_draw,
                euro_f_away AS initial_away,

                euro_l_home AS final_home,
                euro_l_draw AS final_draw,
                euro_l_away AS final_away

            FROM odds

            ORDER BY id DESC
        """)

        rows = cur.fetchall()

        columns = [
            column[0]
            for column in cur.description
        ]

        return [
            dict(zip(columns, row))
            for row in rows
        ]

    finally:

        conn.close()
