# ============================================================
# database.py
# ⚽ Scoreman 분석 DB - 최종 안정화판
#
# 기존 기능 유지
# - Turso 영구 저장
# - SQLite fallback
# - 경기 저장
# - 최종배당 저장
# - 업체별 통계
# - 동일배당 검색
# - 수집 상태 저장
# - Turso 용량 조회
# - collector.py 연동
# - 수동배당 저장
# - 수동배당 확률
# - 실제 결과 대비 부족확률
#
# 핵심 수정
# - 배당 입력 시 완전 동일배당 검색
# - 승/무/패 모두 소수점 2자리까지 동일해야 검색
# - 예: 1.83 / 3.50 / 4.20
#   → DB의 1.83 / 3.50 / 4.20만 검색
# - 1.83 / 3.50 / 4.21 → 제외
# - 1.84 / 3.50 / 4.20 → 제외
# ============================================================

import os
import json
import sqlite3
import time
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

    try:
        conn.execute(
            "PRAGMA busy_timeout = 30000"
        )
    except Exception:
        pass

    return conn


# ============================================================
# SQLITE_BUSY 판단
# ============================================================

def _is_busy_error(error):

    text = str(error).lower()

    keywords = [
        "sqlite_busy",
        "database is locked",
        "database table is locked",
        "busy",
        "stream error",
        "interactive transaction",
        "rolled back because the stream was idle",
        "retry the transaction"
    ]

    return any(
        keyword in text
        for keyword in keywords
    )


# ============================================================
# SQL 실행
# ============================================================

