# ============================================================
# database.py
# ⚽ Scoreman 분석 DB - 최종 교체본
#
# - Turso 영구 저장
# - SQLite fallback
# - 경기 저장
# - 최종배당 저장
# - 업체별 통계
# - 동일배당 검색
# - 수집 상태 저장
# - Turso 용량 조회
# - collector.py 완전 연동
# ============================================================

import os
import json
import sqlite3
from pathlib import Path


# ============================================================
# 기본 설정
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DB_FILE = BASE_DIR / "scoreman.db"

TURSO_DATABASE_URL = os.getenv(
    "TURSO_DATABASE_URL",
    ""
).strip()

TURSO_AUTH_TOKEN = os.getenv(
    "TURSO_AUTH_TOKEN",
    ""
).strip()


# ============================================================
# libSQL
# ============================================================

try:
    import libsql_experimental as libsql

    LIBSQL_AVAILABLE = True

except Exception:
    libsql = None
    LIBSQL_AVAILABLE = False


# ============================================================
# Turso 사용 여부
# ============================================================

def _use_turso():
    return bool(
        TURSO_DATABASE_URL
        and TURSO_AUTH_TOKEN
        and LIBSQL_AVAILABLE
    )


# ============================================================
# DB 연결
# ============================================================

def get_connection():

    if _use_turso():

        return libsql.connect(
            TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN
        )

    conn = sqlite3.connect(
        str(DB_FILE),
        timeout=30,
        check_same_thread=False
    )

    return conn


# ============================================================
# SQL 실행
# ============================================================

def _execute(
    sql,
    params=(),
    fetch=False,
    many=False
):

    conn = get_connection()

    try:

        cur = conn.cursor()

        if many:
            cur.executemany(
                sql,
                params
            )
        else:
            cur.execute(
                sql,
                params
            )

        if fetch:
            return cur.fetchall()

        conn.commit()

        return []

    finally:

        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# DB 초기화
# ============================================================

