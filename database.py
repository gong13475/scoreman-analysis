# =========================================================
# database.py
# Scoreman Analysis Database
# =========================================================

import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional


# =========================================================
# Turso 설정
# =========================================================

TURSO_DATABASE_URL = os.getenv(
    "TURSO_DATABASE_URL",
    ""
).strip()


TURSO_AUTH_TOKEN = os.getenv(
    "TURSO_AUTH_TOKEN",
    ""
).strip()


# =========================================================
# 로컬 SQLite
# =========================================================

LOCAL_DB_PATH = os.getenv(
    "LOCAL_DB_PATH",
    "scoreman.db"
)


# =========================================================
# DB Lock
# =========================================================

_DB_LOCK = threading.RLock()


# =========================================================
# Turso 연결
# =========================================================

def _get_turso_connection():

    if not TURSO_DATABASE_URL:
        return None

    if not TURSO_AUTH_TOKEN:
        return None

    try:

        import libsql_experimental as libsql

    except Exception:

        return None

    try:

        conn = libsql.connect(
            TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN
        )

        return conn

    except Exception:

        return None


# =========================================================
# 현재 DB 연결
# =========================================================

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


# =========================================================
# Row -> Dict
# =========================================================

def _row_to_dict(row, cursor=None):

    if row is None:
        return None

    if isinstance(row, dict):
        return dict(row)

    try:

        return dict(row)

    except Exception:

        pass

    if cursor is not None:

        try:

            columns = [
                description[0]
                for description in cursor.description
            ]

            return {
                columns[index]: row[index]
                for index in range(
                    len(columns)
                )
            }

        except Exception:

            pass

    return row


# =========================================================
# Rows -> Dict List
# =========================================================

def _rows_to_dicts(
    rows,
    cursor=None
):

    result = []

    for row in rows or []:

        converted = _row_to_dict(
            row,
            cursor
        )

        if isinstance(
            converted,
            dict
        ):

            result.append(
                converted
            )

    return result


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

            if fetch:

                rows = cursor.fetchall()

                result = _rows_to_dicts(
                    rows,
                    cursor
                )

            else:

                result = None

            conn.commit()

            return result

        finally:

            conn.close()


# =========================================================
# 테이블 컬럼 확인
# =========================================================

def _get_columns(
    table_name
):

    try:

        rows = _execute(
            f"""
            PRAGMA table_info(
                {table_name}
            )
            """,
            fetch=True
        )

        return {
            str(row.get("name"))
            for row in rows
            if row.get("name") is not None
        }

    except Exception:

        return set()


# =========================================================
# DB 초기화
# =========================================================

def init_database():

    with _DB_LOCK:

        conn = _get_connection()

        try:

            cursor = conn.cursor()

            # =================================================
            # 경기
            # =================================================

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


            # =================================================
            # 배당
            # =================================================

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

                    UNIQUE (
                        schedule_id,
                        bookmaker
                    )
                )
                """
            )


            # =================================================
            # 수집 상태
            # =================================================

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS collection_state (

                    id INTEGER PRIMARY KEY,

                    running INTEGER DEFAULT 0,

                    finished INTEGER DEFAULT 0,

                    stopped INTEGER DEFAULT 0,

                    start_id INTEGER,

                    end_id INTEGER,

                    last_completed_id INTEGER,

                    current INTEGER DEFAULT 0,

                    total INTEGER DEFAULT 0,

                    success INTEGER DEFAULT 0,

                    exists_count INTEGER DEFAULT 0,

                    failed INTEGER DEFAULT 0,

                    odds INTEGER DEFAULT 0,

                    selected_companies TEXT,

                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )


            # =================================================
            # 인덱스
            # =================================================

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


            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_matches_date
                ON matches(match_date)
                """
            )


            # =================================================
            # 상태 기본 row
            # =================================================

            cursor.execute(
                """
                INSERT OR IGNORE INTO collection_state (
                    id,
                    running,
                    finished,
                    stopped
                )
                VALUES (
                    1,
                    0,
                    0,
                    0
                )
                """
            )


            conn.commit()

        finally:

            conn.close()


    return True


# =========================================================
# 경기 저장
# =========================================================

def save_match(
    match
):

    if not match:
        return False

    schedule_id = str(
        match.get(
            "schedule_id",
            ""
        )
    ).strip()

    if not schedule_id:
        return False


    sql = """
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
    """


    _execute(
        sql,
        (
            schedule_id,

            match.get(
                "match_date"
            ),

            match.get(
                "home_team"
            ),

            match.get(
                "away_team"
            ),

            match.get(
                "home_score"
            ),

            match.get(
                "away_score"
            ),

            match.get(
                "result"
            ),

            match.get(
                "source",
                "scoreman"
            )
        )
    )

    return True


