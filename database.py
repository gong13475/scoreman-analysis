import os
import sqlite3
import threading


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
# Turso 연결
# =========================================================

def _get_turso_connection():

    if not TURSO_DATABASE_URL:
        return None

    if not TURSO_AUTH_TOKEN:
        return None

    try:

        import libsql

        conn = libsql.connect(
            database=TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN
        )

        return conn

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

    return conn


# =========================================================
# 결과 변환
# =========================================================

def _fetch_rows(cursor):

    rows = cursor.fetchall()

    columns = []

    if cursor.description:

        columns = [
            column[0]
            for column in cursor.description
        ]

    result = []

    for row in rows:

        if isinstance(row, dict):

            result.append(row)
            continue

        try:

            result.append(
                dict(row)
            )

        except Exception:

            result.append(
                {
                    columns[i]:
                    row[i]

                    for i in range(
                        len(columns)
                    )
                }
            )

    return result


# =========================================================
# SQL 실행
# =========================================================

def _execute(
    sql,
    params=(),
    fetch=False
):

    with _DB_LOCK:

        conn = _get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                sql,
                params
            )

            if fetch:

                result = _fetch_rows(
                    cursor
                )

            else:

                result = None

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
# 경기 + 배당 원자적 저장
# =========================================================

def save_match_with_odds(
    match,
    odds_list
):

    with _DB_LOCK:

        conn = _get_connection()

        try:

            cursor = conn.cursor()

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

        except Exception:

            conn.rollback()
            raise

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

        (
            str(schedule_id),
        ),

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
    )

    if not rows:
        return 0

    return int(
        rows[0].get("cnt", 0)
    )


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
# app.py 호환용
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

            "bookmaker":
                row.get(
                    "bookmaker",
                    ""
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
        SELECT COUNT(*) AS cnt
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

    return int(
        rows[0].get("cnt", 0)
    )


# =========================================================
# 전체 배당 수
# =========================================================

def get_odds_count():

    rows = _execute(
        """
        SELECT COUNT(*) AS cnt
        FROM odds
        """,

        fetch=True
    )

    if not rows:
        return 0

    return int(
        rows[0].get("cnt", 0)
    )


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
    ]


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
        GROUP BY bookmaker
        ORDER BY cnt DESC
        """,

        fetch=True
    ) or []

    return {
        row.get("bookmaker", ""):
        int(row.get("cnt", 0))

        for row in rows
    }


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
            )
    }


# =========================================================
# DB 연결상태
# =========================================================

def is_turso():

    return bool(
        TURSO_DATABASE_URL
        and TURSO_AUTH_TOKEN
        and _get_turso_connection()
        is not None
    )


# =========================================================
# 저장용량
# =========================================================

def get_storage_usage():

    try:

        if is_turso():

            # Turso 원격 DB의 실제 파일 크기는
            # 이 방식으로 직접 얻지 못하므로
            # 현재 저장 행을 기준으로 표시

            matches = get_match_count()
            odds = get_odds_count()

            estimated_bytes = (
                matches * 500
                + odds * 200
            )

            size_mb = (
                estimated_bytes
                / 1024
                / 1024
            )

        else:

            if os.path.exists(
                LOCAL_DB_PATH
            ):

                size_mb = (
                    os.path.getsize(
                        LOCAL_DB_PATH
                    )
                    / 1024
                    / 1024
                )

            else:

                size_mb = 0

        return {

            "success":
                True,

            "size_mb":
                size_mb,

            "size_gb":
                size_mb / 1024,

            "message":
                ""
        }

    except Exception as e:

        return {

            "success":
                False,

            "size_mb":
                0,

            "size_gb":
                0,

            "message":
                str(e)
        }


# =========================================================
# 초기화
# =========================================================

init_database()
