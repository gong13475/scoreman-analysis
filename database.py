# ============================================================
# database.py
# Scoreman 영구 DB
# SQLite / Turso(libsql)
#
# 기능
# - 경기 영구 저장
# - 실제 경기 결과 저장
# - 최종배당 저장
# - 업체별 배당 저장
# - 완료 상태 저장
# - 결과 미확인 경기 조회
# - 마지막 완료 ID
# - Turso UNIQUE 오류 방어
# ============================================================

import os
import sqlite3
from pathlib import Path
from datetime import datetime


DB_FILE = Path(__file__).resolve().parent / "scoreman.db"

TURSO_DATABASE_URL = os.getenv(
    "TURSO_DATABASE_URL",
    ""
).strip()

TURSO_AUTH_TOKEN = os.getenv(
    "TURSO_AUTH_TOKEN",
    ""
).strip()


# ============================================================
# 연결
# ============================================================

def get_connection():

    if TURSO_DATABASE_URL and TURSO_AUTH_TOKEN:

        try:

            import libsql

            conn = libsql.connect(
                TURSO_DATABASE_URL,
                auth_token=TURSO_AUTH_TOKEN,
            )

            return conn

        except Exception as e:

            print(
                f"[Turso 연결 실패] {e}"
            )

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


def _commit(conn):

    try:
        conn.commit()
    except Exception:
        pass


def _rollback(conn):

    try:
        conn.rollback()
    except Exception:
        pass


# ============================================================
# 테이블 생성
# ============================================================

def init_database():

    conn = get_connection()

    try:

        conn.execute("""
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
        """)

        conn.execute("""
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
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS collection_state (
                id TEXT PRIMARY KEY,
                status TEXT,
                updated_at TEXT
            )
        """)

        _commit(conn)

        ensure_columns(conn)

        _commit(conn)

        create_indexes(conn)

        _commit(conn)

    finally:

        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# 인덱스
# ============================================================

def create_indexes(conn):

    indexes = [

        """
        CREATE INDEX IF NOT EXISTS idx_odds_schedule
        ON odds(schedule_id)
        """,

        """
        CREATE INDEX IF NOT EXISTS idx_odds_bookmaker
        ON odds(bookmaker)
        """,

        """
        CREATE INDEX IF NOT EXISTS idx_matches_date
        ON matches(match_date)
        """,

        """
        CREATE INDEX IF NOT EXISTS idx_state_status
        ON collection_state(status)
        """,
    ]

    for sql in indexes:

        try:
            conn.execute(sql)
        except Exception as e:
            print(f"[인덱스] {e}")


