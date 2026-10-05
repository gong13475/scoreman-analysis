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
# SQLite 연결
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
# DB 연결
# =========================================================

def _get_connection():

    conn = _get_turso_connection()

    if conn is not None:
        return conn

    return _get_local_connection()


# =========================================================
# Turso 연결 여부
# =========================================================

def is_turso_connected():

    conn = _get_turso_connection()

    if conn is None:
        return False

    try:

        cursor = conn.cursor()

        cursor.execute(
            "SELECT 1"
        )

        cursor.fetchone()

        try:
            conn.close()
        except Exception:
            pass

        return True

    except Exception:

        try:
            conn.close()
        except Exception:
            pass

        return False


# =========================================================
# 테이블 컬럼 확인
# =========================================================

def _get_columns(
    conn,
    table_name
):

    columns = set()

    try:

        cursor = conn.cursor()

        cursor.execute(
            f"PRAGMA table_info({table_name})"
        )

        rows = cursor.fetchall()

        for row in rows:

            try:

                # sqlite3.Row
                if isinstance(
                    row,
                    sqlite3.Row
                ):

                    name = row["name"]

                elif isinstance(
                    row,
                    dict
                ):

                    name = row.get(
                        "name"
                    )

                else:

                    # PRAGMA table_info
                    # cid, name, type...
                    name = row[1]

                if name:

                    columns.add(
                        str(name)
                    )

            except Exception:
                continue

    except Exception as e:

        print(
            "[컬럼 확인 실패]",
            table_name,
            repr(e)
        )

    return columns


# =========================================================
# 컬럼 자동 추가
# =========================================================

