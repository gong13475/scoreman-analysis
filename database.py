import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional


# =========================================================
# 설정
# =========================================================

TURSO_DATABASE_URL = os.getenv(
    "TURSO_DATABASE_URL",
    ""
).strip()

TURSO_AUTH_TOKEN = os.getenv(
    "TURSO_AUTH_TOKEN",
    ""
).strip()

LOCAL_DB_PATH = os.getenv(
    "LOCAL_DB_PATH",
    "scoreman.db"
)

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
    except ImportError:
        return None

    try:
        return libsql.connect(
            TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN
        )
    except Exception:
        return None


# =========================================================
# DB 연결
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
# 실행
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

            result = None

            if fetch:

                rows = cursor.fetchall()

                result = []

                for row in rows:

                    if isinstance(row, dict):
                        result.append(dict(row))
                    else:
                        try:
                            result.append(
                                dict(row)
                            )
                        except Exception:

                            result.append(
                                {
                                    str(
                                        cursor.description[i][0]
                                    ): value
                                    for i, value
                                    in enumerate(row)
                                }
                            )

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

            # -------------------------------------------------
            # 경기
            # -------------------------------------------------

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

            # -------------------------------------------------
            # 배당
            # -------------------------------------------------

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

            # -------------------------------------------------
            # 작업 상태
            # -------------------------------------------------

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS collection_state (

                    id INTEGER PRIMARY KEY,

                    start_id INTEGER,

                    end_id INTEGER,

                    current_id INTEGER,

                    last_completed_id INTEGER,

                    status TEXT,

                    selected_companies TEXT,

                    total INTEGER DEFAULT 0,

                    success INTEGER DEFAULT 0,

                    exists_count INTEGER DEFAULT 0,

                    failed INTEGER DEFAULT 0,

                    odds INTEGER DEFAULT 0,

                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # -------------------------------------------------
            # 인덱스
            # -------------------------------------------------

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

            match_date = excluded.match_date,
            home_team = excluded.home_team,
            away_team = excluded.away_team,
            home_score = excluded.home_score,
            away_score = excluded.away_score,
            result = excluded.result,
            source = excluded.source,
            updated_at = CURRENT_TIMESTAMP
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

    with _DB_LOCK:

        conn = _get_connection()

        try:

            cursor = conn.cursor()

            # 경기
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

                    match_date = excluded.match_date,
                    home_team = excluded.home_team,
                    away_team = excluded.away_team,
                    home_score = excluded.home_score,
                    away_score = excluded.away_score,
                    result = excluded.result,
                    source = excluded.source,
                    updated_at = CURRENT_TIMESTAMP
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
                        str(
                            match.get(
                                "schedule_id"
                            )
                        ),

                        bookmaker,

                        odds.get(
                            "company_id",
                            ""
                        ),

                        odds.get(
                            "final_home"
                        ),

                        odds.get(
                            "final_draw"
                        ),

                        odds.get(
                            "final_away"
                        )
                    )
                )

                saved += 1

            conn.commit()

            return saved

        finally:

            conn.close()


