# ============================================================
# database.py
# ⚽ Scoreman 영구 DB
# SQLite / Turso(libsql) 대응
# ============================================================

import os
import sqlite3
from pathlib import Path
from datetime import datetime

DB_FILE = Path(__file__).resolve().parent / "scoreman.db"

TURSO_DATABASE_URL = os.getenv(
    "TURSO_DATABASE_URL", ""
).strip()

TURSO_AUTH_TOKEN = os.getenv(
    "TURSO_AUTH_TOKEN", ""
).strip()


# ============================================================
# 연결
# ============================================================

def get_connection():

    # --------------------------------------------------------
    # Turso
    # --------------------------------------------------------
    if TURSO_DATABASE_URL and TURSO_AUTH_TOKEN:

        try:

            import libsql

            return libsql.connect(
                TURSO_DATABASE_URL,
                auth_token=TURSO_AUTH_TOKEN,
            )

        except Exception as e:

            print(
                f"[Turso 연결 실패] {e}"
            )

    # --------------------------------------------------------
    # Local SQLite
    # --------------------------------------------------------

    conn = sqlite3.connect(
        str(DB_FILE),
        check_same_thread=False,
        timeout=30,
    )

    conn.row_factory = sqlite3.Row

    try:

        conn.execute(
            "PRAGMA journal_mode=WAL"
        )

        conn.execute(
            "PRAGMA synchronous=NORMAL"
        )

        conn.execute(
            "PRAGMA busy_timeout=30000"
        )

    except Exception:
        pass

    return conn


# ============================================================
# 커밋
# ============================================================

def _commit(conn):

    try:
        conn.commit()

    except Exception:
        pass


# ============================================================
# 초기화
# ============================================================

def init_database():

    conn = get_connection()

    try:

        # ----------------------------------------------------
        # 경기
        # ----------------------------------------------------

        conn.execute(
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


        # ----------------------------------------------------
        # 배당
        # ----------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS odds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id TEXT NOT NULL,
                company_id TEXT,
                company_name TEXT,
                bookmaker TEXT NOT NULL,
                final_home REAL,
                final_draw REAL,
                final_away REAL,
                UNIQUE(schedule_id, bookmaker)
            )
            """
        )


        # ----------------------------------------------------
        # 수집 상태
        # ----------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS collection_state (
                id TEXT PRIMARY KEY,
                status TEXT,
                updated_at TEXT
            )
            """
        )


        _commit(conn)

        ensure_columns(conn)

        _commit(conn)

    finally:

        try:
            conn.close()

        except Exception:
            pass


# ============================================================
# 기존 DB 컬럼 보정
# ============================================================

def ensure_columns(conn):

    # --------------------------------------------------------
    # odds
    # --------------------------------------------------------

    try:

        rows = conn.execute(
            "PRAGMA table_info(odds)"
        ).fetchall()

        columns = set()

        for row in rows:

            try:
                columns.add(
                    row["name"]
                )

            except Exception:
                columns.add(
                    row[1]
                )


        if "company_id" not in columns:

            conn.execute(
                """
                ALTER TABLE odds
                ADD COLUMN company_id TEXT
                """
            )


        if "company_name" not in columns:

            conn.execute(
                """
                ALTER TABLE odds
                ADD COLUMN company_name TEXT
                """
            )


        if "bookmaker" not in columns:

            conn.execute(
                """
                ALTER TABLE odds
                ADD COLUMN bookmaker TEXT
                """
            )


        if "final_home" not in columns:

            conn.execute(
                """
                ALTER TABLE odds
                ADD COLUMN final_home REAL
                """
            )


        if "final_draw" not in columns:

            conn.execute(
                """
                ALTER TABLE odds
                ADD COLUMN final_draw REAL
                """
            )


        if "final_away" not in columns:

            conn.execute(
                """
                ALTER TABLE odds
                ADD COLUMN final_away REAL
                """
            )


        # ----------------------------------------------------
        # 기존 데이터 업체명 보정
        # ----------------------------------------------------

        conn.execute(
            """
            UPDATE odds
            SET bookmaker = company_name
            WHERE
                (bookmaker IS NULL OR bookmaker = '')
                AND company_name IS NOT NULL
                AND company_name != ''
            """
        )


    except Exception as e:

        print(
            f"[odds 컬럼 확인] {e}"
        )


    # --------------------------------------------------------
    # collection_state
    # --------------------------------------------------------

    try:

        rows = conn.execute(
            "PRAGMA table_info(collection_state)"
        ).fetchall()

        columns = set()

        for row in rows:

            try:
                columns.add(
                    row["name"]
                )

            except Exception:
                columns.add(
                    row[1]
                )


        if "status" not in columns:

            conn.execute(
                """
                ALTER TABLE collection_state
                ADD COLUMN status TEXT
                """
            )


        if "updated_at" not in columns:

            conn.execute(
                """
                ALTER TABLE collection_state
                ADD COLUMN updated_at TEXT
                """
            )


    except Exception as e:

        print(
            f"[collection_state 컬럼 확인] {e}"
        )


