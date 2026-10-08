# ============================================================
# database.py
# ⚽ Scoreman 영구 데이터베이스 - 구조 자동보정 최종본
#
# 유지 기능
# - Turso / libSQL 영구저장
# - SQLite fallback
# - 경기 저장
# - 최종배당 저장
# - 완전 동일배당 검색
# - 업체별 통계
# - 수집 진행상태
# - 중지 후 이어받기
# - 기존 DB 구조 자동보정
#
# 중요 수정
# 1. 기존 odds.bookmaker NOT NULL 대응
# 2. 기존 odds UNIQUE 구조 대응
# 3. 기존 collection_state 구조 대응
# 4. Turso/libSQL에서도 동작
# ============================================================

import os
import sqlite3
from pathlib import Path
from datetime import datetime

try:
    import libsql_experimental as libsql
except Exception:
    libsql = None

try:
    import threading
    DB_LOCK = threading.RLock()
except Exception:
    DB_LOCK = None


# ============================================================
# 기본 설정
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
SQLITE_FILE = BASE_DIR / "scoreman.db"


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
# Turso 사용 여부
# ============================================================

def is_turso_configured():

    return bool(
        _get_database_url()
        and _get_auth_token()
        and libsql is not None
    )


# ============================================================
# 연결
# ============================================================

def get_connection():

    url = _get_database_url()
    token = _get_auth_token()

    if (
        url
        and token
        and libsql is not None
    ):

        try:

            return libsql.connect(
                database=url,
                auth_token=token
            )

        except Exception:
            pass

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
# Row -> dict
# ============================================================

def _rows_to_dicts(rows):

    result = []

    for row in rows:

        if isinstance(row, sqlite3.Row):

            result.append(dict(row))
            continue

        try:

            if hasattr(row, "keys"):

                result.append({
                    key: row[key]
                    for key in row.keys()
                })

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

        cur.execute(sql, params)

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

            return _rows_to_dicts(
                cur.fetchall()
            )

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
# 테이블 존재 확인
# ============================================================

