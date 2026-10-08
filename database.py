# ============================================================
# database.py
# Scoreman 영구 DB
# SQLite / Turso(libsql) 대응
#
# 기능
# - 경기 영구 저장
# - 최종배당 영구 저장
# - 경기 결과 저장
# - 수집 상태 저장
# - 이어받기 위치 저장
# - 기존 결과 누락 경기 보정
# - DB 용량 표시
# ============================================================

import os
import sqlite3
from pathlib import Path
from datetime import datetime


# ============================================================
# DB 경로
# ============================================================

DB_FILE = Path(__file__).resolve().parent / "scoreman.db"


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
# commit
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
# 기존 DB 컬럼 보정
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
                "ALTER TABLE matches ADD COLUMN match_date TEXT",

            "home_team":
                "ALTER TABLE matches ADD COLUMN home_team TEXT",

            "away_team":
                "ALTER TABLE matches ADD COLUMN away_team TEXT",

            "home_score":
                "ALTER TABLE matches ADD COLUMN home_score INTEGER",

            "away_score":
                "ALTER TABLE matches ADD COLUMN away_score INTEGER",

            "result":
                "ALTER TABLE matches ADD COLUMN result TEXT",

            "source":
                "ALTER TABLE matches ADD COLUMN source TEXT",
        }

        for name, sql in required.items():

            if name not in columns:

                try:
                    conn.execute(sql)
                except Exception as e:
                    print(
                        f"[matches 컬럼 추가 실패] "
                        f"{name}: {e}"
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
                "ALTER TABLE odds ADD COLUMN company_id TEXT",

            "company_name":
                "ALTER TABLE odds ADD COLUMN company_name TEXT",

            "bookmaker":
                "ALTER TABLE odds ADD COLUMN bookmaker TEXT",

            "final_home":
                "ALTER TABLE odds ADD COLUMN final_home REAL",

            "final_draw":
                "ALTER TABLE odds ADD COLUMN final_draw REAL",

            "final_away":
                "ALTER TABLE odds ADD COLUMN final_away REAL",
        }

        for name, sql in required.items():

            if name not in columns:

                try:
                    conn.execute(sql)
                except Exception as e:
                    print(
                        f"[odds 컬럼 추가 실패] "
                        f"{name}: {e}"
                    )

        # 기존 bookmaker 보정
        try:

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

        except Exception:
            pass

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
                match_date =
                    COALESCE(
                        excluded.match_date,
                        matches.match_date
                    ),

                home_team =
                    COALESCE(
                        excluded.home_team,
                        matches.home_team
                    ),

                away_team =
                    COALESCE(
                        excluded.away_team,
                        matches.away_team
                    ),

                home_score =
                    COALESCE(
                        excluded.home_score,
                        matches.home_score
                    ),

                away_score =
                    COALESCE(
                        excluded.away_score,
                        matches.away_score
                    ),

                result =
                    COALESCE(
                        excluded.result,
                        matches.result
                    ),

                source =
                    COALESCE(
                        excluded.source,
                        matches.source
                    )
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
# 경기 결과만 업데이트
# ============================================================