# ============================================================
# 경기 저장
# ============================================================

def save_match(
    schedule_id,
    match_date=None,
    home_team=None,
    away_team=None,
    home_score=None,
    away_score=None,
    result=None,
    source="scoreman",
):

    conn = get_connection()

    try:

        conn.execute(
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
                match_date = excluded.match_date,
                home_team = excluded.home_team,
                away_team = excluded.away_team,
                home_score = excluded.home_score,
                away_score = excluded.away_score,
                result = excluded.result,
                source = excluded.source
            """,
            (
                str(schedule_id),
                match_date,
                home_team,
                away_team,
                home_score,
                away_score,
                result,
                source,
            ),
        )

        _commit(conn)

        return True

    except Exception as e:

        try:
            conn.rollback()

        except Exception:
            pass

        print(
            f"[경기 저장 실패] "
            f"ID={schedule_id} "
            f"{type(e).__name__}: {e}"
        )

        return False

    finally:

        try:
            conn.close()

        except Exception:
            pass


# ============================================================
# 배당 저장
# ============================================================

def save_odds(
    schedule_id,
    company_id,
    company_name,
    final_home,
    final_draw,
    final_away,
):

    conn = get_connection()

    try:

        schedule_id = str(
            schedule_id
        )

        company_id = (
            str(company_id)
            if company_id is not None
            else ""
        )

        company_name = str(
            company_name or ""
        ).strip()

        bookmaker = company_name

        if not bookmaker:

            bookmaker = (
                f"CID_{company_id}"
            )


        # ----------------------------------------------------
        # 기존 업체 확인
        # ----------------------------------------------------

        row = conn.execute(
            """
            SELECT id
            FROM odds
            WHERE schedule_id = ?
              AND (
                    bookmaker = ?
                    OR company_name = ?
                  )
            LIMIT 1
            """,
            (
                schedule_id,
                bookmaker,
                company_name,
            ),
        ).fetchone()


        if row:

            try:
                row_id = row["id"]

            except Exception:
                row_id = row[0]


            conn.execute(
                """
                UPDATE odds
                SET
                    company_id = ?,
                    company_name = ?,
                    bookmaker = ?,
                    final_home = ?,
                    final_draw = ?,
                    final_away = ?
                WHERE id = ?
                """,
                (
                    company_id,
                    company_name,
                    bookmaker,
                    float(final_home),
                    float(final_draw),
                    float(final_away),
                    row_id,
                ),
            )


        else:

            conn.execute(
                """
                INSERT INTO odds (
                    schedule_id,
                    company_id,
                    company_name,
                    bookmaker,
                    final_home,
                    final_draw,
                    final_away
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    schedule_id,
                    company_id,
                    company_name,
                    bookmaker,
                    float(final_home),
                    float(final_draw),
                    float(final_away),
                ),
            )


        _commit(conn)

        return True


    except Exception as e:

        try:
            conn.rollback()

        except Exception:
            pass

        print(
            f"[배당 저장 실패] "
            f"ID={schedule_id} "
            f"업체={company_name} "
            f"{type(e).__name__}: {e}"
        )

        return False


    finally:

        try:
            conn.close()

        except Exception:
            pass


# ============================================================
# 완료 상태 저장
# ============================================================