def _execute(
    sql,
    params=(),
    fetch=False,
    many=False,
    retries=4
):

    last_error = None

    for attempt in range(retries):

        conn = None

        try:

            conn = get_connection()

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

                rows = cur.fetchall()

                try:
                    conn.close()
                except Exception:
                    pass

                return rows

            conn.commit()

            try:
                conn.close()
            except Exception:
                pass

            return []

        except Exception as e:

            last_error = e

            try:

                if conn is not None:
                    conn.rollback()

            except Exception:
                pass

            try:

                if conn is not None:
                    conn.close()

            except Exception:
                pass

            if not _is_busy_error(e):

                raise

            wait = 0.5 * (attempt + 1)

            time.sleep(wait)

    if last_error is not None:

        raise last_error

    return []


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

    # --------------------------------------------------------
    # manual_odds
    # --------------------------------------------------------

    _execute(
        """
        CREATE TABLE IF NOT EXISTS manual_odds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id TEXT,
            company_name TEXT NOT NULL,
            home_odds REAL,
            draw_odds REAL,
            away_odds REAL,
            result TEXT,
            home_probability REAL,
            draw_probability REAL,
            away_probability REAL,
            result_probability REAL,
            shortage_probability REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
            str(
                match.get(
                    "schedule_id",
                    ""
                )
            ),
            match.get(
                "match_date",
                ""
            ),
            match.get(
                "home_team",
                ""
            ),
            match.get(
                "away_team",
                ""
            ),
            match.get(
                "home_score"
            ),
            match.get(
                "away_score"
            ),
            match.get(
                "result",
                ""
            ),
            match.get(
                "source",
                "scoreman"
            )
        )
    )

    return True


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

            final_home = row.get(
                "final_home"
            )

            final_draw = row.get(
                "final_draw"
            )

            final_away = row.get(
                "final_away"
            )

            if (
                final_home is None
                or final_draw is None
                or final_away is None
            ):
                continue

            final_home = round(
                float(final_home),
                2
            )

            final_draw = round(
                float(final_draw),
                2
            )

            final_away = round(
                float(final_away),
                2
            )

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
                    final_home,
                    final_draw,
                    final_away
                ),
                retries=4
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

    companies = [
        str(row[0])
        for row in rows
        if row[0]
    ]

    try:

        manual_rows = _execute(
            """
            SELECT DISTINCT company_name
            FROM manual_odds
            WHERE company_name IS NOT NULL
              AND TRIM(company_name) <> ''
            ORDER BY company_name
            """,
            fetch=True
        )

        for row in manual_rows:

            name = str(
                row[0]
            ).strip()

            if name and name not in companies:

                companies.append(name)

    except Exception:
        pass

    return sorted(
        companies,
        key=lambda x: x.lower()
    )


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
            str(row[0]): int(
                row[1] or 0
            )
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

    try:

        manual_odds = int(
            _execute(
                """
                SELECT COUNT(*)
                FROM manual_odds
                """,
                fetch=True
            )[0][0]
        )

    except Exception:

        manual_odds = 0

    return {
        "matches": matches,
        "odds": odds,
        "bookmakers": bookmakers,
        "manual_odds": manual_odds
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

    if selected_companies is None:

        selected_companies = []

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
            int(start_id or 0),
            int(end_id or 0),
            int(last_completed_id or 0),
            int(current or 0),
            int(total or 0),
            1 if running else 0,
            1 if stopped else 0,
            selected_json
        ),
        retries=4
    )

    return True


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


# ============================================================
# 이어받기 시작 ID
# ============================================================

def get_resume_id():

    state = get_collection_state()

    try:

        last_id = int(
            state.get(
                "last_completed_id",
                0
            ) or 0
        )

        end_id = int(
            state.get(
                "end_id",
                0
            ) or 0
        )

        if last_id > 0:

            next_id = last_id + 1

            if end_id <= 0:
                return next_id

            if next_id <= end_id:
                return next_id

    except Exception:

        pass

    return None


# ============================================================
# 배당 확률 계산
# ============================================================

def calculate_odds_probabilities(
    home_odds,
    draw_odds,
    away_odds
):

    home_odds = float(home_odds)
    draw_odds = float(draw_odds)
    away_odds = float(away_odds)

    if (
        home_odds <= 0
        or draw_odds <= 0
        or away_odds <= 0
    ):

        raise ValueError(
            "승/무/패 배당은 0보다 커야 합니다."
        )

    raw_home = 1.0 / home_odds
    raw_draw = 1.0 / draw_odds
    raw_away = 1.0 / away_odds

    total = (
        raw_home
        + raw_draw
        + raw_away
    )

    normalized_home = (
        raw_home / total
    )

    normalized_draw = (
        raw_draw / total
    )

    normalized_away = (
        raw_away / total
    )

    return {

        "home_probability":
            raw_home * 100,

        "draw_probability":
            raw_draw * 100,

        "away_probability":
            raw_away * 100,

        "home_normalized_probability":
            normalized_home * 100,

        "draw_normalized_probability":
            normalized_draw * 100,

        "away_normalized_probability":
            normalized_away * 100,

        "overround":
            total * 100
    }


# ============================================================
# 실제 결과의 배당상 확률
# ============================================================

def get_result_probability(
    result,
    probabilities
):

    result = str(
        result or ""
    ).strip()

    result_upper = result.upper()

    if result in (
        "승",
        "홈",
        "H",
        "HOME"
    ) or result_upper == "WIN":

        return float(
            probabilities[
                "home_normalized_probability"
            ]
        )

    if result in (
        "무",
        "D",
        "DRAW"
    ) or result_upper == "DRAW":

        return float(
            probabilities[
                "draw_normalized_probability"
            ]
        )

    if result in (
        "패",
        "원정",
        "A",
        "AWAY"
    ) or result_upper in (
        "LOSE",
        "LOSS"
    ):

        return float(
            probabilities[
                "away_normalized_probability"
            ]
        )

    return 0.0


# ============================================================
# 부족확률
# ============================================================

def calculate_shortage_probability(
    result,
    probabilities,
    expected_probability=None
):

    result_probability = get_result_probability(
        result,
        probabilities
    )

    if expected_probability is None:

        return {
            "result_probability":
                result_probability,

            "expected_probability":
                None,

            "shortage_probability":
                None
        }

    expected_probability = float(
        expected_probability
    )

    shortage = (
        expected_probability
        - result_probability
    )

    return {
        "result_probability":
            result_probability,

        "expected_probability":
            expected_probability,

        "shortage_probability":
            shortage
    }


# ============================================================
# 수동배당 저장
# ============================================================

def save_manual_odds(
    schedule_id,
    company_name,
    home_odds,
    draw_odds,
    away_odds,
    result=""
):

    company_name = str(
        company_name or ""
    ).strip()

    if not company_name:

        raise ValueError(
            "회사를 선택해주세요."
        )

    probabilities = calculate_odds_probabilities(
        home_odds,
        draw_odds,
        away_odds
    )

    result_probability = get_result_probability(
        result,
        probabilities
    )

    _execute(
        """
        INSERT INTO manual_odds (
            schedule_id,
            company_name,
            home_odds,
            draw_odds,
            away_odds,
            result,
            home_probability,
            draw_probability,
            away_probability,
            result_probability,
            shortage_probability
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(schedule_id or ""),
            company_name,
            round(float(home_odds), 2),
            round(float(draw_odds), 2),
            round(float(away_odds), 2),
            str(result or ""),
            probabilities[
                "home_normalized_probability"
            ],
            probabilities[
                "draw_normalized_probability"
            ],
            probabilities[
                "away_normalized_probability"
            ],
            result_probability,
            None
        ),
        retries=4
    )

    return {
        "schedule_id":
            str(schedule_id or ""),

        "company_name":
            company_name,

        "home_odds":
            round(float(home_odds), 2),

        "draw_odds":
            round(float(draw_odds), 2),

        "away_odds":
            round(float(away_odds), 2),

        "result":
            str(result or ""),

        "home_probability":
            probabilities[
                "home_normalized_probability"
            ],

        "draw_probability":
            probabilities[
                "draw_normalized_probability"
            ],

        "away_probability":
            probabilities[
                "away_normalized_probability"
            ],

        "result_probability":
            result_probability,

        "shortage_probability":
            None,

        "overround":
            probabilities[
                "overround"
            ]
    }


