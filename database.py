# ============================================================
# database.py
# Scoreman 영구 DB
# Turso 우선 / SQLite 자동 fallback
# ============================================================

import os
import sqlite3
from pathlib import Path
from datetime import datetime

DB_FILE = Path(__file__).resolve().parent / "scoreman.db"

_turso_conn = None


# ============================================================
# Turso 연결
# ============================================================

def _use_turso():
    return bool(
        os.getenv("TURSO_DATABASE_URL")
        and os.getenv("TURSO_AUTH_TOKEN")
        and _get_libsql() is not None
    )


def _get_libsql():
    try:
        import libsql
        return libsql
    except Exception:
        return None


def _get_turso_connection():
    global _turso_conn

    libsql = _get_libsql()

    if libsql is None:
        return None

    url = os.getenv("TURSO_DATABASE_URL")
    token = os.getenv("TURSO_AUTH_TOKEN")

    if not url or not token:
        return None

    if _turso_conn is None:
        _turso_conn = libsql.connect(
            database=url,
            auth_token=token
        )

    return _turso_conn


# ============================================================
# SQLite 연결
# ============================================================

def _sqlite_connection():
    conn = sqlite3.connect(
        str(DB_FILE),
        check_same_thread=False,
        timeout=30
    )
    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass

    return conn


def get_connection():
    if _use_turso():
        conn = _get_turso_connection()
        if conn is not None:
            return conn

    return _sqlite_connection()


# ============================================================
# 실행
# ============================================================

def _execute(sql, params=(), fetch=False, many=False):
    conn = get_connection()

    try:
        if many:
            cur = conn.executemany(sql, params)
        else:
            cur = conn.execute(sql, params)

        if fetch:
            rows = cur.fetchall()
            return [dict(row) for row in rows]

        conn.commit()
        return cur.rowcount

    finally:
        if not _use_turso():
            conn.close()


# ============================================================
# DB 초기화
# ============================================================

def init_database():

    conn = get_connection()

    try:
        conn.execute("""
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
        """)

        conn.execute("""
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
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS collection_state (
                id INTEGER PRIMARY KEY,
                start_id INTEGER,
                end_id INTEGER,
                last_completed_id INTEGER,
                current INTEGER,
                total INTEGER,
                running INTEGER,
                stopped INTEGER,
                selected_companies TEXT,
                updated_at TEXT
            )
        """)

        conn.commit()

    finally:
        if not _use_turso():
            conn.close()


# ============================================================
# 경기 저장
# ============================================================

def save_match(match):

    conn = get_connection()

    try:
        conn.execute("""
            INSERT INTO matches (
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
            ON CONFLICT(schedule_id)
            DO UPDATE SET
                match_date=excluded.match_date,
                home_team=excluded.home_team,
                away_team=excluded.away_team,
                home_score=excluded.home_score,
                away_score=excluded.away_score,
                result=excluded.result,
                source=excluded.source
        """, (
            str(match.get("schedule_id")),
            match.get("match_date", ""),
            match.get("home_team", ""),
            match.get("away_team", ""),
            match.get("home_score"),
            match.get("away_score"),
            match.get("result", ""),
            match.get("source", "scoreman")
        ))

        conn.commit()

    finally:
        if not _use_turso():
            conn.close()


# ============================================================
# 경기 + 배당 저장
# ============================================================

def save_match_with_odds(match, odds_list):

    save_match(match)

    conn = get_connection()
    saved = 0

    try:

        for row in odds_list:

            conn.execute("""
                INSERT INTO odds (
                    schedule_id,
                    company_id,
                    company_name,
                    final_home,
                    final_draw,
                    final_away
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(schedule_id, company_name)
                DO UPDATE SET
                    company_id=excluded.company_id,
                    final_home=excluded.final_home,
                    final_draw=excluded.final_draw,
                    final_away=excluded.final_away
            """, (
                str(match.get("schedule_id")),
                str(row.get("company_id", "")),
                str(row.get("company_name", "")),
                row.get("final_home"),
                row.get("final_draw"),
                row.get("final_away")
            ))

            saved += 1

        conn.commit()

    finally:
        if not _use_turso():
            conn.close()

    return saved


# ============================================================
# 경기 조회
# ============================================================

def get_match(schedule_id):

    rows = _execute("""
        SELECT *
        FROM matches
        WHERE schedule_id = ?
        LIMIT 1
    """, (str(schedule_id),), fetch=True)

    return rows[0] if rows else None


def get_all_matches():

    return _execute("""
        SELECT
            schedule_id AS "경기 ID",
            match_date AS "경기일",
            home_team AS "홈",
            away_team AS "원정",
            home_score AS "홈스코어",
            away_score AS "원정스코어",
            result AS "결과"
        FROM matches
        ORDER BY CAST(schedule_id AS INTEGER) DESC
    """, fetch=True)


# ============================================================
# 경기 배당
# ============================================================

