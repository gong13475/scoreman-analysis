import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional


# =========================================================
# 환경설정
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
# Turso
# =========================================================

def _get_turso_connection():
    if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
        return None

    try:
        import libsql_experimental as libsql
    except Exception:
        return None

    try:
        return libsql.connect(
            TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN
        )
    except Exception:
        return None


def _using_turso():
    return bool(
        TURSO_DATABASE_URL
        and TURSO_AUTH_TOKEN
        and _get_turso_connection() is not None
    )


# =========================================================
# 연결
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
# SQL
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
            cur = conn.cursor()

            cur.execute("""
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

            cur.execute("""
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

            cur.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_odds_schedule
                ON odds(schedule_id)
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_odds_bookmaker
                ON odds(bookmaker)
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_match_result
                ON matches(result)
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS collection_state (
                    id INTEGER PRIMARY KEY CHECK(id = 1),
                    start_id INTEGER,
                    end_id INTEGER,
                    last_completed_id INTEGER,
                    current INTEGER DEFAULT 0,
                    total INTEGER DEFAULT 0,
                    running INTEGER DEFAULT 0,
                    stopped INTEGER DEFAULT 0,
                    selected_companies TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                INSERT OR IGNORE INTO collection_state (
                    id
                )
                VALUES (1)
            """)

            conn.commit()

        finally:
            conn.close()

    return True


# =========================================================
# 경기
# =========================================================

def save_match(match):
    _execute("""
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
    """, (
        str(match.get("schedule_id")),
        match.get("match_date"),
        match.get("home_team"),
        match.get("away_team"),
        match.get("home_score"),
        match.get("away_score"),
        match.get("result"),
        match.get("source", "scoreman")
    ))


# =========================================================
# 경기 + 배당
# =========================================================

def save_match_with_odds(
    match,
    odds_list
):
    with _DB_LOCK:
        conn = _get_connection()

        try:
            cur = conn.cursor()

            cur.execute("""
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
            """, (
                str(match.get("schedule_id")),
                match.get("match_date"),
                match.get("home_team"),
                match.get("away_team"),
                match.get("home_score"),
                match.get("away_score"),
                match.get("result"),
                match.get("source", "scoreman")
            ))

            saved = 0

            for odds in odds_list:
                bookmaker = str(
                    odds.get("company_name", "")
                ).strip()

                if not bookmaker:
                    continue

                cur.execute("""
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
                """, (
                    str(match.get("schedule_id")),
                    bookmaker,
                    odds.get("company_id", ""),
                    odds.get("final_home"),
                    odds.get("final_draw"),
                    odds.get("final_away")
                ))

                saved += 1

            conn.commit()

            return saved

        finally:
            conn.close()


# =========================================================
# 경기 조회
# =========================================================

def get_match(schedule_id):
    rows = _execute("""
        SELECT *
        FROM matches
        WHERE schedule_id = ?
        LIMIT 1
    """, (str(schedule_id),), True)

    return rows[0] if rows else None


def get_all_matches():
    return _execute("""
        SELECT *
        FROM matches
        ORDER BY
            CAST(schedule_id AS INTEGER) DESC
    """, fetch=True) or []


def get_match_count():
    rows = _execute("""
        SELECT COUNT(*) AS cnt
        FROM matches
    """, fetch=True) or []

    return int(rows[0]["cnt"]) if rows else 0


# =========================================================
# 배당
# =========================================================

def get_all_odds():
    return _execute("""
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
    """, fetch=True) or []


def get_odds_by_match(schedule_id):
    return _execute("""
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
    """, (str(schedule_id),), True) or []


def get_match_final_odds(schedule_id):
    return get_odds_by_match(schedule_id)


def get_odds_count():
    rows = _execute("""
        SELECT COUNT(*) AS cnt
        FROM odds
    """, fetch=True) or []

    return int(rows[0]["cnt"]) if rows else 0


def get_odds_count_by_match(schedule_id):
    rows = _execute("""
        SELECT COUNT(*) AS cnt
        FROM odds
        WHERE schedule_id = ?
    """, (str(schedule_id),), True) or []

    return int(rows[0]["cnt"]) if rows else 0


# =========================================================
# 업체
# =========================================================

def get_company_names():
    rows = _execute("""
        SELECT DISTINCT bookmaker
        FROM odds
        WHERE bookmaker IS NOT NULL
        AND bookmaker != ''
        ORDER BY bookmaker
    """, fetch=True) or []

    return [
        row["bookmaker"]
        for row in rows
    ]


def get_company_counts():
    rows = _execute("""
        SELECT
            bookmaker,
            COUNT(*) AS cnt
        FROM odds
        GROUP BY bookmaker
        ORDER BY cnt DESC
    """, fetch=True) or []

    return {
        row["bookmaker"]: int(row["cnt"])
        for row in rows
    }


# =========================================================
# 배당 검색
# =========================================================

def search_odds(
    home_odds,
    draw_odds,
    away_odds,
    companies=None,
    tolerance=0.001
):
    params = [
        float(home_odds),
        float(draw_odds),
        float(away_odds),
        float(tolerance)
    ]

    sql = """
        SELECT
            m.schedule_id,
            m.match_date,
            m.home_team,
            m.away_team,
            m.home_score,
            m.away_score,
            m.result,
            o.bookmaker,
            o.home_odds,
            o.draw_odds,
            o.away_odds
        FROM odds o
        JOIN matches m
            ON m.schedule_id = o.schedule_id
        WHERE
            ABS(o.home_odds - ?) <= ?
            AND ABS(o.draw_odds - ?) <= ?
            AND ABS(o.away_odds - ?) <= ?
    """

    # tolerance를 각각 사용
    params = [
        float(home_odds),
        float(tolerance),
        float(draw_odds),
        float(tolerance),
        float(away_odds),
        float(tolerance)
    ]

    if companies:
        placeholders = ",".join(
            ["?"] * len(companies)
        )

        sql += f"""
            AND LOWER(o.bookmaker)
            IN ({placeholders})
        """

        params.extend([
            str(x).strip().lower()
            for x in companies
        ])

    sql += """
        ORDER BY
            CAST(m.schedule_id AS INTEGER) DESC
    """

    return _execute(
        sql,
        params,
        fetch=True
    ) or []


# =========================================================
# DB 상태
# =========================================================

def get_database_status():
    return {
        "matches": get_match_count(),
        "odds": get_odds_count(),
        "bookmakers": len(
            get_company_names()
        ),
        "turso": bool(
            _get_turso_connection() is not None
        )
    }


# =========================================================
# 저장용량
# =========================================================

def get_storage_usage():
    try:
        if _get_turso_connection() is None:
            if os.path.exists(LOCAL_DB_PATH):
                size_bytes = os.path.getsize(
                    LOCAL_DB_PATH
                )
            else:
                size_bytes = 0

            approximate = False

        else:
            # Turso는 로컬 DB 파일 크기를
            # 실제 서버 저장량으로 볼 수 없으므로
            # 논리적 데이터량을 별도 표시
            counts = (
                get_match_count()
                + get_odds_count()
            )

            size_bytes = counts * 512
            approximate = True

        mb = size_bytes / 1024 / 1024
        gb = mb / 1024

        return {
            "success": True,
            "size_mb": mb,
            "size_gb": gb,
            "approximate": approximate,
            "message": ""
        }

    except Exception as e:
        return {
            "success": False,
            "size_mb": 0,
            "size_gb": 0,
            "approximate": False,
            "message": str(e)
        }


# =========================================================
# 수집 상태 저장
# =========================================================

def save_collection_state(
    start_id=None,
    end_id=None,
    last_completed_id=None,
    current=0,
    total=0,
    running=False,
    stopped=False,
    selected_companies=None
):
    import json

    if selected_companies is None:
        selected_companies = []

    _execute("""
        UPDATE collection_state
        SET
            start_id = ?,
            end_id = ?,
            last_completed_id = ?,
            current = ?,
            total = ?,
            running = ?,
            stopped = ?,
            selected_companies = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    """, (
        start_id,
        end_id,
        last_completed_id,
        current,
        total,
        1 if running else 0,
        1 if stopped else 0,
        json.dumps(
            selected_companies,
            ensure_ascii=False
        )
    ))


def get_collection_state():
    import json

    rows = _execute("""
        SELECT *
        FROM collection_state
        WHERE id = 1
        LIMIT 1
    """, fetch=True) or []

    if not rows:
        return {
            "start_id": None,
            "end_id": None,
            "last_completed_id": None,
            "current": 0,
            "total": 0,
            "running": False,
            "stopped": False,
            "selected_companies": []
        }

    row = rows[0]

    try:
        companies = json.loads(
            row.get(
                "selected_companies"
            ) or "[]"
        )
    except Exception:
        companies = []

    return {
        "start_id":
            row.get("start_id"),

        "end_id":
            row.get("end_id"),

        "last_completed_id":
            row.get("last_completed_id"),

        "current":
            int(row.get("current") or 0),

        "total":
            int(row.get("total") or 0),

        "running":
            bool(row.get("running")),

        "stopped":
            bool(row.get("stopped")),

        "selected_companies":
            companies
    }


def clear_collection_state():
    save_collection_state(
        start_id=None,
        end_id=None,
        last_completed_id=None,
        current=0,
        total=0,
        running=False,
        stopped=False,
        selected_companies=[]
    )


# =========================================================
# 초기화
# =========================================================

init_database()