def _table_exists(
    conn,
    table_name
):

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name=?
            """,
            (table_name,)
        )

        return cur.fetchone() is not None

    except Exception:

        return False


# ============================================================
# 컬럼 조회
# ============================================================

def _get_columns(
    conn,
    table_name
):

    columns = []

    try:

        cur = conn.cursor()

        cur.execute(
            f"PRAGMA table_info({table_name})"
        )

        rows = cur.fetchall()

        for row in rows:

            try:
                columns.append(
                    str(row[1])
                )
            except Exception:
                pass

    except Exception:
        pass

    return columns


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

        # ====================================================
        # MATCHES
        # ====================================================

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

        # ====================================================
        # ODDS
        # ====================================================

        if not _table_exists(conn, "odds"):

            cur.execute(
                """
                CREATE TABLE odds (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    schedule_id TEXT NOT NULL,

                    company_id TEXT,

                    company_name TEXT NOT NULL,

                    final_home REAL,

                    final_draw REAL,

                    final_away REAL,

                    bookmaker TEXT,

                    UNIQUE(
                        schedule_id,
                        company_name
                    )

                )
                """
            )

        else:

            # ------------------------------------------------
            # 기존 odds 구조 확인
            # ------------------------------------------------

            columns = _get_columns(
                conn,
                "odds"
            )

            # 필요한 컬럼 자동 추가
            required = {

                "schedule_id":
                    "TEXT",

                "company_id":
                    "TEXT",

                "company_name":
                    "TEXT",

                "final_home":
                    "REAL",

                "final_draw":
                    "REAL",

                "final_away":
                    "REAL",

                "bookmaker":
                    "TEXT"

            }

            for name, col_type in required.items():

                if name not in columns:

                    try:

                        cur.execute(
                            f"""
                            ALTER TABLE odds
                            ADD COLUMN {name}
                            {col_type}
                            """
                        )

                    except Exception:
                        pass

            # ------------------------------------------------
            # 기존 bookmaker NOT NULL 문제 해결
            #
            # 기존 테이블이
            # bookmaker TEXT NOT NULL
            # 로 만들어져 있어도 INSERT 시 반드시 값을
            # 넣도록 save_odds에서 처리한다.
            # ------------------------------------------------

        # ====================================================
        # COLLECTION STATE
        # ====================================================

        if not _table_exists(
            conn,
            "collection_state"
        ):

            cur.execute(
                """
                CREATE TABLE collection_state (

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

        else:

            columns = _get_columns(
                conn,
                "collection_state"
            )

            required = {

                "start_id":
                    "INTEGER",

                "end_id":
                    "INTEGER",

                "current_id":
                    "INTEGER",

                "last_completed_id":
                    "INTEGER",

                "running":
                    "INTEGER DEFAULT 0",

                "stopped":
                    "INTEGER DEFAULT 0",

                "updated_at":
                    "TEXT"

            }

            for name, col_type in required.items():

                if name not in columns:

                    try:

                        cur.execute(
                            f"""
                            ALTER TABLE collection_state
                            ADD COLUMN {name}
                            {col_type}
                            """
                        )

                    except Exception:
                        pass

        # ====================================================
        # COLLECTION LOGS
        # ====================================================

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS collection_logs (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                created_at TEXT,

                message TEXT

            )
            """
        )

        # ====================================================
        # INDEX
        # ====================================================

        try:

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_odds_schedule
                ON odds(schedule_id)
                """
            )

        except Exception:
            pass

        try:

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_odds_company
                ON odds(company_name)
                """
            )

        except Exception:
            pass

        try:

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_matches_date
                ON matches(match_date)
                """
            )

        except Exception:
            pass

        # ====================================================
        # 기존 UNIQUE 구조가 없을 경우
        #
        # 기존 DB 때문에
        # ON CONFLICT(schedule_id,company_name)
        # 를 사용할 수 없는 경우를 피하기 위해
        # UNIQUE INDEX를 생성한다.
        # ====================================================

        try:

            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS
                idx_odds_schedule_company
                ON odds(
                    schedule_id,
                    company_name
                )
                """
            )

        except Exception:
            pass

        # ====================================================
        # 동일배당 검색용
        # ====================================================

        try:

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_odds_exact
                ON odds(
                    company_name,
                    final_home,
                    final_draw,
                    final_away
                )
                """
            )

        except Exception:
            pass

        try:
            conn.commit()
        except Exception:
            pass

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
#
# 핵심:
# - bookmaker 컬럼이 있는 기존 DB 대응
# - bookmaker NOT NULL 대응
# - 기존 UNIQUE 충돌 회피
# - 먼저 UPDATE
# - 없으면 INSERT
# ============================================================

def save_odds(
    schedule_id,
    company_id,
    company_name,
    final_home,
    final_draw,
    final_away
):

    try:

        final_home = float(final_home)
        final_draw = float(final_draw)
        final_away = float(final_away)

    except Exception as e:

        raise ValueError(
            f"배당 숫자 변환 실패: {e}"
        )

    schedule_id = str(
        schedule_id
    )

    company_id = str(
        company_id or ""
    )

    company_name = str(
        company_name or ""
    ).strip()

    if not company_name:

        raise ValueError(
            "회사명이 없습니다."
        )

    conn = None

    try:

        if DB_LOCK:
            DB_LOCK.acquire()

        conn = get_connection()
        cur = conn.cursor()

        columns = _get_columns(
            conn,
            "odds"
        )

        # ----------------------------------------------------
        # 기존 데이터가 있으면 UPDATE
        # ----------------------------------------------------

        cur.execute(
            """
            SELECT id
            FROM odds
            WHERE schedule_id = ?
            AND LOWER(TRIM(company_name))
                =
                LOWER(TRIM(?))
            LIMIT 1
            """,
            (
                schedule_id,
                company_name
            )
        )

        existing = cur.fetchone()

        if existing:

            row_id = existing[0]

            if "bookmaker" in columns:

                cur.execute(
                    """
                    UPDATE odds
                    SET
                        company_id = ?,
                        company_name = ?,
                        final_home = ?,
                        final_draw = ?,
                        final_away = ?,
                        bookmaker = ?
                    WHERE id = ?
                    """,
                    (
                        company_id,
                        company_name,
                        final_home,
                        final_draw,
                        final_away,
                        company_name,
                        row_id
                    )
                )

            else:

                cur.execute(
                    """
                    UPDATE odds
                    SET
                        company_id = ?,
                        company_name = ?,
                        final_home = ?,
                        final_draw = ?,
                        final_away = ?
                    WHERE id = ?
                    """,
                    (
                        company_id,
                        company_name,
                        final_home,
                        final_draw,
                        final_away,
                        row_id
                    )
                )

        else:

            # ------------------------------------------------
            # 신규 INSERT
            # ------------------------------------------------

            if "bookmaker" in columns:

                cur.execute(
                    """
                    INSERT INTO odds (

                        schedule_id,
                        company_id,
                        company_name,
                        final_home,
                        final_draw,
                        final_away,
                        bookmaker

                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        schedule_id,
                        company_id,
                        company_name,
                        final_home,
                        final_draw,
                        final_away,
                        company_name
                    )
                )

            else:

                cur.execute(
                    """
                    INSERT INTO odds (

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
                        schedule_id,
                        company_id,
                        company_name,
                        final_home,
                        final_draw,
                        final_away
                    )
                )

        try:
            conn.commit()
        except Exception:
            pass

        return True

    except Exception as e:

        try:

            if conn:
                conn.rollback()

        except Exception:
            pass

        raise ValueError(
            str(e)
        )

    finally:

        try:

            if conn:
                conn.close()

        except Exception:
            pass

        if DB_LOCK:
            DB_LOCK.release()


