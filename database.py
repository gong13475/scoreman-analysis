# ============================================================
# database.py
# Scoreman 영구 DB
# SQLite / Turso(libsql) 대응
#
# 기능
# - 경기 영구 저장
# - 해외업체 최종배당 영구 저장
# - 수집 완료상태 영구 저장
# - 이어받기 위치 저장
# - DB 용량 조회
# - 기존 DB 컬럼 자동 보정
# ============================================================

import os
import sqlite3
from pathlib import Path
from datetime import datetime


DB_FILE = (
    Path(__file__).resolve().parent
    / "scoreman.db"
)


TURSO_DATABASE_URL = os.getenv(
    "TURSO_DATABASE_URL",
    "",
).strip()


TURSO_AUTH_TOKEN = os.getenv(
    "TURSO_AUTH_TOKEN",
    "",
).strip()


# ============================================================
# 연결
# ============================================================

def get_connection():

    # --------------------------------------------------------
    # Turso
    # --------------------------------------------------------

    if (
        TURSO_DATABASE_URL
        and TURSO_AUTH_TOKEN
    ):

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
# DB 종류
# ============================================================

def get_database_type():

    if (
        TURSO_DATABASE_URL
        and TURSO_AUTH_TOKEN
    ):
        return "Turso 영구 DB"

    return "로컬 SQLite"


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
                bookmaker TEXT,
                final_home REAL,
                final_draw REAL,
                final_away REAL
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
# 컬럼 자동 보정
# ============================================================

