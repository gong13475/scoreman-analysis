import os
import sqlite3
import json
import threading
from pathlib import Path

try:
    import libsql_experimental as libsql
    LIBSQL_IMPORT_ERROR = ""
except Exception as e:
    libsql = None
    LIBSQL_IMPORT_ERROR = str(e)

import streamlit as st


# =========================================================
# 기본 설정
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

SQLITE_PATH = BASE_DIR / "scoreman.db"

_DB_LOCK = threading.RLock()


# =========================================================
# 설정값 읽기
# 환경변수 우선
# 없으면 Streamlit Secrets 확인
# =========================================================

def _get_secret(name):

    try:

        value = st.secrets.get(
            name,
            ""
        )

        if value is None:
            return ""

        return str(value).strip()

    except Exception:

        return ""


TURSO_DATABASE_URL = (
    os.getenv(
        "TURSO_DATABASE_URL",
        ""
    ).strip()
    or _get_secret(
        "TURSO_DATABASE_URL"
    )
)

TURSO_AUTH_TOKEN = (
    os.getenv(
        "TURSO_AUTH_TOKEN",
        ""
    ).strip()
    or _get_secret(
        "TURSO_AUTH_TOKEN"
    )
)


# =========================================================
# Turso 사용 여부
# =========================================================

def _use_turso():

    return bool(
        TURSO_DATABASE_URL
        and TURSO_AUTH_TOKEN
        and libsql is not None
    )


# =========================================================
# DB 연결
# =========================================================

def get_connection():

    if _use_turso():

        return libsql.connect(
            TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN
        )

    return sqlite3.connect(
        SQLITE_PATH,
        check_same_thread=False
    )


# =========================================================
# 실제 Turso 연결 테스트
# =========================================================

def test_turso_connection():

    if not TURSO_DATABASE_URL:

        return {
            "success": False,
            "connected": False,
            "message":
                "TURSO_DATABASE_URL이 설정되지 않았습니다."
        }

    if not TURSO_AUTH_TOKEN:

        return {
            "success": False,
            "connected": False,
            "message":
                "TURSO_AUTH_TOKEN이 설정되지 않았습니다."
        }

    if libsql is None:

        return {
            "success": False,
            "connected": False,
            "message":
                "libsql_experimental 모듈을 사용할 수 없습니다.",
            "error":
                LIBSQL_IMPORT_ERROR
        }

    conn = None

    try:

        conn = libsql.connect(
            TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN
        )

        cur = conn.cursor()

        cur.execute(
            "SELECT 1"
        )

        row = cur.fetchone()

        if row and int(row[0]) == 1:

            return {
                "success": True,
                "connected": True,
                "message":
                    "Turso 연결 성공"
            }

        return {
            "success": False,
            "connected": False,
            "message":
                "Turso 연결은 되었지만 테스트 쿼리 결과가 올바르지 않습니다."
        }

    except Exception as e:

        return {
            "success": False,
            "connected": False,
            "message":
                "Turso 연결 실패",
            "error": str(e)
        }

    finally:

        if conn is not None:

            try:
                conn.close()
            except Exception:
                pass


# =========================================================
# SQL 실행
# =========================================================

def _execute(
    sql,
    params=(),
    fetch=False,
    many=False
):

    with _DB_LOCK:

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

            rows = None

            if fetch:
                rows = cur.fetchall()

            conn.commit()

            return rows

        finally:

            conn.close()


# =========================================================
# 딕셔너리 1행
# =========================================================

def _execute_dict(
    sql,
    params=()
):

    with _DB_LOCK:

        conn = get_connection()

        try:

            cur = conn.cursor()

            cur.execute(
                sql,
                params
            )

            if not cur.description:

                conn.commit()

                return None

            columns = [
                x[0]
                for x in cur.description
            ]

            row = cur.fetchone()

            if not row:

                conn.commit()

                return None

            return dict(
                zip(
                    columns,
                    row
                )
            )

        finally:

            conn.close()