def save_collection_state(
    schedule_id,
    status="completed",
):

    conn = get_connection()

    try:

        now = datetime.now().isoformat(
            timespec="seconds"
        )


        # ----------------------------------------------------
        # 중요
        # INSERT가 아니라 UPSERT
        #
        # 같은 ID를 다시 저장해도
        # UNIQUE constraint 오류가 발생하지 않음
        # ----------------------------------------------------

        conn.execute(
            """
            INSERT INTO collection_state (
                id,
                status,
                updated_at
            )
            VALUES (?, ?, ?)

            ON CONFLICT(id)
            DO UPDATE SET
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                str(schedule_id),
                status,
                now,
            ),
        )


        _commit(conn)

        return True


    except Exception as e:

        try:
            conn.rollback()

        except Exception:
            pass

        print(
            f"[상태 저장 오류] "
            f"{type(e).__name__}: {e}"
        )

        return False


    finally:

        try:
            conn.close()

        except Exception:
            pass


# ============================================================
# 완료 여부
# ============================================================

def is_collection_completed(
    schedule_id
):

    conn = get_connection()

    try:

        row = conn.execute(
            """
            SELECT status
            FROM collection_state
            WHERE id = ?
            LIMIT 1
            """,
            (
                str(schedule_id),
            ),
        ).fetchone()


        if not row:

            return False


        try:

            status = row["status"]

        except Exception:

            status = row[0]


        return status == "completed"


    except Exception:

        return False


    finally:

        try:
            conn.close()

        except Exception:
            pass


# ============================================================
# DB 용량 계산
# ============================================================

def get_database_size():

    # --------------------------------------------------------
    # 반환값
    #
    # bytes
    # mb
    # gb
    # source
    # --------------------------------------------------------

    result = {
        "bytes": 0,
        "mb": 0.0,
        "gb": 0.0,
        "source": "unknown",
    }


    # ========================================================
    # 1. Turso / libSQL
    # ========================================================

    if TURSO_DATABASE_URL and TURSO_AUTH_TOKEN:

        conn = None

        try:

            conn = get_connection()


            # ------------------------------------------------
            # SQLite/libSQL page 정보
            # ------------------------------------------------

            page_count = None
            page_size = None


            try:

                row = conn.execute(
                    "PRAGMA page_count"
                ).fetchone()

                if row:

                    page_count = int(
                        row[0]
                    )

            except Exception:
                pass


            try:

                row = conn.execute(
                    "PRAGMA page_size"
                ).fetchone()

                if row:

                    page_size = int(
                        row[0]
                    )

            except Exception:
                pass


            if (
                page_count is not None
                and page_size is not None
            ):

                size_bytes = (
                    page_count
                    * page_size
                )

                result["bytes"] = (
                    size_bytes
                )

                result["mb"] = (
                    size_bytes
                    / (1024 * 1024)
                )

                result["gb"] = (
                    size_bytes
                    / (1024 * 1024 * 1024)
                )

                result["source"] = (
                    "Turso/libSQL"
                )

                return result


        except Exception as e:

            print(
                f"[Turso DB 용량 조회 실패] "
                f"{e}"
            )

        finally:

            if conn is not None:

                try:
                    conn.close()

                except Exception:
                    pass


    # ========================================================
    # 2. Local SQLite
    # ========================================================

    try:

        if DB_FILE.exists():

            size_bytes = (
                DB_FILE.stat().st_size
            )

            result["bytes"] = (
                size_bytes
            )

            result["mb"] = (
                size_bytes
                / (1024 * 1024)
            )

            result["gb"] = (
                size_bytes
                / (1024 * 1024 * 1024)
            )

            result["source"] = (
                "Local SQLite"
            )

            return result

    except Exception as e:

        print(
            f"[SQLite DB 용량 조회 실패] "
            f"{e}"
        )


    return result


# ============================================================
# DB 통계
# ============================================================

def get_database_status():

    conn = get_connection()

    result = {
        "matches": 0,
        "odds": 0,
        "bookmakers": 0,
        "completed": 0,

        "db_size_bytes": 0,
        "db_size_mb": 0.0,
        "db_size_gb": 0.0,
        "db_size_source": "unknown",
    }


    try:

        # ----------------------------------------------------
        # 경기
        # ----------------------------------------------------

        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM matches
            """
        ).fetchone()


        if row:

            result["matches"] = int(
                row[0]
            )


        # ----------------------------------------------------
        # 배당
        # ----------------------------------------------------

        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM odds
            """
        ).fetchone()


        if row:

            result["odds"] = int(
                row[0]
            )


        # ----------------------------------------------------
        # 업체
        # ----------------------------------------------------

        try:

            row = conn.execute(
                """
                SELECT COUNT(DISTINCT bookmaker)
                FROM odds
                WHERE bookmaker IS NOT NULL
                  AND bookmaker != ''
                """
            ).fetchone()

        except Exception:

            row = conn.execute(
                """
                SELECT COUNT(DISTINCT company_name)
                FROM odds
                WHERE company_name IS NOT NULL
                  AND company_name != ''
                """
            ).fetchone()


        if row:

            result["bookmakers"] = int(
                row[0]
            )


        # ----------------------------------------------------
        # 완료 상태
        # ----------------------------------------------------

        try:

            row = conn.execute(
                """
                SELECT COUNT(*)
                FROM collection_state
                WHERE status = 'completed'
                """
            ).fetchone()

            if row:

                result["completed"] = int(
                    row[0]
                )

        except Exception:

            pass


    except Exception as e:

        print(
            f"[DB 상태 조회 오류] {e}"
        )


    finally:

        try:
            conn.close()

        except Exception:
            pass


    # --------------------------------------------------------
    # DB 용량
    # --------------------------------------------------------

    try:

        size = get_database_size()

        result["db_size_bytes"] = (
            size["bytes"]
        )

        result["db_size_mb"] = (
            size["mb"]
        )

        result["db_size_gb"] = (
            size["gb"]
        )

        result["db_size_source"] = (
            size["source"]
        )

    except Exception as e:

        print(
            f"[DB 용량 상태 오류] {e}"
        )


    return result


# ============================================================
# 업체 목록
# ============================================================

def get_bookmakers():

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT
                bookmaker,
                COUNT(*) AS games
            FROM odds
            WHERE bookmaker IS NOT NULL
              AND bookmaker != ''
            GROUP BY bookmaker
            ORDER BY bookmaker
            """
        ).fetchall()


        result = []


        for row in rows:

            try:

                name = row["bookmaker"]
                games = row["games"]

            except Exception:

                name = row[0]
                games = row[1]


            result.append(
                {
                    "bookmaker": name,
                    "games": games,
                }
            )


        return result


    except Exception:

        return []


    finally:

        try:
            conn.close()

        except Exception:
            pass