def ensure_columns(conn):

    # --------------------------------------------------------
    # matches
    # --------------------------------------------------------

    try:

        rows = conn.execute(
            "PRAGMA table_info(matches)"
        ).fetchall()

        columns = set()

        for row in rows:

            try:
                columns.add(row["name"])

            except Exception:
                columns.add(row[1])

        required = {
            "match_date":
                "TEXT",

            "home_team":
                "TEXT",

            "away_team":
                "TEXT",

            "home_score":
                "INTEGER",

            "away_score":
                "INTEGER",

            "result":
                "TEXT",

            "source":
                "TEXT",
        }

        for name, typ in required.items():

            if name not in columns:

                conn.execute(
                    f"""
                    ALTER TABLE matches
                    ADD COLUMN {name} {typ}
                    """
                )

    except Exception as e:

        print(
            f"[matches 컬럼 확인] {e}"
        )

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
                columns.add(row["name"])

            except Exception:
                columns.add(row[1])

        required = {
            "company_id":
                "TEXT",

            "company_name":
                "TEXT",

            "bookmaker":
                "TEXT",

            "final_home":
                "REAL",

            "final_draw":
                "REAL",

            "final_away":
                "REAL",
        }

        for name, typ in required.items():

            if name not in columns:

                conn.execute(
                    f"""
                    ALTER TABLE odds
                    ADD COLUMN {name} {typ}
                    """
                )

        # 기존 bookmaker 보정

        conn.execute(
            """
            UPDATE odds
            SET bookmaker = company_name
            WHERE
                (
                    bookmaker IS NULL
                    OR bookmaker = ''
                )
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
                columns.add(row["name"])

            except Exception:
                columns.add(row[1])

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

        bookmaker = (
            company_name
            if company_name
            else f"CID_{company_id}"
        )

        home = float(final_home)
        draw = float(final_draw)
        away = float(final_away)

        # ----------------------------------------------------
        # 기존 업체 확인
        # ----------------------------------------------------

        row = conn.execute(
            """
            SELECT id
            FROM odds
            WHERE
                schedule_id = ?
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
                    home,
                    draw,
                    away,
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
                    home,
                    draw,
                    away,
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
# 수집 상태 저장
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

        # 반드시 UPSERT
        # UNIQUE constraint 오류 방지

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
    schedule_id,
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

        return (
            str(status)
            == "completed"
        )

    except Exception:

        return False

    finally:

        try:
            conn.close()

        except Exception:
            pass


# ============================================================
# 마지막 완료 ID
# ============================================================

def get_last_completed_id():

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT id
            FROM collection_state
            WHERE status = 'completed'
            """
        ).fetchall()

        values = []

        for row in rows:

            try:
                value = row["id"]

            except Exception:
                value = row[0]

            try:
                values.append(
                    int(value)
                )

            except Exception:
                continue

        if not values:
            return None

        return max(values)

    except Exception:

        return None

    finally:

        try:
            conn.close()

        except Exception:
            pass


# ============================================================
# 특정 범위 마지막 완료 ID
# ============================================================

def get_last_completed_id_in_range(
    start_id,
    end_id,
):

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT id
            FROM collection_state
            WHERE
                status = 'completed'
                AND CAST(id AS INTEGER)
                    BETWEEN ?
                    AND ?
            """,
            (
                int(start_id),
                int(end_id),
            ),
        ).fetchall()

        values = []

        for row in rows:

            try:
                value = row["id"]

            except Exception:
                value = row[0]

            try:
                values.append(
                    int(value)
                )

            except Exception:
                continue

        if not values:
            return None

        return max(values)

    except Exception:

        return None

    finally:

        try:
            conn.close()

        except Exception:
            pass


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
        "size_bytes": 0,
        "size_mb": 0.0,
        "type": get_database_type(),
        "last_completed_id":
            get_last_completed_id(),
    }

    try:

        row = conn.execute(
            "SELECT COUNT(*) FROM matches"
        ).fetchone()

        if row:
            result["matches"] = int(
                row[0]
            )

        row = conn.execute(
            "SELECT COUNT(*) FROM odds"
        ).fetchone()

        if row:
            result["odds"] = int(
                row[0]
            )

        row = conn.execute(
            """
            SELECT COUNT(DISTINCT bookmaker)
            FROM odds
            WHERE
                bookmaker IS NOT NULL
                AND bookmaker != ''
            """
        ).fetchone()

        if row:
            result["bookmakers"] = int(
                row[0]
            )

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

        # ----------------------------------------------------
        # SQLite/Turso 용량
        # ----------------------------------------------------

        try:

            page_count = conn.execute(
                "PRAGMA page_count"
            ).fetchone()

            page_size = conn.execute(
                "PRAGMA page_size"
            ).fetchone()

            if page_count and page_size:

                size_bytes = (
                    int(page_count[0])
                    * int(page_size[0])
                )

                result["size_bytes"] = (
                    size_bytes
                )

                result["size_mb"] = (
                    size_bytes
                    / 1024
                    / 1024
                )

        except Exception:
            pass

        # 로컬 SQLite 실제 파일 크기도 확인

        if (
            result["size_bytes"] == 0
            and DB_FILE.exists()
        ):

            try:

                size_bytes = (
                    DB_FILE.stat().st_size
                )

                result["size_bytes"] = (
                    size_bytes
                )

                result["size_mb"] = (
                    size_bytes
                    / 1024
                    / 1024
                )

            except Exception:
                pass

    except Exception as e:

        print(
            f"[DB 상태 오류] {e}"
        )

    finally:

        try:
            conn.close()

        except Exception:
            pass

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
            WHERE
                bookmaker IS NOT NULL
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
# 분석 데이터
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
                    o.company_name,
                    o.final_home,
                    o.final_draw,
                    o.final_away
                FROM matches m
                INNER JOIN odds o
                    ON m.schedule_id =
                       o.schedule_id
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
                    o.company_name,
                    o.final_home,
                    o.final_draw,
                    o.final_away
                FROM matches m
                INNER JOIN odds o
                    ON m.schedule_id =
                       o.schedule_id
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
                        "company_name": row[9],
                        "final_home": row[10],
                        "final_draw": row[11],
                        "final_away": row[12],
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
    schedule_id,
):

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT
                m.*,
                o.bookmaker,
                o.company_id,
                o.company_name,
                o.final_home,
                o.final_draw,
                o.final_away
            FROM matches m
            LEFT JOIN odds o
                ON m.schedule_id =
                   o.schedule_id
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
