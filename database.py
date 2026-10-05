import os
import sqlite3
import threading


TURSO_DATABASE_URL = os.getenv(
    "TURSO_DATABASE_URL",
    ""
)

TURSO_AUTH_TOKEN = os.getenv(
    "TURSO_AUTH_TOKEN",
    ""
)

LOCAL_DB_PATH = os.getenv(
    "LOCAL_DB_PATH",
    "scoreman.db"
)

_DB_LOCK = threading.RLock()


def _get_turso_connection():

    if not TURSO_DATABASE_URL:
        return None

    if not TURSO_AUTH_TOKEN:
        return None

    try:
        import libsql_experimental as libsql

        return libsql.connect(
            TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN
        )

    except Exception:
        return None


def _get_connection():

    conn = _get_turso_connection()

    if conn is not None:
        return conn

    conn = sqlite3.connect(
        LOCAL_DB_PATH,
        check_same_thread=False,
        timeout=60
    )

    conn.row_factory = sqlite3.Row

    return conn


def _execute(
    sql,
    params=(),
    fetch=False,
    many=False
):

    with _DB_LOCK:

        conn = _get_connection()

        try:

            cursor = conn.cursor()

            if many:
                cursor.executemany(
                    sql,
                    params
                )
            else:
                cursor.execute(
                    sql,
                    params
                )

            result = None

            if fetch:

                rows = cursor.fetchall()

                result = [
                    dict(row)
                    for row in rows
                ]

            conn.commit()

            return result

        finally:
            conn.close()


# =========================================================
# 초기화
# =========================================================