# =========================================================
# 경기 + 배당 저장
# =========================================================

def save_match_with_odds(
    match,
    odds_list
):

    if not match:
        return 0


    schedule_id = str(
        match.get(
            "schedule_id",
            ""
        )
    ).strip()


    if not schedule_id:
        return 0


    with _DB_LOCK:

        conn = _get_connection()

        try:

            cursor = conn.cursor()


            # =================================================
            # 경기
            # =================================================

            cursor.execute(
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

                    schedule_id,

                    match.get(
                        "match_date"
                    ),

                    match.get(
                        "home_team"
                    ),

                    match.get(
                        "away_team"
                    ),

                    match.get(
                        "home_score"
                    ),

                    match.get(
                        "away_score"
                    ),

                    match.get(
                        "result"
                    ),

                    match.get(
                        "source",
                        "scoreman"
                    )
                )
            )


            # =================================================
            # 배당
            # =================================================

            saved = 0


            for odds in odds_list or []:

                bookmaker = str(
                    odds.get(
                        "company_name",
                        odds.get(
                            "bookmaker",
                            ""
                        )
                    )
                ).strip()


                if not bookmaker:
                    continue


                company_id = odds.get(
                    "company_id",
                    ""
                )


                home_odds = odds.get(
                    "final_home",
                    odds.get(
                        "home_odds"
                    )
                )


                draw_odds = odds.get(
                    "final_draw",
                    odds.get(
                        "draw_odds"
                    )
                )


                away_odds = odds.get(
                    "final_away",
                    odds.get(
                        "away_odds"
                    )
                )


                cursor.execute(
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

                        schedule_id,

                        bookmaker,

                        company_id,

                        home_odds,

                        draw_odds,

                        away_odds
                    )
                )


                saved += 1


            conn.commit()

            return saved


        except Exception:

            conn.rollback()

            raise


        finally:

            conn.close()


# =========================================================
# 경기 조회
# =========================================================

def get_match(
    schedule_id
):

    rows = _execute(
        """
        SELECT *
        FROM matches
        WHERE schedule_id = ?
        LIMIT 1
        """,
        (
            str(schedule_id),
        ),
        fetch=True
    )


    if rows:
        return rows[0]


    return None


# =========================================================
# 전체 경기
# =========================================================

def get_all_matches():

    return _execute(
        """
        SELECT *
        FROM matches
        ORDER BY
            CAST(schedule_id AS INTEGER) DESC
        """,
        fetch=True
    ) or []


# =========================================================
# 경기 수
# =========================================================

def get_match_count():

    rows = _execute(
        """
        SELECT
            COUNT(*) AS cnt
        FROM matches
        """,
        fetch=True
    )


    if not rows:
        return 0


    value = rows[0].get(
        "cnt",
        0
    )


    try:
        return int(value or 0)

    except Exception:
        return 0


# =========================================================
# 전체 배당
# =========================================================

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

        ORDER BY
            CAST(schedule_id AS INTEGER) DESC,
            bookmaker
        """,
        fetch=True
    ) or []


# =========================================================
# 특정 경기 배당
# =========================================================

def get_odds_by_match(
    schedule_id
):

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

        WHERE schedule_id = ?

        ORDER BY bookmaker
        """,
        (
            str(schedule_id),
        ),
        fetch=True
    ) or []


# =========================================================
# UI 호환용
# =========================================================

def get_match_final_odds(
    schedule_id
):

    rows = get_odds_by_match(
        schedule_id
    )


    result = []


    for row in rows:

        result.append({

            "schedule_id":
                row.get(
                    "schedule_id"
                ),

            "bookmaker":
                row.get(
                    "bookmaker"
                ),

            "company_id":
                row.get(
                    "company_id"
                ),

            "final_home":
                row.get(
                    "home_odds"
                ),

            "final_draw":
                row.get(
                    "draw_odds"
                ),

            "final_away":
                row.get(
                    "away_odds"
                ),

            "home_odds":
                row.get(
                    "home_odds"
                ),

            "draw_odds":
                row.get(
                    "draw_odds"
                ),

            "away_odds":
                row.get(
                    "away_odds"
                )
        })


    return result


# =========================================================
# 특정 경기 배당 수
# =========================================================

def get_odds_count_by_match(
    schedule_id
):

    rows = _execute(
        """
        SELECT
            COUNT(*) AS cnt
        FROM odds
        WHERE schedule_id = ?
        """,
        (
            str(schedule_id),
        ),
        fetch=True
    )


    if not rows:
        return 0


    try:

        return int(
            rows[0].get(
                "cnt",
                0
            ) or 0
        )

    except Exception:

        return 0


