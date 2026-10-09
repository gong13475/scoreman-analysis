# ============================================================
# database.py
# Scoreman 해외배당 영구 데이터베이스
# SQLite / Turso(libsql)
# ============================================================

import os
import sqlite3

from pathlib import Path
from datetime import datetime


# ============================================================
# 기본 설정
# ============================================================

DB_FILE = Path(__file__).resolve().parent / "scoreman.db"

_ACTIVE_MODE = "SQLite"


# ============================================================
# 환경변수 / Streamlit Secrets
# ============================================================

def _get_setting(name):

    value = os.getenv(name, "").strip()

    if value:
        return value

    try:
        import streamlit as st

        value = str(st.secrets.get(name, "")).strip()

        if value:
            return value

        try:
            section = st.secrets.get("turso", {})

            value = str(section.get(name, "")).strip()

            if value:
                return value

        except Exception:
            pass

    except Exception:
        pass

    return ""


TURSO_DATABASE_URL = _get_setting("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = _get_setting("TURSO_AUTH_TOKEN")


# ============================================================
# 연결
# ============================================================

def get_connection():

    global _ACTIVE_MODE

    if bool(TURSO_DATABASE_URL) != bool(TURSO_AUTH_TOKEN):

        _ACTIVE_MODE = "Turso 설정 오류"

        raise RuntimeError(
            "TURSO_DATABASE_URL과 TURSO_AUTH_TOKEN을 "
            "모두 설정해야 합니다."
        )

    if TURSO_DATABASE_URL and TURSO_AUTH_TOKEN:

        try:
            import libsql

            conn = libsql.connect(
                TURSO_DATABASE_URL,
                auth_token=TURSO_AUTH_TOKEN,
            )

            _ACTIVE_MODE = "Turso"

            return conn

        except Exception as error:

            _ACTIVE_MODE = "Turso 연결 오류"

            raise RuntimeError(
                f"Turso 연결 실패: {error}"
            ) from error

    conn = sqlite3.connect(
        str(DB_FILE),
        check_same_thread=False,
        timeout=30,
    )

    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    _ACTIVE_MODE = "SQLite"

    return conn


# ============================================================
# 공통 함수
# ============================================================

def _commit(conn):
    conn.commit()


def _row_to_dict(row, columns=None):

    if row is None:
        return None

    if isinstance(row, dict):
        return dict(row)

    try:
        return {
            key: row[key]
            for key in row.keys()
        }

    except Exception:
        pass

    if columns:

        try:
            return {
                columns[i]: row[i]
                for i in range(min(len(columns), len(row)))
            }

        except Exception:
            pass

    return None


def _scalar(conn, sql, params=()):

    row = conn.execute(sql, params).fetchone()

    if row is None:
        return 0

    return row[0] or 0


# ============================================================
# DB 초기화
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

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_odds_schedule_id
            ON odds(schedule_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_odds_bookmaker
            ON odds(bookmaker)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_collection_status
            ON collection_state(status)
        """)

        conn.execute("""
            UPDATE odds

            SET bookmaker =
                CASE

                    WHEN company_name IS NOT NULL
                         AND TRIM(company_name) != ''

                    THEN TRIM(company_name)

                    WHEN company_id IS NOT NULL
                         AND TRIM(company_id) != ''

                    THEN 'CID_' || TRIM(company_id)

                    ELSE 'UNKNOWN'

                END

            WHERE bookmaker IS NULL
               OR TRIM(bookmaker) = ''
        """)

        _commit(conn)

    finally:

        conn.close()


# ============================================================
# 기존 DB 컬럼 보정
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

        rows = conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()

        existing = set()

        for row in rows:

            try:
                existing.add(row["name"])

            except Exception:
                existing.add(row[1])

        for name, data_type in columns.items():

            if name not in existing:

                conn.execute(
                    f"ALTER TABLE {table} "
                    f"ADD COLUMN {name} {data_type}"
                )

    _commit(conn)


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

            ON CONFLICT(schedule_id)

            DO UPDATE SET

                match_date =
                    COALESCE(excluded.match_date, matches.match_date),

                home_team =
                    COALESCE(NULLIF(excluded.home_team, ''), matches.home_team),

                away_team =
                    COALESCE(NULLIF(excluded.away_team, ''), matches.away_team),

                home_score =
                    COALESCE(excluded.home_score, matches.home_score),

                away_score =
                    COALESCE(excluded.away_score, matches.away_score),

                result =
                    COALESCE(excluded.result, matches.result),

                source =
                    COALESCE(excluded.source, matches.source)

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

    except Exception as error:

        try:
            conn.rollback()
        except Exception:
            pass

        print(
            f"[경기 저장 실패] ID={schedule_id}: {error}",
            flush=True,
        )

        return False

    finally:

        conn.close()


# ============================================================
# 최종배당 저장
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

        cid = str(company_id or "").strip()

        cname = str(company_name or "").strip()

        bookmaker = cname or f"CID_{cid}"

        home = float(final_home)
        draw = float(final_draw)
        away = float(final_away)

        if min(home, draw, away) <= 0:
            raise ValueError("배당은 0보다 커야 합니다.")

        if max(home, draw, away) > 1000:
            raise ValueError("배당 범위 오류")

        if cid:

            row = conn.execute("""
                SELECT id

                FROM odds

                WHERE schedule_id = ?
                  AND company_id = ?

                LIMIT 1
            """, (
                sid,
                cid,
            )).fetchone()

        else:

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
                home,
                draw,
                away,
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
                home,
                draw,
                away,
            ))

        _commit(conn)

        return True

    except Exception as error:

        try:
            conn.rollback()
        except Exception:
            pass

        print(
            f"[배당 저장 실패] ID={schedule_id} "
            f"업체={company_name}: {error}",
            flush=True,
        )

        return False

    finally:

        conn.close()


# ============================================================
# 수집 상태 저장
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

        conn.execute("""
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

        """, (
            sid,
            str(status),
            now,
        ))

        _commit(conn)

        return True

    except Exception as error:

        try:
            conn.rollback()
        except Exception:
            pass

        print(
            f"[상태 저장 오류] ID={schedule_id}: {error}",
            flush=True,
        )

        return False

    finally:

        conn.close()


# ============================================================
# 업체별 수집 상태
#
# 전체 경기 완료 상태와 특정 업체 수집 상태를 분리한다.
# 특정 업체만 수집했다고 전체 업체 수집 완료로 처리하지 않는다.
# ============================================================

def _company_state_id(schedule_id, company_name):

    company = str(company_name or "").strip().casefold()

    return f"{schedule_id}::company::{company}"


def save_company_collection_state(
    schedule_id,
    company_name,
    status="completed",
):

    state_id = _company_state_id(
        schedule_id,
        company_name,
    )

    return save_collection_state(
        state_id,
        status,
    )


def is_company_collection_completed(
    schedule_id,
    company_name,
):

    conn = get_connection()

    try:

        state_id = _company_state_id(
            schedule_id,
            company_name,
        )

        row = conn.execute("""
            SELECT status

            FROM collection_state

            WHERE id = ?

            LIMIT 1
        """, (
            state_id,
        )).fetchone()

        if not row:
            return False

        try:
            status = row["status"]
        except Exception:
            status = row[0]

        return str(status) == "completed"

    finally:

        conn.close()


# ============================================================
# 전체 경기 수집 완료 여부
# ============================================================

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
            status = row["status"]
        except Exception:
            status = row[0]

        return str(status) == "completed"

    finally:

        conn.close()


# ============================================================
# 마지막 전체 수집 완료 ID
# ============================================================

def get_last_completed_id():

    conn = get_connection()

    try:

        row = conn.execute("""
            SELECT MAX(CAST(id AS INTEGER))

            FROM collection_state

            WHERE status = 'completed'

              AND id GLOB '[0-9]*'

              AND id NOT LIKE '%::company::%'

        """).fetchone()

        if row and row[0] is not None:
            return int(row[0])

        return None

    finally:

        conn.close()


# ============================================================
# 실패 / 진행 중 / 부분 수집 ID
# ============================================================

def get_first_pending_id(
    start_id,
    end_id,
    include_partial=True,
):

    conn = get_connection()

    try:

        statuses = [
            "failed",
            "in_progress",
        ]

        if include_partial:
            statuses.append("partial")

        placeholders = ",".join(
            "?" for _ in statuses
        )

        row = conn.execute(f"""
            SELECT MIN(CAST(id AS INTEGER))

            FROM collection_state

            WHERE status IN ({placeholders})

              AND id GLOB '[0-9]*'

              AND id NOT LIKE '%::company::%'

              AND CAST(id AS INTEGER) >= ?

              AND CAST(id AS INTEGER) <= ?

        """, tuple(statuses) + (
            int(start_id),
            int(end_id),
        )).fetchone()

        if row and row[0] is not None:
            return int(row[0])

        return None

    finally:

        conn.close()


# ============================================================
# 결과 미확인 경기
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

        columns = [
            "schedule_id",
            "match_date",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
            "result",
        ]

        return [
            _row_to_dict(row, columns)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# DB 상태
# ============================================================

def get_database_status():

    conn = get_connection()

    try:

        return {

            "matches": int(
                _scalar(
                    conn,
                    "SELECT COUNT(*) FROM matches",
                )
            ),

            "odds": int(
                _scalar(
                    conn,
                    "SELECT COUNT(*) FROM odds",
                )
            ),

            "bookmakers": int(
                _scalar(
                    conn,
                    """
                    SELECT COUNT(DISTINCT bookmaker)

                    FROM odds

                    WHERE bookmaker IS NOT NULL
                      AND bookmaker != ''
                    """,
                )
            ),

            "results": int(
                _scalar(
                    conn,
                    """
                    SELECT COUNT(*)

                    FROM matches

                    WHERE result IN ('승','무','패')
                    """,
                )
            ),

            "unresolved": int(
                _scalar(
                    conn,
                    """
                    SELECT COUNT(*)

                    FROM matches

                    WHERE

                        result IS NULL

                        OR result = ''

                        OR home_score IS NULL

                        OR away_score IS NULL
                    """,
                )
            ),
        }

    finally:

        conn.close()


# ============================================================
# 업체별 경기 수
# ============================================================

def get_bookmakers():

    conn = get_connection()

    try:

        rows = conn.execute("""
            SELECT

                bookmaker,

                COUNT(*) AS odds_count,

                COUNT(DISTINCT schedule_id) AS games

            FROM odds

            WHERE bookmaker IS NOT NULL
              AND bookmaker != ''

            GROUP BY bookmaker

            ORDER BY games DESC, bookmaker

        """).fetchall()

        columns = [
            "bookmaker",
            "odds_count",
            "games",
        ]

        result = []

        for row in rows:

            item = _row_to_dict(row, columns)

            if item:

                item["odds_count"] = int(
                    item.get("odds_count") or 0
                )

                item["games"] = int(
                    item.get("games") or 0
                )

                result.append(item)

        return result

    finally:

        conn.close()


# ============================================================
# 분석 데이터
# ============================================================

def get_analysis_rows(bookmaker=None):

    conn = get_connection()

    columns = [
        "schedule_id",
        "match_date",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "result",
        "bookmaker",
        "company_id",
        "final_home",
        "final_draw",
        "final_away",
    ]

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

        sql += " ORDER BY m.match_date DESC"

        rows = conn.execute(
            sql,
            tuple(params),
        ).fetchall()

        return [
            _row_to_dict(row, columns)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# 특정 경기 및 배당
# ============================================================

def get_match_odds(schedule_id):

    conn = get_connection()

    try:

        rows = conn.execute("""
            SELECT

                m.schedule_id,
                m.match_date,

                m.home_team,
                m.away_team,

                m.home_score,
                m.away_score,

                m.result,

                o.company_id,
                o.company_name,
                o.bookmaker,

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

        columns = [
            "schedule_id",
            "match_date",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
            "result",
            "company_id",
            "company_name",
            "bookmaker",
            "final_home",
            "final_draw",
            "final_away",
        ]

        return [
            _row_to_dict(row, columns)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# DB 용량
# ============================================================

def get_database_size():

    mode = _ACTIVE_MODE

    # --------------------------------------------------------
    # Turso: SQL로 계산한 데이터 크기 추정치
    #
    # 이 값은 Turso 계정의 실제 과금 용량이나 할당량이 아니다.
    # --------------------------------------------------------

    if mode == "Turso":

        conn = get_connection()

        try:

            total = 0

            queries = [

                """
                SELECT COALESCE(
                    SUM(
                        LENGTH(COALESCE(schedule_id, ''))
                        + LENGTH(COALESCE(match_date, ''))
                        + LENGTH(COALESCE(home_team, ''))
                        + LENGTH(COALESCE(away_team, ''))
                        + LENGTH(COALESCE(result, ''))
                        + LENGTH(COALESCE(source, ''))
                    ),
                    0
                )

                FROM matches
                """,

                """
                SELECT COALESCE(
                    SUM(
                        LENGTH(COALESCE(schedule_id, ''))
                        + LENGTH(COALESCE(company_id, ''))
                        + LENGTH(COALESCE(company_name, ''))
                        + LENGTH(COALESCE(bookmaker, ''))
                        + LENGTH(CAST(COALESCE(final_home, 0) AS TEXT))
                        + LENGTH(CAST(COALESCE(final_draw, 0) AS TEXT))
                        + LENGTH(CAST(COALESCE(final_away, 0) AS TEXT))
                    ),
                    0
                )

                FROM odds
                """,

                """
                SELECT COALESCE(
                    SUM(
                        LENGTH(COALESCE(id, ''))
                        + LENGTH(COALESCE(status, ''))
                        + LENGTH(COALESCE(updated_at, ''))
                    ),
                    0
                )

                FROM collection_state
                """,
            ]

            try:

                for query in queries:

                    row = conn.execute(query).fetchone()

                    if row:
                        total += int(row[0] or 0)

            except Exception:
                total = 0

            return {

                "bytes": total,

                "mb": total / 1024 / 1024,

                "gb": total / 1024 / 1024 / 1024,

                "mode": "Turso",

                "estimated": True,
            }

        finally:

            conn.close()

    # --------------------------------------------------------
    # SQLite: 실제 로컬 파일 크기
    # --------------------------------------------------------

    if mode == "SQLite":

        total = 0

        for path in (
            DB_FILE,
            Path(str(DB_FILE) + "-wal"),
            Path(str(DB_FILE) + "-shm"),
        ):

            try:

                if path.exists():
                    total += path.stat().st_size

            except Exception:
                pass

        return {

            "bytes": total,

            "mb": total / 1024 / 1024,

            "gb": total / 1024 / 1024 / 1024,

            "mode": "SQLite",

            "estimated": False,
        }

    return {

        "bytes": 0,

        "mb": 0,

        "gb": 0,

        "mode": mode,

        "estimated": True,
    }
