import os
import sqlite3
import json
import threading
from pathlib import Path

try:
    import libsql_experimental as libsql
except Exception:
    libsql = None

import streamlit as st


# =========================================================
# 기본 설정
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

SQLITE_PATH = BASE_DIR / "scoreman.db"

_DB_LOCK = threading.RLock()


# =========================================================
# 설정값
# =========================================================

def _get_secret(name):
    """
    Streamlit Secrets에서 설정값을 읽습니다.
    Secrets가 없거나 접근할 수 없는 경우 빈 문자열을 반환합니다.
    """

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


def _get_turso_database_url():
    """
    환경변수 우선.
    없으면 Streamlit Secrets 사용.
    """

    return (
        os.getenv(
            "TURSO_DATABASE_URL",
            ""
        ).strip()
        or _get_secret(
            "TURSO_DATABASE_URL"
        )
    )


def _get_turso_auth_token():
    """
    환경변수 우선.
    없으면 Streamlit Secrets 사용.
    """

    return (
        os.getenv(
            "TURSO_AUTH_TOKEN",
            ""
        ).strip()
        or _get_secret(
            "TURSO_AUTH_TOKEN"
        )
    )


# =========================================================
# 기존 호환용 설정값
#
# 기존 코드에서 직접 참조할 가능성을 고려하여
# 전역 변수도 유지합니다.
# =========================================================

TURSO_DATABASE_URL = _get_turso_database_url()

TURSO_AUTH_TOKEN = _get_turso_auth_token()


# =========================================================
# Turso 설정 새로 읽기
# =========================================================

def _refresh_turso_config():
    """
    앱 실행 중 환경변수/Secrets가 변경된 경우에도
    현재 설정을 다시 확인할 수 있도록 합니다.

    기존 전역 변수도 함께 갱신합니다.
    """

    global TURSO_DATABASE_URL
    global TURSO_AUTH_TOKEN

    TURSO_DATABASE_URL = (
        _get_turso_database_url()
    )

    TURSO_AUTH_TOKEN = (
        _get_turso_auth_token()
    )

    return (
        TURSO_DATABASE_URL,
        TURSO_AUTH_TOKEN
    )


# =========================================================
# Turso 사용 여부
# =========================================================

def _use_turso():

    url, token = (
        _refresh_turso_config()
    )

    return bool(
        url
        and token
        and libsql is not None
    )


# =========================================================
# DB 연결
# =========================================================

def get_connection():

    if _use_turso():

        url = TURSO_DATABASE_URL
        token = TURSO_AUTH_TOKEN

        return libsql.connect(
            url,
            auth_token=token
        )

    return sqlite3.connect(
        SQLITE_PATH,
        check_same_thread=False
    )


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
# 테이블 존재 여부
# =========================================================