# =========================================================
# 초기화
# =========================================================

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
            bookmaker TEXT NOT NULL,
            bookmaker_id TEXT,
            home_odds REAL NOT NULL,
            draw_odds REAL NOT NULL,
            away_odds REAL NOT NULL,
            UNIQUE(schedule_id, bookmaker)
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
            current INTEGER DEFAULT 0,
            total INTEGER DEFAULT 0,
            running INTEGER DEFAULT 0,
            stopped INTEGER DEFAULT 0,
            selected_companies TEXT DEFAULT '[]'
        )
        """
    )

    _execute(
        """
        INSERT OR IGNORE INTO collection_state
        (id, selected_companies)
        VALUES (1, '[]')
        """
    )


# =========================================================
# DB 상태
# =========================================================

def get_database_status():

    matches = _execute(
        """
        SELECT COUNT(*)
        FROM matches
        """,
        fetch=True
    )[0][0]

    odds = _execute(
        """
        SELECT COUNT(*)
        FROM odds
        """,
        fetch=True
    )[0][0]

    bookmakers = _execute(
        """
        SELECT COUNT(DISTINCT bookmaker)
        FROM odds
        """,
        fetch=True
    )[0][0]

    return {
        "matches": int(matches),
        "odds": int(odds),
        "bookmakers": int(bookmakers)
    }


# =========================================================
# DB 저장 크기
# =========================================================

def _format_size(size_bytes):

    size_bytes = int(
        size_bytes or 0
    )

    return {
        "size_bytes": size_bytes,
        "size_mb":
            size_bytes
            / 1024
            / 1024,
        "size_gb":
            size_bytes
            / 1024
            / 1024
            / 1024
    }


def _get_sqlite_file_size():

    if not SQLITE_PATH.exists():
        return 0

    try:

        return SQLITE_PATH.stat().st_size

    except Exception:

        return 0


def _get_turso_logical_size():

    conn = get_connection()

    try:

        cur = conn.cursor()

        page_count = 0
        page_size = 0

        try:

            cur.execute(
                "PRAGMA page_count"
            )

            row = cur.fetchone()

            if row:

                page_count = int(
                    row[0] or 0
                )

        except Exception:
            pass

        try:

            cur.execute(
                "PRAGMA page_size"
            )

            row = cur.fetchone()

            if row:

                page_size = int(
                    row[0] or 0
                )

        except Exception:
            pass

        if (
            page_count > 0
            and page_size > 0
        ):

            return (
                page_count
                * page_size
            )

        total = 0

        try:

            cur.execute(
                """
                SELECT COUNT(*)
                FROM matches
                """
            )

            matches_count = int(
                cur.fetchone()[0]
                or 0
            )

            cur.execute(
                """
                SELECT COUNT(*)
                FROM odds
                """
            )

            odds_count = int(
                cur.fetchone()[0]
                or 0
            )

            cur.execute(
                """
                SELECT COUNT(*)
                FROM collection_state
                """
            )

            state_count = int(
                cur.fetchone()[0]
                or 0
            )

            total = (
                matches_count * 512
                + odds_count * 256
                + state_count * 1024
            )

        except Exception:

            total = 0

        return total

    finally:

        conn.close()


def get_storage_usage():

    try:

        if _use_turso():

            size_bytes = (
                _get_turso_logical_size()
            )

            size = _format_size(
                size_bytes
            )

            return {
                "success": True,
                **size,
                "storage_type": "Turso",
                "measurement":
                    "Turso DB 논리적 저장 크기",
                "quota_available": False
            }

        size_bytes = (
            _get_sqlite_file_size()
        )

        size = _format_size(
            size_bytes
        )

        return {
            "success": True,
            **size,
            "storage_type": "SQLite",
            "measurement":
                "현재 실행 환경의 SQLite 파일 크기",
            "quota_available": False
        }

    except Exception as e:

        return {
            "success": False,
            "size_bytes": 0,
            "size_mb": 0,
            "size_gb": 0,
            "storage_type":
                (
                    "Turso"
                    if _use_turso()
                    else "SQLite"
                ),
            "measurement": "",
            "quota_available": False,
            "error": str(e)
        }


# =========================================================
# DB 정보
# =========================================================

def get_database_info():

    usage = get_storage_usage()

    connection_test = None

    if (
        TURSO_DATABASE_URL
        and TURSO_AUTH_TOKEN
        and libsql is not None
    ):

        connection_test = (
            test_turso_connection()
        )

    return {
        "using_turso":
            _use_turso(),

        "turso_configured":
            bool(
                TURSO_DATABASE_URL
                and TURSO_AUTH_TOKEN
            ),

        "libsql_available":
            libsql is not None,

        "libsql_import_error":
            LIBSQL_IMPORT_ERROR,

        "database_url_configured":
            bool(
                TURSO_DATABASE_URL
            ),

        "auth_token_configured":
            bool(
                TURSO_AUTH_TOKEN
            ),

        "connection_test":
            connection_test,

        "storage":
            usage
    }


# =========================================================
# 경기 조회
# =========================================================

def get_match(schedule_id):

    return _execute_dict(
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
        """,
        (
            str(schedule_id),
        )
    )


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
        ORDER BY CAST(
            schedule_id AS INTEGER
        )
        """,
        fetch=True
    )

    columns = [
        "schedule_id",
        "match_date",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "result",
        "source"
    ]

    return [
        dict(
            zip(
                columns,
                row
            )
        )
        for row in rows
    ]


# =========================================================
# 업체
# =========================================================

def get_company_names():

    rows = _execute(
        """
        SELECT DISTINCT bookmaker
        FROM odds
        ORDER BY bookmaker
        """,
        fetch=True
    )

    return [
        row[0]
        for row in rows
        if row[0]
    ]


def get_company_counts():

    rows = _execute(
        """
        SELECT
            bookmaker,
            COUNT(DISTINCT schedule_id)
        FROM odds
        GROUP BY bookmaker
        ORDER BY bookmaker
        """,
        fetch=True
    )

    return {
        row[0]: int(row[1])
        for row in rows
    }


# =========================================================
# 경기 + 최종배당 저장
# =========================================================

def save_match_with_odds(
    match,
    odds_list
):

    with _DB_LOCK:

        conn = get_connection()

        try:

            cur = conn.cursor()

            cur.execute(
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
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?
                )

                ON CONFLICT(schedule_id)
                DO UPDATE SET
                    match_date=excluded.match_date,
                    home_team=excluded.home_team,
                    away_team=excluded.away_team,
                    home_score=excluded.home_score,
                    away_score=excluded.away_score,
                    result=excluded.result,
                    source=excluded.source
                """,
                (
                    str(
                        match["schedule_id"]
                    ),
                    match.get(
                        "match_date",
                        ""
                    ),
                    match.get(
                        "home_team",
                        ""
                    ),
                    match.get(
                        "away_team",
                        ""
                    ),
                    match.get(
                        "home_score"
                    ),
                    match.get(
                        "away_score"
                    ),
                    match.get(
                        "result",
                        ""
                    ),
                    match.get(
                        "source",
                        "scoreman"
                    )
                )
            )

            saved = 0

            for row in odds_list:

                company_name = (
                    row.get(
                        "company_name"
                    )
                    or row.get(
                        "bookmaker"
                    )
                    or ""
                )

                if not company_name:
                    continue

                cur.execute(
                    """
                    INSERT INTO odds (
                        schedule_id,
                        bookmaker,
                        bookmaker_id,
                        home_odds,
                        draw_odds,
                        away_odds
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?
                    )

                    ON CONFLICT(
                        schedule_id,
                        bookmaker
                    )
                    DO UPDATE SET
                        bookmaker_id=
                            excluded.bookmaker_id,
                        home_odds=
                            excluded.home_odds,
                        draw_odds=
                            excluded.draw_odds,
                        away_odds=
                            excluded.away_odds
                    """,
                    (
                        str(
                            match["schedule_id"]
                        ),
                        company_name,
                        row.get(
                            "company_id",
                            ""
                        ),
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

            conn.commit()

            return saved

        finally:

            conn.close()


# =========================================================
# 경기별 배당
# =========================================================

def get_odds_by_match(
    schedule_id
):

    rows = _execute(
        """
        SELECT
            bookmaker,
            bookmaker_id,
            home_odds,
            draw_odds,
            away_odds
        FROM odds
        WHERE schedule_id = ?
        ORDER BY bookmaker
        """,
        (
            str(schedule_id),
        ),
        fetch=True
    )

    columns = [
        "bookmaker",
        "bookmaker_id",
        "home_odds",
        "draw_odds",
        "away_odds"
    ]

    return [
        dict(
            zip(
                columns,
                row
            )
        )
        for row in rows
    ]


# =========================================================
# 배당 검색
# =========================================================

def search_odds(
    home,
    draw,
    away,
    companies=None,
    tolerance=0.001
):

    sql = """
        SELECT
            o.schedule_id,
            m.match_date,
            m.home_team,
            m.away_team,
            o.bookmaker,
            o.home_odds,
            o.draw_odds,
            o.away_odds,
            m.home_score,
            m.away_score,
            m.result
        FROM odds o
        JOIN matches m
          ON m.schedule_id =
             o.schedule_id
        WHERE
            ABS(o.home_odds - ?) <= ?
            AND ABS(o.draw_odds - ?) <= ?
            AND ABS(o.away_odds - ?) <= ?
    """

    params = [
        float(home),
        tolerance,
        float(draw),
        tolerance,
        float(away),
        tolerance
    ]

    if companies:

        placeholders = ",".join(
            "?"
            for _ in companies
        )

        sql += (
            " AND o.bookmaker "
            f"IN ({placeholders})"
        )

        params.extend(
            companies
        )

    sql += """
        ORDER BY CAST(
            o.schedule_id AS INTEGER
        )
    """

    rows = _execute(
        sql,
        params,
        fetch=True
    )

    columns = [
        "schedule_id",
        "match_date",
        "home_team",
        "away_team",
        "bookmaker",
        "home_odds",
        "draw_odds",
        "away_odds",
        "home_score",
        "away_score",
        "result"
    ]

    return [
        dict(
            zip(
                columns,
                row
            )
        )
        for row in rows
    ]


# =========================================================
# 수집 상태 저장
# =========================================================

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

    _execute(
        """
        INSERT INTO collection_state (
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
        VALUES (
            1, ?, ?, ?, ?, ?, ?, ?, ?
        )

        ON CONFLICT(id)
        DO UPDATE SET
            start_id=excluded.start_id,
            end_id=excluded.end_id,
            last_completed_id=
                excluded.last_completed_id,
            current=excluded.current,
            total=excluded.total,
            running=excluded.running,
            stopped=excluded.stopped,
            selected_companies=
                excluded.selected_companies
        """,
        (
            start_id,
            end_id,
            last_completed_id,
            current,
            total,
            1 if running else 0,
            1 if stopped else 0,
            json.dumps(
                selected_companies or [],
                ensure_ascii=False
            )
        )
    )


def get_collection_state():

    row = _execute_dict(
        """
        SELECT *
        FROM collection_state
        WHERE id = 1
        """
    )

    if not row:
        return {}

    try:

        row["selected_companies"] = json.loads(
            row.get(
                "selected_companies",
                "[]"
            )
        )

    except Exception:

        row["selected_companies"] = []

    return row
