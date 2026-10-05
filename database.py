import os
import sqlite3
import threading
import urllib.request
import urllib.parse
import json
from typing import Any


# =========================================================
# 환경설정
# =========================================================

LOCAL_DB_PATH = os.getenv(
    "LOCAL_DB_PATH",
    "scoreman.db"
)

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
# Streamlit Secrets 보조
# =========================================================

def _load_secrets():

    global TURSO_DATABASE_URL
    global TURSO_AUTH_TOKEN

    if TURSO_DATABASE_URL and TURSO_AUTH_TOKEN:
        return

    try:

        import streamlit as st

        url = st.secrets.get(
            "TURSO_DATABASE_URL",
            ""
        )

        token = st.secrets.get(
            "TURSO_AUTH_TOKEN",
            ""
        )

        if url:
            TURSO_DATABASE_URL = str(url).strip()

        if token:
            TURSO_AUTH_TOKEN = str(token).strip()

    except Exception:
        pass


_load_secrets()


# =========================================================
# Turso URL 변환
# =========================================================

def _turso_http_url():

    if not TURSO_DATABASE_URL:
        return ""

    url = TURSO_DATABASE_URL.strip()

    if url.startswith("libsql://"):

        return (
            "https://"
            + url[len("libsql://"):]
        )

    if url.startswith("https://"):
        return url

    if url.startswith("http://"):
        return url

    return ""


# =========================================================
# Turso 연결 여부
# =========================================================

def is_turso_configured():

    _load_secrets()

    return bool(
        TURSO_DATABASE_URL
        and TURSO_AUTH_TOKEN
        and _turso_http_url()
    )


# =========================================================
# Turso HTTP SQL
# =========================================================

def _turso_execute(
    sql,
    params=(),
    fetch=False
):

    url = _turso_http_url()

    if not url:
        raise RuntimeError(
            "Turso URL이 없습니다."
        )

    payload = {

        "requests": [

            {
                "type": "execute",

                "stmt": {

                    "sql": sql,

                    "args": [
                        _turso_value(x)
                        for x in params
                    ]
                }
            },

            {
                "type": "close"
            }
        ]
    }

    body = json.dumps(
        payload
    ).encode("utf-8")

    request = urllib.request.Request(

        url,

        data=body,

        method="POST",

        headers={
            "Content-Type":
                "application/json",

            "Authorization":
                "Bearer "
                + TURSO_AUTH_TOKEN
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        raw = response.read()

    data = json.loads(
        raw.decode("utf-8")
    )

    if "error" in data:

        raise RuntimeError(
            str(data["error"])
        )

    if not fetch:
        return None

    results = data.get(
        "results",
        []
    )

    if not results:
        return []

    result = results[0]

    response_data = result.get(
        "response",
        {}
    )

    cols = response_data.get(
        "cols",
        []
    )

    rows = response_data.get(
        "rows",
        []
    )

    column_names = []

    for col in cols:

        if isinstance(col, dict):

            column_names.append(
                col.get(
                    "name",
                    ""
                )
            )

        else:

            column_names.append(
                str(col)
            )

    output = []

    for row in rows:

        values = []

        for cell in row:

            if isinstance(cell, dict):

                values.append(
                    cell.get(
                        "value"
                    )
                )

            else:

                values.append(cell)

        output.append(
            dict(
                zip(
                    column_names,
                    values
                )
            )
        )

    return output


# =========================================================
# Turso 값
# =========================================================

def _turso_value(value):

    if value is None:

        return {
            "type": "null"
        }

    if isinstance(
        value,
        bool
    ):

        return {
            "type": "integer",
            "value": "1" if value else "0"
        }

    if isinstance(
        value,
        int
    ):

        return {
            "type": "integer",
            "value": str(value)
        }

    if isinstance(
        value,
        float
    ):

        return {
            "type": "float",
            "value": str(value)
        }

    return {
        "type": "text",
        "value": str(value)
    }


# =========================================================
# SQLite
# =========================================================

def _get_local_connection():

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
    fallback=True
):

    with _DB_LOCK:

        # -------------------------------------------------
        # Turso 우선
        # -------------------------------------------------

        if is_turso_configured():

            try:

                return _turso_execute(
                    sql,
                    params,
                    fetch
                )

            except Exception:
                pass

        # -------------------------------------------------
        # SQLite fallback
        # -------------------------------------------------

        if not fallback:

            raise RuntimeError(
                "Turso 실행 실패"
            )

        conn = _get_local_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                sql,
                params
            )

            if fetch:

                rows = cursor.fetchall()

                result = [
                    dict(row)
                    for row in rows
                ]

            else:

                result = None

            conn.commit()

            return result

        finally:

            conn.close()


# =========================================================
# 초기화
# =========================================================

def init_database():

    tables = [

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
        """,

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
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_odds_schedule
        ON odds(schedule_id)
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_odds_bookmaker
        ON odds(bookmaker)
        """
    ]

    for sql in tables:

        _execute(
            sql,
            fallback=True
        )

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
            str(
                match.get(
                    "schedule_id"
                )
            ),

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


# =========================================================
# 경기 + 배당 저장
# =========================================================

def save_match_with_odds(
    match,
    odds_list
):

    save_match(
        match
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
        """

        _execute(
            sql,
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

    return saved


# =========================================================
# 경기
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

    return int(
        rows[0].get(
            "cnt",
            0
        ) or 0
    )


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
# app 호환용
# =========================================================

def get_match_final_odds(
    schedule_id
):

    rows = get_odds_by_match(
        schedule_id
    )

    return [

        {
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
        }

        for row in rows
    ]


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

    return int(
        rows[0].get(
            "cnt",
            0
        ) or 0
    )


# =========================================================
# 경기별 배당 수
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
    ) or []

    if not rows:
        return 0

    return int(
        rows[0].get(
            "cnt",
            0
        ) or 0
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
        row.get(
            "bookmaker",
            ""
        )

        for row in rows

        if row.get(
            "bookmaker",
            ""
        )
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

    return {

        row.get(
            "bookmaker",
            ""
        ):

        int(
            row.get(
                "cnt",
                0
            ) or 0
        )

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
            ),

        "turso":
            is_turso_configured()
    }


# =========================================================
# DB 상태 상세
# =========================================================

def get_connection_status():

    if is_turso_configured():

        try:

            _turso_execute(
                "SELECT 1",
                (),
                True
            )

            return {

                "connected":
                    True,

                "mode":
                    "Turso",

                "message":
                    "Turso DB 연결 정상"
            }

        except Exception as e:

            return {

                "connected":
                    False,

                "mode":
                    "SQLite",

                "message":
                    "Turso 연결 실패: "
                    + str(e)
            }

    return {

        "connected":
            True,

        "mode":
            "SQLite",

        "message":
            "로컬 SQLite 모드"
    }


# =========================================================
# 저장용량
# =========================================================

def get_storage_usage():

    try:

        if is_turso_configured():

            # Turso에서는 로컬 DB 파일 크기를
            # 실제 저장용량으로 사용하지 않는다.

            return {

                "success":
                    True,

                "size_mb":
                    0,

                "size_gb":
                    0,

                "message":
                    "Turso 저장용량은 Turso 대시보드에서 확인하세요."
            }

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

            "size_mb":
                size_mb,

            "size_gb":
                size_gb,

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
# 시작
# =========================================================

init_database()