def _table_exists(
    table_name
):

    try:

        row = _execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            """,
            (table_name,),
            fetch=True
        )

        return bool(row)

    except Exception:

        return False


# =========================================================
# 컬럼 존재 여부
# =========================================================

def _column_exists(
    table_name,
    column_name
):

    try:

        rows = _execute(
            f"""
            PRAGMA table_info({table_name})
            """,
            fetch=True
        )

        for row in rows:

            if len(row) > 1:

                if str(row[1]) == column_name:

                    return True

    except Exception:

        pass

    return False


# =========================================================
# 인덱스 생성
# =========================================================

def _create_indexes():

    indexes = [

        """
        CREATE INDEX IF NOT EXISTS
        idx_odds_schedule_id
        ON odds(schedule_id)
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_odds_bookmaker
        ON odds(bookmaker)
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_odds_schedule_bookmaker
        ON odds(schedule_id, bookmaker)
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_matches_schedule_id
        ON matches(schedule_id)
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_matches_result
        ON matches(result)
        """

    ]

    for sql in indexes:

        try:

            _execute(sql)

        except Exception:
            pass


# =========================================================
# 초기화
# =========================================================

def init_database():

    # -----------------------------------------------------
    # 경기
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # 배당
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # 수집 상태
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # 기존 DB에 혹시 selected_companies가 없는 경우
    # -----------------------------------------------------

    if _table_exists(
        "collection_state"
    ):

        if not _column_exists(
            "collection_state",
            "selected_companies"
        ):

            try:

                _execute(
                    """
                    ALTER TABLE collection_state
                    ADD COLUMN selected_companies
                    TEXT DEFAULT '[]'
                    """
                )

            except Exception:
                pass


    # -----------------------------------------------------
    # 기본 상태
    # -----------------------------------------------------

    _execute(
        """
        INSERT OR IGNORE INTO collection_state
        (
            id,
            selected_companies
        )
        VALUES (
            1,
            '[]'
        )
        """
    )


    # -----------------------------------------------------
    # 인덱스
    # -----------------------------------------------------

    _create_indexes()


# =========================================================
# DB 상태
# =========================================================

def get_database_status():

    try:

        matches = _execute(
            """
            SELECT COUNT(*)
            FROM matches
            """,
            fetch=True
        )[0][0]

    except Exception:

        matches = 0


    try:

        odds = _execute(
            """
            SELECT COUNT(*)
            FROM odds
            """,
            fetch=True
        )[0][0]

    except Exception:

        odds = 0


    try:

        bookmakers = _execute(
            """
            SELECT COUNT(DISTINCT bookmaker)
            FROM odds
            """,
            fetch=True
        )[0][0]

    except Exception:

        bookmakers = 0


    return {
        "matches": int(
            matches or 0
        ),

        "odds": int(
            odds or 0
        ),

        "bookmakers": int(
            bookmakers or 0
        )
    }


# =========================================================
# DB 저장 크기
# =========================================================

def _format_size(
    size_bytes
):

    size_bytes = int(
        size_bytes or 0
    )

    return {
        "size_bytes":
            size_bytes,

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


# =========================================================
# SQLite 파일 크기
# =========================================================

def _get_sqlite_file_size():

    if not SQLITE_PATH.exists():

        return 0

    try:

        return SQLITE_PATH.stat().st_size

    except Exception:

        return 0


# =========================================================
# Turso 논리적 크기
# =========================================================

def _get_turso_logical_size():

    """
    현재 연결된 Turso/libSQL DB의 논리적 크기입니다.

    주의:
    Turso 계정 전체 사용량이나 무료 플랜 quota가 아닙니다.
    """

    conn = get_connection()

    try:

        cur = conn.cursor()

        page_count = 0
        page_size = 0


        # -------------------------------------------------
        # page_count
        # -------------------------------------------------

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


        # -------------------------------------------------
        # page_size
        # -------------------------------------------------

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


        # -------------------------------------------------
        # fallback
        # -------------------------------------------------

        total = 0

        try:

            cur.execute(
                """
                SELECT COUNT(*)
                FROM matches
                """
            )

            matches_count = int(
                cur.fetchone()[0] or 0
            )


            cur.execute(
                """
                SELECT COUNT(*)
                FROM odds
                """
            )

            odds_count = int(
                cur.fetchone()[0] or 0
            )


            cur.execute(
                """
                SELECT COUNT(*)
                FROM collection_state
                """
            )

            state_count = int(
                cur.fetchone()[0] or 0
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


# =========================================================
# DB 저장 용량
# =========================================================

def get_storage_usage():

    """
    현재 DB 자체의 저장 크기입니다.

    Turso:
        연결된 DB의 논리적 저장 크기

    SQLite:
        scoreman.db 실제 파일 크기
    """

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
# DB 연결 정보
# =========================================================

def get_database_info():

    _refresh_turso_config()

    usage = get_storage_usage()

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

        "database_url_configured":
            bool(
                TURSO_DATABASE_URL
            ),

        "auth_token_configured":
            bool(
                TURSO_AUTH_TOKEN
            ),

        "storage":
            usage
    }


# =========================================================
# 경기 조회
# =========================================================

def get_match(
    schedule_id
):

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


# =========================================================
# 경기 전체 조회
# =========================================================

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
        ORDER BY
            CAST(
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
        SELECT DISTINCT
            bookmaker
        FROM odds
        WHERE bookmaker IS NOT NULL
          AND bookmaker != ''
        ORDER BY bookmaker
        """,
        fetch=True
    )

    return [
        row[0]
        for row in rows
        if row[0]
    ]


# =========================================================
# 업체별 경기 수
# =========================================================

