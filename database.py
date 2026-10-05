# database.py
import os
import sqlite3
import threading
from typing import Optional


TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL", "")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")

LOCAL_DB_PATH = os.getenv("LOCAL_DB_PATH", "scoreman.db")

_DB_LOCK = threading.RLock()


# =========================================================
# 연결
# =========================================================

def _get_turso_connection():
    if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
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
# SQL
# =========================================================

def _execute(sql, params=(), fetch=False, many=False):
    with _DB_LOCK:
        conn = _get_connection()

        try:
            cursor = conn.cursor()

            if many:
                cursor.executemany(sql, params)
            else:
                cursor.execute(sql, params)

            result = None

            if fetch:
                rows = cursor.fetchall()

                result = []

                for row in rows:
                    if isinstance(row, dict):
                        result.append(row)
                    else:
                        result.append(dict(row))

            conn.commit()

            return result

        finally:
            conn.close()


# =========================================================
# DB 초기화
# =========================================================

def init_database():

    with _DB_LOCK:
        conn = _get_connection()

        try:
            cursor = conn.cursor()

            # 경기
            cursor.execute("""
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
            """)

            # 배당
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS odds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule_id TEXT NOT NULL,
                    bookmaker TEXT NOT NULL,
                    company_id TEXT,
                    home_odds REAL,
                    draw_odds REAL,
                    away_odds REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(schedule_id, bookmaker)
                )
            """)

            # 수집 상태
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS collection_state (
                    id INTEGER PRIMARY KEY,
                    start_id INTEGER,
                    end_id INTEGER,
                    current_id INTEGER,
                    last_completed_id INTEGER,
                    total INTEGER DEFAULT 0,
                    success INTEGER DEFAULT 0,
                    exists_count INTEGER DEFAULT 0,
                    failed INTEGER DEFAULT 0,
                    odds INTEGER DEFAULT 0,
                    running INTEGER DEFAULT 0,
                    stopped INTEGER DEFAULT 0,
                    finished INTEGER DEFAULT 0,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 인덱스
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_odds_schedule
                ON odds(schedule_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_odds_bookmaker
                ON odds(bookmaker)
            """)

            conn.commit()

        finally:
            conn.close()

    return True


# =========================================================
# 경기 저장
# =========================================================