def init_database():

    with _DB_LOCK:

        conn = _get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS matches (

                    schedule_id TEXT PRIMARY KEY,

                    match_date TEXT,

                    home_team TEXT,

                    away_team TEXT,

                    home_score INTEGER,

                    away_score INTEGER,

                    result TEXT,

                    source TEXT DEFAULT 'scoreman',

                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS odds (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    schedule_id TEXT NOT NULL,

                    bookmaker TEXT NOT NULL,

                    company_id TEXT,

                    home_odds REAL,

                    draw_odds REAL,

                    away_odds REAL,

                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                    UNIQUE(
                        schedule_id,
                        bookmaker
                    )
                )
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_odds_schedule
                ON odds(schedule_id)
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_odds_bookmaker
                ON odds(bookmaker)
                """
            )

            conn.commit()

        finally:
            conn.close()

    return True


# =========================================================
# 경기 저장
# =========================================================

def save_match(match):

    _execute(
        """
        INSERT INTO matches (

            schedule_id,
            match_date,
            home_team,
            away_team,
            home_score,
            away_score,
            result,
            source,
            updated_at

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)

        ON CONFLICT(schedule_id)
        DO UPDATE SET

            match_date =
                excluded.match_date,

            home_team =
                excluded.home_team,

            away_team =
                excluded.away_team,

            home_score =
                excluded.home_score,

            away_score =
                excluded.away_score,

            result =
                excluded.result,

            source =
                excluded.source,

            updated_at =
                CURRENT_TIMESTAMP
        """,

        (
            str(match.get("schedule_id")),
            match.get("match_date"),
            match.get("home_team"),
            match.get("away_team"),
            match.get("home_score"),
            match.get("away_score"),
            match.get("result"),
            match.get("source", "scoreman")
        )
    )


# =========================================================
# 경기 + 배당 저장
# =========================================================

def save_match_with_odds(
    match,
    odds_list
):

    save_match(match)

    saved = 0

    for odds in odds_list:

        bookmaker = str(
            odds.get(
                "company_name",
                ""
            )
        ).strip()

        if not bookmaker:
            continue

        _execute(
            """
            INSERT INTO odds (

                schedule_id,
                bookmaker,
                company_id,
                home_odds,
                draw_odds,
                away_odds

            )

            VALUES (?, ?, ?, ?, ?, ?)

            ON CONFLICT(
                schedule_id,
                bookmaker
            )

            DO UPDATE SET

                company_id =
                    excluded.company_id,

                home_odds =
                    excluded.home_odds,

                draw_odds =
                    excluded.draw_odds,

                away_odds =
                    excluded.away_odds
            """,

            (
                str(match["schedule_id"]),
                bookmaker,
                odds.get("company_id", ""),
                odds.get("final_home"),
                odds.get("final_draw"),
                odds.get("final_away")
            )
        )

        saved += 1

    return saved


# =========================================================
# 경기
# =========================================================

def get_match(schedule_id):

    rows = _execute(
        """
        SELECT *
        FROM matches
        WHERE schedule_id = ?
        LIMIT 1
        """,
        (str(schedule_id),),
        fetch=True
    )

    return rows[0] if rows else None


def get_all_matches():

    return _execute(
        """
        SELECT *
        FROM matches
        ORDER BY CAST(schedule_id AS INTEGER) DESC
        """,
        fetch=True
    ) or []


def get_match_count():

    rows = _execute(
        """
        SELECT COUNT(*) AS cnt
        FROM matches
        """,
        fetch=True
    )

    return int(rows[0]["cnt"]) if rows else 0


# =========================================================
# 배당
# =========================================================

def get_odds_by_match(schedule_id):

    return _execute(
        """
        SELECT

            schedule_id,
            bookmaker,
            company_id,

            home_odds AS final_home,
            draw_odds AS final_draw,
            away_odds AS final_away

        FROM odds

        WHERE schedule_id = ?

        ORDER BY bookmaker
        """,
        (str(schedule_id),),
        fetch=True
    ) or []


def get_match_final_odds(schedule_id):

    return get_odds_by_match(schedule_id)


def get_all_odds():

    return _execute(
        """
        SELECT
            schedule_id,
            bookmaker,
            company_id,
            home_odds,
            draw_odds,
            away_odds
        FROM odds
        ORDER BY CAST(schedule_id AS INTEGER) DESC
        """,
        fetch=True
    ) or []


def get_odds_count():

    rows = _execute(
        """
        SELECT COUNT(*) AS cnt
        FROM odds
        """,
        fetch=True
    )

    return int(rows[0]["cnt"]) if rows else 0


def get_odds_count_by_match(schedule_id):

    rows = _execute(
        """
        SELECT COUNT(*) AS cnt
        FROM odds
        WHERE schedule_id = ?
        """,
        (str(schedule_id),),
        fetch=True
    )

    return int(rows[0]["cnt"]) if rows else 0


# =========================================================
# 업체
# =========================================================

def get_company_names():

    rows = _execute(
        """
        SELECT DISTINCT bookmaker
        FROM odds
        WHERE bookmaker IS NOT NULL
        AND bookmaker != ''
        ORDER BY bookmaker
        """,
        fetch=True
    ) or []

    return [
        row["bookmaker"]
        for row in rows
    ]


def get_company_counts():

    rows = _execute(
        """
        SELECT
            bookmaker,
            COUNT(*) AS cnt
        FROM odds
        GROUP BY bookmaker
        ORDER BY cnt DESC
        """,
        fetch=True
    ) or []

    return {
        row["bookmaker"]: int(row["cnt"])
        for row in rows
    }


# =========================================================
# 배당 검색
# =========================================================

def search_multiple_final_odds(
    company_odds
):

    if not company_odds:
        return []

    result = []

    for company, odds in company_odds.items():

        try:

            home = float(odds["home"])
            draw = float(odds["draw"])
            away = float(odds["away"])

        except Exception:
            continue

        rows = _execute(
            """
            SELECT DISTINCT
                m.*
            FROM matches m
            INNER JOIN odds o
                ON m.schedule_id = o.schedule_id
            WHERE LOWER(o.bookmaker) = LOWER(?)
              AND ABS(o.home_odds - ?) < 0.0001
              AND ABS(o.draw_odds - ?) < 0.0001
              AND ABS(o.away_odds - ?) < 0.0001
            ORDER BY
                CAST(m.schedule_id AS INTEGER) DESC
            """,
            (
                company,
                home,
                draw,
                away
            ),
            fetch=True
        ) or []

        result.extend(rows)

    unique = {}

    for row in result:
        unique[str(row["schedule_id"])] = row

    return list(unique.values())


# =========================================================
# 상태
# =========================================================

def get_database_status():

    return {
        "matches": get_match_count(),
        "odds": get_odds_count(),
        "bookmakers": len(get_company_names())
    }


def get_storage_usage():

    try:

        if (
            TURSO_DATABASE_URL
            and TURSO_AUTH_TOKEN
        ):

            return {
                "success": True,
                "size_mb": 0,
                "size_gb": 0,
                "message": "Turso"
            }

        if os.path.exists(
            LOCAL_DB_PATH
        ):

            size = os.path.getsize(
                LOCAL_DB_PATH
            )

        else:
            size = 0

        mb = size / 1024 / 1024

        return {
            "success": True,
            "size_mb": mb,
            "size_gb": mb / 1024,
            "message": ""
        }

    except Exception as e:

        return {
            "success": False,
            "size_mb": 0,
            "size_gb": 0,
            "message": str(e)
        }


init_database()