def init_database():

    # --------------------------------------------------------
    # matches
    # --------------------------------------------------------

    _execute(
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

    # --------------------------------------------------------
    # odds
    # --------------------------------------------------------

    _execute(
        """
        CREATE TABLE IF NOT EXISTS odds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id TEXT NOT NULL,
            company_id TEXT,
            company_name TEXT NOT NULL,
            final_home REAL,
            final_draw REAL,
            final_away REAL,
            UNIQUE(schedule_id, company_name)
        )
        """
    )

    # --------------------------------------------------------
    # collection_state
    # --------------------------------------------------------

    _execute(
        """
        CREATE TABLE IF NOT EXISTS collection_state (
            id INTEGER PRIMARY KEY,
            start_id INTEGER,
            end_id INTEGER,
            last_completed_id INTEGER,
            current INTEGER,
            total INTEGER,
            running INTEGER,
            stopped INTEGER,
            selected_companies TEXT
        )
        """
    )


# ============================================================
# 경기 저장
# ============================================================

def save_match(match):

    _execute(
        """
        INSERT OR REPLACE INTO matches (
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
        """,
        (
            str(match.get("schedule_id", "")),
            match.get("match_date", ""),
            match.get("home_team", ""),
            match.get("away_team", ""),
            match.get("home_score"),
            match.get("away_score"),
            match.get("result", ""),
            match.get("source", "scoreman")
        )
    )


# ============================================================
# 경기 + 배당 저장
# ============================================================

def save_match_with_odds(
    match,
    odds_list
):

    save_match(match)

    saved = 0

    for row in odds_list:

        try:

            company_name = str(
                row.get(
                    "company_name",
                    ""
                )
            ).strip()

            if not company_name:
                continue

            _execute(
                """
                INSERT OR REPLACE INTO odds (
                    schedule_id,
                    company_id,
                    company_name,
                    final_home,
                    final_draw,
                    final_away
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(
                        match.get(
                            "schedule_id",
                            ""
                        )
                    ),
                    str(
                        row.get(
                            "company_id",
                            ""
                        )
                    ),
                    company_name,
                    float(
                        row.get(
                            "final_home"
                        )
                    ),
                    float(
                        row.get(
                            "final_draw"
                        )
                    ),
                    float(
                        row.get(
                            "final_away"
                        )
                    )
                )
            )

            saved += 1

        except Exception:
            continue

    return saved


# ============================================================
# 경기 조회
# ============================================================

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
            source
        FROM matches
        WHERE schedule_id = ?
        LIMIT 1
        """,
        (
            str(schedule_id),
        ),
        fetch=True
    )

    if not rows:
        return None

    row = rows[0]

    return {
        "schedule_id": row[0],
        "match_date": row[1],
        "home_team": row[2],
        "away_team": row[3],
        "home_score": row[4],
        "away_score": row[5],
        "result": row[6],
        "source": row[7]
    }


# ============================================================
# 전체 경기
# ============================================================

def get_all_matches():

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
            source
        FROM matches
        ORDER BY schedule_id DESC
        """,
        fetch=True
    )

    return [
        {
            "schedule_id": row[0],
            "match_date": row[1],
            "home_team": row[2],
            "away_team": row[3],
            "home_score": row[4],
            "away_score": row[5],
            "result": row[6],
            "source": row[7]
        }
        for row in rows
    ]


# ============================================================
# 경기별 배당
# ============================================================

def get_odds_by_match(schedule_id):

    rows = _execute(
        """
        SELECT
            company_id,
            company_name,
            final_home,
            final_draw,
            final_away
        FROM odds
        WHERE schedule_id = ?
        ORDER BY company_name
        """,
        (
            str(schedule_id),
        ),
        fetch=True
    )

    return [
        {
            "company_id": row[0],
            "company_name": row[1],
            "bookmaker": row[1],
            "final_home": row[2],
            "final_draw": row[3],
            "final_away": row[4],
            "home_odds": row[2],
            "draw_odds": row[3],
            "away_odds": row[4]
        }
        for row in rows
    ]


# ============================================================
# 업체 목록
# ============================================================

def get_company_list():

    rows = _execute(
        """
        SELECT DISTINCT company_name
        FROM odds
        WHERE company_name IS NOT NULL
          AND TRIM(company_name) <> ''
        ORDER BY company_name
        """,
        fetch=True
    )

    return [
        str(row[0])
        for row in rows
        if row[0]
    ]


# ============================================================
# 업체별 저장 경기 수
# ============================================================

def get_company_counts():

    try:

        rows = _execute(
            """
            SELECT
                company_name,
                COUNT(DISTINCT schedule_id)
            FROM odds
            WHERE company_name IS NOT NULL
              AND TRIM(company_name) <> ''
            GROUP BY company_name
            ORDER BY COUNT(DISTINCT schedule_id) DESC
            """,
            fetch=True
        )

        return {
            str(row[0]): int(row[1] or 0)
            for row in rows
        }

    except Exception:
        return {}


# ============================================================
# DB 상태
# ============================================================

def get_database_status():

    try:
        matches = int(
            _execute(
                """
                SELECT COUNT(*)
                FROM matches
                """,
                fetch=True
            )[0][0]
        )
    except Exception:
        matches = 0

    try:
        odds = int(
            _execute(
                """
                SELECT COUNT(*)
                FROM odds
                """,
                fetch=True
            )[0][0]
        )
    except Exception:
        odds = 0

    try:
        bookmakers = int(
            _execute(
                """
                SELECT COUNT(DISTINCT company_name)
                FROM odds
                WHERE company_name IS NOT NULL
                  AND TRIM(company_name) <> ''
                """,
                fetch=True
            )[0][0]
        )
    except Exception:
        bookmakers = 0

    return {
        "matches": matches,
        "odds": odds,
        "bookmakers": bookmakers
    }


# ============================================================
# DB 연결 정보
# ============================================================

def get_database_info():

    return {
        "database_url_configured":
            bool(TURSO_DATABASE_URL),

        "auth_token_configured":
            bool(TURSO_AUTH_TOKEN),

        "libsql_available":
            bool(LIBSQL_AVAILABLE),

        "using_turso":
            bool(_use_turso())
    }


# ============================================================
# 수집 상태 저장
# ============================================================

def save_collection_state(
    start_id,
    end_id,
    last_completed_id,
    current,
    total,
    running,
    stopped,
    selected_companies=None
):

    selected_json = json.dumps(
        selected_companies,
        ensure_ascii=False
    )

    _execute(
        """
        INSERT OR REPLACE INTO collection_state (
            id,
            start_id,
            end_id,
            last_completed_id,
            current,
            total,
            running,
            stopped,
            selected_companies
        )
        VALUES (
            1, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            int(start_id),
            int(end_id),
            int(last_completed_id or 0),
            int(current or 0),
            int(total or 0),
            1 if running else 0,
            1 if stopped else 0,
            selected_json
        )
    )


# ============================================================
# 수집 상태 조회
# ============================================================

def get_collection_state():

    try:

        rows = _execute(
            """
            SELECT
                start_id,
                end_id,
                last_completed_id,
                current,
                total,
                running,
                stopped,
                selected_companies
            FROM collection_state
            WHERE id = 1
            LIMIT 1
            """,
            fetch=True
        )

        if not rows:

            return {
                "start_id": None,
                "end_id": None,
                "last_completed_id": 0,
                "current": 0,
                "total": 0,
                "running": False,
                "stopped": False,
                "selected_companies": None
            }

        row = rows[0]

        try:
            selected = json.loads(
                row[7]
            )
        except Exception:
            selected = None

        return {
            "start_id": row[0],
            "end_id": row[1],
            "last_completed_id": row[2],
            "current": row[3],
            "total": row[4],
            "running": bool(row[5]),
            "stopped": bool(row[6]),
            "selected_companies": selected
        }

    except Exception:
        return {}


