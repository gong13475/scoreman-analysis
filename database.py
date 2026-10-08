# ============================================================
# database.py
# ⚽ Scoreman 영구 데이터베이스 - 구조 자동복구 최종본
#
# 핵심
# - Turso / libSQL 영구저장
# - SQLite fallback
# - 기존 DB 데이터 최대한 보존
# - 오래된 odds 구조 자동 보정
# - bookmaker / company_name 호환
# - collection_state 구조 자동 보정
# - UNIQUE / ON CONFLICT 오류 제거
# - 경기 저장
# - 최종배당 저장
# - 완전 동일배당 검색
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
# Turso 사용 여부
# ============================================================

def is_turso_configured():

    return bool(
        _get_database_url()
        and _get_auth_token()
        and libsql is not None
    )


# ============================================================
# DB 연결
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
# Row → dict
# ============================================================

def _row_to_dict(row):

    if row is None:
        return None

    try:

        if isinstance(row, sqlite3.Row):
            return dict(row)

    except Exception:
        pass

    try:

        if hasattr(row, "keys"):

            return {
                key: row[key]
                for key in row.keys()
            }

    except Exception:
        pass

    try:

        return dict(row)

    except Exception:

        return {}


def _rows_to_dicts(rows):

    result = []

    for row in rows:

        item = _row_to_dict(row)

        if item is not None:
            result.append(item)

    return result


# ============================================================
# 테이블 컬럼 조회
# ============================================================

def _get_columns(cur, table_name):

    columns = []

    try:

        rows = cur.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()

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
# 테이블 존재 여부
# ============================================================