def get_odds_by_match(schedule_id):

    return _execute("""
        SELECT
            company_name AS bookmaker,
            final_home AS home_odds,
            final_draw AS draw_odds,
            final_away AS away_odds,
            company_id
        FROM odds
        WHERE schedule_id = ?
        ORDER BY company_name
    """, (str(schedule_id),), fetch=True)


# ============================================================
# 업체 목록
# ============================================================

def get_company_list():

    rows = _execute("""
        SELECT DISTINCT company_name
        FROM odds
        WHERE company_name IS NOT NULL
          AND company_name <> ''
        ORDER BY company_name
    """, fetch=True)

    return [
        row["company_name"]
        for row in rows
    ]


def get_company_counts():

    rows = _execute("""
        SELECT
            company_name,
            COUNT(DISTINCT schedule_id) AS cnt
        FROM odds
        WHERE company_name IS NOT NULL
          AND company_name <> ''
        GROUP BY company_name
        ORDER BY cnt DESC
    """, fetch=True)

    return {
        row["company_name"]: int(row["cnt"])
        for row in rows
    }


# ============================================================
# DB 상태
# ============================================================

def get_database_status():

    rows = _execute("""
        SELECT
            (SELECT COUNT(*) FROM matches) AS matches,
            (SELECT COUNT(*) FROM odds) AS odds,
            (SELECT COUNT(DISTINCT company_name) FROM odds)
                AS bookmakers
    """, fetch=True)

    if not rows:
        return {
            "matches": 0,
            "odds": 0,
            "bookmakers": 0
        }

    return rows[0]


def get_database_info():

    return {
        "database_url_configured":
            bool(os.getenv("TURSO_DATABASE_URL")),

        "auth_token_configured":
            bool(os.getenv("TURSO_AUTH_TOKEN")),

        "libsql_available":
            _get_libsql() is not None,

        "using_turso":
            _use_turso()
    }


# ============================================================
# 저장 용량
# ============================================================

def get_storage_usage():

    if _use_turso():

        try:
            conn = get_connection()

            row = conn.execute("""
                SELECT
                    page_count * page_size
                FROM pragma_page_count(),
                     pragma_page_size()
            """).fetchone()

            size = int(row[0] or 0)

            return {
                "success": True,
                "size_mb": size / 1024 / 1024,
                "size_gb": size / 1024 / 1024 / 1024,
                "storage_type": "Turso"
            }

        except Exception as e:

            return {
                "success": False,
                "size_mb": 0,
                "size_gb": 0,
                "storage_type": "Turso",
                "error": str(e)
            }

    try:

        if DB_FILE.exists():
            size = DB_FILE.stat().st_size
        else:
            size = 0

        return {
            "success": True,
            "size_mb": size / 1024 / 1024,
            "size_gb": size / 1024 / 1024 / 1024,
            "storage_type": "SQLite"
        }

    except Exception as e:

        return {
            "success": False,
            "size_mb": 0,
            "size_gb": 0,
            "storage_type": "SQLite",
            "error": str(e)
        }


# ============================================================
# 수집 상태
# ============================================================

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

    import json

    selected_json = json.dumps(
        selected_companies,
        ensure_ascii=False
    ) if selected_companies else ""

    conn = get_connection()

    try:

        conn.execute("""
            INSERT INTO collection_state (
                id,
                start_id,
                end_id,
                last_completed_id,
                current,
                total,
                running,
                stopped,
                selected_companies,
                updated_at
            )
            VALUES (
                1, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(id)
            DO UPDATE SET
                start_id=excluded.start_id,
                end_id=excluded.end_id,
                last_completed_id=excluded.last_completed_id,
                current=excluded.current,
                total=excluded.total,
                running=excluded.running,
                stopped=excluded.stopped,
                selected_companies=excluded.selected_companies,
                updated_at=excluded.updated_at
        """, (
            int(start_id),
            int(end_id),
            int(last_completed_id or 0),
            int(current or 0),
            int(total or 0),
            1 if running else 0,
            1 if stopped else 0,
            selected_json,
            datetime.now().isoformat()
        ))

        conn.commit()

    finally:
        if not _use_turso():
            conn.close()


def get_collection_state():

    rows = _execute("""
        SELECT *
        FROM collection_state
        WHERE id = 1
        LIMIT 1
    """, fetch=True)

    if not rows:
        return {}

    row = rows[0]

    import json

    selected = row.get("selected_companies")

    if selected:
        try:
            selected = json.loads(selected)
        except Exception:
            selected = None
    else:
        selected = None

    return {
        "start_id": row.get("start_id"),
        "end_id": row.get("end_id"),
        "last_completed_id":
            row.get("last_completed_id"),
        "current": row.get("current"),
        "total": row.get("total"),
        "running": bool(row.get("running")),
        "stopped": bool(row.get("stopped")),
        "selected_companies": selected,
        "updated_at": row.get("updated_at")
    }


# ============================================================
# 초기화
# ============================================================

init_database()
