import sqlite3
import os

DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "scoreman_final_v3.db"
)


def get_connection():
    return sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )


def init_database():

    conn = get_connection()

    try:
        cur = conn.cursor()

        cur.execute(
            "CREATE TABLE IF NOT EXISTS matches ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "schedule_id TEXT NOT NULL,"
            "home_team TEXT,"
            "away_team TEXT,"
            "match_date TEXT,"
            "home_score INTEGER,"
            "away_score INTEGER,"
            "result TEXT,"
            "page_url TEXT,"
            "created_at TEXT"
            ")"
        )

        cur.execute(
            "CREATE TABLE IF NOT EXISTS odds ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "schedule_id TEXT NOT NULL,"
            "company_id INTEGER,"
            "company_name TEXT,"
            "euro_f_home REAL,"
            "euro_f_draw REAL,"
            "euro_f_away REAL,"
            "euro_l_home REAL,"
            "euro_l_draw REAL,"
            "euro_l_away REAL,"
            "ou_f_home REAL,"
            "ou_f_goal REAL,"
            "ou_f_away REAL,"
            "ou_l_home REAL,"
            "ou_l_goal REAL,"
            "ou_l_away REAL,"
            "ah_f_home REAL,"
            "ah_f_goal REAL,"
            "ah_f_away REAL,"
            "ah_l_home REAL,"
            "ah_l_goal REAL,"
            "ah_l_away REAL,"
            "created_at TEXT"
            ")"
        )

        conn.commit()

    finally:
        conn.close()


def save_match(
    schedule_id,
    home_team="",
    away_team="",
    match_date="",
    home_score=None,
    away_score=None,
    result="",
    page_url=""
):

    conn = get_connection()

    try:
        cur = conn.cursor()

        cur.execute(
            "DELETE FROM matches WHERE schedule_id=?",
            (str(schedule_id),)
        )

        cur.execute(
            """
            INSERT INTO matches (
                schedule_id,
                home_team,
                away_team,
                match_date,
                home_score,
                away_score,
                result,
                page_url,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                str(schedule_id),
                home_team,
                away_team,
                match_date,
                home_score,
                away_score,
                result,
                page_url
            )
        )

        conn.commit()

    finally:
        conn.close()


def to_float(value):

    try:
        if value is None:
            return None

        value = str(value).strip()

        if value in ("", "-", "None", "null"):
            return None

        return float(value)

    except Exception:
        return None


def save_odds(
    schedule_id,
    company_id,
    company_name,
    euro_f,
    euro_l,
    ou_f,
    ou_l,
    ah_f,
    ah_l
):

    conn = get_connection()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO odds (
                schedule_id,
                company_id,
                company_name,

                euro_f_home,
                euro_f_draw,
                euro_f_away,

                euro_l_home,
                euro_l_draw,
                euro_l_away,

                ou_f_home,
                ou_f_goal,
                ou_f_away,

                ou_l_home,
                ou_l_goal,
                ou_l_away,

                ah_f_home,
                ah_f_goal,
                ah_f_away,

                ah_l_home,
                ah_l_goal,
                ah_l_away,

                created_at
            )
            VALUES (
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                datetime('now')
            )
            """,
            (
                str(schedule_id),
                company_id,
                company_name,

                to_float(euro_f.get("u")),
                to_float(euro_f.get("g")),
                to_float(euro_f.get("d")),

                to_float(euro_l.get("u")),
                to_float(euro_l.get("g")),
                to_float(euro_l.get("d")),

                to_float(ou_f.get("u")),
                to_float(ou_f.get("g")),
                to_float(ou_f.get("d")),

                to_float(ou_l.get("u")),
                to_float(ou_l.get("g")),
                to_float(ou_l.get("d")),

                to_float(ah_f.get("u")),
                to_float(ah_f.get("g")),
                to_float(ah_f.get("d")),

                to_float(ah_l.get("u")),
                to_float(ah_l.get("g")),
                to_float(ah_l.get("d"))
            )
        )

        conn.commit()

    finally:
        conn.close()


def save_all_odds(schedule_id, mixodds):

    count = 0

    for item in mixodds or []:

        try:

            save_odds(
                schedule_id,
                item.get("cid"),
                item.get("cn", ""),
                item.get("euro", {}).get("f", {}),
                item.get("euro", {}).get("l", {}),
                item.get("ou", {}).get("f", {}),
                item.get("ou", {}).get("l", {}),
                item.get("ah", {}).get("f", {}),
                item.get("ah", {}).get("l", {})
            )

            count += 1

        except Exception:
            continue

    return count


def get_match(schedule_id):

    conn = get_connection()

    try:

        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM matches WHERE schedule_id=?",
            (str(schedule_id),)
        )

        row = cur.fetchone()

        if row is None:
            return None

        columns = [x[0] for x in cur.description]

        return dict(zip(columns, row))

    finally:
        conn.close()


def get_odds(schedule_id):

    conn = get_connection()

    try:

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

        columns = [x[0] for x in cur.description]

        return [
            dict(zip(columns, row))
            for row in rows
        ]

    finally:
        conn.close()


def get_database_stats():

    conn = get_connection()

    try:

        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM matches")
        match_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM odds")
        odds_count = cur.fetchone()[0]

        return {
            "matches": match_count,
            "odds": odds_count
        }

    finally:
        conn.close()
