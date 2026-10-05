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
        import libsql_experimental as libsql
    except ImportError:
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
# Row 안전 변환
# =========================================================

def _row_to_dict(row, description=None):

    if row is None:
        return None

    if isinstance(row, dict):
        return dict(row)

    try:
        return dict(row)
    except Exception:
        pass

    if description:

        try:

            columns = [
                item[0]
                for item in description
            ]

            return dict(
                zip(columns, row)
            )

        except Exception:
            pass

    try:

        return {
            str(i): value
            for i, value in enumerate(row)
        }

    except Exception:

        return {}


# =========================================================
# 여러 Row 안전 변환
# =========================================================

def _rows_to_dicts(rows, description=None):

    result = []

    for row in rows or []:

        result.append(
            _row_to_dict(
                row,
                description
            )
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
                    getattr(
                        cursor,
                        "description",
                        None
                    )
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

                    created_at TEXT
                        DEFAULT CURRENT_TIMESTAMP,

                    updated_at TEXT
                        DEFAULT CURRENT_TIMESTAMP
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

                    created_at TEXT
                        DEFAULT CURRENT_TIMESTAMP,

                    UNIQUE (
                        schedule_id,
                        bookmaker
                    )
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

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_matches_date
                ON matches(match_date)
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

            match.get("match_date"),

            match.get("home_team"),

            match.get("away_team"),

            match.get("home_score"),

            match.get("away_score"),

            match.get("result"),

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

    with _DB_LOCK:

        conn = _get_connection()

        try:

            cursor = conn.cursor()

            # -------------------------------------------------
            # 경기
            # -------------------------------------------------

            schedule_id = str(
                match.get(
                    "schedule_id",
                    ""
                )
            ).strip()

            if not schedule_id:
                return 0

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

                    match.get("match_date"),

                    match.get("home_team"),

                    match.get("away_team"),

                    match.get("home_score"),

                    match.get("away_score"),

                    match.get("result"),

                    match.get(
                        "source",
                        "scoreman"
                    )
                )
            )

            # -------------------------------------------------
            # 배당
            # -------------------------------------------------

            saved = 0

            for odds in odds_list or []:

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
                        schedule_id,

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
        SELECT
            schedule_id,
            match_date,
            home_team,
            away_team,
            home_score,
            away_score,
            result,
            source,
            created_at,
            updated_at
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
        SELECT
            schedule_id,
            match_date,
            home_team,
            away_team,
            home_score,
            away_score,
            result,
            source,
            created_at,
            updated_at
        FROM matches
        ORDER BY
            CASE
                WHEN schedule_id GLOB '[0-9]*'
                THEN CAST(schedule_id AS INTEGER)
                ELSE 0
            END DESC
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

    row = rows[0]

    # 정상적인 경우
    if "cnt" in row:
        return int(
            row["cnt"] or 0
        )

    # 혹시 드라이버가 컬럼명을
    # 이상하게 반환하는 경우
    values = list(
        row.values()
    )

    if values:
        try:
            return int(
                values[0] or 0
            )
        except Exception:
            pass

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

            CASE
                WHEN schedule_id GLOB '[0-9]*'
                THEN CAST(schedule_id AS INTEGER)
                ELSE 0
            END DESC,

            bookmaker
        """,
        fetch=True
    ) or []


# =========================================================
# 특정 경기 배당
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
        (
            str(schedule_id),
        ),
        fetch=True
    ) or []


# =========================================================
# app.py 호환용
# =========================================================

def get_match_final_odds(schedule_id):

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

            # 기존 컬럼
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
                ),

            # app.py에서 사용하는 이름
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

    row = rows[0]

    if "cnt" in row:
        try:
            return int(
                row["cnt"] or 0
            )
        except Exception:
            return 0

    return 0


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

    row = rows[0]

    if "cnt" in row:

        try:
            return int(
                row["cnt"] or 0
            )
        except Exception:
            return 0

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

        if not bookmaker:
            continue

        try:

            count = int(
                row.get(
                    "cnt",
                    0
                )
                or 0
            )

        except Exception:

            count = 0

        result[
            bookmaker
        ] = count

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
            )
    }


# =========================================================
# 저장용량
# =========================================================

def get_storage_usage():

    try:

        # ---------------------------------------------
        # 로컬 SQLite
        # ---------------------------------------------

        if not TURSO_DATABASE_URL:

            if os.path.exists(
                LOCAL_DB_PATH
            ):

                size_bytes = os.path.getsize(
                    LOCAL_DB_PATH
                )

            else:

                size_bytes = 0

        # ---------------------------------------------
        # Turso
        # ---------------------------------------------

        else:

            # Turso는 로컬 DB 파일이 아니므로
            # SQLite 파일 크기를 사용할 수 없음.
            #
            # 여기서는 테이블 수를 이용한
            # 논리적 표시값만 제공.
            rows = _execute(
                """
                SELECT COUNT(*) AS cnt
                FROM sqlite_master
                WHERE type='table'
                """,
                fetch=True
            )

            table_count = 0

            if rows:

                try:
                    table_count = int(
                        rows[0].get(
                            "cnt",
                            0
                        )
                        or 0
                    )
                except Exception:
                    table_count = 0

            size_bytes = (
                table_count
                * 1024
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
                "DB 정상"
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
# 시작 시 초기화
# =========================================================

init_database()
