# ============================================================
# database.py
# Scoreman 영구 DB
# SQLite / Turso(libsql)
#
# 주요 기능
# 1. Turso 영구 저장
# 2. 로컬 SQLite 지원
# 3. 경기 및 최종배당 저장
# 4. 수집 상태 UPSERT
# 5. 중복 배당 정리
# 6. 실패 / 진행 중 / 완료 상태 관리
# 7. 업체별 분석 데이터 조회
# 8. DB 상태 및 용량 조회
# ============================================================

import os
import sqlite3

from pathlib import Path
from datetime import datetime


# ============================================================
# 기본 설정
# ============================================================

DB_FILE = Path(__file__).resolve().parent / "scoreman.db"


def _get_setting(name):
    """
    환경변수 또는 Streamlit Secrets에서 설정을 읽는다.
    """

    value = os.getenv(name, "").strip()

    if value:
        return value

    try:
        import streamlit as st

        value = str(
            st.secrets.get(name, "")
        ).strip()

        if value:
            return value

        # [turso] 형태의 중첩 Secrets도 지원
        try:
            section = st.secrets.get("turso", {})

            value = str(
                section.get(name, "")
            ).strip()

            if value:
                return value

        except Exception:
            pass

    except Exception:
        pass

    return ""


TURSO_DATABASE_URL = _get_setting(
    "TURSO_DATABASE_URL"
)

TURSO_AUTH_TOKEN = _get_setting(
    "TURSO_AUTH_TOKEN"
)


_ACTIVE_MODE = "SQLite"


# ============================================================
# DB 연결
# ============================================================

def get_connection():

    global _ACTIVE_MODE

    # 설정이 일부만 존재하면 잘못된 연결로 판단
    if bool(TURSO_DATABASE_URL) != bool(TURSO_AUTH_TOKEN):

        _ACTIVE_MODE = "Turso 설정 오류"

        raise RuntimeError(
            "TURSO_DATABASE_URL과 TURSO_AUTH_TOKEN을 "
            "모두 설정해야 합니다."
        )

    # Turso 연결
    if TURSO_DATABASE_URL and TURSO_AUTH_TOKEN:

        try:

            import libsql

            conn = libsql.connect(
                TURSO_DATABASE_URL,
                auth_token=TURSO_AUTH_TOKEN,
            )

            _ACTIVE_MODE = "Turso"

            return conn

        except Exception as e:

            _ACTIVE_MODE = "Turso 연결 오류"

            raise RuntimeError(
                f"Turso 연결 실패: {e}"
            ) from e

    # 로컬 SQLite
    conn = sqlite3.connect(
        str(DB_FILE),
        check_same_thread=False,
        timeout=30,
    )

    conn.row_factory = sqlite3.Row

    try:

        conn.execute(
            "PRAGMA busy_timeout=30000"
        )

        conn.execute(
            "PRAGMA journal_mode=WAL"
        )

        conn.execute(
            "PRAGMA synchronous=NORMAL"
        )

    except Exception:
        pass

    _ACTIVE_MODE = "SQLite"

    return conn


# ============================================================
# 커밋
# ============================================================

def _commit(conn):

    # 커밋 실패를 무시하지 않는다.
    conn.commit()


# ============================================================
# 결과 행 변환
# ============================================================