# ============================================================
# 수동배당 조회
# ============================================================

def get_manual_odds(
    schedule_id=None,
    company_name=None
):

    conditions = []
    params = []

    if schedule_id is not None:

        conditions.append(
            "schedule_id = ?"
        )

        params.append(
            str(schedule_id)
        )

    if company_name:

        conditions.append(
            """
            LOWER(TRIM(company_name))
            = LOWER(TRIM(?))
            """
        )

        params.append(
            str(company_name)
        )

    where = ""

    if conditions:

        where = (
            "WHERE "
            + " AND ".join(
                conditions
            )
        )

    rows = _execute(
        f"""
        SELECT
            id,
            schedule_id,
            company_name,
            home_odds,
            draw_odds,
            away_odds,
            result,
            home_probability,
            draw_probability,
            away_probability,
            result_probability,
            shortage_probability,
            created_at
        FROM manual_odds
        {where}
        ORDER BY id DESC
        """,
        tuple(params),
        fetch=True
    )

    return [
        {
            "id": row[0],
            "schedule_id": row[1],
            "company_name": row[2],
            "home_odds": row[3],
            "draw_odds": row[4],
            "away_odds": row[5],
            "result": row[6],
            "home_probability": row[7],
            "draw_probability": row[8],
            "away_probability": row[9],
            "result_probability": row[10],
            "shortage_probability": row[11],
            "created_at": row[12]
        }
        for row in rows
    ]


# ============================================================
# 수동배당 부족확률 업데이트
# ============================================================

def update_manual_shortage(
    manual_id,
    expected_probability
):

    rows = _execute(
        """
        SELECT
            result_probability
        FROM manual_odds
        WHERE id = ?
        LIMIT 1
        """,
        (
            int(manual_id),
        ),
        fetch=True
    )

    if not rows:

        return False

    result_probability = float(
        rows[0][0] or 0
    )

    expected_probability = float(
        expected_probability
    )

    shortage = (
        expected_probability
        - result_probability
    )

    _execute(
        """
        UPDATE manual_odds
        SET
            shortage_probability = ?
        WHERE id = ?
        """,
        (
            shortage,
            int(manual_id)
        ),
        retries=4
    )

    return True