def save_match(match):

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
            match_date = excluded.match_date,
            home_team = excluded.home_team,
            away_team = excluded.away_team,
            home_score = excluded.home_score,
            away_score = excluded.away_score,
            result = excluded.result,
            source = excluded.source,
            updated_at = CURRENT_TIMESTAMP
    """

    _execute(
        sql,
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

def save_match_with_odds(match, odds_list):

    with _DB_LOCK:

        save_match(match)

        saved = 0

        for odds in odds_list:

            bookmaker = str(
                odds.get("company_name", "")
            ).strip()

            if not bookmaker:
                continue

            sql = """
                INSERT INTO odds (
                    schedule_id,
                    bookmaker,
                    company_id,
                    home_odds,
                    draw_odds,
                    away_odds
                )
                VALUES (?, ?, ?, ?, ?, ?)

                ON CONFLICT(schedule_id, bookmaker)
                DO UPDATE SET
                    company_id = excluded.company_id,
                    home_odds = excluded.home_odds,
                    draw_odds = excluded.draw_odds,
                    away_odds = excluded.away_odds
            """

            _execute(
                sql,
                (
                    str(match.get("schedule_id")),
                    bookmaker,
                    odds.get("company_id", ""),
                    odds.get("final_home"),
                    odds.get("final_draw"),
                    odds.get("final_away")
                )
            )

            saved += 1

        return saved


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


def get_all_matches():

    return _execute(
        """
        SELECT *
        FROM matches
        ORDER BY CAST(schedule_id AS INTEGER) DESC
        """,
        fetch=True
    ) or []


def get_match_count():

    rows = _execute(
        """
        SELECT COUNT(*) AS cnt
        FROM matches
        """,
        fetch=True
    )

    if not rows:
        return 0

    return int(rows[0].get("cnt", 0))


# =========================================================
# 배당
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
# app.py 호환 함수
# =========================================================

def get_match_final_odds(schedule_id):
    return get_odds_by_match(schedule_id)


def get_odds_count_by_match(schedule_id):

    rows = _execute(
        """
        SELECT COUNT(*) AS cnt
        FROM odds
        WHERE schedule_id = ?
        """,
        (str(schedule_id),),
        fetch=True
    )

    return int(rows[0].get("cnt", 0)) if rows else 0


def get_odds_count():

    rows = _execute(
        """
        SELECT COUNT(*) AS cnt
        FROM odds
        """,
        fetch=True
    )

    return int(rows[0].get("cnt", 0)) if rows else 0


# =========================================================
# 업체
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
        row["bookmaker"]
        for row in rows
    ]


def get_company_counts():

    rows = _execute(
        """
        SELECT bookmaker, COUNT(*) AS cnt
        FROM odds
        GROUP BY bookmaker
        ORDER BY cnt DESC
        """,
        fetch=True
    ) or []

    return {
        row["bookmaker"]: int(row["cnt"])
        for row in rows
    }


# =========================================================
# DB 상태
# =========================================================

def get_database_status():

    return {
        "matches": get_match_count(),
        "odds": get_odds_count(),
        "bookmakers": len(get_company_names())
    }


# =========================================================
# 수집 상태 저장
# =========================================================

def save_collection_state(
    start_id=None,
    end_id=None,
    current_id=None,
    last_completed_id=None,
    total=0,
    success=0,
    exists_count=0,
    failed=0,
    odds=0,
    running=False,
    stopped=False,
    finished=False
):

    sql = """
        INSERT INTO collection_state (
            id,
            start_id,
            end_id,
            current_id,
            last_completed_id,
            total,
            success,
            exists_count,
            failed,
            odds,
            running,
            stopped,
            finished,
            updated_at
        )
        VALUES (
            1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP
        )

        ON CONFLICT(id)
        DO UPDATE SET
            start_id = excluded.start_id,
            end_id = excluded.end_id,
            current_id = excluded.current_id,
            last_completed_id = excluded.last_completed_id,
            total = excluded.total,
            success = excluded.success,
            exists_count = excluded.exists_count,
            failed = excluded.failed,
            odds = excluded.odds,
            running = excluded.running,
            stopped = excluded.stopped,
            finished = excluded.finished,
            updated_at = CURRENT_TIMESTAMP
    """

    _execute(
        sql,
        (
            start_id,
            end_id,
            current_id,
            last_completed_id,
            total,
            success,
            exists_count,
            failed,
            odds,
            1 if running else 0,
            1 if stopped else 0,
            1 if finished else 0
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
            "start_id": None,
            "end_id": None,
            "current_id": None,
            "last_completed_id": None,
            "total": 0,
            "success": 0,
            "exists_count": 0,
            "failed": 0,
            "odds": 0,
            "running": False,
            "stopped": False,
            "finished": False
        }

    row = rows[0]

    return {
        "start_id": row.get("start_id"),
        "end_id": row.get("end_id"),
        "current_id": row.get("current_id"),
        "last_completed_id": row.get(
            "last_completed_id"
        ),
        "total": int(row.get("total") or 0),
        "success": int(row.get("success") or 0),
        "exists_count": int(
            row.get("exists_count") or 0
        ),
        "failed": int(row.get("failed") or 0),
        "odds": int(row.get("odds") or 0),
        "running": bool(row.get("running")),
        "stopped": bool(row.get("stopped")),
        "finished": bool(row.get("finished"))
    }


# =========================================================
# 마지막 수집 번호
# =========================================================

def get_last_completed_id():

    state = get_collection_state()

    return state.get("last_completed_id")


# =========================================================
# 저장 용량
# =========================================================

def get_storage_usage():

    try:

        if TURSO_DATABASE_URL:

            # Turso 원격 DB는 로컬 파일 크기로
            # 실제 사용량을 측정할 수 없으므로
            # 현재 레코드 기준 참고값만 표시
            matches = get_match_count()
            odds = get_odds_count()

            estimated_bytes = (
                matches * 300
                + odds * 180
            )

            size_mb = (
                estimated_bytes
                / 1024
                / 1024
            )

        else:

            if os.path.exists(LOCAL_DB_PATH):
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

        return {
            "success": True,
            "size_mb": size_mb,
            "size_gb": size_mb / 1024,
            "message": ""
        }

    except Exception as e:

        return {
            "success": False,
            "size_mb": 0,
            "size_gb": 0,
            "message": str(e)
        }


# =========================================================
# 시작
# =========================================================

init_database()
