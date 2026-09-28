import sqlite3

DB_FILE = "scoreman.db"


def get_connection():
    return sqlite3.connect(DB_FILE)


def init_database():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
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

    cur.execute("""
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def save_match(
    scoreman_id,
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
        INSERT OR REPLACE INTO matches
        (
            scoreman_id,
            match_date,
            home_team,
            away_team,
            home_score,
            away_score,
            result
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        str(scoreman_id),
        match_date,
        home_team,
        away_team,
        home_score,
        away_score,
        result
    ))

    conn.commit()
    conn.close()


def save_odds(
    scoreman_id,
    company,
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
        INSERT INTO odds
        (
            scoreman_id,
            company,
            initial_home,
            initial_draw,
            initial_away,
            final_home,
            final_draw,
            final_away
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(scoreman_id),
        company,
        initial_home,
        initial_draw,
        initial_away,
        final_home,
        final_draw,
        final_away
    ))

    conn.commit()
    conn.close()


def get_match_count():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM matches"
    )

    result = cur.fetchone()[0]

    conn.close()

    return result


def get_odds_count():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM odds"
    )

    result = cur.fetchone()[0]

    conn.close()

    return result


def get_matches():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            scoreman_id,
            match_date,
            home_team,
            away_team,
            home_score,
            away_score,
            result
        FROM matches
        ORDER BY id DESC
    """)

    result = cur.fetchall()

    conn.close()

    return result


def get_odds():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            scoreman_id,
            company,
            initial_home,
            initial_draw,
            initial_away,
            final_home,
            final_draw,
            final_away
        FROM odds
        ORDER BY id DESC
    """)

    result = cur.fetchall()

    conn.close()

    return result


init_database()
