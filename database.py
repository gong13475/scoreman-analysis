import sqlite3

DB_FILE = "historical_odds.db"


def get_connection():
    return sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )


def create_database():

    conn = get_connection()
    cursor = conn.cursor()

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
            UNIQUE(scoreman_id, company)
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
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO matches (
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
        scoreman_id,
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
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO odds (
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
        scoreman_id,
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
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM matches"
    )

    result = cursor.fetchone()[0]

    conn.close()

    return result


def get_odds_count():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM odds"
    )

    result = cursor.fetchone()[0]

    conn.close()

    return result


def get_all_data():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            m.scoreman_id,
            m.match_date,
            m.home_team,
            m.away_team,
            m.home_score,
            m.away_score,
            m.result,
            o.company,
            o.initial_home,
            o.initial_draw,
            o.initial_away,
            o.final_home,
            o.final_draw,
            o.final_away
        FROM matches m
        LEFT JOIN odds o
        ON m.scoreman_id = o.scoreman_id
        ORDER BY m.id DESC
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows
