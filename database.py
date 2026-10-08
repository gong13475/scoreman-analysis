# ============================================================
# database.py
# Scoreman 영구 DB
# SQLite / Turso(libsql)
# ============================================================

import os
import sqlite3
from pathlib import Path
from datetime import datetime

DB_FILE = Path(__file__).resolve().parent / "scoreman.db"

TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL", "").strip()
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "").strip()


# ============================================================
# 연결
# ============================================================

def get_connection():

    if TURSO_DATABASE_URL and TURSO_AUTH_TOKEN:

        try:
            import libsql

            return libsql.connect(
                TURSO_DATABASE_URL,
                auth_token=TURSO_AUTH_TOKEN,
            )

        except Exception as e:
            print(f"[Turso 연결 실패] {e}")

    conn = sqlite3.connect(
        str(DB_FILE),
        check_same_thread=False,
        timeout=30,
    )

    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass

    return conn


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

        # 기존 중복 배당 제거
        try:
            conn.execute("""
                DELETE FROM odds
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM odds
                    GROUP BY schedule_id, bookmaker
                )
            """)
            _commit(conn)
        except Exception:
            pass

    finally:
        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# 컬럼 보정
# ============================================================

def ensure_columns(conn):

    tables = {
        "matches": {
            "match_date": "TEXT",
            "home_team": "TEXT",
            "away_team": "TEXT",
            "home_score": "INTEGER",
            "away_score": "INTEGER",
            "result": "TEXT",
            "source": "TEXT",
        },
        "odds": {
            "company_id": "TEXT",
            "company_name": "TEXT",
            "bookmaker": "TEXT",
            "final_home": "REAL",
            "final_draw": "REAL",
            "final_away": "REAL",
        },
        "collection_state": {
            "status": "TEXT",
            "updated_at": "TEXT",
        },
    }

    for table, columns in tables.items():

        try:

            rows = conn.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()

            existing = set()

            for row in rows:
                try:
                    existing.add(row["name"])
                except Exception:
                    existing.add(row[1])

            for name, typ in columns.items():

                if name not in existing:

                    try:
                        conn.execute(
                            f"ALTER TABLE {table} "
                            f"ADD COLUMN {name} {typ}"
                        )
                    except Exception as e:
                        print(
                            f"[컬럼 추가 실패] "
                            f"{table}.{name}: {e}"
                        )

        except Exception as e:
            print(f"[컬럼 확인 실패] {table}: {e}")


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

        # 기존 경기 확인
        row = conn.execute("""
            SELECT schedule_id
            FROM matches
            WHERE schedule_id = ?
            LIMIT 1
        """, (sid,)).fetchone()

        if row:

            conn.execute("""
                UPDATE matches
                SET
                    match_date = COALESCE(?, match_date),
                    home_team = CASE
                        WHEN ? IS NOT NULL AND ? != ''
                        THEN ?
                        ELSE home_team
                    END,
                    away_team = CASE
                        WHEN ? IS NOT NULL AND ? != ''
                        THEN ?
                        ELSE away_team
                    END,
                    home_score = CASE
                        WHEN ? IS NOT NULL THEN ?
                        ELSE home_score
                    END,
                    away_score = CASE
                        WHEN ? IS NOT NULL THEN ?
                        ELSE away_score
                    END,
                    result = CASE
                        WHEN ? IS NOT NULL AND ? != ''
                        THEN ?
                        ELSE result
                    END,
                    source = COALESCE(?, source)
                WHERE schedule_id = ?
            """, (
                match_date,

                home_team,
                home_team,
                home_team,

                away_team,
                away_team,
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

        sid = str(schedule_id)
        cid = str(company_id or "")
        cname = str(company_name or "").strip()

        bookmaker = cname or f"CID_{cid}"

        row = conn.execute("""
            SELECT id
            FROM odds
            WHERE schedule_id = ?
              AND bookmaker = ?
            LIMIT 1
        """, (
            sid,
            bookmaker,
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
                float(final_home),
                float(final_draw),
                float(final_away),
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
                float(final_home),
                float(final_draw),
                float(final_away),
            ))

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
# 완료 상태
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

        row = conn.execute("""
            SELECT id
            FROM collection_state
            WHERE id = ?
            LIMIT 1
        """, (sid,)).fetchone()

        if row:

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


def is_collection_completed(schedule_id):

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
            return str(row["status"]) == "completed"
        except Exception:
            return str(row[0]) == "completed"

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
            ORDER BY match_date DESC
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
            SELECT MAX(CAST(id AS INTEGER))
            FROM collection_state
            WHERE status = 'completed'
        """).fetchone()

        if row and row[0] is not None:
            return int(row[0])

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
    }

    try:

        result["matches"] = int(
            conn.execute(
                "SELECT COUNT(*) FROM matches"
            ).fetchone()[0]
        )

        result["odds"] = int(
            conn.execute(
                "SELECT COUNT(*) FROM odds"
            ).fetchone()[0]
        )

        result["bookmakers"] = int(
            conn.execute("""
                SELECT COUNT(DISTINCT bookmaker)
                FROM odds
                WHERE bookmaker IS NOT NULL
                  AND bookmaker != ''
            """).fetchone()[0]
        )

        result["results"] = int(
            conn.execute("""
                SELECT COUNT(*)
                FROM matches
                WHERE result IN ('승','무','패')
            """).fetchone()[0]
        )

        result["unresolved"] = int(
            conn.execute("""
                SELECT COUNT(*)
                FROM matches
                WHERE
                    result IS NULL
                    OR result = ''
                    OR home_score IS NULL
                    OR away_score IS NULL
            """).fetchone()[0]
        )

    except Exception as e:
        print(f"[DB 상태 오류] {e}")

    finally:

        try:
            conn.close()
        except Exception:
            pass

    return result


# ============================================================
# 업체
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
# 분석
# ============================================================

def get_analysis_rows(bookmaker=None):

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
                o.final_home,
                o.final_draw,
                o.final_away
            FROM matches m
            INNER JOIN odds o
                ON m.schedule_id = o.schedule_id
            WHERE m.result IN ('승','무','패')
        """

        params = []

        if bookmaker:
            sql += " AND o.bookmaker = ?"
            params.append(bookmaker)

        sql += """
            ORDER BY m.match_date DESC
        """

        rows = conn.execute(
            sql,
            tuple(params),
        ).fetchall()

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
                    "bookmaker": row[7],
                    "company_id": row[8],
                    "final_home": row[9],
                    "final_draw": row[10],
                    "final_away": row[11],
                })

        return result

    except Exception as e:

        print(f"[분석 데이터 오류] {e}")
        return []

    finally:

        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# 특정 경기
# ============================================================

def get_match_odds(schedule_id):

    conn = get_connection()

    try:

        rows = conn.execute("""
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
        """, (
            str(schedule_id),
        )).fetchall()

        result = []

        for row in rows:

            try:
                result.append(dict(row))
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

    conn = get_connection()

    try:

        page_count = conn.execute(
            "PRAGMA page_count"
        ).fetchone()

        page_size = conn.execute(
            "PRAGMA page_size"
        ).fetchone()

        pc = int(page_count[0]) if page_count else 0
        ps = int(page_size[0]) if page_size else 4096

        value = pc * ps

        return {
            "bytes": value,
            "mb": value / 1024 / 1024,
            "gb": value / 1024 / 1024 / 1024,
            "mode": "Turso",
        }

    except Exception:
        return {
            "bytes": 0,
            "mb": 0,
            "gb": 0,
            "mode": "unknown",
        }

    finally:

        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# 시작
# ============================================================

try:
    init_database()
except Exception as e:
    print(f"[DB 초기화 오류] {e}")
