import sqlite3
from pathlib import Path


# =========================================================
# DB 파일
# =========================================================

DB_FILE = Path(__file__).resolve().parent / "historical_odds.db"


# =========================================================
# DB 연결
# =========================================================

def get_connection():
    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


# =========================================================
# DB 초기화
# =========================================================

def init_database():

    conn = get_connection()

    cursor = conn.cursor()

    # -----------------------------------------------------
    # 경기 테이블
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            schedule_id TEXT UNIQUE,

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

    # -----------------------------------------------------
    # 배당 테이블
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS odds (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            schedule_id TEXT,

            company_id TEXT,

            company_name TEXT,

            initial_home REAL,

            initial_draw REAL,

            initial_away REAL,

            final_home REAL,

            final_draw REAL,

            final_away REAL,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(
                schedule_id,
                company_id
            )
        )
    """)

    # -----------------------------------------------------
    # 인덱스
    # -----------------------------------------------------

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_matches_schedule
        ON matches(schedule_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_matches_date
        ON matches(match_date)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_odds_schedule
        ON odds(schedule_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_odds_company
        ON odds(company_name)
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
    result,
    source="Scoreman"
):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
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

        VALUES (?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(schedule_id)
        DO UPDATE SET

            match_date = excluded.match_date,

            home_team = excluded.home_team,

            away_team = excluded.away_team,

            home_score = excluded.home_score,

            away_score = excluded.away_score,

            result = excluded.result,

            source = excluded.source
    """, (

        str(schedule_id),

        match_date,

        home_team,

        away_team,

        home_score,

        away_score,

        result,

        source

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

    cursor = conn.cursor()

    cursor.execute("""
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

        ON CONFLICT(
            schedule_id,
            company_id
        )

        DO UPDATE SET

            company_name = excluded.company_name,

            initial_home = excluded.initial_home,

            initial_draw = excluded.initial_draw,

            initial_away = excluded.initial_away,

            final_home = excluded.final_home,

            final_draw = excluded.final_draw,

            final_away = excluded.final_away
    """, (

        str(schedule_id),

        str(company_id)
        if company_id is not None
        else "",

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
# 경기 개수
# =========================================================

def get_match_count():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM matches
    """)

    count = cursor.fetchone()[0]

    conn.close()

    return count


# =========================================================
# 배당 개수
# =========================================================

def get_odds_count():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM odds
    """)

    count = cursor.fetchone()[0]

    conn.close()

    return count


# =========================================================
# 전체 경기
# =========================================================

def get_all_matches():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT

            schedule_id,

            match_date,

            home_team,

            away_team,

            home_score,

            away_score,

            result,

            source

        FROM matches

        ORDER BY

            CASE
                WHEN match_date IS NULL THEN 1
                ELSE 0
            END,

            match_date DESC,

            id DESC
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# 전체 배당
# =========================================================

def get_all_odds():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT

            schedule_id,

            company_id,

            company_name,

            initial_home,

            initial_draw,

            initial_away,

            final_home,

            final_draw,

            final_away

        FROM odds

        ORDER BY id DESC
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# 특정 경기
# =========================================================

def get_match(schedule_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT *

        FROM matches

        WHERE schedule_id = ?

        LIMIT 1
    """, (str(schedule_id),))

    row = cursor.fetchone()

    conn.close()

    return row


# =========================================================
# 특정 경기 배당
# =========================================================

def get_match_odds(schedule_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT *

        FROM odds

        WHERE schedule_id = ?

        ORDER BY company_name
    """, (str(schedule_id),))

    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# DB 전체 삭제
# =========================================================

def clear_database():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM odds
    """)

    cursor.execute("""
        DELETE FROM matches
    """)

    conn.commit()

    conn.close()


# =========================================================
# DB 테스트
# =========================================================

if __name__ == "__main__":

    init_database()

    print("================================")
    print("SQLite DB 초기화 완료")
    print("DB 위치:")
    print(DB_FILE)
    print("경기 수:", get_match_count())
    print("배당 수:", get_odds_count())
    print("================================")
