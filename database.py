# ============================================================
# database.py
# ⚽ Scoreman 분석 DB - 최종본
# ============================================================

import os
import json
import sqlite3
from pathlib import Path


DB_FILE = (
    Path(__file__).resolve().parent
    / "scoreman.db"
)


TURSO_DATABASE_URL = os.getenv(
    "TURSO_DATABASE_URL",
    ""
).strip()

TURSO_AUTH_TOKEN = os.getenv(
    "TURSO_AUTH_TOKEN",
    ""
).strip()


try:

    import libsql_experimental as libsql

    LIBSQL_AVAILABLE = True

except Exception:

    libsql = None

    LIBSQL_AVAILABLE = False


def _use_turso():

    return bool(
        TURSO_DATABASE_URL
        and TURSO_AUTH_TOKEN
        and LIBSQL_AVAILABLE
    )


def get_connection():

    if _use_turso():

        return libsql.connect(
            TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN
        )

    return sqlite3.connect(
        str(DB_FILE),
        timeout=30,
        check_same_thread=False
    )


def _execute(
    sql,
    params=(),
    fetch=False,
    many=False
):

    conn = get_connection()

    try:

        cur = conn.cursor()

        if many:

            cur.executemany(
                sql,
                params
            )

        else:

            cur.execute(
                sql,
                params
            )

        if fetch:

            return cur.fetchall()

        conn.commit()

        return []

    finally:

        try:
            conn.close()
        except Exception:
            pass


def init_database():

    _execute(
        """
        CREATE TABLE IF NOT EXISTS matches (
            schedule_id TEXT PRIMARY KEY,
            match_date TEXT,
            home_team TEXT,
            away_team TEXT,
            home_score INTEGER,
            away_score INTEGER,
            result TEXT,
            source TEXT
        )
        """
    )

    _execute(
        """
        CREATE TABLE IF NOT EXISTS odds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id TEXT NOT NULL,
            company_id TEXT,
            company_name TEXT NOT NULL,
            final_home REAL,
            final_draw REAL,
            final_away REAL,
            UNIQUE(schedule_id, company_name)
        )
        """
    )

    _execute(
        """
        CREATE TABLE IF NOT EXISTS collection_state (
            id INTEGER PRIMARY KEY,
            start_id INTEGER,
            end_id INTEGER,
            last_completed_id INTEGER,
            current INTEGER,
            total INTEGER,
            running INTEGER,
            stopped INTEGER,
            selected_companies TEXT
        )
        """
    )


def save_match(match):

    _execute(
        """
        INSERT OR REPLACE INTO matches (
            schedule_id,
            match_date,
            home_team,
            away_team,
            home_score,
            away_score,
            result,
            source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(match.get("schedule_id", "")),
            match.get("match_date", ""),
            match.get("home_team", ""),
            match.get("away_team", ""),
            match.get("home_score"),
            match.get("away_score"),
            match.get("result", ""),
            match.get("source", "scoreman")
        )
    )


def save_match_with_odds(
    match,
    odds_list
):

    save_match(match)

    saved = 0

    for row in odds_list:

        try:

            company_name = str(
                row.get(
                    "company_name",
                    ""
                )
            ).strip()

            if not company_name:
                continue

            _execute(
                """
                INSERT OR REPLACE INTO odds (
                    schedule_id,
                    company_id,
                    company_name,
                    final_home,
                    final_draw,
                    final_away
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(
                        match.get(
                            "schedule_id",
                            ""
                        )
                    ),
                    str(
                        row.get(
                            "company_id",
                            ""
                        )
                    ),
                    company_name,
                    float(
                        row["final_home"]
                    ),
                    float(
                        row["final_draw"]
                    ),
                    float(
                        row["final_away"]
                    )
                )
            )

            saved += 1

        except Exception:
            continue

    return saved


