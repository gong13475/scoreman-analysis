import os
import sqlite3
import json
import threading
from pathlib import Path

try:
    import libsql_experimental as libsql
except Exception:
    libsql = None


# =========================================================
# 설정
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

SQLITE_PATH = BASE_DIR / "scoreman.db"

TURSO_DATABASE_URL = os.getenv(
    "TURSO_DATABASE_URL",
    ""
).strip()

TURSO_AUTH_TOKEN = os.getenv(
    "TURSO_AUTH_TOKEN",
    ""
).strip()

_DB_LOCK = threading.RLock()


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
# 기본 SQL 실행
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
# Dictionary 조회
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

                return None

            columns = [
                x[0]
                for x in cur.description
            ]

            row = cur.fetchone()

            if not row:

                return None

            return dict(
                zip(columns, row)
            )

        finally:

            conn.close()


# =========================================================
# DB 초기화
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
        (
            id,
            selected_companies
        )
        VALUES
        (
            1,
            '[]'
        )
        """
    )


# =========================================================
# DB 상태
# =========================================================

def get_database_status():

    matches = _execute(
        "SELECT COUNT(*) FROM matches",
        fetch=True
    )[0][0]

    odds = _execute(
        "SELECT COUNT(*) FROM odds",
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

def get_storage_usage():

    # -----------------------------------------------------
    # Turso 사용 중
    # -----------------------------------------------------
    if _use_turso():

        return {
            "success": True,

            "size_bytes": None,

            "size_mb": None,

            "size_gb": None,

            "storage_type": "Turso",

            "is_turso": True,

            "message": (
                "현재 데이터베이스는 Turso를 사용 중입니다. "
                "Turso 실제 저장 용량과 무료 플랜 사용량은 "
                "Turso 콘솔에서 확인하세요."
            )
        }

    # -----------------------------------------------------
    # SQLite 사용 중
    # -----------------------------------------------------
    try:

        if SQLITE_PATH.exists():

            size_bytes = SQLITE_PATH.stat().st_size

        else:

            size_bytes = 0

        return {
            "success": True,

            "size_bytes": size_bytes,

            "size_mb": (
                size_bytes / 1024 / 1024
            ),

            "size_gb": (
                size_bytes / 1024 / 1024 / 1024
            ),

            "storage_type": "SQLite",

            "is_turso": False,

            "message": (
                "현재 로컬 SQLite 파일의 "
                "저장 크기입니다."
            )
        }

    except Exception as e:

        return {
            "success": False,

            "size_bytes": 0,

            "size_mb": 0,

            "size_gb": 0,

            "storage_type": "SQLite",

            "is_turso": False,

            "message": str(e)
        }


# =========================================================
# DB 정보
# =========================================================

def get_database_info():

    usage = get_storage_usage()

    return {
        "using_turso": _use_turso(),

        "turso_configured": bool(
            TURSO_DATABASE_URL
            and TURSO_AUTH_TOKEN
        ),

        "libsql_available": (
            libsql is not None
        ),

        "storage": usage
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
        ORDER BY CAST(schedule_id AS INTEGER)
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
        dict(zip(columns, row))
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
                """,
                (
                    str(match["schedule_id"]),
                    match.get("match_date", ""),
                    match.get("home_team", ""),
                    match.get("away_team", ""),
                    match.get("home_score"),
                    match.get("away_score"),
                    match.get("result", ""),
                    match.get("source", "scoreman")
                )
            )

            saved = 0

            for row in odds_list:

                company_name = (
                    row.get("company_name")
                    or row.get("bookmaker")
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
                    VALUES (?, ?, ?, ?, ?, ?)

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
                        str(match["schedule_id"]),

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

def get_odds_by_match(schedule_id):

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
        dict(zip(columns, row))
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
          ON m.schedule_id = o.schedule_id
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
        dict(zip(columns, row))
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
