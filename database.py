import os
import sqlite3
import threading
from typing import Any


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

        import turso_serverless

        conn = turso_serverless.connect(
            TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN
        )

        return conn

    except Exception as e:

        print(
            "[Turso 연결 실패]",
            repr(e)
        )

        return None


# =========================================================
# 로컬 SQLite
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
# 연결
# =========================================================

def _get_connection():

    conn = _get_turso_connection()

    if conn is not None:
        return conn

    return _get_local_connection()


# =========================================================
# Turso 여부
# =========================================================

def is_turso_connected():

    conn = _get_turso_connection()

    if conn is None:
        return False

    try:

        conn.execute(
            "SELECT 1"
        ).fetchone()

        conn.close()

        return True

    except Exception:

        try:
            conn.close()
        except Exception:
            pass

        return False


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

            result = None

            if fetch:

                rows = cursor.fetchall()

                result = []

                description = getattr(
                    cursor,
                    "description",
                    None
                )

                columns = []

                if description:

                    columns = [
                        col[0]
                        for col in description
                    ]

                for row in rows:

                    if isinstance(
                        row,
                        sqlite3.Row
                    ):

                        result.append(
                            dict(row)
                        )

                    elif isinstance(
                        row,
                        dict
                    ):

                        result.append(
                            dict(row)
                        )

                    else:

                        result.append(
                            dict(
                                zip(
                                    columns,
                                    row
                                )
                            )
                        )

            try:
                conn.commit()
            except Exception:
                pass

            return result

        finally:

            try:
                conn.close()
            except Exception:
                pass


# =========================================================
# DB 초기화
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

                    UNIQUE (
                        schedule_id,
                        bookmaker
                    )
                )
                """
            )

            # -------------------------------------------------
            # 수집 상태
            # -------------------------------------------------

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS collection_state (

                    id INTEGER PRIMARY KEY,

                    start_id INTEGER,

                    end_id INTEGER,

                    last_completed_id INTEGER,

                    current INTEGER DEFAULT 0,

                    total INTEGER DEFAULT 0,

                    success INTEGER DEFAULT 0,

                    exists_count INTEGER DEFAULT 0,

                    failed INTEGER DEFAULT 0,

                    odds INTEGER DEFAULT 0,

                    running INTEGER DEFAULT 0,

                    stopped INTEGER DEFAULT 0,

                    finished INTEGER DEFAULT 0,

                    updated_at TEXT
                        DEFAULT CURRENT_TIMESTAMP
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

            try:
                conn.commit()
            except Exception:
                pass

        finally:

            try:
                conn.close()
            except Exception:
                pass

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
            str(
                match.get(
                    "schedule_id",
                    ""
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
                    str(
                        match.get(
                            "schedule_id",
                            ""
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
                                "schedule_id",
                                ""
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

            try:
                conn.close()
            except Exception:
                pass


# =========================================================
# 경기 1개
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
        )
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
# 앱 호환용
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
                ),

            "company_id":
                row.get(
                    "company_id",
                    ""
                )
        })

    return result


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
        )
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
    ) or []

    if not rows:
        return 0

    return int(
        rows[0].get(
            "cnt",
            0
        )
    )


# =========================================================
# 업체名称
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
            "bookmaker"
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
            )
        )

        for row in rows

        if row.get(
            "bookmaker"
        )
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
            is_turso_connected()
    }


# =========================================================
# 저장 용량
# =========================================================

def get_storage_usage():

    try:

        if is_turso_connected():

            # Turso 원격 DB의 정확한 물리 파일 크기는
            # 앱에서 직접 얻을 수 없으므로 논리 데이터량 표시

            matches = get_match_count()

            odds = get_odds_count()

            estimated_bytes = (
                matches * 512
                + odds * 256
            )

            size_mb = (
                estimated_bytes
                / 1024
                / 1024
            )

            return {

                "success":
                    True,

                "size_mb":
                    size_mb,

                "size_gb":
                    size_mb / 1024,

                "message":
                    "Turso 논리 데이터 추정량"
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

        return {

            "success":
                True,

            "size_mb":
                size_mb,

            "size_gb":
                size_mb / 1024,

            "message":
                "로컬 SQLite 파일 크기"
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
# 수집 상태 저장
# =========================================================

def save_collection_state(
    state=None,
    **kwargs
):

    if state is None:
        state = {}

    data = dict(state)
    data.update(kwargs)

    def val(name, default=None):

        return data.get(
            name,
            default
        )

    sql = """
        INSERT INTO collection_state (

            id,
            start_id,
            end_id,
            last_completed_id,
            current,
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

            running =
                excluded.running,

            stopped =
                excluded.stopped,

            finished =
                excluded.finished,

            updated_at =
                CURRENT_TIMESTAMP
    """

    _execute(
        sql,
        (

            val(
                "start_id"
            ),

            val(
                "end_id"
            ),

            val(
                "last_completed_id"
            ),

            val(
                "current",
                0
            ),

            val(
                "total",
                0
            ),

            val(
                "success",
                0
            ),

            val(
                "exists",
                val(
                    "exists_count",
                    0
                )
            ),

            val(
                "failed",
                0
            ),

            val(
                "odds",
                0
            ),

            1 if val(
                "running",
                False
            ) else 0,

            1 if val(
                "stopped",
                False
            ) else 0,

            1 if val(
                "finished",
                False
            ) else 0
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
    ) or []

    if not rows:
        return None

    row = rows[0]

    return {

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
                )
            ),

        "total":
            int(
                row.get(
                    "total",
                    0
                )
            ),

        "success":
            int(
                row.get(
                    "success",
                    0
                )
            ),

        "exists":
            int(
                row.get(
                    "exists_count",
                    0
                )
            ),

        "failed":
            int(
                row.get(
                    "failed",
                    0
                )
            ),

        "odds":
            int(
                row.get(
                    "odds",
                    0
                )
            ),

        "running":
            bool(
                row.get(
                    "running",
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

        "finished":
            bool(
                row.get(
                    "finished",
                    0
                )
            )
    }


# =========================================================
# 초기화
# =========================================================

init_database()