def get_match(schedule_id):

    rows = _execute(
        """
        SELECT
            schedule_id,
            match_date,
            home_team,
            away_team,
            home_score,
            away_score,
            result,
            source
        FROM matches
        WHERE schedule_id = ?
        LIMIT 1
        """,
        (str(schedule_id),),
        fetch=True
    )

    if not rows:
        return None

    r = rows[0]

    return {
        "schedule_id": r[0],
        "match_date": r[1],
        "home_team": r[2],
        "away_team": r[3],
        "home_score": r[4],
        "away_score": r[5],
        "result": r[6],
        "source": r[7]
    }


def get_all_matches():

    rows = _execute(
        """
        SELECT
            schedule_id,
            match_date,
            home_team,
            away_team,
            home_score,
            away_score,
            result,
            source
        FROM matches
        ORDER BY schedule_id DESC
        """,
        fetch=True
    )

    return [
        {
            "schedule_id": r[0],
            "match_date": r[1],
            "home_team": r[2],
            "away_team": r[3],
            "home_score": r[4],
            "away_score": r[5],
            "result": r[6],
            "source": r[7]
        }
        for r in rows
    ]


def get_odds_by_match(schedule_id):

    rows = _execute(
        """
        SELECT
            company_id,
            company_name,
            final_home,
            final_draw,
            final_away
        FROM odds
        WHERE schedule_id = ?
        ORDER BY company_name
        """,
        (str(schedule_id),),
        fetch=True
    )

    return [
        {
            "company_id": r[0],
            "company_name": r[1],
            "bookmaker": r[1],
            "final_home": r[2],
            "final_draw": r[3],
            "final_away": r[4],
            "home_odds": r[2],
            "draw_odds": r[3],
            "away_odds": r[4]
        }
        for r in rows
    ]


def get_company_list():

    rows = _execute(
        """
        SELECT DISTINCT TRIM(company_name)
        FROM odds
        WHERE company_name IS NOT NULL
        AND TRIM(company_name) <> ''
        ORDER BY TRIM(company_name)
        """,
        fetch=True
    )

    return [
        str(r[0]).strip()
        for r in rows
        if r[0]
    ]


def get_company_counts():

    rows = _execute(
        """
        SELECT
            TRIM(company_name),
            COUNT(DISTINCT schedule_id)
        FROM odds
        WHERE company_name IS NOT NULL
        AND TRIM(company_name) <> ''
        GROUP BY TRIM(company_name)
        ORDER BY COUNT(DISTINCT schedule_id) DESC
        """,
        fetch=True
    )

    return {
        str(r[0]): int(r[1] or 0)
        for r in rows
        if r[0]
    }


def get_database_status():

    try:

        matches = _execute(
            "SELECT COUNT(*) FROM matches",
            fetch=True
        )[0][0]

    except Exception:

        matches = 0

    try:

        odds = _execute(
            "SELECT COUNT(*) FROM odds",
            fetch=True
        )[0][0]

    except Exception:

        odds = 0

    try:

        bookmakers = _execute(
            """
            SELECT COUNT(DISTINCT TRIM(company_name))
            FROM odds
            WHERE company_name IS NOT NULL
            AND TRIM(company_name) <> ''
            """,
            fetch=True
        )[0][0]

    except Exception:

        bookmakers = 0

    return {
        "matches": int(matches or 0),
        "odds": int(odds or 0),
        "bookmakers": int(bookmakers or 0)
    }


def get_database_info():

    return {
        "database_url_configured":
            bool(TURSO_DATABASE_URL),

        "auth_token_configured":
            bool(TURSO_AUTH_TOKEN),

        "libsql_available":
            bool(LIBSQL_AVAILABLE),

        "using_turso":
            bool(_use_turso())
    }


