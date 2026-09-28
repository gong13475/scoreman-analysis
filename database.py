import sqlite3
import os

DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "scoreman_test.db"
)


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_database():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY,
            schedule_id TEXT,
            home_team TEXT,
            away_team TEXT,
            match_date TEXT,
            home_score INTEGER,
            away_score INTEGER,
            result TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS odds (
            id INTEGER PRIMARY KEY,
            schedule_id TEXT,
            company_id INTEGER,
            company_name TEXT,

            euro_f_home REAL,
            euro_f_draw REAL,
            euro_f_away REAL,

            euro_l_home REAL,
            euro_l_draw REAL,
            euro_l_away REAL
        )
    """)

    conn.commit()
    conn.close()


def save_match(
    schedule_id,
    home_team,
    away_team,
    match_date="",
    home_score=None,
    away_score=None,
    result=""
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO matches (
            schedule_id,
            home_team,
            away_team,
            match_date,
            home_score,
            away_score,
            result
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        str(schedule_id),
        home_team,
        away_team,
        match_date,
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
    euro_f,
    euro_l
):

    conn = get_connection()
    cur = conn.cursor()

    def value(d, key):
        try:
            return float(d.get(key))
        except:
            return None

    cur.execute("""
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(schedule_id),
        company_id,
        company_name,

        value(euro_f, "u"),
        value(euro_f, "g"),
        value(euro_f, "d"),

        value(euro_l, "u"),
        value(euro_l, "g"),
        value(euro_l, "d")
    ))

    conn.commit()
    conn.close()


def save_all_odds(schedule_id, mixodds):

    count = 0

    for item in mixodds:

        try:

            save_odds(
                schedule_id,
                item.get("cid"),
                item.get("cn", ""),
                item.get("euro", {}).get("f", {}),
                item.get("euro", {}).get("l", {})
            )

            count += 1

        except Exception:
            pass

    return count


def get_match(schedule_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM matches
        WHERE schedule_id=?
        """,
        (str(schedule_id),)
    )

    row = cur.fetchone()

    conn.close()

    return row


def get_odds(schedule_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM odds
        WHERE schedule_id=?
        ORDER BY id
        """,
        (str(schedule_id),)
    )

    rows = cur.fetchall()

    conn.close()

    return rows


def get_database_stats():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM matches")
    matches = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM odds")
    odds = cur.fetchone()[0]

    conn.close()

    return {
        "matches": matches,
        "odds": odds
    }
def get_match_count():

    conn = get_connection()

    try:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM matches")

        return cur.fetchone()[0]

    finally:
        conn.close()


def get_odds_count():

    conn = get_connection()

    try:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM odds")

        return cur.fetchone()[0]

    finally:
        conn.close()
def get_match_count():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM matches")
        return cur.fetchone()[0]
    finally:
        conn.close()


def get_odds_count():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM odds")
        return cur.fetchone()[0]
    finally:
        conn.close()