# =========================================================
# 전체 배당 수
# =========================================================

def get_odds_count():

    rows = _execute(
        """
        SELECT
            COUNT(*) AS cnt
        FROM odds
        """,
        fetch=True
    )


    if not rows:
        return 0


    try:

        return int(
            rows[0].get(
                "cnt",
                0
            ) or 0
        )

    except Exception:

        return 0


# =========================================================
# 업체명
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
    ) or []


    result = []


    for row in rows:

        name = row.get(
            "bookmaker"
        )


        if name:

            result.append(
                str(name)
            )


    return result


# =========================================================
# 업체별 저장량
# =========================================================

def get_company_counts():

    rows = _execute(
        """
        SELECT

            bookmaker,
            COUNT(*) AS cnt

        FROM odds

        WHERE bookmaker IS NOT NULL
          AND bookmaker != ''

        GROUP BY bookmaker

        ORDER BY cnt DESC
        """,
        fetch=True
    ) or []


    result = {}


    for row in rows:

        name = row.get(
            "bookmaker"
        )


        if not name:
            continue


        try:

            count = int(
                row.get(
                    "cnt",
                    0
                ) or 0
            )

        except Exception:

            count = 0


        result[str(name)] = count


    return result


# =========================================================
# DB 상태
# =========================================================

def get_database_status():

    return {

        "matches":
            get_match_count(),

        "odds":
            get_odds_count(),

        "bookmakers":
            len(
                get_company_names()
            ),

        "database":
            (
                "Turso"
                if is_turso()
                else "SQLite"
            ),

        "turso":
            is_turso()
    }


# =========================================================
# Turso 사용 여부
# =========================================================

def is_turso():

    if not TURSO_DATABASE_URL:
        return False

    if not TURSO_AUTH_TOKEN:
        return False


    try:

        conn = _get_turso_connection()

        if conn is None:
            return False

        conn.close()

        return True

    except Exception:

        return False


# =========================================================
# DB 상태 텍스트
# =========================================================

def get_database_message():

    if is_turso():

        return (
            "🟢 Turso DB 연결 정상"
        )


    if (
        TURSO_DATABASE_URL
        or TURSO_AUTH_TOKEN
    ):

        return (
            "🟡 Turso 설정이 있으나 "
            "연결되지 않았습니다. "
            "현재 SQLite를 사용합니다."
        )


    return (
        "🟡 로컬 SQLite 사용 중"
    )


# =========================================================
# 저장 용량
# =========================================================

def get_storage_usage():

    try:

        # =================================================
        # SQLite
        # =================================================

        if not is_turso():

            if os.path.exists(
                LOCAL_DB_PATH
            ):

                size_bytes = os.path.getsize(
                    LOCAL_DB_PATH
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
            )


            return {

                "success":
                    True,

                "size_bytes":
                    size_bytes,

                "size_mb":
                    size_mb,

                "size_gb":
                    size_gb,

                "message":
                    "SQLite 로컬 저장소"
            }


        # =================================================
        # Turso
        # =================================================
        #
        # Turso 환경에서는 실제 파일 크기를
        # 로컬 os.path.getsize()로 계산하면 안 됨.
        #
        # 따라서 실제 파일 크기 대신
        # 저장 데이터 기준의 논리적 상태를 반환.
        # =================================================

        match_count = get_match_count()

        odds_count = get_odds_count()

        bookmaker_count = len(
            get_company_names()
        )


        return {

            "success":
                True,

            "size_bytes":
                0,

            "size_mb":
                0.0,

            "size_gb":
                0.0,

            "matches":
                match_count,

            "odds":
                odds_count,

            "bookmakers":
                bookmaker_count,

            "message":
                "Turso 원격 DB 사용 중"
        }


    except Exception as e:

        return {

            "success":
                False,

            "size_bytes":
                0,

            "size_mb":
                0.0,

            "size_gb":
                0.0,

            "message":
                str(e)
        }


# =========================================================
# 수집 상태 저장
# =========================================================