# ============================================================
# ============================================================
# ⭐ 완전 동일배당 검색
# ============================================================
#
# 핵심 규칙
#
# 입력:
#   1.83 / 3.50 / 4.20
#
# DB:
#   1.83 / 3.50 / 4.20  → 검색
#
# DB:
#   1.83 / 3.50 / 4.21  → 제외
#
# DB:
#   1.84 / 3.50 / 4.20  → 제외
#
# DB:
#   1.83 / 3.51 / 4.20  → 제외
#
# 즉 승/무/패 3개 모두 소수점 2자리까지 완전히 같아야 한다.
#
# 업체명도 완전히 같은 업체만 검색한다.
# 대소문자/앞뒤 공백은 무시한다.
# ============================================================

def search_same_odds(
    company_name,
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.0001
):

    # --------------------------------------------------------
    # 입력값을 소수점 2자리로 고정
    # --------------------------------------------------------

    home_odds = round(
        float(home_odds),
        2
    )

    draw_odds = round(
        float(draw_odds),
        2
    )

    away_odds = round(
        float(away_odds),
        2
    )

    # --------------------------------------------------------
    # tolerance는 호환성을 위해 인자로 유지하지만
    # 실제 검색은 ROUND(..., 2) 완전일치 사용
    # --------------------------------------------------------

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

          AND ROUND(CAST(o.final_home AS REAL), 2)
              = ROUND(CAST(? AS REAL), 2)

          AND ROUND(CAST(o.final_draw AS REAL), 2)
              = ROUND(CAST(? AS REAL), 2)

          AND ROUND(CAST(o.final_away AS REAL), 2)
              = ROUND(CAST(? AS REAL), 2)

        ORDER BY m.match_date DESC
        """,
        (
            str(company_name),
            home_odds,
            draw_odds,
            away_odds
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
# 전체 업체 완전 동일배당 검색
# ============================================================

def search_same_odds_all_companies(
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.0001
):

    home_odds = round(
        float(home_odds),
        2
    )

    draw_odds = round(
        float(draw_odds),
        2
    )

    away_odds = round(
        float(away_odds),
        2
    )

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

        WHERE ROUND(CAST(o.final_home AS REAL), 2)
              = ROUND(CAST(? AS REAL), 2)

          AND ROUND(CAST(o.final_draw AS REAL), 2)
              = ROUND(CAST(? AS REAL), 2)

          AND ROUND(CAST(o.final_away AS REAL), 2)
              = ROUND(CAST(? AS REAL), 2)

        ORDER BY m.match_date DESC
        """,
        (
            home_odds,
            draw_odds,
            away_odds
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
# 완전 동일배당 개수
# ============================================================

def count_same_odds(
    company_name,
    home_odds,
    draw_odds,
    away_odds
):

    rows = search_same_odds(
        company_name,
        home_odds,
        draw_odds,
        away_odds
    )

    return len(rows)


# ============================================================
# 마지막 완료 ID
# ============================================================

def get_last_completed_id():

    state = get_collection_state()

    try:

        return int(
            state.get(
                "last_completed_id",
                0
            ) or 0
        )

    except Exception:

        return 0


# ============================================================
# DB 저장 테스트
# ============================================================

def test_database_connection():

    try:

        rows = _execute(
            """
            SELECT 1
            """,
            fetch=True,
            retries=4
        )

        return bool(
            rows
            and rows[0][0] == 1
        )

    except Exception:

        return False


# ============================================================
# 저장용량
# ============================================================

def get_storage_usage():

    # --------------------------------------------------------
    # Turso
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
                page_count
                * page_size
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
# 모듈 로드 시 DB 초기화
# ============================================================

try:

    init_database()

except Exception:

    pass