def _ensure_column(
    conn,
    table_name,
    column_name,
    column_type
):

    columns = _get_columns(
        conn,
        table_name
    )

    if column_name in columns:
        return False

    try:

        cursor = conn.cursor()

        cursor.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name}
            {column_type}
            """
        )

        try:
            conn.commit()
        except Exception:
            pass

        print(
            f"[DB 마이그레이션] "
            f"{table_name}.{column_name} 추가"
        )

        return True

    except Exception as e:

        print(
            f"[DB 마이그레이션 실패] "
            f"{table_name}.{column_name}:",
            repr(e)
        )

        return False


# =========================================================
# DB 마이그레이션
# =========================================================

def _migrate_database(
    conn
):

    # -----------------------------------------------------
    # matches
    # -----------------------------------------------------

    match_columns = _get_columns(
        conn,
        "matches"
    )

    if match_columns:

        _ensure_column(
            conn,
            "matches",
            "match_date",
            "TEXT"
        )

        _ensure_column(
            conn,
            "matches",
            "home_team",
            "TEXT"
        )

        _ensure_column(
            conn,
            "matches",
            "away_team",
            "TEXT"
        )

        _ensure_column(
            conn,
            "matches",
            "home_score",
            "INTEGER"
        )

        _ensure_column(
            conn,
            "matches",
            "away_score",
            "INTEGER"
        )

        _ensure_column(
            conn,
            "matches",
            "result",
            "TEXT"
        )

        _ensure_column(
            conn,
            "matches",
            "source",
            "TEXT"
        )

        _ensure_column(
            conn,
            "matches",
            "created_at",
            "TEXT"
        )

        _ensure_column(
            conn,
            "matches",
            "updated_at",
            "TEXT"
        )

    # -----------------------------------------------------
    # odds
    # -----------------------------------------------------

    odds_columns = _get_columns(
        conn,
        "odds"
    )

    if odds_columns:

        # 핵심 오류 수정
        _ensure_column(
            conn,
            "odds",
            "company_id",
            "TEXT"
        )

        _ensure_column(
            conn,
            "odds",
            "bookmaker",
            "TEXT"
        )

        _ensure_column(
            conn,
            "odds",
            "home_odds",
            "REAL"
        )

        _ensure_column(
            conn,
            "odds",
            "draw_odds",
            "REAL"
        )

        _ensure_column(
            conn,
            "odds",
            "away_odds",
            "REAL"
        )

        _ensure_column(
            conn,
            "odds",
            "created_at",
            "TEXT"
        )

        # 예전 코드에서 사용했을 가능성이 있는
        # final_* 컬럼도 유지
        _ensure_column(
            conn,
            "odds",
            "final_home",
            "REAL"
        )

        _ensure_column(
            conn,
            "odds",
            "final_draw",
            "REAL"
        )

        _ensure_column(
            conn,
            "odds",
            "final_away",
            "REAL"
        )

    # -----------------------------------------------------
    # collection_state
    # -----------------------------------------------------

    state_columns = _get_columns(
        conn,
        "collection_state"
    )

    if state_columns:

        _ensure_column(
            conn,
            "collection_state",
            "start_id",
            "INTEGER"
        )

        _ensure_column(
            conn,
            "collection_state",
            "end_id",
            "INTEGER"
        )

        _ensure_column(
            conn,
            "collection_state",
            "last_completed_id",
            "INTEGER"
        )

        _ensure_column(
            conn,
            "collection_state",
            "current",
            "INTEGER"
        )

        _ensure_column(
            conn,
            "collection_state",
            "total",
            "INTEGER"
        )

        _ensure_column(
            conn,
            "collection_state",
            "success",
            "INTEGER"
        )

        _ensure_column(
            conn,
            "collection_state",
            "exists_count",
            "INTEGER"
        )

        _ensure_column(
            conn,
            "collection_state",
            "failed",
            "INTEGER"
        )

        _ensure_column(
            conn,
            "collection_state",
            "odds",
            "INTEGER"
        )

        _ensure_column(
            conn,
            "collection_state",
            "running",
            "INTEGER"
        )

        _ensure_column(
            conn,
            "collection_state",
            "stopped",
            "INTEGER"
        )

        _ensure_column(
            conn,
            "collection_state",
            "finished",
            "INTEGER"
        )

        _ensure_column(
            conn,
            "collection_state",
            "updated_at",
            "TEXT"
        )

    try:
        conn.commit()
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

                    created_at TEXT
                        DEFAULT CURRENT_TIMESTAMP,

                    updated_at TEXT
                        DEFAULT CURRENT_TIMESTAMP
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

                    final_home REAL,

                    final_draw REAL,

                    final_away REAL,

                    created_at TEXT
                        DEFAULT CURRENT_TIMESTAMP,

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

            try:
                conn.commit()
            except Exception:
                pass

            # =================================================
            # 기존 DB 자동 마이그레이션
            # =================================================

            _migrate_database(
                conn
            )

            # =================================================
            # 인덱스
            # =================================================

            try:

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
                    idx_odds_company
                    ON odds(company_id)
                    """
                )

                conn.commit()

            except Exception as e:

                print(
                    "[인덱스 생성 오류]",
                    repr(e)
                )

        finally:

            try:
                conn.close()
            except Exception:
                pass

    return True


# =========================================================
# 일반 SQL 실행
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
# 경기 저장
# =========================================================

