# ============================================================
# database.py
# ⚽ Scoreman 영구 데이터베이스 - 호환 안정판
#
# 기능
# - Turso / libSQL 영구저장
# - SQLite fallback
# - 기존 DB 구조 자동 호환
# - 경기 저장
# - 최종배당 저장
# - 완전 동일배당 검색
# - 업체별 통계
# - 수집 진행상태 저장
# - 중지 후 이어받기
# - 기존 bookmaker 컬럼 호환
# - 기존 UNIQUE 구조에 의존하지 않는 저장 방식
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

try:
    import threading
    DB_LOCK = threading.RLock()
except Exception:
    DB_LOCK = None


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
# Turso 여부
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

    # --------------------------------------------------------
    # Turso / libSQL
    # --------------------------------------------------------

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

        conn.execute(
            "PRAGMA journal_mode=WAL"
        )

        conn.execute(
            "PRAGMA synchronous=NORMAL"
        )

    except Exception:
        pass

    return conn


# ============================================================
# Row -> dict
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

            return _rows_to_dicts(
                [row]
            )[0]

        if fetch:

            rows = cur.fetchall()

            return _rows_to_dicts(
                rows
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
# 테이블 컬럼 확인
# ============================================================

def _get_columns(
    conn,
    table_name
):

    columns = set()

    try:

        cur = conn.cursor()

        cur.execute(
            f"PRAGMA table_info({table_name})"
        )

        rows = cur.fetchall()

        for row in rows:

            try:
                columns.add(
                    str(row[1])
                )
            except Exception:
                pass

    except Exception:
        pass

    return columns


# ============================================================
# 인덱스 생성 안전 처리
# ============================================================

def _safe_create_index(
    cur,
    sql
):

    try:

        cur.execute(sql)

    except Exception:
        pass


# ============================================================
# DB 초기화 / 기존 DB 자동 보정
# ============================================================

def init_database():

    conn = None

    try:

        if DB_LOCK:
            DB_LOCK.acquire()

        conn = get_connection()

        cur = conn.cursor()

        # ====================================================
        # matches
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
        # odds
        #
        # 기존 DB에는 bookmaker가 있을 수 있음.
        # 따라서 bookmaker를 절대 삭제하지 않는다.
        # ====================================================

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS odds (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                schedule_id TEXT NOT NULL,

                company_id TEXT,

                company_name TEXT,

                bookmaker TEXT,

                final_home REAL,

                final_draw REAL,

                final_away REAL

            )
            """
        )

        # ====================================================
        # collection_state
        #
        # 기존 DB에 일부 컬럼만 존재할 수 있음.
        # ====================================================

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

        # ====================================================
        # collection_logs
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
        # 기존 odds 컬럼 자동 추가
        # ====================================================

        odds_columns = _get_columns(
            conn,
            "odds"
        )

        required_odds_columns = {

            "company_id": "TEXT",

            "company_name": "TEXT",

            "bookmaker": "TEXT",

            "final_home": "REAL",

            "final_draw": "REAL",

            "final_away": "REAL"

        }

        for column_name, column_type in required_odds_columns.items():

            if column_name not in odds_columns:

                try:

                    cur.execute(
                        f"""
                        ALTER TABLE odds
                        ADD COLUMN {column_name}
                        {column_type}
                        """
                    )

                except Exception:
                    pass

        # ====================================================
        # collection_state 컬럼 자동 추가
        # ====================================================

        state_columns = _get_columns(
            conn,
            "collection_state"
        )

        required_state_columns = {

            "start_id": "INTEGER",

            "end_id": "INTEGER",

            "current_id": "INTEGER",

            "last_completed_id": "INTEGER",

            "running": "INTEGER DEFAULT 0",

            "stopped": "INTEGER DEFAULT 0",

            "updated_at": "TEXT"

        }

        for column_name, column_type in required_state_columns.items():

            if column_name not in state_columns:

                try:

                    cur.execute(
                        f"""
                        ALTER TABLE collection_state
                        ADD COLUMN {column_name}
                        {column_type}
                        """
                    )

                except Exception:
                    pass

        # ====================================================
        # 인덱스
        # ====================================================

        _safe_create_index(
            cur,
            """
            CREATE INDEX IF NOT EXISTS
            idx_odds_schedule
            ON odds(schedule_id)
            """
        )

        _safe_create_index(
            cur,
            """
            CREATE INDEX IF NOT EXISTS
            idx_odds_company
            ON odds(company_name)
            """
        )

        _safe_create_index(
            cur,
            """
            CREATE INDEX IF NOT EXISTS
            idx_odds_bookmaker
            ON odds(bookmaker)
            """
        )

        _safe_create_index(
            cur,
            """
            CREATE INDEX IF NOT EXISTS
            idx_matches_date
            ON matches(match_date)
            """
        )

        _safe_create_index(
            cur,
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

        # ====================================================
        # 기존 bookmaker 데이터가 있고
        # company_name이 비어 있으면 서로 보정
        # ====================================================

        try:

            cur.execute(
                """
                UPDATE odds
                SET company_name = bookmaker
                WHERE
                    (
                        company_name IS NULL
                        OR TRIM(company_name) = ''
                    )
                    AND bookmaker IS NOT NULL
                    AND TRIM(bookmaker) <> ''
                """
            )

        except Exception:
            pass

        # ====================================================
        # 반대로 bookmaker가 비어 있으면 company_name 사용
        #
        # 기존 bookmaker NOT NULL 구조가 있을 경우
        # 새 저장에서도 반드시 값이 들어가도록 보정.
        # ====================================================

        try:

            cur.execute(
                """
                UPDATE odds
                SET bookmaker = company_name
                WHERE
                    (
                        bookmaker IS NULL
                        OR TRIM(bookmaker) = ''
                    )
                    AND company_name IS NOT NULL
                    AND TRIM(company_name) <> ''
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

    schedule_id = str(
        schedule_id
    )

    # --------------------------------------------------------
    # 먼저 UPDATE
    # --------------------------------------------------------

    updated = _execute(

        """
        UPDATE matches
        SET

            match_date = ?,
            home_team = ?,
            away_team = ?,
            home_score = ?,
            away_score = ?,
            result = ?,
            source = ?

        WHERE schedule_id = ?
        """,

        (

            str(match_date or ""),

            str(home_team or ""),

            str(away_team or ""),

            home_score,

            away_score,

            str(result or ""),

            str(source or "Scoreman"),

            schedule_id

        ),

        commit=True
    )

    if updated:

        # 존재하는지 확인
        if match_exists(schedule_id):

            return True

    # --------------------------------------------------------
    # 없으면 INSERT
    # --------------------------------------------------------

    return _execute(

        """
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
        """,

        (

            schedule_id,

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
# ON CONFLICT 사용 안 함.
#
# 기존 DB의 UNIQUE 구조가 달라도 작동.
# ============================================================

def save_odds(
    schedule_id,
    company_id,
    company_name,
    final_home,
    final_draw,
    final_away
):

    # --------------------------------------------------------
    # 값 검증
    # --------------------------------------------------------

    try:

        final_home = float(
            final_home
        )

        final_draw = float(
            final_draw
        )

        final_away = float(
            final_away
        )

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

    # ========================================================
    # 기존 odds 구조의 bookmaker NOT NULL 대응
    # ========================================================

    # --------------------------------------------------------
    # 1. 동일 경기 + 동일 업체가 있는지 검색
    #
    # company_name 우선
    # bookmaker도 같이 검색
    # --------------------------------------------------------

    existing = _execute(

        """
        SELECT id
        FROM odds
        WHERE
            schedule_id = ?
            AND
            (
                LOWER(TRIM(COALESCE(company_name, '')))
                =
                LOWER(TRIM(?))

                OR

                LOWER(TRIM(COALESCE(bookmaker, '')))
                =
                LOWER(TRIM(?))
            )
        ORDER BY id
        LIMIT 1
        """,

        (

            schedule_id,

            company_name,

            company_name

        ),

        fetchone=True
    )

    # ========================================================
    # 2. 기존 행 UPDATE
    # ========================================================

    if existing:

        row_id = existing.get(
            "id"
        )

        # 먼저 일반적인 UPDATE
        try:

            result = _execute(

                """
                UPDATE odds
                SET

                    company_id = ?,

                    company_name = ?,

                    bookmaker = ?,

                    final_home = ?,

                    final_draw = ?,

                    final_away = ?

                WHERE id = ?
                """,

                (

                    company_id,

                    company_name,

                    company_name,

                    final_home,

                    final_draw,

                    final_away,

                    row_id

                ),

                commit=True
            )

            if result:

                return True

        except Exception:

            # ------------------------------------------------
            # bookmaker 컬럼이 없는 아주 오래된 DB 대응
            # ------------------------------------------------

            try:

                result = _execute(

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

                    ),

                    commit=True
                )

                if result:
                    return True

            except Exception:
                pass

    # ========================================================
    # 3. 기존 행이 없으면 INSERT
    # ========================================================

    # --------------------------------------------------------
    # bookmaker 컬럼 존재 여부 확인
    # --------------------------------------------------------

    conn = None

    try:

        if DB_LOCK:
            DB_LOCK.acquire()

        conn = get_connection()

        columns = _get_columns(
            conn,
            "odds"
        )

        cur = conn.cursor()

        if "bookmaker" in columns:

            cur.execute(

                """
                INSERT INTO odds (

                    schedule_id,
                    company_id,
                    company_name,
                    bookmaker,
                    final_home,
                    final_draw,
                    final_away

                )

                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,

                (

                    schedule_id,

                    company_id,

                    company_name,

                    company_name,

                    final_home,

                    final_draw,

                    final_away

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

        conn.commit()

        return True

    except Exception as e:

        raise ValueError(
            f"최종배당 저장 실패: {type(e).__name__}: {e}"
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
# 경기 존재 여부
# ============================================================

def match_exists(
    schedule_id
):

    row = _execute(

        """
        SELECT schedule_id
        FROM matches
        WHERE schedule_id = ?
        LIMIT 1
        """,

        (
            str(schedule_id),
        ),

        fetchone=True
    )

    return bool(row)


# ============================================================
# 경기 조회
# ============================================================

def get_match(
    schedule_id
):

    return _execute(

        """
        SELECT *
        FROM matches
        WHERE schedule_id = ?
        LIMIT 1
        """,

        (
            str(schedule_id),
        ),

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
                     OR TRIM(match_date) = ''
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

def get_odds_by_match(
    schedule_id
):

    return _execute(

        """
        SELECT *
        FROM odds
        WHERE schedule_id = ?
        ORDER BY company_name, bookmaker
        """,

        (
            str(schedule_id),
        ),

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
        WHERE
            company_name IS NOT NULL
            AND TRIM(company_name) <> ''

        ORDER BY company_name
        """,

        fetch=True
    )

    return [

        str(
            row.get(
                "company_name",
                ""
            )
        )

        for row in rows

        if row.get(
            "company_name"
        )

    ]


# ============================================================
# 업체별 경기 수
# ============================================================

def get_company_counts():

    rows = _execute(

        """
        SELECT

            CASE

                WHEN company_name IS NOT NULL
                     AND TRIM(company_name) <> ''
                THEN company_name

                ELSE bookmaker

            END AS company_name,

            COUNT(
                DISTINCT schedule_id
            ) AS cnt

        FROM odds

        GROUP BY

            CASE

                WHEN company_name IS NOT NULL
                     AND TRIM(company_name) <> ''
                THEN company_name

                ELSE bookmaker

            END

        ORDER BY cnt DESC
        """,

        fetch=True
    )

    result = {}

    for row in rows:

        name = str(
            row.get(
                "company_name",
                ""
            )
            or ""
        ).strip()

        if not name:
            continue

        result[name] = int(
            row.get(
                "cnt",
                0
            )
            or 0
        )

    return result


# ============================================================
# DB 상태
# ============================================================

def get_database_status():

    try:

        row = _execute(

            """
            SELECT

                (
                    SELECT COUNT(*)
                    FROM matches
                ) AS matches,

                (
                    SELECT COUNT(*)
                    FROM odds
                ) AS odds,

                (
                    SELECT COUNT(
                        DISTINCT
                        CASE
                            WHEN company_name IS NOT NULL
                                 AND TRIM(company_name) <> ''
                            THEN company_name
                            ELSE bookmaker
                        END
                    )
                    FROM odds
                ) AS bookmakers
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
                    row.get(
                        "matches",
                        0
                    )
                    or 0
                ),

            "odds":
                int(
                    row.get(
                        "odds",
                        0
                    )
                    or 0
                ),

            "bookmakers":
                int(
                    row.get(
                        "bookmakers",
                        0
                    )
                    or 0
                )

        }

    except Exception:

        return {

            "matches": 0,

            "odds": 0,

            "bookmakers": 0

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

                int(
                    row.get(
                        "page_count",
                        0
                    )
                    or 0
                )

                *

                int(
                    row.get(
                        "page_size",
                        0
                    )
                    or 0
                )

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
# 완전 동일배당 검색
# ============================================================

def search_same_odds(
    company_name,
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0
):

    try:

        h = float(
            home_odds
        )

        d = float(
            draw_odds
        )

        a = float(
            away_odds
        )

    except Exception:

        return []

    company_name = str(
        company_name or ""
    ).strip()

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

            CASE

                WHEN o.company_name IS NOT NULL
                     AND TRIM(o.company_name) <> ''
                THEN o.company_name

                ELSE o.bookmaker

            END AS company_name,

            o.final_home AS home_odds,
            o.final_draw AS draw_odds,
            o.final_away AS away_odds

        FROM odds o

        INNER JOIN matches m
            ON m.schedule_id = o.schedule_id

        WHERE

            LOWER(
                TRIM(
                    CASE

                        WHEN o.company_name IS NOT NULL
                             AND TRIM(o.company_name) <> ''
                        THEN o.company_name

                        ELSE o.bookmaker

                    END
                )
            )

            =

            LOWER(
                TRIM(?)
            )

            AND o.final_home = ?
            AND o.final_draw = ?
            AND o.final_away = ?

        ORDER BY

            m.match_date DESC,
            m.schedule_id DESC

        """,

        (

            company_name,

            h,

            d,

            a

        ),

        fetch=True
    )


# ============================================================
# 수집 상태 저장
#
# ON CONFLICT 사용 안 함.
# 기존 DB의 id PRIMARY KEY 구조와 관계없이
# UPDATE -> INSERT 순서로 처리.
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

    values = (

        int(start_id or 0),

        int(end_id or 0),

        int(current_id or 0),

        int(last_completed_id or 0),

        1 if running else 0,

        1 if stopped else 0,

        now

    )

    # ========================================================
    # 1. 기존 id=1 행 UPDATE
    # ========================================================

    try:

        updated = _execute(

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

            values,

            commit=True
        )

        if updated:

            row = _execute(

                """
                SELECT id
                FROM collection_state
                WHERE id = 1
                LIMIT 1
                """,

                fetchone=True
            )

            if row:

                return True

    except Exception:
        pass

    # ========================================================
    # 2. id=1이 없으면 INSERT
    # ========================================================

    try:

        return _execute(

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

            VALUES (
                1, ?, ?, ?, ?, ?, ?, ?
            )
            """,

            values,

            commit=True
        )

    except Exception as e:

        # ====================================================
        # 혹시 기존 DB에 current_id가 없는 경우
        # 여기까지 온다면 현재 DB 구조를 한번 더 보정
        # ====================================================

        try:

            conn = None

            if DB_LOCK:
                DB_LOCK.acquire()

            conn = get_connection()

            columns = _get_columns(
                conn,
                "collection_state"
            )

            cur = conn.cursor()

            if "current_id" not in columns:

                cur.execute(
                    """
                    ALTER TABLE collection_state
                    ADD COLUMN current_id INTEGER
                    """
                )

            if "last_completed_id" not in columns:

                cur.execute(
                    """
                    ALTER TABLE collection_state
                    ADD COLUMN last_completed_id INTEGER
                    """
                )

            if "running" not in columns:

                cur.execute(
                    """
                    ALTER TABLE collection_state
                    ADD COLUMN running INTEGER DEFAULT 0
                    """
                )

            if "stopped" not in columns:

                cur.execute(
                    """
                    ALTER TABLE collection_state
                    ADD COLUMN stopped INTEGER DEFAULT 0
                    """
                )

            if "updated_at" not in columns:

                cur.execute(
                    """
                    ALTER TABLE collection_state
                    ADD COLUMN updated_at TEXT
                    """
                )

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

        # ====================================================
        # 최종 UPDATE 재시도
        # ====================================================

        try:

            return _execute(

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

                values,

                commit=True
            )

        except Exception:

            raise e


# ============================================================
# 수집 상태 조회
# ============================================================

def get_collection_state():

    try:

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

    except Exception:

        return {}


# ============================================================
# 수집 로그 저장
# ============================================================

def save_collection_log(
    message
):

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
# 수집 로그 조회
# ============================================================

def get_collection_logs(
    limit=200
):

    rows = _execute(

        """
        SELECT

            created_at,
            message

        FROM collection_logs

        ORDER BY id DESC

        LIMIT ?
        """,

        (
            int(limit),
        ),

        fetch=True
    )

    rows.reverse()

    return rows


# ============================================================
# DB 초기화 자동 실행
# ============================================================

try:

    init_database()

except Exception:

    pass


# ============================================================
# 직접 실행 테스트
# ============================================================

if __name__ == "__main__":

    print(
        "========================================"
    )

    print(
        "Scoreman database.py 테스트"
    )

    print(
        "========================================"
    )

    try:

        init_database()

        print(
            "DB 정보:",
            get_database_info()
        )

        print(
            "DB 상태:",
            get_database_status()
        )

        print(
            "수집 상태:",
            get_collection_state()
        )

    except Exception as e:

        print(
            "오류:",
            type(e).__name__,
            str(e)
    )
