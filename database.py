import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).parent / "scoreman.db"


# =========================================================
# DB 연결
# =========================================================

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
# 테이블 존재 여부
# =========================================================

def table_exists(cur, table_name):
    cur.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        AND name=?
    """, (table_name,))

    return cur.fetchone() is not None


# =========================================================
# 컬럼 확인
# =========================================================

def get_columns(cur, table_name):
    cur.execute(
        f"PRAGMA table_info({table_name})"
    )

    return {
        row[1]
        for row in cur.fetchall()
    }


# =========================================================
# DB 초기화 / 자동 수정
# =========================================================

def init_database():

    conn = get_connection()
    cur = conn.cursor()

    # -----------------------------------------------------
    # matches 테이블
    # -----------------------------------------------------

    if not table_exists(cur, "matches"):

        cur.execute("""
            CREATE TABLE matches (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                schedule_id TEXT UNIQUE NOT NULL,

                match_date TEXT,

                home_team TEXT,

                away_team TEXT,

                home_score INTEGER,

                away_score INTEGER,

                result TEXT,

                source TEXT DEFAULT 'Scoreman',

                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

    else:

        columns = get_columns(
            cur,
            "matches"
        )

        required_columns = {

            "schedule_id":
                "TEXT",

            "match_date":
                "TEXT",

            "home_team":
                "TEXT",

            "away_team":
                "TEXT",

            "home_score":
                "INTEGER",

            "away_score":
                "INTEGER",

            "result":
                "TEXT",

            "source":
                "TEXT",

            "created_at":
                "TEXT"

        }

        for column, data_type in required_columns.items():

            if column not in columns:

                cur.execute(
                    f"""
                    ALTER TABLE matches
                    ADD COLUMN {column} {data_type}
                    """
                )

    # -----------------------------------------------------
    # odds 테이블
    # -----------------------------------------------------

    if not table_exists(cur, "odds"):

        cur.execute("""
            CREATE TABLE odds (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                schedule_id TEXT NOT NULL,

                company_id INTEGER,

                company_name TEXT,

                initial_home REAL,

                initial_draw REAL,

                initial_away REAL,

                final_home REAL,

                final_draw REAL,

                final_away REAL,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(schedule_id, company_id)
            )
        """)

    else:

        columns = get_columns(
            cur,
            "odds"
        )

        required_columns = {

            "schedule_id":
                "TEXT",

            "company_id":
                "INTEGER",

            "company_name":
                "TEXT",

            "initial_home":
                "REAL",

            "initial_draw":
                "REAL",

            "initial_away":
                "REAL",

            "final_home":
                "REAL",

            "final_draw":
                "REAL",

            "final_away":
                "REAL",

            "created_at":
                "TEXT"

        }

        for column, data_type in required_columns.items():

            if column not in columns:

                cur.execute(
                    f"""
                    ALTER TABLE odds
                    ADD COLUMN {column} {data_type}
                    """
                )

    conn.commit()

    # =====================================================
    # 인덱스
    # =====================================================

    # 기존에 잘못된 인덱스가 있으면 삭제
    cur.execute("""
        DROP INDEX IF EXISTS idx_matches_schedule
    """)

    cur.execute("""
        DROP INDEX IF EXISTS idx_odds_schedule
    """)

    # matches에 schedule_id가 실제 존재할 때만 생성
    match_columns = get_columns(
        cur,
        "matches"
    )

    if "schedule_id" in match_columns:

        cur.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_matches_schedule
            ON matches(schedule_id)
        """)

    odds_columns = get_columns(
        cur,
        "odds"
    )

    if "schedule_id" in odds_columns:

        cur.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_odds_schedule
            ON odds(schedule_id)
        """)

    conn.commit()
    conn.close()


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
    result
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id
        FROM matches
        WHERE schedule_id = ?
    """, (
        str(schedule_id),
    ))

    existing = cur.fetchone()

    if existing:

        cur.execute("""
            UPDATE matches
            SET
                match_date = ?,
                home_team = ?,
                away_team = ?,
                home_score = ?,
                away_score = ?,
                result = ?,
                source = 'Scoreman'
            WHERE schedule_id = ?
        """, (
            match_date,
            home_team,
            away_team,
            home_score,
            away_score,
            result,
            str(schedule_id)
        ))

    else:

        cur.execute("""
            INSERT INTO matches (
                schedule_id,
                match_date,
                home_team,
                away_team,
                home_score,
                away_score,
                result,
                source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Scoreman')
        """, (
            str(schedule_id),
            match_date,
            home_team,
            away_team,
            home_score,
            away_score,
            result
        ))

    conn.commit()
    conn.close()


# =========================================================
# 배당 저장
# =========================================================

def save_odds(
    schedule_id,
    company_id,
    company_name,
    initial_home,
    initial_draw,
    initial_away,
    final_home,
    final_draw,
    final_away
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id
        FROM odds
        WHERE schedule_id = ?
        AND company_id = ?
    """, (
        str(schedule_id),
        company_id
    ))

    existing = cur.fetchone()

    if existing:

        cur.execute("""
            UPDATE odds
            SET
                company_name = ?,
                initial_home = ?,
                initial_draw = ?,
                initial_away = ?,
                final_home = ?,
                final_draw = ?,
                final_away = ?
            WHERE schedule_id = ?
            AND company_id = ?
        """, (
            company_name,
            initial_home,
            initial_draw,
            initial_away,
            final_home,
            final_draw,
            final_away,
            str(schedule_id),
            company_id
        ))

    else:

        cur.execute("""
            INSERT INTO odds (
                schedule_id,
                company_id,
                company_name,
                initial_home,
                initial_draw,
                initial_away,
                final_home,
                final_draw,
                final_away
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(schedule_id),
            company_id,
            company_name,
            initial_home,
            initial_draw,
            initial_away,
            final_home,
            final_draw,
            final_away
        ))

    conn.commit()
    conn.close()


# =========================================================
# 경기 수
# =========================================================

def get_match_count():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM matches
        WHERE schedule_id IS NOT NULL
    """)

    count = cur.fetchone()[0]

    conn.close()

    return count


# =========================================================
# 배당 수
# =========================================================

def get_odds_count():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM odds
        WHERE schedule_id IS NOT NULL
    """)

    count = cur.fetchone()[0]

    conn.close()

    return count


# =========================================================
# 특정 경기
# =========================================================

def get_match(schedule_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM matches
        WHERE schedule_id = ?
    """, (
        str(schedule_id),
    ))

    row = cur.fetchone()

    conn.close()

    if row:
        return dict(row)

    return None


# =========================================================
# 특정 경기 배당
# =========================================================

def get_odds(schedule_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM odds
        WHERE schedule_id = ?
        ORDER BY company_id
    """, (
        str(schedule_id),
    ))

    rows = cur.fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


# =========================================================
# 전체 경기
# =========================================================

def get_all_matches():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM matches
        ORDER BY id DESC
    """)

    rows = cur.fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


# =========================================================
# 전체 배당
# =========================================================

def get_all_odds():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM odds
        ORDER BY id DESC
    """)

    rows = cur.fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


# =========================================================
# DB 전체 삭제
# =========================================================

def clear_database():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM odds
    """)

    cur.execute("""
        DELETE FROM matches
    """)

    conn.commit()
    conn.close()