def save_collection_state(
    state=None,
    **kwargs
):

    if state is None:
        state = {}


    if kwargs:

        state = {
            **state,
            **kwargs
        }


    selected_companies = state.get(
        "selected_companies",
        []
    )


    if selected_companies is None:

        selected_companies = []


    if isinstance(
        selected_companies,
        (list, tuple, set)
    ):

        selected_companies = ",".join(
            str(x)
            for x in selected_companies
        )

    else:

        selected_companies = str(
            selected_companies
        )


    def value(
        key,
        default=None
    ):

        return state.get(
            key,
            default
        )


    _execute(
        """
        INSERT INTO collection_state (

            id,
            running,
            finished,
            stopped,
            start_id,
            end_id,
            last_completed_id,
            current,
            total,
            success,
            exists_count,
            failed,
            odds,
            selected_companies,
            updated_at

        )

        VALUES (

            1,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?,
            CURRENT_TIMESTAMP

        )

        ON CONFLICT(id)
        DO UPDATE SET

            running =
                excluded.running,

            finished =
                excluded.finished,

            stopped =
                excluded.stopped,

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

            success =
                excluded.success,

            exists_count =
                excluded.exists_count,

            failed =
                excluded.failed,

            odds =
                excluded.odds,

            selected_companies =
                excluded.selected_companies,

            updated_at =
                CURRENT_TIMESTAMP
        """,
        (

            int(bool(
                value(
                    "running",
                    False
                )
            )),

            int(bool(
                value(
                    "finished",
                    False
                )
            )),

            int(bool(
                value(
                    "stopped",
                    False
                )
            )),

            value(
                "start_id"
            ),

            value(
                "end_id"
            ),

            value(
                "last_completed_id"
            ),

            int(
                value(
                    "current",
                    0
                ) or 0
            ),

            int(
                value(
                    "total",
                    0
                ) or 0
            ),

            int(
                value(
                    "success",
                    0
                ) or 0
            ),

            int(
                value(
                    "exists",
                    value(
                        "exists_count",
                        0
                    )
                ) or 0
            ),

            int(
                value(
                    "failed",
                    0
                ) or 0
            ),

            int(
                value(
                    "odds",
                    0
                ) or 0
            ),

            selected_companies
        )
    )


    return True


# =========================================================
# 수집 상태 조회
# =========================================================

def get_collection_state():

    rows = _execute(
        """
        SELECT *
        FROM collection_state
        WHERE id = 1
        LIMIT 1
        """,
        fetch=True
    )


    if not rows:

        return {

            "running":
                False,

            "finished":
                False,

            "stopped":
                False,

            "start_id":
                None,

            "end_id":
                None,

            "last_completed_id":
                None,

            "current":
                0,

            "total":
                0,

            "success":
                0,

            "exists":
                0,

            "failed":
                0,

            "odds":
                0,

            "selected_companies":
                []
        }


    row = rows[0]


    companies = row.get(
        "selected_companies",
        ""
    )


    if companies:

        companies = [
            x.strip()
            for x in str(
                companies
            ).split(",")
            if x.strip()
        ]

    else:

        companies = []


    return {

        "running":
            bool(
                row.get(
                    "running",
                    0
                )
            ),

        "finished":
            bool(
                row.get(
                    "finished",
                    0
                )
            ),

        "stopped":
            bool(
                row.get(
                    "stopped",
                    0
                )
            ),

        "start_id":
            row.get(
                "start_id"
            ),

        "end_id":
            row.get(
                "end_id"
            ),

        "last_completed_id":
            row.get(
                "last_completed_id"
            ),

        "current":
            int(
                row.get(
                    "current",
                    0
                ) or 0
            ),

        "total":
            int(
                row.get(
                    "total",
                    0
                ) or 0
            ),

        "success":
            int(
                row.get(
                    "success",
                    0
                ) or 0
            ),

        "exists":
            int(
                row.get(
                    "exists_count",
                    0
                ) or 0
            ),

        "failed":
            int(
                row.get(
                    "failed",
                    0
                ) or 0
            ),

        "odds":
            int(
                row.get(
                    "odds",
                    0
                ) or 0
            ),

        "selected_companies":
            companies
    }


# =========================================================
# 마지막 완료 경기 ID
# =========================================================

def get_last_completed_id():

    state = get_collection_state()

    return state.get(
        "last_completed_id"
    )


# =========================================================
# 수집 상태 초기화
# =========================================================

def reset_collection_state():

    return save_collection_state({

        "running":
            False,

        "finished":
            False,

        "stopped":
            False,

        "start_id":
            None,

        "end_id":
            None,

        "last_completed_id":
            None,

        "current":
            0,

        "total":
            0,

        "success":
            0,

        "exists":
            0,

        "failed":
            0,

        "odds":
            0,

        "selected_companies":
            []
    })


# =========================================================
# DB 테스트
# =========================================================

def test_database():

    try:

        init_database()

        status = get_database_status()

        return {

            "success":
                True,

            "status":
                status,

            "message":
                get_database_message()
        }

    except Exception as e:

        return {

            "success":
                False,

            "status":
                {},

            "message":
                str(e)
        }


# =========================================================
# 초기화
# =========================================================

init_database()