def update_match_result(
    schedule_id,
    home_score,
    away_score,
    result,
):

    conn = get_connection()

    try:

        conn.execute(
            """
            UPDATE matches
            SET
                home_score = ?,
                away_score = ?,
                result = ?
            WHERE schedule_id = ?
            """,
            (
                home_score,
                away_score,
                result,
                str(schedule_id),
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
            f"[결과 업데이트 실패] "
            f"ID={schedule_id} "
            f"{e}"
        )

        return False

    finally:

        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# 경기 기본정보
# ============================================================

def get_match(schedule_id):

    conn = get_connection()

    try:

        row = conn.execute(
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
            LIMIT 1
            """,
            (str(schedule_id),),
        ).fetchone()

        if not row:
            return None

        try:
            return dict(row)

        except Exception:

            return {
                "schedule_id": row[0],
                "match_date": row[1],
                "home_team": row[2],
                "away_team": row[3],
                "home_score": row[4],
                "away_score": row[5],
                "result": row[6],
                "source": row[7],
            }

    except Exception:

        return None

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

        home = float(final_home)
        draw = float(final_draw)
        away = float(final_away)

        # ----------------------------------------------------
        # 기존 업체 찾기
        # ----------------------------------------------------

        row = conn.execute(
            """
            SELECT id
            FROM odds
            WHERE schedule_id = ?
              AND (
                    bookmaker = ?
                    OR company_name = ?
                    OR (
                        company_id = ?
                        AND company_id != ''
                    )
                  )
            LIMIT 1
            """,
            (
                schedule_id,
                bookmaker,
                company_name,
                company_id,
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
# 상태 확인
# ============================================================

def get_collection_status(
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
            (str(schedule_id),),
        ).fetchone()

        if not row:
            return None

        try:
            return row["status"]
        except Exception:
            return row[0]

    except Exception:

        return None

    finally:

        try:
            conn.close()
        except Exception:
            pass


def is_collection_completed(
    schedule_id,
):

    return (
        get_collection_status(
            schedule_id
        )
        == "completed"
    )


# ============================================================
# 마지막 완료 ID
# ============================================================

def get_last_completed_id(
    start_id=None,
    end_id=None,
):

    conn = get_connection()

    try:

        sql = """
            SELECT MAX(
                CAST(id AS INTEGER)
            )
            FROM collection_state
            WHERE status = 'completed'
        """

        params = []

        if start_id is not None:

            sql += """
                AND CAST(id AS INTEGER) >= ?
            """

            params.append(
                int(start_id)
            )

        if end_id is not None:

            sql += """
                AND CAST(id AS INTEGER) <= ?
            """

            params.append(
                int(end_id)
            )

        row = conn.execute(
            sql,
            tuple(params),
        ).fetchone()

        if not row or row[0] is None:
            return None

        return int(row[0])

    except Exception:

        return None

    finally:

        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# 이어받기 ID
# ============================================================

def get_resume_id(
    start_id,
    end_id,
):

    start_id = int(start_id)
    end_id = int(end_id)

    if end_id < start_id:
        return start_id

    last = get_last_completed_id(
        start_id,
        end_id,
    )

    if last is None:
        return start_id

    next_id = last + 1

    if next_id > end_id:
        return end_id + 1

    return next_id


# ============================================================
# DB 통계
# ============================================================

def get_database_status():

    conn = get_connection()

    result = {
        "matches": 0,
        "odds": 0,
        "bookmakers": 0,
    }

    try:

        row = conn.execute(
            "SELECT COUNT(*) FROM matches"
        ).fetchone()

        if row:
            result["matches"] = int(row[0])

        row = conn.execute(
            "SELECT COUNT(*) FROM odds"
        ).fetchone()

        if row:
            result["odds"] = int(row[0])

        row = conn.execute(
            """
            SELECT COUNT(DISTINCT bookmaker)
            FROM odds
            WHERE bookmaker IS NOT NULL
              AND bookmaker != ''
            """
        ).fetchone()

        if row:
            result["bookmakers"] = int(row[0])

    except Exception:
        pass

    finally:

        try:
            conn.close()
        except Exception:
            pass

    return result


# ============================================================
# DB 용량
# ============================================================

def get_database_size_bytes():

    # --------------------------------------------------------
    # Local SQLite
    # --------------------------------------------------------

    if DB_FILE.exists():

        try:

            return int(
                DB_FILE.stat().st_size
            )

        except Exception:
            pass

    # --------------------------------------------------------
    # Turso / libSQL
    # --------------------------------------------------------

    conn = get_connection()

    try:

        page_count = conn.execute(
            "PRAGMA page_count"
        ).fetchone()

        page_size = conn.execute(
            "PRAGMA page_size"
        ).fetchone()

        if (
            page_count
            and page_size
        ):

            return (
                int(page_count[0])
                * int(page_size[0])
            )

    except Exception:
        pass

    finally:

        try:
            conn.close()
        except Exception:
            pass

    return 0


def format_bytes(
    value,
):

    try:
        value = float(value)
    except Exception:
        return "0 B"

    units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB",
    ]

    for unit in units:

        if abs(value) < 1024:

            if unit == "B":
                return f"{value:.0f} {unit}"

            return f"{value:.2f} {unit}"

        value /= 1024

    return f"{value:.2f} PB"


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

                    o.final_home,
                    o.final_draw,
                    o.final_away

                FROM matches m

                INNER JOIN odds o
                    ON m.schedule_id =
                       o.schedule_id

                WHERE o.bookmaker = ?

                ORDER BY
                    m.match_date DESC
                """,
                (bookmaker,),
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
                    ON m.schedule_id =
                       o.schedule_id

                ORDER BY
                    m.match_date DESC
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
# 특정 경기 배당
# ============================================================

def get_match_odds(
    schedule_id,
):

    conn = get_connection()

    try:

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

            LEFT JOIN odds o
                ON m.schedule_id =
                   o.schedule_id

            WHERE m.schedule_id = ?

            ORDER BY o.bookmaker
            """,
            (str(schedule_id),),
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
# 결과 누락 경기 찾기
# ============================================================

def get_missing_result_matches(
    limit=100,
):

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT
                schedule_id,
                match_date,
                home_team,
                away_team,
                home_score,
                away_score,
                result
            FROM matches
            WHERE
                result IS NULL
                OR result = ''
            ORDER BY
                CAST(schedule_id AS INTEGER)
            LIMIT ?
            """,
            (int(limit),),
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