def get_company_counts():

    rows = _execute(
        """
        SELECT
            bookmaker,
            COUNT(DISTINCT schedule_id)
        FROM odds
        WHERE bookmaker IS NOT NULL
          AND bookmaker != ''
        GROUP BY bookmaker
        ORDER BY bookmaker
        """,
        fetch=True
    )

    return {
        row[0]:
            int(
                row[1] or 0
            )
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


            # -------------------------------------------------
            # 경기 저장
            # -------------------------------------------------

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
                        excluded.source
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


            # -------------------------------------------------
            # 배당 저장
            # -------------------------------------------------

            for row in (
                odds_list or []
            ):

                company_name = (
                    row.get(
                        "company_name"
                    )
                    or row.get(
                        "bookmaker"
                    )
                    or ""
                )


                company_name = str(
                    company_name
                ).strip()


                if not company_name:

                    continue


                try:

                    home_odds = float(
                        row[
                            "final_home"
                        ]
                    )

                    draw_odds = float(
                        row[
                            "final_draw"
                        ]
                    )

                    away_odds = float(
                        row[
                            "final_away"
                        ]
                    )

                except Exception:

                    continue


                if (
                    home_odds <= 0
                    or draw_odds <= 0
                    or away_odds <= 0
                ):

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

                        bookmaker_id =
                            excluded.bookmaker_id,

                        home_odds =
                            excluded.home_odds,

                        draw_odds =
                            excluded.draw_odds,

                        away_odds =
                            excluded.away_odds
                    """,
                    (
                        str(
                            match[
                                "schedule_id"
                            ]
                        ),

                        company_name,

                        row.get(
                            "company_id",
                            ""
                        ),

                        home_odds,

                        draw_odds,

                        away_odds
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
            ABS(
                o.home_odds - ?
            ) <= ?

            AND ABS(
                o.draw_odds - ?
            ) <= ?

            AND ABS(
                o.away_odds - ?
            ) <= ?
    """


    params = [
        float(home),
        float(tolerance),

        float(draw),
        float(tolerance),

        float(away),
        float(tolerance)
    ]


    if companies:

        companies = [
            str(x).strip()
            for x in companies
            if str(x).strip()
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
        ORDER BY
            CAST(
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
            1,
            ?, ?, ?, ?, ?, ?, ?, ?
        )

        ON CONFLICT(id)
        DO UPDATE SET

            start_id =
                excluded.start_id,

            end_id =
                excluded.end_id,

            last_completed_id =
                excluded.last_completed_id,

            current =
                excluded.current,

            total =
                excluded.total,

            running =
                excluded.running,

            stopped =
                excluded.stopped,

            selected_companies =
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


# =========================================================
# 수집 상태 조회
# =========================================================

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

        selected = row.get(
            "selected_companies",
            "[]"
        )


        if selected is None:

            selected = "[]"


        if isinstance(
            selected,
            str
        ):

            row[
                "selected_companies"
            ] = json.loads(
                selected
            )

        else:

            row[
                "selected_companies"
            ] = list(
                selected
            )

    except Exception:

        row[
            "selected_companies"
        ] = []


    # 숫자값을 최대한 안전하게 정리
    for key in [
        "start_id",
        "end_id",
        "last_completed_id",
        "current",
        "total"
    ]:

        value = row.get(key)

        if value is None:
            continue

        try:

            row[key] = int(
                value
            )

        except Exception:

            pass


    return row


# =========================================================
# 현재 DB 타입
# =========================================================

def get_database_type():

    if _use_turso():

        return "Turso"

    return "SQLite"


# =========================================================
# 연결 테스트
# =========================================================

def test_connection():

    try:

        conn = get_connection()

        try:

            cur = conn.cursor()

            cur.execute(
                "SELECT 1"
            )

            row = cur.fetchone()

            return {
                "success":
                    bool(
                        row
                        and row[0] == 1
                    ),

                "database":
                    get_database_type(),

                "error": ""
            }

        finally:

            conn.close()

    except Exception as e:

        return {
            "success": False,
            "database":
                get_database_type(),
            "error": str(e)
        }


# =========================================================
# DB 전체 상태
# =========================================================

def get_full_database_status():

    status = get_database_status()

    info = get_database_info()

    connection = test_connection()

    state = get_collection_state()

    return {
        "database":
            info,

        "connection":
            connection,

        "counts":
            status,

        "collection":
            state
            }