# ============================================================
# 저장용량
# ============================================================

def get_storage_usage():

    # --------------------------------------------------------
    # Turso / libSQL
    # --------------------------------------------------------

    if _use_turso():

        try:

            rows = _execute(
                """
                PRAGMA page_count
                """,
                fetch=True
            )

            page_count = 0

            if rows:
                page_count = int(
                    rows[0][0] or 0
                )

            rows = _execute(
                """
                PRAGMA page_size
                """,
                fetch=True
            )

            page_size = 0

            if rows:
                page_size = int(
                    rows[0][0] or 0
                )

            size_bytes = (
                page_count * page_size
            )

            size_mb = (
                size_bytes
                / 1024
                / 1024
            )

            return {
                "success": True,
                "size_mb": size_mb,
                "size_gb": size_mb / 1024,
                "storage_type": "Turso"
            }

        except Exception:
            pass

    # --------------------------------------------------------
    # SQLite
    # --------------------------------------------------------

    try:

        if DB_FILE.exists():

            size_bytes = (
                DB_FILE.stat().st_size
            )

            size_mb = (
                size_bytes
                / 1024
                / 1024
            )

            return {
                "success": True,
                "size_mb": size_mb,
                "size_gb": size_mb / 1024,
                "storage_type": "SQLite"
            }

    except Exception:
        pass

    return {
        "success": False,
        "size_mb": 0,
        "size_gb": 0,
        "storage_type": "SQLite",
        "error":
            "DB 저장 용량을 확인할 수 없습니다."
    }


# ============================================================
# 동일배당 검색
# ============================================================

def search_same_odds(
    company_name,
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.0001
):

    rows = _execute(
        """
        SELECT
            m.schedule_id,
            m.match_date,
            m.home_team,
            m.away_team,
            m.home_score,
            m.away_score,
            m.result,
            o.company_name,
            o.final_home,
            o.final_draw,
            o.final_away
        FROM odds o
        JOIN matches m
          ON m.schedule_id = o.schedule_id
        WHERE LOWER(TRIM(o.company_name))
              = LOWER(TRIM(?))
          AND ABS(o.final_home - ?) <= ?
          AND ABS(o.final_draw - ?) <= ?
          AND ABS(o.final_away - ?) <= ?
        ORDER BY m.match_date DESC
        """,
        (
            company_name,
            float(home_odds),
            float(tolerance),
            float(draw_odds),
            float(tolerance),
            float(away_odds),
            float(tolerance)
        ),
        fetch=True
    )

    return [
        {
            "schedule_id": row[0],
            "match_date": row[1],
            "home_team": row[2],
            "away_team": row[3],
            "home_score": row[4],
            "away_score": row[5],
            "result": row[6],
            "bookmaker": row[7],
            "company_name": row[7],
            "home_odds": row[8],
            "draw_odds": row[9],
            "away_odds": row[10]
        }
        for row in rows
    ]


# ============================================================
# 수동 분석용 전체 동일배당 검색
# ============================================================

def search_same_odds_all_companies(
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.0001
):

    rows = _execute(
        """
        SELECT
            m.schedule_id,
            m.match_date,
            m.home_team,
            m.away_team,
            m.home_score,
            m.away_score,
            m.result,
            o.company_name,
            o.final_home,
            o.final_draw,
            o.final_away
        FROM odds o
        JOIN matches m
          ON m.schedule_id = o.schedule_id
        WHERE ABS(o.final_home - ?) <= ?
          AND ABS(o.final_draw - ?) <= ?
          AND ABS(o.final_away - ?) <= ?
        ORDER BY m.match_date DESC
        """,
        (
            float(home_odds),
            float(tolerance),
            float(draw_odds),
            float(tolerance),
            float(away_odds),
            float(tolerance)
        ),
        fetch=True
    )

    return [
        {
            "schedule_id": row[0],
            "match_date": row[1],
            "home_team": row[2],
            "away_team": row[3],
            "home_score": row[4],
            "away_score": row[5],
            "result": row[6],
            "company_name": row[7],
            "home_odds": row[8],
            "draw_odds": row[9],
            "away_odds": row[10]
        }
        for row in rows
    ]


# ============================================================
# 모듈 로드 시 DB 초기화
# ============================================================

try:
    init_database()
except Exception:
    pass