# =========================================================
# 경기 조회
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
        SELECT COUNT(*) AS cnt
        FROM matches
        """,
        fetch=True
    ) or []

    if not rows:
        return 0

    try:
        return int(
            rows[0].get("cnt", 0)
        )
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
# 경기별 배당
# =========================================================

def get_odds_by_match(schedule_id):

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
        (str(schedule_id),),
        fetch=True
    ) or []


# =========================================================
# 앱 호환용
# =========================================================

def get_match_final_odds(schedule_id):

    return get_odds_by_match(
        schedule_id
    )


# =========================================================
# 특정 경기 배당 수
# =========================================================

def get_odds_count_by_match(schedule_id):

    rows = _execute(
        """
        SELECT COUNT(*) AS cnt
        FROM odds
        WHERE schedule_id = ?
        """,
        (str(schedule_id),),
        fetch=True
    ) or []

    if not rows:
        return 0

    try:
        return int(
            rows[0].get("cnt", 0)
        )
    except Exception:
        return 0


# =========================================================
# 배당 수
# =========================================================

def get_odds_count():

    rows = _execute(
        """
        SELECT COUNT(*) AS cnt
        FROM odds
        """,
        fetch=True
    ) or []

    if not rows:
        return 0

    try:
        return int(
            rows[0].get("cnt", 0)
        )
    except Exception:
        return 0


# =========================================================
# 업체명
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
        row.get("bookmaker", "")
        for row in rows
        if row.get("bookmaker")
    ]


# =========================================================
# 업체별 수
# =========================================================

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

    result = {}

    for row in rows:

        bookmaker = row.get(
            "bookmaker"
        )

        if bookmaker:

            try:
                result[bookmaker] = int(
                    row.get("cnt", 0)
                )
            except Exception:
                result[bookmaker] = 0

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

        "turso":
            bool(
                _get_turso_connection()
            )
    }


# =========================================================
# 작업 상태 저장
# =========================================================

def save_collection_state(
    start_id,
    end_id,
    current_id,
    last_completed_id,
    status,
    selected_companies,
    total,
    success,
    exists_count,
    failed,
    odds
):

    import json

    companies = json.dumps(
        selected_companies or [],
        ensure_ascii=False
    )

    _execute(
        """
        INSERT INTO collection_state (

            id,
            start_id,
            end_id,
            current_id,
            last_completed_id,
            status,
            selected_companies,
            total,
            success,
            exists_count,
            failed,
            odds,
            updated_at

        )

        VALUES (
            1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP
        )

        ON CONFLICT(id)

        DO UPDATE SET

            start_id = excluded.start_id,
            end_id = excluded.end_id,
            current_id = excluded.current_id,
            last_completed_id = excluded.last_completed_id,
            status = excluded.status,
            selected_companies = excluded.selected_companies,
            total = excluded.total,
            success = excluded.success,
            exists_count = excluded.exists_count,
            failed = excluded.failed,
            odds = excluded.odds,
            updated_at = CURRENT_TIMESTAMP
        """,

        (
            int(start_id),
            int(end_id),
            int(current_id) if current_id is not None else None,
            int(last_completed_id)
            if last_completed_id is not None
            else None,
            status,
            companies,
            int(total),
            int(success),
            int(exists_count),
            int(failed),
            int(odds)
        )
    )


# =========================================================
# 작업 상태 조회
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
    ) or []

    if not rows:
        return None

    row = rows[0]

    import json

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


# =========================================================
# 마지막 완료 ID
# =========================================================

def get_last_completed_id():

    state = get_collection_state()

    if not state:
        return None

    value = state.get(
        "last_completed_id"
    )

    try:
        return int(value)
    except Exception:
        return None


# =========================================================
# 저장공간
# =========================================================

def get_storage_usage():

    """
    정확한 Turso 청구/스토리지 API가 없는 환경에서는
    SQLite 파일 크기 또는 논리적인 추정값을 표시한다.
    """

    try:

        if not TURSO_DATABASE_URL:

            if os.path.exists(
                LOCAL_DB_PATH
            ):
                size_bytes = os.path.getsize(
                    LOCAL_DB_PATH
                )
            else:
                size_bytes = 0

        else:

            # Turso에서는 로컬 DB 파일이 없으므로
            # 저장 행 기반의 보수적 추정값을 사용한다.

            match_count = get_match_count()
            odds_count = get_odds_count()

            # 경기 1건당 1KB
            # 배당 1건당 300B
            size_bytes = (
                match_count * 1024
                + odds_count * 300
            )

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

            "limit_gb":
                5.0,

            "used_percent":
                (
                    size_gb
                    / 5.0
                    * 100
                ),

            "message":
                ""
        }

    except Exception as e:

        return {

            "success":
                False,

            "size_bytes":
                0,

            "size_mb":
                0,

            "size_gb":
                0,

            "limit_gb":
                5.0,

            "used_percent":
                0,

            "message":
                str(e)
        }


# =========================================================
# 초기화
# =========================================================

init_database()