def _row_to_dict(row, columns=None):

    if row is None:
        return None

    try:

        if isinstance(row, dict):
            return dict(row)

    except Exception:
        pass

    try:

        keys = row.keys()

        return {
            key: row[key]
            for key in keys
        }

    except Exception:
        pass

    if columns is not None:

        try:

            return {
                columns[index]: row[index]
                for index in range(
                    min(len(columns), len(row))
                )
            }

        except Exception:
            pass

    return None


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

        # 업체명이 없는 기존 배당 데이터 보정
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

        # 기존 중복 배당 정리
        conn.execute("""
            DELETE FROM odds

            WHERE id NOT IN (

                SELECT MIN(id)

                FROM odds

                GROUP BY
                    schedule_id,
                    bookmaker
            )
        """)

        _commit(conn)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_odds_schedule_id

            ON odds(schedule_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_state_status

            ON collection_state(status)
        """)

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

            if name in existing:
                continue

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
                        CASE

                            WHEN ? IS NOT NULL
                                 AND ? != ''

                            THEN ?

                            ELSE home_team

                        END,

                    away_team =
                        CASE

                            WHEN ? IS NOT NULL
                                 AND ? != ''

                            THEN ?

                            ELSE away_team

                        END,

                    home_score =
                        COALESCE(?, home_score),

                    away_score =
                        COALESCE(?, away_score),

                    result =
                        CASE

                            WHEN ? IN ('승','무','패')

                            THEN ?

                            ELSE result

                        END,

                    source =
                        COALESCE(?, source)

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
                away_score,

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
            f"{type(e).__name__}: {e}",
            flush=True,
        )

        return False

    finally:

        try:
            conn.close()
        except Exception:
            pass


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
            raise ValueError("배당 범위를 벗어났습니다.")

        # 업체 ID가 있으면 ID를 우선 사용
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

    except Exception as e:

        try:
            conn.rollback()
        except Exception:
            pass

        print(
            f"[배당 저장 실패] "
            f"ID={schedule_id} "
            f"업체={company_name} "
            f"{type(e).__name__}: {e}",
            flush=True,
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

        sid = str(schedule_id)

        now = datetime.now().isoformat(
            timespec="seconds"
        )

        # SELECT 후 INSERT하는 방식 대신 UPSERT 사용
        # UNIQUE constraint failed: collection_state.id 방지

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

    except Exception as e:

        try:
            conn.rollback()
        except Exception:
            pass

        print(
            f"[상태 저장 오류] "
            f"ID={schedule_id} "
            f"{type(e).__name__}: {e}",
            flush=True,
        )

        return False

    finally:

        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# 수집 완료 여부
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

        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# 마지막 정상 완료 ID
# ============================================================

def get_last_completed_id():

    conn = get_connection()

    try:

        row = conn.execute("""
            SELECT MAX(CAST(id AS INTEGER))

            FROM collection_state

            WHERE status = 'completed'
              AND id GLOB '[0-9]*'
        """).fetchone()

        if row and row[0] is not None:
            return int(row[0])

        return None

    finally:

        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# 실패 / 중단된 수집 ID
# ============================================================

def get_first_pending_id(
    start_id,
    end_id,
):

    conn = get_connection()

    try:

        row = conn.execute("""
            SELECT MIN(CAST(id AS INTEGER))

            FROM collection_state

            WHERE status IN (
                'failed',
                'in_progress'
            )

              AND id GLOB '[0-9]*'

              AND CAST(id AS INTEGER) >= ?

              AND CAST(id AS INTEGER) <= ?

        """, (
            int(start_id),
            int(end_id),
        )).fetchone()

        if row and row[0] is not None:
            return int(row[0])

        return None

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

    columns = [

        "schedule_id",
        "match_date",

        "home_team",
        "away_team",

        "home_score",
        "away_score",

        "result",
    ]

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

            item = _row_to_dict(
                row,
                columns,
            )

            if item is not None:
                result.append(item)

        return result

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

        return result

    finally:

        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# 업체 목록
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

        result = []

        for row in rows:

            try:

                result.append({

                    "bookmaker": row["bookmaker"],

                    "odds_count": int(
                        row["odds_count"]
                    ),

                    "games": int(
                        row["games"]
                    ),
                })

            except Exception:

                result.append({

                    "bookmaker": row[0],

                    "odds_count": int(row[1]),

                    "games": int(row[2]),
                })

        return result

    finally:

        try:
            conn.close()
        except Exception:
            pass


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

            sql += """
                AND o.bookmaker = ?
            """

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

            item = _row_to_dict(
                row,
                columns,
            )

            if item is not None:
                result.append(item)

        return result

    finally:

        try:
            conn.close()
        except Exception:
            pass


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

        result = []

        for row in rows:

            item = _row_to_dict(
                row,
                columns,
            )

            if item is not None:
                result.append(item)

        return result

    finally:

        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# DB 용량
# ============================================================

def get_database_size():

    mode = _ACTIVE_MODE

    if mode == "Turso":

        conn = get_connection()

        try:

            try:

                page_count = conn.execute(
                    "PRAGMA page_count"
                ).fetchone()

                page_size = conn.execute(
                    "PRAGMA page_size"
                ).fetchone()

                pages = int(
                    page_count[0]
                ) if page_count else 0

                size = int(
                    page_size[0]
                ) if page_size else 4096

                value = pages * size

            except Exception:

                value = 0

            return {

                "bytes": value,

                "mb": value / 1024 / 1024,

                "gb": value / 1024 / 1024 / 1024,

                "mode": "Turso",
            }

        finally:

            try:
                conn.close()
            except Exception:
                pass

    if mode != "SQLite":

        return {

            "bytes": 0,
            "mb": 0,
            "gb": 0,

            "mode": mode,
        }

    try:

        value = (
            DB_FILE.stat().st_size
            if DB_FILE.exists()
            else 0
        )

        wal_file = Path(
            str(DB_FILE) + "-wal"
        )

        if wal_file.exists():
            value += wal_file.stat().st_size

        return {

            "bytes": value,

            "mb": value / 1024 / 1024,

            "gb": value / 1024 / 1024 / 1024,

            "mode": "SQLite",
        }

    except Exception:

        return {

            "bytes": 0,
            "mb": 0,
            "gb": 0,

            "mode": mode,
                }