def _table_exists(cur, table_name):

    try:

        row = cur.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name=?
            LIMIT 1
            """,
            (table_name,)
        ).fetchone()

        return row is not None

    except Exception:

        return False


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

            return _row_to_dict(row)

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
# matches 생성
# ============================================================

def _create_matches(cur):

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


# ============================================================
# matches 구조 보정
# ============================================================

def _repair_matches(cur):

    columns = _get_columns(
        cur,
        "matches"
    )

    required = {

        "match_date": "TEXT",
        "home_team": "TEXT",
        "away_team": "TEXT",
        "home_score": "INTEGER",
        "away_score": "INTEGER",
        "result": "TEXT",
        "source": "TEXT"

    }

    for name, typ in required.items():

        if name not in columns:

            try:

                cur.execute(
                    f"""
                    ALTER TABLE matches
                    ADD COLUMN {name} {typ}
                    """
                )

            except Exception:
                pass


# ============================================================
# odds 신규 표준 테이블
# ============================================================

def _create_standard_odds_table(
    cur,
    table_name="odds"
):

    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (

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


# ============================================================
# odds 구조 자동 복구
#
# 중요:
# 기존 DB가
#
# odds.bookmaker NOT NULL
#
# 또는
#
# bookmaker 기반 UNIQUE
#
# 인 경우 기존 테이블을 표준 구조로 교체한다.
# ============================================================

def _repair_odds(cur):

    if not _table_exists(
        cur,
        "odds"
    ):

        _create_standard_odds_table(
            cur,
            "odds"
        )

        return


    columns = _get_columns(
        cur,
        "odds"
    )

    # --------------------------------------------------------
    # 이미 표준 구조인지 확인
    # --------------------------------------------------------

    standard_columns = {

        "schedule_id",
        "company_id",
        "company_name",
        "final_home",
        "final_draw",
        "final_away"

    }

    has_standard = standard_columns.issubset(
        set(columns)
    )

    # --------------------------------------------------------
    # 기존 bookmaker 구조를 표준 구조로 변환
    # --------------------------------------------------------

    if not has_standard:

        old_table = "odds_old_scoreman"

        # 이전 백업 테이블이 있으면 삭제
        try:

            cur.execute(
                f"DROP TABLE IF EXISTS {old_table}"
            )

        except Exception:
            pass

        # 기존 odds 이름 변경
        cur.execute(
            f"""
            ALTER TABLE odds
            RENAME TO {old_table}
            """
        )

        # 새 표준 odds
        _create_standard_odds_table(
            cur,
            "odds"
        )

        old_columns = _get_columns(
            cur,
            old_table
        )

        # ----------------------------------------------------
        # 어떤 이름의 컬럼을 사용할지 결정
        # ----------------------------------------------------

        schedule_expr = (
            "schedule_id"
            if "schedule_id" in old_columns
            else "NULL"
        )

        company_id_expr = (
            "company_id"
            if "company_id" in old_columns
            else (
                "cid"
                if "cid" in old_columns
                else "NULL"
            )
        )

        company_name_expr = (
            "company_name"
            if "company_name" in old_columns
            else (
                "bookmaker"
                if "bookmaker" in old_columns
                else "''"
            )
        )

        home_expr = (
            "final_home"
            if "final_home" in old_columns
            else (
                "home_odds"
                if "home_odds" in old_columns
                else "NULL"
            )
        )

        draw_expr = (
            "final_draw"
            if "final_draw" in old_columns
            else (
                "draw_odds"
                if "draw_odds" in old_columns
                else "NULL"
            )
        )

        away_expr = (
            "final_away"
            if "final_away" in old_columns
            else (
                "away_odds"
                if "away_odds" in old_columns
                else "NULL"
            )
        )

        # ----------------------------------------------------
        # 기존 데이터 복사
        # 중복 업체는 첫 번째 값만 유지
        # ----------------------------------------------------

        try:

            cur.execute(
                f"""
                INSERT OR IGNORE INTO odds (
                    schedule_id,
                    company_id,
                    company_name,
                    final_home,
                    final_draw,
                    final_away
                )

                SELECT

                    {schedule_expr},

                    {company_id_expr},

                    COALESCE(
                        NULLIF(
                            TRIM(
                                CAST(
                                    {company_name_expr}
                                    AS TEXT
                                )
                            ),
                            ''
                        ),
                        'Unknown'
                    ),

                    {home_expr},
                    {draw_expr},
                    {away_expr}

                FROM {old_table}

                WHERE {schedule_expr} IS NOT NULL
                """
            )

        except Exception:

            # 데이터 복사가 실패하더라도
            # 신규 수집은 정상적으로 가능하도록 진행
            pass

        # 백업 테이블은 삭제하지 않는다.
        # 기존 데이터 안전 보존.
        #
        # odds_old_scoreman
        # 이름으로 남겨둔다.


    else:

        # ----------------------------------------------------
        # 표준 컬럼은 있지만 일부 누락 가능성 보정
        # ----------------------------------------------------

        required = {

            "company_id": "TEXT",
            "company_name": "TEXT",
            "final_home": "REAL",
            "final_draw": "REAL",
            "final_away": "REAL"

        }

        for name, typ in required.items():

            if name not in columns:

                try:

                    cur.execute(
                        f"""
                        ALTER TABLE odds
                        ADD COLUMN {name} {typ}
                        """
                    )

                except Exception:
                    pass

        # ----------------------------------------------------
        # bookmaker 컬럼이 예전에 남아 있어도 상관없음
        # NOT NULL 오류를 피하기 위해 저장 시
        # 표준 컬럼에 직접 저장한다.
        # ----------------------------------------------------


# ============================================================
# odds UNIQUE 보장
#
# 기존 테이블에 UNIQUE가 없을 경우
# 별도 인덱스로 보장한다.
# ============================================================

def _ensure_odds_unique_index(cur):

    try:

        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            ux_odds_schedule_company
            ON odds(
                schedule_id,
                company_name
            )
            """
        )

    except Exception:

        # 기존 중복 데이터가 존재하면
        # UNIQUE INDEX 생성이 실패할 수 있다.
        #
        # 이 경우 저장 함수는 UPDATE → INSERT 방식으로
        # 동작하므로 수집 자체에는 문제가 없다.
        pass


# ============================================================
# collection_state 생성
# ============================================================

