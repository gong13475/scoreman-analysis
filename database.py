# ============================================================
# database.py
# ⚽ Scoreman 영구 데이터베이스
#
# 기능
# - Turso / libSQL 영구저장
# - SQLite fallback
# - 경기 저장
# - 최종배당 저장
# - 동일배당 검색
# - 업체별 통계
# - 수집 진행상태 저장
# - 중지 후 이어받기
# ============================================================

import os
import sqlite3
from pathlib import Path
from datetime import datetime

try:
    import libsql_experimental as libsql
except Exception:
    libsql = None


# ============================================================
# 기본 설정
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
SQLITE_FILE = BASE_DIR / "scoreman.db"

DB_LOCK = None

try:
    import threading
    DB_LOCK = threading.RLock()
except Exception:
    pass


# ============================================================
# 환경변수
# ============================================================

def _get_database_url():

    return (
        os.getenv("TURSO_DATABASE_URL")
        or os.getenv("LIBSQL_URL")
        or ""
    ).strip()


def _get_auth_token():

    return (
        os.getenv("TURSO_AUTH_TOKEN")
        or os.getenv("LIBSQL_AUTH_TOKEN")
        or ""
    ).strip()


# ============================================================
# 연결 방식
# ============================================================

def is_turso_configured():

    return bool(
        _get_database_url()
        and _get_auth_token()
        and libsql is not None
    )


