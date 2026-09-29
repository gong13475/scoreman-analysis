import sqlite3
from pathlib import Path
from datetime import datetime


DB_FILE = Path(__file__).parent / "historical_odds.db"


# =========================================================
# DB 연결
# =========================================================

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
# DB 초기화
# =========================================================

def init_database():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            source TEXT,
            sport TEXT,
            league TEXT,

            game_date TEXT,
            game_time TEXT,

            home_team TEXT,
            away_team TEXT,

            home_odds REAL,
            draw_odds REAL,
            away_odds REAL,

            result TEXT,

            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


# =========================================================
# 경기 저장
# =========================================================

def save_game(
    source,
    sport,
    league,
    game_date,
    game_time,
    home_team,
    away_team,
    home_odds,
    draw_odds,
    away_odds,
    result=""
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO games (
            source,
            sport,
            league,
            game_date,
            game_time,
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
        game_date,
        game_time,
        home_team,
        away_team,
        home_odds,
        draw_odds,
        away_odds,
        result,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


# =========================================================
# 경기 여러 개 저장
# =========================================================

def save_games(games):

    if not games:
        return 0

    conn = get_connection()
    cur = conn.cursor()

    count = 0

    for game in games:

        cur.execute("""
            INSERT INTO games (
                source,
                sport,
                league,
                game_date,
                game_time,
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
            game.get("source", "Scoreman"),
            game.get("sport", ""),
            game.get("league", ""),
            game.get("game_date", ""),
            game.get("game_time", ""),
            game.get("home_team", ""),
            game.get("away_team", ""),
            game.get("home_odds", 0),
            game.get("draw_odds", 0),
            game.get("away_odds", 0),
            game.get("result", ""),
            datetime.now().isoformat()
        ))

        count += 1

    conn.commit()
    conn.close()

    return count


# =========================================================
# 경기 조회
# =========================================================

def get_games(
    sport="",
    league="",
    source="",
    limit=5000
):

    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT *
        FROM games
        WHERE 1=1
    """

    params = []

    if sport:

        query += " AND sport = ?"
        params.append(sport)

    if league:

        query += " AND league = ?"
        params.append(league)

    if source:

        query += " AND source = ?"
        params.append(source)

    query += """
        ORDER BY game_date DESC, game_time DESC
        LIMIT ?
    """

    params.append(limit)

    cur.execute(query, params)

    rows = cur.fetchall()

    conn.close()

    return [dict(row) for row in rows]


# =========================================================
# 전체 경기
# =========================================================

def get_all_games(limit=10000):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM games
        ORDER BY game_date DESC, game_time DESC
        LIMIT ?
    """, (limit,))

    rows = cur.fetchall()

    conn.close()

    return [dict(row) for row in rows]


# =========================================================
# DB 경기수
# =========================================================

def count_games():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) AS cnt
        FROM games
    """)

    result = cur.fetchone()["cnt"]

    conn.close()

    return result


# =========================================================
# DB 삭제
# =========================================================

def clear_database():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM games")

    conn.commit()
    conn.close()