def _create_collection_state(
    cur
):

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS collection_state (

            id INTEGER PRIMARY KEY,

            start_id INTEGER DEFAULT 0,

            end_id INTEGER DEFAULT 0,

            current_id INTEGER DEFAULT 0,

            last_completed_id INTEGER DEFAULT 0,

            running INTEGER DEFAULT 0,

            stopped INTEGER DEFAULT 0,

            updated_at TEXT

        )
        """
    )


# ============================================================
# collection_state 구조 자동 보정
# ============================================================

def _repair_collection_state(cur):

    if not _table_exists(
        cur,
        "collection_state"
    ):

        _create_collection_state(
            cur
        )

        return

    columns = _get_columns(
        cur,
        "collection_state"
    )

    required = {

        "start_id": "INTEGER DEFAULT 0",

        "end_id": "INTEGER DEFAULT 0",

        "current_id": "INTEGER DEFAULT 0",

        "last_completed_id":
            "INTEGER DEFAULT 0",

        "running":
            "INTEGER DEFAULT 0",

        "stopped":
            "INTEGER DEFAULT 0",

        "updated_at":
            "TEXT"

    }

    for name, typ in required.items():

        if name not in columns:

            try:

                cur.execute(
                    f"""
                    ALTER TABLE collection_state
                    ADD COLUMN {name} {typ}
                    """
                )

            except Exception:
                pass


# ============================================================
# collection_logs
# ============================================================

def _create_collection_logs(cur):

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS collection_logs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            created_at TEXT,

            message TEXT

        )
        """
    )


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

        # ----------------------------------------------------
        # 기본 테이블
        # ----------------------------------------------------

        _create_matches(
            cur
        )

        _repair_matches(
            cur
        )

        _repair_odds(
            cur
        )

        _repair_collection_state(
            cur
        )

        _create_collection_logs(
            cur
        )

        # ----------------------------------------------------
        # 인덱스
        # ----------------------------------------------------

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

        _ensure_odds_unique_index(
            cur
        )

        # ----------------------------------------------------
        # 기존 collection_state가 비어 있으면
        # id=1을 미리 생성하지 않는다.
        #
        # save_collection_state에서
        # UPDATE → INSERT 방식 사용
        # ----------------------------------------------------

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
    # 기존 경기 UPDATE
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

    # --------------------------------------------------------
    # UPDATE 결과와 관계없이 존재 여부 확인
    # --------------------------------------------------------

    if match_exists(
        schedule_id
    ):

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
# 중요:
# ON CONFLICT를 사용하지 않는다.
#
# 이유:
# 기존 Turso DB에 bookmaker 기반 UNIQUE,
# company_name 기반 UNIQUE,
# 또는 UNIQUE 자체가 없는 경우가 있기 때문이다.
#
# 따라서:
# 1. 같은 경기 + 업체 UPDATE
# 2. 없으면 INSERT
#
# 방식으로 처리한다.
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

    # --------------------------------------------------------
    # 1. 기존 동일 경기 + 동일 업체 UPDATE
    # --------------------------------------------------------

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

            WHERE schedule_id = ?

            AND LOWER(
                TRIM(company_name)
            )
            =
            LOWER(
                TRIM(?)
            )

            """,

            (

                company_id,

                company_name,

                final_home,

                final_draw,

                final_away,

                schedule_id,

                company_name

            ),

            commit=True

        )

    except Exception:

        result = False

    # --------------------------------------------------------
    # 2. 존재하는지 다시 확인
    # --------------------------------------------------------

    try:

        existing = _execute(

            """
            SELECT id
            FROM odds

            WHERE schedule_id = ?

            AND LOWER(
                TRIM(company_name)
            )
            =
            LOWER(
                TRIM(?)
            )

            LIMIT 1

            """,

            (

                schedule_id,
                company_name

            ),

            fetchone=True

        )

    except Exception:

        existing = None

    if existing:

        return True

    # --------------------------------------------------------
    # 3. 기존 bookmaker NOT NULL 구조가 남아 있어도
    # bookmaker에 회사명을 넣어줄 수 있도록 처리
    # --------------------------------------------------------

    try:

        columns = _execute(

            """
            PRAGMA table_info(odds)
            """,

            fetch=True

        )

    except Exception:

        columns = []

    column_names = {

        str(
            row.get(
                "name",
                ""
            )
        )

        for row in columns

    }

    # --------------------------------------------------------
    # 4. bookmaker 컬럼이 실제로 존재하고 NOT NULL이면
    # 그것도 함께 입력한다.
    #
    # 기존 구조 호환용.
    # --------------------------------------------------------

    if "bookmaker" in column_names:

        sql = """
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
        """

        params = (

            schedule_id,

            company_id,

            company_name,

            final_home,

            final_draw,

            final_away,

            company_name

        )

    else:

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
        """

        params = (

            schedule_id,

            company_id,

            company_name,

            final_home,

            final_draw,

            final_away

        )

    # --------------------------------------------------------
    # 5. INSERT
    # --------------------------------------------------------

    try:

        _execute(

            sql,

            params,

            commit=True

        )

        return True

    except Exception as e:

        # ----------------------------------------------------
        # 다른 오래된 UNIQUE 구조 때문에 INSERT가 실패할
        # 경우 마지막으로 기존 row를 찾아 UPDATE
        # ----------------------------------------------------

        try:

            old_row = _execute(

                """
                SELECT id
                FROM odds

                WHERE schedule_id = ?

                AND (
                    LOWER(TRIM(company_name))
                    =
                    LOWER(TRIM(?))

                    OR

                    (
                        bookmaker IS NOT NULL
                        AND
                        LOWER(TRIM(bookmaker))
                        =
                        LOWER(TRIM(?))
                    )
                )

                LIMIT 1
                """,

                (

                    schedule_id,
                    company_name,
                    company_name

                ),

                fetchone=True

            )

        except Exception:

            old_row = None

        if old_row:

            row_id = old_row.get(
                "id"
            )

            if "bookmaker" in column_names:

                _execute(

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

                    ),

                    commit=True

                )

            else:

                _execute(

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

            return True

        raise ValueError(
            f"최종배당 저장 실패: {e}"
        )


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

        ORDER BY company_name

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
# 업체별 저장 경기 수
# ============================================================

def get_company_counts():

    rows = _execute(

        """
        SELECT

            company_name,

            COUNT(
                DISTINCT schedule_id
            ) AS cnt

        FROM odds

        WHERE company_name IS NOT NULL

        AND TRIM(company_name) <> ''

        GROUP BY company_name

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
        )

        if name:

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
                        DISTINCT company_name
                    )
                    FROM odds

                    WHERE company_name
                    IS NOT NULL

                    AND TRIM(
                        company_name
                    ) <> ''
                ) AS bookmakers

            """,

            fetchone=True

        )

    except Exception:

        return {

            "matches": 0,
            "odds": 0,
            "bookmakers": 0

        }

    if not row:

        return {

            "matches": 0,
            "odds": 0,
            "bookmakers": 0

        }

    return {

        "matches": int(
            row.get(
                "matches",
                0
            )
            or 0
        ),

        "odds": int(
            row.get(
                "odds",
                0
            )
            or 0
        ),

        "bookmakers": int(
            row.get(
                "bookmakers",
                0
            )
            or 0
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

            "error": str(e)

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

            o.final_home
                AS home_odds,

            o.final_draw
                AS draw_odds,

            o.final_away
                AS away_odds

        FROM odds o

        INNER JOIN matches m

            ON m.schedule_id
             =
             o.schedule_id

        WHERE LOWER(
            TRIM(o.company_name)
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
# 중요:
# ON CONFLICT(id) 제거
#
# UPDATE 먼저
# → 존재하면 성공
# → 없으면 INSERT
#
# 기존 UNIQUE 오류 방지
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

    # --------------------------------------------------------
    # UPDATE
    # --------------------------------------------------------

    try:

        _execute(

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

        pass

    # --------------------------------------------------------
    # 실제 존재 여부 확인
    # --------------------------------------------------------

    try:

        row = _execute(

            """
            SELECT id

            FROM collection_state

            WHERE id = 1

            LIMIT 1

            """,

            fetchone=True

        )

    except Exception:

        row = None

    if row:

        return True

    # --------------------------------------------------------
    # 없으면 INSERT
    # --------------------------------------------------------

    try:

        _execute(

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

        return True

    except Exception as e:

        # ----------------------------------------------------
        # 동시에 다른 작업이 먼저 만들었을 경우
        # 마지막으로 UPDATE
        # ----------------------------------------------------

        try:

            _execute(

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

            return True

        except Exception:

            raise e


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
# 초기화 테스트
# ============================================================

if __name__ == "__main__":

    print(
        "========================================"
    )

    print(
        "⚽ Scoreman DB 구조 점검"
    )

    print(
        "========================================"
    )

    init_database()

    print(
        "DB 정보:"
    )

    print(
        get_database_info()
    )

    print(
        "DB 상태:"
    )

    print(
        get_database_status()
    )

    print(
        "수집 상태:"
    )

    print(
        get_collection_state()
    )

    print(
        "업체:"
    )

    print(
        get_company_list()
    )

    print(
        "========================================"
    )
