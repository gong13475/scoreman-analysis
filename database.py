import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).parent / "scoreman.db"


def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS odds (
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

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_matches_schedule
        ON matches(schedule_id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_odds_schedule
        ON odds(schedule_id)
    """)

    conn.commit()
    conn.close()


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
        INSERT INTO matches (
            schedule_id,
            match_date,
            home_team,
            away_team,
            home_score,
            away_score,
            result
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(schedule_id)
        DO UPDATE SET
            match_date = excluded.match_date,
            home_team = excluded.home_team,
            away_team = excluded.away_team,
            home_score = excluded.home_score,
            away_score = excluded.away_score,
            result = excluded.result
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
        ON CONFLICT(schedule_id, company_id)
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


def get_match_count():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM matches")
    count = cur.fetchone()[0]

    conn.close()
    return count


def get_odds_count():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM odds")
    count = cur.fetchone()[0]

    conn.close()
    return count


def get_match(schedule_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM matches
        WHERE schedule_id = ?
    """, (str(schedule_id),))

    row = cur.fetchone()

    conn.close()

    return dict(row) if row else None


def get_odds(schedule_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM odds
        WHERE schedule_id = ?
        ORDER BY company_id
    """, (str(schedule_id),))

    rows = cur.fetchall()

    conn.close()

    return [dict(row) for row in rows]


def get_all_matches():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM matches
        ORDER BY match_date DESC, id DESC
    """)

    rows = cur.fetchall()

    conn.close()

    return [dict(row) for row in rows]


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

    return [dict(row) for row in rows]


def clear_database():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM odds")
    cur.execute("DELETE FROM matches")

    conn.commit()
    conn.close()