def save_match(
    match
):

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

        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?,
            CURRENT_TIMESTAMP
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
                excluded.source,

            updated_at =
                CURRENT_TIMESTAMP
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

            # 혹시 기존 DB라면 여기서도 마이그레이션
            _migrate_database(
                conn
            )

            cursor = conn.cursor()

            schedule_id = str(
                match.get(
                    "schedule_id",
                    ""
                )
            )

            # -------------------------------------------------
            # 경기 저장
            # -------------------------------------------------

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

                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    CURRENT_TIMESTAMP
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

            saved = 0

            # -------------------------------------------------
            # 배당 저장
            # -------------------------------------------------

            for odds in (
                odds_list or []
            ):

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

                # 숫자/문자 모두 안전하게 저장
                final_home = odds.get(
                    "final_home",
                    odds.get(
                        "home_odds"
                    )
                )

                final_draw = odds.get(
                    "final_draw",
                    odds.get(
                        "draw_odds"
                    )
                )

                final_away = odds.get(
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
                        away_odds,

                        final_home,
                        final_draw,
                        final_away

                    )

                    VALUES (
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?
                    )

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
                            excluded.away_odds,

                        final_home =
                            excluded.final_home,

                        final_draw =
                            excluded.final_draw,

                        final_away =
                            excluded.final_away
                    """,
                    (

                        schedule_id,

                        bookmaker,

                        company_id,

                        final_home,

                        final_draw,

                        final_away,

                        final_home,

                        final_draw,

                        final_away
                    )
                )

                saved += 1

            conn.commit()

            print(
                f"[저장 완료] "
                f"ID={schedule_id} "
                f"{match.get('home_team', '')} "
                f"vs "
                f"{match.get('away_team', '')} "
                f"/ 결과={match.get('result', '')} "
                f"/ 최종배당={saved}개"
            )

            return saved

        except Exception as e:

            try:
                conn.rollback()
            except Exception:
                pass

            raise RuntimeError(
                f"SQLite error: {e}"
            ) from e

        finally:

            try:
                conn.close()
            except Exception:
                pass


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
    ) or []

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
        ) or 0
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
            away_odds,

            final_home,
            final_draw,
            final_away

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
            away_odds,

            final_home,
            final_draw,
            final_away

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
# 기존 app.py 호환
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

            "company_id":
                row.get(
                    "company_id",
                    ""
                ),

            "final_home":
                row.get(
                    "final_home",
                    row.get(
                        "home_odds"
                    )
                ),

            "final_draw":
                row.get(
                    "final_draw",
                    row.get(
                        "draw_odds"
                    )
                ),

            "final_away":
                row.get(
                    "final_away",
                    row.get(
                        "away_odds"
                    )
                )
        })

    return result


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
            "bookmaker"
        )
    ]


# =========================================================
# 업체별 경기 수
# =========================================================

def get_company_counts():

    rows = _execute(
        """
        SELECT

            bookmaker,
            COUNT(DISTINCT schedule_id) AS cnt

        FROM odds

        WHERE bookmaker IS NOT NULL
          AND bookmaker != ''

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

            matches = get_match_count()

            odds = get_odds_count()

            # Turso 화면에서 정확한 물리 용량을
            # 이 방식으로 직접 가져오는 것이 아니므로
            # 앱 내부에서는 논리 데이터 추정값 표시

            estimated_bytes = (
                matches * 512
                +
                odds * 512
            )

            size_mb = (
                estimated_bytes
                /
                1024
                /
                1024
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

            size_bytes = (
                os.path.getsize(
                    LOCAL_DB_PATH
                )
            )

        else:

            size_bytes = 0


        size_mb = (
            size_bytes
            /
            1024
            /
            1024
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


    data = dict(
        state
    )


    data.update(
        kwargs
    )


    def val(
        name,
        default=None
    ):

        return data.get(
            name,
            default
        )


    _execute(
        """
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

            1,

            ?, ?,

            ?,

            ?, ?, ?, ?, ?, ?,

            ?, ?, ?,

            CURRENT_TIMESTAMP
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
        """,

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


    def integer(
        name,
        default=0
    ):

        value = row.get(
            name,
            default
        )

        try:

            return int(
                value or 0
            )

        except Exception:

            return default


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
            integer(
                "current"
            ),

        "total":
            integer(
                "total"
            ),

        "success":
            integer(
                "success"
            ),

        "exists":
            integer(
                "exists_count"
            ),

        "exists_count":
            integer(
                "exists_count"
            ),

        "failed":
            integer(
                "failed"
            ),

        "odds":
            integer(
                "odds"
            ),

        "running":
            bool(
                integer(
                    "running"
                )
            ),

        "stopped":
            bool(
                integer(
                    "stopped"
                )
            ),

        "finished":
            bool(
                integer(
                    "finished"
                )
            )
    }


# =========================================================
# DB 상태 초기화
# =========================================================

def reset_collection_state():

    _execute(
        """
        DELETE FROM collection_state
        WHERE id = 1
        """
    )

    return True


# =========================================================
# 시작 시 DB 자동 초기화
# =========================================================

init_database()
