import sqlite3
from pathlib import Path
from datetime import datetime


# =========================================================
# DB 기본 설정
# =========================================================

DB_FILE = Path(__file__).parent / "historical_odds.db"


# =========================================================
# DB 연결
# =========================================================

def get_connection():

    conn = sqlite3.connect(
        DB_FILE
    )

    conn.row_factory = sqlite3.Row

    return conn


# =========================================================
# 데이터베이스 생성
# =========================================================

def create_database():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            source TEXT,

            sport TEXT,

            league TEXT,

            match_date TEXT,

            match_time TEXT,

            home_team TEXT,

            away_team TEXT,

            home_odds REAL,

            draw_odds REAL,

            away_odds REAL,

            result TEXT,

            created_at TEXT,

            UNIQUE(
                source,
                match_date,
                match_time,
                home_team,
                away_team
            )
        )
    """)

    conn.commit()

    conn.close()


# =========================================================
# 경기 저장
# =========================================================

def save_match(
    source="Scoreman",
    sport="축구",
    league="",
    match_date="",
    match_time="",
    home_team="",
    away_team="",
    home_odds=0,
    draw_odds=0,
    away_odds=0,
    result=""
):

    create_database()

    conn = get_connection()

    cursor = conn.cursor()

    try:

        cursor.execute("""
            INSERT OR IGNORE INTO matches (

                source,
                sport,
                league,
                match_date,
                match_time,
                home_team,
                away_team,
                home_odds,
                draw_odds,
                away_odds,
                result,
                created_at

            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (

            source,
            sport,
            league,
            match_date,
            match_time,
            home_team,
            away_team,
            home_odds,
            draw_odds,
            away_odds,
            result,
            datetime.now().isoformat()

        ))

        conn.commit()

        inserted = cursor.rowcount

    finally:

        conn.close()

    return inserted


# =========================================================
# 경기 여러 개 저장
# =========================================================

def save_matches(matches):

    create_database()

    count = 0

    for match in matches:

        result = save_match(

            source=match.get(
                "source",
                "Scoreman"
            ),

            sport=match.get(
                "sport",
                "축구"
            ),

            league=match.get(
                "league",
                ""
            ),

            match_date=match.get(
                "match_date",
                ""
            ),

            match_time=match.get(
                "match_time",
                ""
            ),

            home_team=match.get(
                "home_team",
                ""
            ),

            away_team=match.get(
                "away_team",
                ""
            ),

            home_odds=match.get(
                "home_odds",
                0
            ),

            draw_odds=match.get(
                "draw_odds",
                0
            ),

            away_odds=match.get(
                "away_odds",
                0
            ),

            result=match.get(
                "result",
                ""
            )
        )

        count += result

    return count


# =========================================================
# DB 상태
# =========================================================

def get_database_status():

    create_database()

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM matches
    """)

    total = cursor.fetchone()["count"]

    conn.close()

    return {
        "database": str(DB_FILE),
        "matches": total
    }


# =========================================================
# 경기 조회
# =========================================================

def get_matches(
    limit=10000
):

    create_database()

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT *

        FROM matches

        ORDER BY
            match_date DESC,
            match_time DESC

        LIMIT ?
    """, (
        limit,
    ))

    rows = cursor.fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


# =========================================================
# 전체 경기 삭제
# =========================================================

def clear_database():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM matches"
    )

    conn.commit()

    conn.close()


# =========================================================
# 실행 테스트
# =========================================================

if __name__ == "__main__":

    create_database()

    print(
        get_database_status()
    )
