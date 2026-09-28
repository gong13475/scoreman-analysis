import sqlite3
import os


# =========================================================
# DB 파일
# =========================================================

DB_FILE = "historical_odds.db"


# =========================================================
# DB 연결
# =========================================================

def get_connection():

    return sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )


# =========================================================
# DB 생성
# =========================================================

def create_database():

    conn = get_connection()

    cursor = conn.cursor()

    # -----------------------------------------------------
    # 경기 테이블
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            scoreman_id TEXT UNIQUE,

            match_date TEXT,

            home_team TEXT,

            away_team TEXT,

            home_score INTEGER,

            away_score INTEGER,

            result TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )
    """)


    # -----------------------------------------------------
    # 배당 테이블
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS odds (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            scoreman_id TEXT,

            company TEXT,

            initial_home REAL,

            initial_draw REAL,

            initial_away REAL,

            final_home REAL,

            final_draw REAL,

            final_away REAL,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE (
                scoreman_id,
                company
            )

   