def save_collection_state(
    start_id,
    end_id,
    last_completed_id,
    current,
    total,
    running,
    stopped,
    selected_companies=None
):

    selected_json = json.dumps(
        selected_companies,
        ensure_ascii=False
    )

    _execute(
        """
        INSERT OR REPLACE INTO collection_state (
            id,
            start_id,
            end_id,
            last_completed_id,
            current,
            total,
            running,
            stopped,
            selected_companies
        )
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(start_id),
            int(end_id),
            int(last_completed_id or 0),
            int(current or 0),
            int(total or 0),
            1 if running else 0,
            1 if stopped else 0,
            selected_json
        )
    )


def get_collection_state():

    try:

        rows = _execute(
            """
            SELECT
                start_id,
                end_id,
                last_completed_id,
                current,
                total,
                running,
                stopped,
                selected_companies
            FROM collection_state
            WHERE id = 1
            LIMIT 1
            """,
            fetch=True
        )

        if not rows:

            return {
                "start_id": None,
                "end_id": None,
                "last_completed_id": 0,
                "current": 0,
                "total": 0,
                "running": False,
                "stopped": False,
                "selected_companies": None
            }

        r = rows[0]

        try:
            selected = json.loads(r[7])
        except Exception:
            selected = None

        return {
            "start_id": r[0],
            "end_id": r[1],
            "last_completed_id": r[2] or 0,
            "current": r[3] or 0,
            "total": r[4] or 0,
            "running": bool(r[5]),
            "stopped": bool(r[6]),
            "selected_companies": selected
        }

    except Exception:

        return {}


def get_storage_usage():

    if _use_turso():

        try:

            rows = _execute(
                """
                SELECT
                    page_count,
                    page_size
                FROM pragma_page_count(),
                     pragma_page_size()
                """,
                fetch=True
            )

            if rows:

                size_bytes = (
                    int(rows[0][0] or 0)
                    * int(rows[0][1] or 0)
                )

                size_mb = (
                    size_bytes
                    / 1024
                    / 1024
                )

                return {
                    "success": True,
                    "size_mb": size_mb,
                    "size_gb": size_mb / 1024,
                    "storage_type": "Turso"
                }

        except Exception:
            pass

    try:

        if DB_FILE.exists():

            size_bytes = DB_FILE.stat().st_size

            size_mb = (
                size_bytes
                / 1024
                / 1024
            )

            return {
                "success": True,
                "size_mb": size_mb,
                "size_gb": size_mb / 1024,
                "storage_type": "SQLite"
            }

    except Exception:
        pass

    return {
        "success": False,
        "size_mb": 0,
        "size_gb": 0,
        "storage_type":
            "Turso" if _use_turso() else "SQLite",
        "error":
            "DB 저장 용량을 확인할 수 없습니다."
    }


def search_same_odds(
    company_name,
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.0001
):

    rows = _execute(
        """
        SELECT
            m.schedule_id,
            m.match_date,
            m.home_team,
            m.away_team,
            m.home_score,
            m.away_score,
            m.result,
            o.company_name,
            o.final_home,
            o.final_draw,
            o.final_away
        FROM odds o
        JOIN matches m
          ON m.schedule_id = o.schedule_id
        WHERE LOWER(TRIM(o.company_name))
              = LOWER(TRIM(?))
          AND ABS(o.final_home - ?) <= ?
          AND ABS(o.final_draw - ?) <= ?
          AND ABS(o.final_away - ?) <= ?
        ORDER BY m.match_date DESC
        """,
        (
            company_name,
            float(home_odds),
            float(tolerance),
            float(draw_odds),
            float(tolerance),
            float(away_odds),
            float(tolerance)
        ),
        fetch=True
    )

    return [
        {
            "schedule_id": r[0],
            "match_date": r[1],
            "home_team": r[2],
            "away_team": r[3],
            "home_score": r[4],
            "away_score": r[5],
            "result": r[6],
            "bookmaker": r[7],
            "home_odds": r[8],
            "draw_odds": r[9],
            "away_odds": r[10]
        }
        for r in rows
    ]


init_database()
