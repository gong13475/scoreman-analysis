import sqlite3
import os

DB_FILE = "historical_odds.db"


def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    conn = get_connection()
    cur = conn.cursor()

    # -----------------------------------------------------
    # 경기 테이블
    # -----------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id TEXT UNIQUE,
            home_team TEXT,
            away_team TEXT,
            match_date TEXT,
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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS odds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id TEXT,
            company_id INTEGER,
            company_name TEXT,

            euro_first_home REAL,
            euro_first_draw REAL,
            euro_first_away REAL,

            euro_last_home REAL,
            euro_last_draw REAL,
            euro_last_away REAL,

            euro_result_home REAL,
            euro_result_draw REAL,
            euro_result_away REAL,

            ou_first_home REAL,
            ou_first_goal REAL,
            ou_first_away REAL,

            ou_last_home REAL,
            ou_last_goal REAL,
            ou_last_away REAL,

            ah_first_home REAL,
            ah_first_goal REAL,
            ah_first_away REAL,

            ah_last_home REAL,
            ah_last_goal REAL,
            ah_last_away REAL,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(schedule_id, company_id)
        )
    """)

    # -----------------------------------------------------
    # 기존 인덱스가 꼬여 있어도 안전하게 처리
    # -----------------------------------------------------
    try:
        cur.execute("DROP INDEX IF EXISTS idx_matches_schedule")
    except Exception:
        pass

    try:
        cur.execute("DROP INDEX IF EXISTS idx_odds_schedule")
    except Exception:
        pass

    # -----------------------------------------------------
    # 인덱스 재생성
    # -----------------------------------------------------
    cur.execute("""
        CREATE INDEX idx_matches_schedule
        ON matches(schedule_id)
    """)

    cur.execute("""
        CREATE INDEX idx_odds_schedule
        ON odds(schedule_id)
    """)

    conn.commit()
    conn.close()


# ---------------------------------------------------------
# 경기 저장
# ---------------------------------------------------------
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
            result,
            source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Scoreman')
        ON CONFLICT(schedule_id)
        DO UPDATE SET
            home_team=excluded.home_team,
            away_team=excluded.away_team,
            match_date=excluded.match_date,
            home_score=excluded.home_score,
            away_score=excluded.away_score,
            result=excluded.result
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


# ---------------------------------------------------------
# 배당 저장
# ---------------------------------------------------------
def save_odds(schedule_id, item):

    conn = get_connection()
    cur = conn.cursor()

    euro = item.get("euro", {})
    ef = euro.get("f", {})
    el = euro.get("l", {})
    er = euro.get("r", {})

    ou = item.get("ou", {})
    ouf = ou.get("f", {})
    oul = ou.get("l", {})

    ah = item.get("ah", {})
    ahf = ah.get("f", {})
    ahl = ah.get("l", {})

    def num(v):
        try:
            return float(v)
        except:
            return None

    cur.execute("""
        INSERT INTO odds (
            schedule_id,
            company_id,
            company_name,

            euro_first_home,
            euro_first_draw,
            euro_first_away,

            euro_last_home,
            euro_last_draw,
            euro_last_away,

            euro_result_home,
            euro_result_draw,
            euro_result_away,

            ou_first_home,
            ou_first_goal,
            ou_first_away,

            ou_last_home,
            ou_last_goal,
            ou_last_away,

            ah_first_home,
            ah_first_goal,
            ah_first_away,

            ah_last_home,
            ah_last_goal,
            ah_last_away
        )
        VALUES (
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?
        )
        ON CONFLICT(schedule_id, company_id)
        DO UPDATE SET
            company_name=excluded.company_name,

            euro_first_home=excluded.euro_first_home,
            euro_first_draw=excluded.euro_first_draw,
            euro_first_away=excluded.euro_first_away,

            euro_last_home=excluded.euro_last_home,
            euro_last_draw=excluded.euro_last_draw,
            euro_last_away=excluded.euro_last_away,

            euro_result_home=excluded.euro_result_home,
            euro_result_draw=excluded.euro_result_draw,
            euro_result_away=excluded.euro_result_away,

            ou_first_home=excluded.ou_first_home,
            ou_first_goal=excluded.ou_first_goal,
            ou_first_away=excluded.ou_first_away,

            ou_last_home=excluded.ou_last_home,
            ou_last_goal=excluded.ou_last_goal,
            ou_last_away=excluded.ou_last_away,

            ah_first_home=excluded.ah_first_home,
            ah_first_goal=excluded.ah_first_goal,
            ah_first_away=excluded.ah_first_away,

            ah_last_home=excluded.ah_last_home,
            ah_last_goal=excluded.ah_last_goal,
            ah_last_away=excluded.ah_last_away
    """, (
        str(schedule_id),
        item.get("cid"),
        item.get("cn"),

        num(ef.get("u")),
        num(ef.get("g")),
        num(ef.get("d")),

        num(el.get("u")),
        num(el.get("g")),
        num(el.get("d")),

        num(er.get("u")),
        num(er.get("g")),
        num(er.get("d")),

        num(ouf.get("u")),
        num(ouf.get("g")),
        num(ouf.get("d")),

        num(oul.get("u")),
        num(oul.get("g")),
        num(oul.get("d")),

        num(ahf.get("u")),
        num(ahf.get("g")),
        num(ahf.get("d")),

        num(ahl.get("u")),
        num(ahl.get("g")),
        num(ahl.get("d"))
    ))

    conn.commit()
    conn.close()


# ---------------------------------------------------------
# 경기 수
# ---------------------------------------------------------
def count_matches():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM matches")
    result = cur.fetchone()[0]

    conn.close()
    return result


# ---------------------------------------------------------
# 배당 수
# ---------------------------------------------------------
def count_odds():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM odds")
    result = cur.fetchone()[0]

    conn.close()
    return result


# ---------------------------------------------------------
# 경기 목록
# ---------------------------------------------------------
def get_matches():
    conn = get_connection()

    rows = conn.execute("""
        SELECT *
        FROM matches
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return [dict(row) for row in rows]


# ---------------------------------------------------------
# 배당 목록
# ---------------------------------------------------------
def get_odds(schedule_id=None):

    conn = get_connection()

    if schedule_id:
        rows = conn.execute("""
            SELECT *
            FROM odds
            WHERE schedule_id = ?
            ORDER BY company_id
        """, (str(schedule_id),)).fetchall()
    else:
        rows = conn.execute("""
            SELECT *
            FROM odds
            ORDER BY id DESC
        """).fetchall()

    conn.close()

    return [dict(row) for row in rows]
