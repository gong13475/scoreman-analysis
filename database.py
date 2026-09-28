import sqlite3
from datetime import datetime


DB_FILE = "historical_odds.db"


def get_connection():
    return sqlite3.connect(DB_FILE)


def create_database():

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

            created_at TEXT

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

            created_at TEXT,

            UNIQUE(
                scoreman_id,
                company
            )

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

    create_database()

    conn = get_connection()
    cur = conn.cursor()

    now = datetime.now().isoformat()

    cur.execute("""
        INSERT INTO matches (
            scoreman_id,
            match_date,
            home_team,
            away_team,
            home_score,
            away_score,
            result,
            created_at
        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(scoreman_id)
        DO UPDATE SET

            match_date = excluded.match_date,

            home_team = excluded.home_team,

            away_team = excluded.away_team,

            home_score = excluded.home_score,

            away_score = excluded.away_score,

            result = excluded.result

    """, (
        scoreman_id,
        match_date,
        home_team,
        away_team,
        home_score,
        away_score,
        result,
        now
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

    create_database()

    conn = get_connection()
    cur = conn.cursor()

    now = datetime.now().isoformat()

    cur.execute("""
        INSERT INTO odds (

            scoreman_id,

            company,

            initial_home,

            initial_draw,

            initial_away,

            final_home,

            final_draw,

            final_away,

            created_at

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(
            scoreman_id,
            company
        )

        DO UPDATE SET

            initial_home =
                excluded.initial_home,

            initial_draw =
                excluded.initial_draw,

            initial_away =
                excluded.initial_away,

            final_home =
                excluded.final_home,

            final_draw =
                excluded.final_draw,

            final_away =
                excluded.final_away

    """, (

        scoreman_id,

        company,

        initial_home,

        initial_draw,

        initial_away,

        final_home,

        final_draw,

        final_away,

        now

    ))

    conn.commit()
    conn.close()


def get_match_count():

    create_database()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM matches"
    )

    count = cur.fetchone()[0]

    conn.close()

    return count


def get_odds_count():

    create_database()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM odds"
    )

    count = cur.fetchone()[0]

    conn.close()

    return count


def get_all_data():

    create_database()

    conn = get_connection()

    query = """
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

        ON m.scoreman_id =
           o.scoreman_id

        ORDER BY
            m.match_date DESC
    """

    rows = conn.execute(query).fetchall()

    conn.close()

    return rows