# ============================================================
# 컬럼 보정
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

        fields = [

            (
                "match_date",
                "ALTER TABLE matches ADD COLUMN match_date TEXT"
            ),

            (
                "home_team",
                "ALTER TABLE matches ADD COLUMN home_team TEXT"
            ),

            (
                "away_team",
                "ALTER TABLE matches ADD COLUMN away_team TEXT"
            ),

            (
                "home_score",
                "ALTER TABLE matches ADD COLUMN home_score INTEGER"
            ),

            (
                "away_score",
                "ALTER TABLE matches ADD COLUMN away_score INTEGER"
            ),

            (
                "result",
                "ALTER TABLE matches ADD COLUMN result TEXT"
            ),

            (
                "source",
                "ALTER TABLE matches ADD COLUMN source TEXT"
            ),
        ]

        for name, sql in fields:

            if name not in columns:

                try:
                    conn.execute(sql)
                except Exception as e:
                    print(
                        f"[matches 컬럼 추가] "
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

        fields = [

            (
                "company_id",
                "ALTER TABLE odds ADD COLUMN company_id TEXT"
            ),

            (
                "company_name",
                "ALTER TABLE odds ADD COLUMN company_name TEXT"
            ),

            (
                "bookmaker",
                "ALTER TABLE odds ADD COLUMN bookmaker TEXT"
            ),

            (
                "final_home",
                "ALTER TABLE odds ADD COLUMN final_home REAL"
            ),

            (
                "final_draw",
                "ALTER TABLE odds ADD COLUMN final_draw REAL"
            ),

            (
                "final_away",
                "ALTER TABLE odds ADD COLUMN final_away REAL"
            ),
        ]

        for name, sql in fields:

            if name not in columns:

                try:
                    conn.execute(sql)
                except Exception as e:
                    print(
                        f"[odds 컬럼 추가] "
                        f"{name}: {e}"
                    )

        try:

            conn.execute("""
                UPDATE odds
                SET bookmaker = company_name
                WHERE
                    (bookmaker IS NULL OR bookmaker = '')
                    AND company_name IS NOT NULL
                    AND company_name != ''
            """)

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

            try:

                conn.execute("""
                    ALTER TABLE collection_state
                    ADD COLUMN status TEXT
                """)

            except Exception as e:
                print(
                    f"[state status 추가] {e}"
                )

        if "updated_at" not in columns:

            try:

                conn.execute("""
                    ALTER TABLE collection_state
                    ADD COLUMN updated_at TEXT
                """)

            except Exception as e:
                print(
                    f"[state updated_at 추가] {e}"
                )

    except Exception as e:

        print(
            f"[collection_state 확인] {e}"
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

        sid = str(schedule_id)

        # ----------------------------------------------------
        # 기존 경기 확인
        # ----------------------------------------------------

        row = conn.execute("""
            SELECT schedule_id
            FROM matches
            WHERE schedule_id = ?
            LIMIT 1
        """, (
            sid,
        )).fetchone()

        if row:

            conn.execute("""
                UPDATE matches
                SET
                    match_date =
                        COALESCE(?, match_date),

                    home_team =
                        COALESCE(?, home_team),

                    away_team =
                        COALESCE(?, away_team),

                    home_score =
                        CASE
                            WHEN ? IS NOT NULL
                            THEN ?
                            ELSE home_score
                        END,

                    away_score =
                        CASE
                            WHEN ? IS NOT NULL
                            THEN ?
                            ELSE away_score
                        END,

                    result =
                        CASE
                            WHEN ? IS NOT NULL
                                 AND ? != ''
                            THEN ?
                            ELSE result
                        END,

                    source =
                        COALESCE(?, source)

                WHERE schedule_id = ?
            """, (
                match_date,

                home_team,
                away_team,

                home_score,
                home_score,

                away_score,
                away_score,

                result,
                result,
                result,

                source,

                sid,
            ))

        else:

            conn.execute("""
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
            """, (
                sid,
                match_date,
                home_team,
                away_team,
                home_score,
                away_score,
                result,
                source,
            ))

        _commit(conn)

        return True

    except Exception as e:

        _rollback(conn)

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

        sid = str(schedule_id)

        cid = (
            str(company_id)
            if company_id is not None
            else ""
        )

        cname = str(
            company_name or ""
        ).strip()

        bookmaker = (
            cname
            if cname
            else f"CID_{cid}"
        )

        fh = float(final_home)
        fd = float(final_draw)
        fa = float(final_away)

        # ----------------------------------------------------
        # 업체 기준으로 기존 데이터 검색
        # ----------------------------------------------------

        row = conn.execute("""
            SELECT id
            FROM odds
            WHERE
                schedule_id = ?
                AND (
                    bookmaker = ?
                    OR (
                        company_name = ?
                        AND company_name != ''
                    )
                    OR (
                        company_id = ?
                        AND company_id != ''
                    )
                )
            LIMIT 1
        """, (
            sid,
            bookmaker,
            cname,
            cid,
        )).fetchone()

        if row:

            try:
                row_id = row["id"]
            except Exception:
                row_id = row[0]

            conn.execute("""
                UPDATE odds
                SET
                    company_id = ?,
                    company_name = ?,
                    bookmaker = ?,
                    final_home = ?,
                    final_draw = ?,
                    final_away = ?
                WHERE id = ?
            """, (
                cid,
                cname,
                bookmaker,
                fh,
                fd,
                fa,
                row_id,
            ))

        else:

            conn.execute("""
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
            """, (
                sid,
                cid,
                cname,
                bookmaker,
                fh,
                fd,
                fa,
            ))

        _commit(conn)

        return True

    except Exception as e:

        _rollback(conn)

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

        sid = str(schedule_id)

        now = datetime.now().isoformat(
            timespec="seconds"
        )

        # ----------------------------------------------------
        # 먼저 UPDATE
        # ----------------------------------------------------

        cursor = conn.execute("""
            UPDATE collection_state
            SET
                status = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            status,
            now,
            sid,
        ))

        # ----------------------------------------------------
        # 없으면 INSERT
        # ----------------------------------------------------

        try:
            affected = cursor.rowcount
        except Exception:
            affected = 0

        if not affected:

            try:

                conn.execute("""
                    INSERT INTO collection_state (
                        id,
                        status,
                        updated_at
                    )
                    VALUES (?, ?, ?)
                """, (
                    sid,
                    status,
                    now,
                ))

            except Exception as insert_error:

                # 다른 연결에서 이미 삽입된 경우
                # 다시 UPDATE
                if "UNIQUE" in str(
                    insert_error
                ).upper():

                    conn.execute("""
                        UPDATE collection_state
                        SET
                            status = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (
                        status,
                        now,
                        sid,
                    ))

                else:
                    raise

        _commit(conn)

        return True

    except Exception as e:

        _rollback(conn)

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

        row = conn.execute("""
            SELECT status
            FROM collection_state
            WHERE id = ?
            LIMIT 1
        """, (
            str(schedule_id),
        )).fetchone()

        if not row:
            return False

        try:
            return (
                str(row["status"])
                .lower()
                == "completed"
            )

        except Exception:

            return (
                str(row[0]).lower()
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
# 결과 없는 경기
# ============================================================

def get_unresolved_matches():

    conn = get_connection()

    try:

        rows = conn.execute("""
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
                OR home_score IS NULL
                OR away_score IS NULL
            ORDER BY
                match_date DESC,
                schedule_id DESC
        """).fetchall()

        result = []

        for row in rows:

            try:
                result.append(dict(row))

            except Exception:

                result.append({
                    "schedule_id": row[0],
                    "match_date": row[1],
                    "home_team": row[2],
                    "away_team": row[3],
                    "home_score": row[4],
                    "away_score": row[5],
                    "result": row[6],
                })

        return result

    except Exception:

        return []

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

        row = conn.execute("""
            SELECT MAX(
                CAST(id AS INTEGER)
            )
            FROM collection_state
            WHERE status = 'completed'
        """).fetchone()

        if row:

            value = row[0]

            if value is not None:
                return int(value)

        return None

    except Exception:

        return None

    finally:

        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# DB 상태
# ============================================================

def get_database_status():

    conn = get_connection()

    result = {
        "matches": 0,
        "odds": 0,
        "bookmakers": 0,
        "results": 0,
        "unresolved": 0,
        "completed": 0,
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

        row = conn.execute("""
            SELECT COUNT(DISTINCT bookmaker)
            FROM odds
            WHERE bookmaker IS NOT NULL
              AND bookmaker != ''
        """).fetchone()

        if row:
            result["bookmakers"] = int(row[0])

        row = conn.execute("""
            SELECT COUNT(*)
            FROM matches
            WHERE result IN ('승', '무', '패')
        """).fetchone()

        if row:
            result["results"] = int(row[0])

        row = conn.execute("""
            SELECT COUNT(*)
            FROM matches
            WHERE
                result IS NULL
                OR result = ''
                OR home_score IS NULL
                OR away_score IS NULL
        """).fetchone()

        if row:
            result["unresolved"] = int(row[0])

        row = conn.execute("""
            SELECT COUNT(*)
            FROM collection_state
            WHERE status = 'completed'
        """).fetchone()

        if row:
            result["completed"] = int(row[0])

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

        rows = conn.execute("""
            SELECT
                bookmaker,
                COUNT(*) AS games
            FROM odds
            WHERE bookmaker IS NOT NULL
              AND bookmaker != ''
            GROUP BY bookmaker
            ORDER BY bookmaker
        """).fetchall()

        result = []

        for row in rows:

            try:

                result.append({
                    "bookmaker": row["bookmaker"],
                    "games": int(row["games"]),
                })

            except Exception:

                result.append({
                    "bookmaker": row[0],
                    "games": int(row[1]),
                })

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
    bookmaker=None
):

    conn = get_connection()

    try:

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
                o.company_id,
                o.company_name,
                o.final_home,
                o.final_draw,
                o.final_away
            FROM matches m
            INNER JOIN odds o
                ON m.schedule_id = o.schedule_id
            WHERE
                m.result IN ('승', '무', '패')
        """

        params = []

        if bookmaker:

            sql += """
                AND o.bookmaker = ?
            """

            params.append(
                bookmaker
            )

        sql += """
            ORDER BY
                m.match_date DESC,
                m.schedule_id DESC
        """

        rows = conn.execute(
            sql,
            tuple(params),
        ).fetchall()

        result = []

        for row in rows:

            try:

                result.append(
                    dict(row)
                )

            except Exception:

                result.append({
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
                })

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

        rows = conn.execute("""
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
                ON m.schedule_id = o.schedule_id
            WHERE
                m.schedule_id = ?
            ORDER BY
                o.bookmaker
        """, (
            str(schedule_id),
        )).fetchall()

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
# DB 용량
# ============================================================

def get_database_size():

    # --------------------------------------------------------
    # Local SQLite
    # --------------------------------------------------------

    if not (
        TURSO_DATABASE_URL
        and TURSO_AUTH_TOKEN
    ):

        try:

            if DB_FILE.exists():

                size = DB_FILE.stat().st_size

                return {
                    "bytes": size,
                    "mb": size / 1024 / 1024,
                    "gb": size / 1024 / 1024 / 1024,
                    "mode": "SQLite",
                }

        except Exception:
            pass

    # --------------------------------------------------------
    # Turso
    # --------------------------------------------------------

    conn = get_connection()

    try:

        try:

            row = conn.execute("""
                SELECT
                    page_count * page_size
                FROM pragma_page_count(),
                     pragma_page_size()
            """).fetchone()

        except Exception:

            row = conn.execute(
                "PRAGMA page_count"
            ).fetchone()

            page_count = (
                int(row[0])
                if row
                else 0
            )

            row2 = conn.execute(
                "PRAGMA page_size"
            ).fetchone()

            page_size = (
                int(row2[0])
                if row2
                else 4096
            )

            value = (
                page_count
                * page_size
            )

            return {
                "bytes": value,
                "mb": value / 1024 / 1024,
                "gb": value / 1024 / 1024 / 1024,
                "mode": "Turso",
            }

        if row:

            value = int(row[0])

            return {
                "bytes": value,
                "mb": value / 1024 / 1024,
                "gb": value / 1024 / 1024 / 1024,
                "mode": "Turso",
            }

    except Exception:
        pass

    finally:

        try:
            conn.close()
        except Exception:
            pass

    return {
        "bytes": 0,
        "mb": 0,
        "gb": 0,
        "mode": "unknown",
    }


# ============================================================
# 시작 시 초기화
# ============================================================

try:

    init_database()

except Exception as e:

    print(
        f"[DB 초기화 오류] {e}"
        )