# ============================================================
# 분석용 전체 데이터
# ============================================================

def get_analysis_rows(
    bookmaker=None,
):

    conn = get_connection()

    try:

        if bookmaker:

            rows = conn.execute(
                """
                SELECT
                    m.schedule_id,
                    m.match_date,
                    m.home_team,
                    m.away_team,
                    m.home_score,
                    m.away_score,
                    m.result,
                    o.bookmaker,
                    o.company_id,
                    o.final_home,
                    o.final_draw,
                    o.final_away
                FROM matches m
                INNER JOIN odds o
                    ON m.schedule_id = o.schedule_id
                WHERE o.bookmaker = ?
                ORDER BY m.match_date DESC
                """,
                (
                    bookmaker,
                ),
            ).fetchall()


        else:

            rows = conn.execute(
                """
                SELECT
                    m.schedule_id,
                    m.match_date,
                    m.home_team,
                    m.away_team,
                    m.home_score,
                    m.away_score,
                    m.result,
                    o.bookmaker,
                    o.company_id,
                    o.final_home,
                    o.final_draw,
                    o.final_away
                FROM matches m
                INNER JOIN odds o
                    ON m.schedule_id = o.schedule_id
                ORDER BY m.match_date DESC
                """
            ).fetchall()


        result = []


        for row in rows:

            try:

                result.append(
                    dict(row)
                )

            except Exception:

                result.append(
                    {
                        "schedule_id": row[0],
                        "match_date": row[1],
                        "home_team": row[2],
                        "away_team": row[3],
                        "home_score": row[4],
                        "away_score": row[5],
                        "result": row[6],
                        "bookmaker": row[7],
                        "company_id": row[8],
                        "final_home": row[9],
                        "final_draw": row[10],
                        "final_away": row[11],
                    }
                )


        return result


    except Exception as e:

        print(
            f"[분석 데이터 오류] {e}"
        )

        return []


    finally:

        try:
            conn.close()

        except Exception:
            pass


# ============================================================
# 특정 경기
# ============================================================

def get_match_odds(
    schedule_id
):

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT
                m.*,
                o.bookmaker,
                o.company_id,
                o.final_home,
                o.final_draw,
                o.final_away
            FROM matches m
            LEFT JOIN odds o
                ON m.schedule_id = o.schedule_id
            WHERE m.schedule_id = ?
            """,
            (
                str(schedule_id),
            ),
        ).fetchall()


        result = []


        for row in rows:

            try:

                result.append(
                    dict(row)
                )

            except Exception:

                pass


        return result


    except Exception:

        return []


    finally:

        try:
            conn.close()

        except Exception:
            pass


# ============================================================
# 초기화
# ============================================================

try:

    init_database()

except Exception as e:

    print(
        f"[DB 초기화 오류] {e}"
            )