def get_connection():

    url = _get_database_url()
    token = _get_auth_token()

    # --------------------------------------------------------
    # Turso
    # --------------------------------------------------------

    if (
        url
        and token
        and libsql is not None
    ):

        try:

            conn = libsql.connect(
                database=url,
                auth_token=token
            )

            return conn

        except Exception:
            pass

    # --------------------------------------------------------
    # SQLite fallback
    # --------------------------------------------------------

    conn = sqlite3.connect(
        str(SQLITE_FILE),
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


# ============================================================
# Row 변환
# ============================================================

def _rows_to_dicts(rows):

    result = []

    for row in rows:

        try:

            if isinstance(row, sqlite3.Row):
                result.append(dict(row))
                continue

        except Exception:
            pass

        try:

            if hasattr(row, "keys"):

                result.append(
                    {
                        key: row[key]
                        for key in row.keys()
                    }
                )

                continue

        except Exception:
            pass

        try:

            result.append(dict(row))

        except Exception:

            result.append({})

    return result


# ============================================================
# SQL 실행
# ============================================================

def _execute(
    sql,
    params=(),
    fetch=False,
    fetchone=False,
    commit=False
):

    conn = None

    try:

        if DB_LOCK:
            DB_LOCK.acquire()

        conn = get_connection()

        cur = conn.cursor()

        cur.execute(
            sql,
            params
        )

        if commit:

            try:
                conn.commit()
            except Exception:
                pass

        if fetchone:

            row = cur.fetchone()

            if row is None:
                return None

            return _rows_to_dicts([row])[0]

        if fetch:

            rows = cur.fetchall()

            return _rows_to_dicts(rows)

        return True

    finally:

        try:
            if conn:
                conn.close()
        except Exception:
            pass

        if DB_LOCK:
            DB_LOCK.release()


# ============================================================
# DB 초기화
# ============================================================

def init_database():

    conn = None

    try:

        if DB_LOCK:
            DB_LOCK.acquire()

        conn = get_connection()

        cur = conn.cursor()

        cur.execute(
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

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS odds (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                schedule_id TEXT NOT NULL,

                company_id TEXT,

                company_name TEXT NOT NULL,

                final_home REAL,

                final_draw REAL,

                final_away REAL,

                UNIQUE(
                    schedule_id,
                    company_name
                )

            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS collection_state (

                id INTEGER PRIMARY KEY,

                start_id INTEGER,

                end_id INTEGER,

                current_id INTEGER,

                last_completed_id INTEGER,

                running INTEGER DEFAULT 0,

                stopped INTEGER DEFAULT 0,

                updated_at TEXT

            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS collection_logs (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                created_at TEXT,

                message TEXT

            )
            """
        )

        # ----------------------------------------------------
        # 인덱스
        # ----------------------------------------------------

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_odds_schedule
            ON odds(schedule_id)
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_odds_company
            ON odds(company_name)
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_matches_date
            ON matches(match_date)
            """
        )

        conn.commit()

    finally:

        try:
            if conn:
                conn.close()
        except Exception:
            pass

        if DB_LOCK:
            DB_LOCK.release()


# ============================================================
# 경기 저장
# ============================================================

def save_match(
    schedule_id,
    match_date="",
    home_team="",
    away_team="",
    home_score=None,
    away_score=None,
    result="",
    source="Scoreman"
):

    sql = """
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

            match_date = excluded.match_date,
            home_team = excluded.home_team,
            away_team = excluded.away_team,
            home_score = excluded.home_score,
            away_score = excluded.away_score,
            result = excluded.result,
            source = excluded.source
    """

    return _execute(
        sql,
        (
            str(schedule_id),
            str(match_date or ""),
            str(home_team or ""),
            str(away_team or ""),
            home_score,
            away_score,
            str(result or ""),
            str(source or "Scoreman")
        ),
        commit=True
    )


# ============================================================
# 배당 저장
# ============================================================

def save_odds(
    schedule_id,
    company_id,
    company_name,
    final_home,
    final_draw,
    final_away
):

    sql = """
        INSERT INTO odds (
            schedule_id,
            company_id,
            company_name,
            final_home,
            final_draw,
            final_away
        )
        VALUES (?, ?, ?, ?, ?, ?)

        ON CONFLICT(
            schedule_id,
            company_name
        )
        DO UPDATE SET

            company_id = excluded.company_id,
            final_home = excluded.final_home,
            final_draw = excluded.final_draw,
            final_away = excluded.final_away
    """

    return _execute(
        sql,
        (
            str(schedule_id),
            str(company_id or ""),
            str(company_name or ""),
            final_home,
            final_draw,
            final_away
        ),
        commit=True
    )


# ============================================================
# 경기 존재 여부
# ============================================================

def match_exists(schedule_id):

    row = _execute(
        """
        SELECT schedule_id
        FROM matches
        WHERE schedule_id = ?
        LIMIT 1
        """,
        (str(schedule_id),),
        fetchone=True
    )

    return bool(row)


# ============================================================
# 경기 조회
# ============================================================

def get_match(schedule_id):

    return _execute(
        """
        SELECT *
        FROM matches
        WHERE schedule_id = ?
        LIMIT 1
        """,
        (str(schedule_id),),
        fetchone=True
    )


# ============================================================
# 전체 경기
# ============================================================

def get_all_matches():

    return _execute(
        """
        SELECT *
        FROM matches
        ORDER BY
            CASE
                WHEN match_date IS NULL
                THEN 1
                ELSE 0
            END,
            match_date DESC,
            schedule_id DESC
        """,
        fetch=True
    )


# ============================================================
# 경기 배당
# ============================================================

def get_odds_by_match(schedule_id):

    return _execute(
        """
        SELECT *
        FROM odds
        WHERE schedule_id = ?
        ORDER BY company_name
        """,
        (str(schedule_id),),
        fetch=True
    )


# ============================================================
# 업체 목록
# ============================================================

def get_company_list():

    rows = _execute(
        """
        SELECT DISTINCT company_name
        FROM odds
        WHERE company_name IS NOT NULL
        AND TRIM(company_name) <> ''
        ORDER BY company_name
        """,
        fetch=True
    )

    return [
        str(row.get("company_name", ""))
        for row in rows
        if row.get("company_name")
    ]


# ============================================================
# 업체별 저장 경기 수
# ============================================================

def get_company_counts():

    rows = _execute(
        """
        SELECT
            company_name,
            COUNT(DISTINCT schedule_id) AS cnt
        FROM odds
        GROUP BY company_name
        ORDER BY cnt DESC
        """,
        fetch=True
    )

    result = {}

    for row in rows:

        result[
            str(row.get("company_name", ""))
        ] = int(
            row.get("cnt", 0) or 0
        )

    return result


# ============================================================
# DB 상태
# ============================================================

def get_database_status():

    row = _execute(
        """
        SELECT
            (SELECT COUNT(*) FROM matches) AS matches,
            (SELECT COUNT(*) FROM odds) AS odds,
            (SELECT COUNT(DISTINCT company_name)
             FROM odds) AS bookmakers
        """,
        fetchone=True
    )

    if not row:

        return {
            "matches": 0,
            "odds": 0,
            "bookmakers": 0
        }

    return {
        "matches":
            int(row.get("matches", 0) or 0),

        "odds":
            int(row.get("odds", 0) or 0),

        "bookmakers":
            int(row.get("bookmakers", 0) or 0)
    }


# ============================================================
# DB 정보
# ============================================================

def get_database_info():

    url = _get_database_url()
    token = _get_auth_token()

    using_turso = (
        bool(url)
        and bool(token)
        and libsql is not None
    )

    return {

        "using_turso":
            using_turso,

        "database_url_configured":
            bool(url),

        "auth_token_configured":
            bool(token),

        "libsql_available":
            libsql is not None,

        "sqlite_file":
            str(SQLITE_FILE)

    }


# ============================================================
# 저장 용량
# ============================================================

def get_storage_usage():

    try:

        row = _execute(
            """
            SELECT
                page_count,
                page_size
            FROM pragma_page_count(),
                 pragma_page_size()
            """,
            fetchone=True
        )

        if row:

            size_bytes = (
                int(row.get("page_count", 0) or 0)
                *
                int(row.get("page_size", 0) or 0)
            )

        else:

            size_bytes = 0

        size_mb = (
            size_bytes / 1024 / 1024
        )

        size_gb = (
            size_mb / 1024
        )

        return {

            "success": True,

            "size_bytes":
                size_bytes,

            "size_mb":
                size_mb,

            "size_gb":
                size_gb,

            "storage_type":
                "Turso/libSQL"
                if is_turso_configured()
                else "SQLite"

        }

    except Exception as e:

        return {

            "success": False,

            "error":
                str(e)

        }


# ============================================================
# 동일배당 검색
# ============================================================

def search_same_odds(
    company_name,
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.01
):

    try:

        h = float(home_odds)
        d = float(draw_odds)
        a = float(away_odds)

        t = abs(float(tolerance))

    except Exception:

        return []

    return _execute(
        """
        SELECT

            m.schedule_id,
            m.match_date,
            m.home_team,
            m.away_team,
            m.home_score,
            m.away_score,
            m.result,
            m.source,

            o.company_id,
            o.company_name,

            o.final_home AS home_odds,
            o.final_draw AS draw_odds,
            o.final_away AS away_odds

        FROM odds o

        INNER JOIN matches m
            ON m.schedule_id = o.schedule_id

        WHERE LOWER(TRIM(o.company_name))
              = LOWER(TRIM(?))

          AND o.final_home
              BETWEEN ? AND ?

          AND o.final_draw
              BETWEEN ? AND ?

          AND o.final_away
              BETWEEN ? AND ?

        ORDER BY m.match_date DESC
        """,
        (
            str(company_name),
            h - t,
            h + t,
            d - t,
            d + t,
            a - t,
            a + t
        ),
        fetch=True
    )


# ============================================================
# 수집 상태 저장
# ============================================================

def save_collection_state(
    start_id,
    end_id,
    current_id,
    last_completed_id,
    running,
    stopped
):

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    sql = """
        INSERT INTO collection_state (
            id,
            start_id,
            end_id,
            current_id,
            last_completed_id,
            running,
            stopped,
            updated_at
        )
        VALUES (
            1, ?, ?, ?, ?, ?, ?, ?
        )

        ON CONFLICT(id)
        DO UPDATE SET

            start_id = excluded.start_id,
            end_id = excluded.end_id,
            current_id = excluded.current_id,
            last_completed_id =
                excluded.last_completed_id,
            running = excluded.running,
            stopped = excluded.stopped,
            updated_at = excluded.updated_at
    """

    return _execute(
        sql,
        (
            int(start_id or 0),
            int(end_id or 0),
            int(current_id or 0),
            int(last_completed_id or 0),
            1 if running else 0,
            1 if stopped else 0,
            now
        ),
        commit=True
    )


# ============================================================
# 수집 상태 조회
# ============================================================

def get_collection_state():

    row = _execute(
        """
        SELECT *
        FROM collection_state
        WHERE id = 1
        LIMIT 1
        """,
        fetchone=True
    )

    return row or {}


# ============================================================
# 수집 로그
# ============================================================

def save_collection_log(message):

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    return _execute(
        """
        INSERT INTO collection_logs (
            created_at,
            message
        )
        VALUES (?, ?)
        """,
        (
            now,
            str(message)
        ),
        commit=True
    )


def get_collection_logs(limit=200):

    rows = _execute(
        """
        SELECT
            created_at,
            message
        FROM collection_logs
        ORDER BY id DESC
        LIMIT ?
        """,
        (int(limit),),
        fetch=True
    )

    rows.reverse()

    return rows


# ============================================================
# 테스트
# ============================================================

if __name__ == "__main__":

    init_database()

    print(
        get_database_info()
    )

    print(
        get_database_status()
            )