# ============================================================
# 경기 존재
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
        SELECT DISTINCT
            company_name
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
# 업체별 경기 수
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

            (SELECT COUNT(*)
             FROM matches) AS matches,

            (SELECT COUNT(*)
             FROM odds) AS odds,

            (SELECT COUNT(DISTINCT company_name)
             FROM odds
             WHERE company_name IS NOT NULL
             AND TRIM(company_name) <> '') AS bookmakers
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
            int(
                row.get("matches", 0) or 0
            ),

        "odds":
            int(
                row.get("odds", 0) or 0
            ),

        "bookmakers":
            int(
                row.get("bookmakers", 0) or 0
            )

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
            size_bytes
            / 1024
            / 1024
        )

        size_gb = (
            size_mb
            / 1024
            / 1024
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
# 완전 동일배당
# ============================================================

def search_same_odds(
    company_name,
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0
):

    try:

        h = float(home_odds)
        d = float(draw_odds)
        a = float(away_odds)

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
              =
              LOWER(TRIM(?))

          AND o.final_home = ?
          AND o.final_draw = ?
          AND o.final_away = ?

        ORDER BY
            m.match_date DESC,
            m.schedule_id DESC
        """,
        (
            str(company_name).strip(),
            h,
            d,
            a
        ),
        fetch=True
    )


# ============================================================
# 수집 상태 저장
#
# 기존 DB의 id=1이 이미 존재해도
# UPDATE 방식으로 저장한다.
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

    conn = None

    try:

        if DB_LOCK:
            DB_LOCK.acquire()

        conn = get_connection()
        cur = conn.cursor()

        # ----------------------------------------------------
        # 기존 id=1 확인
        # ----------------------------------------------------

        cur.execute(
            """
            SELECT id
            FROM collection_state
            WHERE id = 1
            LIMIT 1
            """
        )

        exists = cur.fetchone()

        if exists:

            cur.execute(
                """
                UPDATE collection_state
                SET

                    start_id = ?,
                    end_id = ?,
                    current_id = ?,
                    last_completed_id = ?,
                    running = ?,
                    stopped = ?,
                    updated_at = ?

                WHERE id = 1
                """,
                (
                    int(start_id or 0),
                    int(end_id or 0),
                    int(current_id or 0),
                    int(last_completed_id or 0),
                    1 if running else 0,
                    1 if stopped else 0,
                    now
                )
            )

        else:

            cur.execute(
                """
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
                VALUES (1, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(start_id or 0),
                    int(end_id or 0),
                    int(current_id or 0),
                    int(last_completed_id or 0),
                    1 if running else 0,
                    1 if stopped else 0,
                    now
                )
            )

        try:
            conn.commit()
        except Exception:
            pass

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


# ============================================================
# 로그 조회
# ============================================================

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
# 초기화 테스트
# ============================================================

if __name__ == "__main__":

    init_database()

    print(
        get_database_info()
    )

    print(
        get_database_status()
    )

    print(
        get_collection_state()
                )
