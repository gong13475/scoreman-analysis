# ============================================================
# database.py
# 스코어맨 분석기
# Turso Cloud SQLite 영구저장 버전
# ============================================================

import streamlit as st
import libsql_experimental as libsql


# =========================================================
# Turso 연결
# =========================================================

@st.cache_resource
def get_connection():

    url = st.secrets.get(
        "TURSO_DATABASE_URL",
        ""
    ).strip()

    token = st.secrets.get(
        "TURSO_AUTH_TOKEN",
        ""
    ).strip()

    if not url:
        raise RuntimeError(
            "TURSO_DATABASE_URL이 없습니다.\n"
            "Streamlit Cloud → Settings → Secrets를 확인하세요."
        )

    if not token:
        raise RuntimeError(
            "TURSO_AUTH_TOKEN이 없습니다.\n"
            "Streamlit Cloud → Settings → Secrets를 확인하세요."
        )

    # libsql:// → https://
    if url.startswith("libsql://"):
        url = "https://" + url[len("libsql://"):]

    conn = libsql.connect(
        "historical-odds.db",
        sync_url=url,
        auth_token=token
    )

    return conn


# =========================================================
# SQL 실행
# =========================================================

def execute(sql, params=()):

    conn = get_connection()

    cursor = conn.execute(
        sql,
        params
    )

    conn.commit()

    return cursor


# =========================================================
# DB 초기화
# =========================================================

def init_database():

    try:

        conn = get_connection()

        # -------------------------------------------------
        # 경기 테이블
        # -------------------------------------------------

        conn.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id TEXT NOT NULL UNIQUE,
                match_date TEXT,
                home_team TEXT,
                away_team TEXT,
                home_score INTEGER,
                away_score INTEGER,
                result TEXT,
                source TEXT DEFAULT 'Scoreman',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # -------------------------------------------------
        # 배당 테이블
        # -------------------------------------------------

        conn.execute("""
            CREATE TABLE IF NOT EXISTS odds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id TEXT NOT NULL,
                bookmaker TEXT NOT NULL,
                home_odds REAL,
                draw_odds REAL,
                away_odds REAL,
                odds_type TEXT DEFAULT 'final',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (
                    schedule_id,
                    bookmaker,
                    odds_type
                )
            )
        """)

        # -------------------------------------------------
        # 인덱스
        # -------------------------------------------------

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_matches_date
            ON matches(match_date)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_matches_result
            ON matches(result)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_odds_schedule
            ON odds(schedule_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_odds_bookmaker
            ON odds(bookmaker)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_odds_values
            ON odds(
                bookmaker,
                home_odds,
                draw_odds,
                away_odds
            )
        """)

        conn.commit()

        # -------------------------------------------------
        # 테이블 확인
        # -------------------------------------------------

        conn.execute(
            "SELECT 1 FROM matches LIMIT 1"
        ).fetchone()

        conn.execute(
            "SELECT 1 FROM odds LIMIT 1"
        ).fetchone()

        return True

    except Exception as e:

        print(
            "Turso DB 초기화 오류:",
            e
        )

        return False


# =========================================================
# DB 상태
# =========================================================

def get_database_status():

    conn = get_connection()

    match_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM matches
        """
    ).fetchone()[0]

    odds_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM odds
        """
    ).fetchone()[0]

    bookmaker_count = conn.execute(
        """
        SELECT COUNT(
            DISTINCT bookmaker
        )
        FROM odds
        """
    ).fetchone()[0]

    return {

        "matches":
            int(match_count),

        "odds":
            int(odds_count),

        "bookmakers":
            int(bookmaker_count),

        "db_exists":
            True,

        "db_file":
            "Turso Cloud SQLite"
    }


# =========================================================
# 실제 DB 사용량
# =========================================================

def get_storage_usage():

    try:

        conn = get_connection()

        page_count = conn.execute(
            "PRAGMA page_count"
        ).fetchone()[0]

        page_size = conn.execute(
            "PRAGMA page_size"
        ).fetchone()[0]

        size_bytes = (
            int(page_count)
            * int(page_size)
        )

        return {

            "success":
                True,

            "size_bytes":
                size_bytes,

            "size_mb":
                size_bytes
                / 1024
                / 1024,

            "size_gb":
                size_bytes
                / 1024
                / 1024
                / 1024,

            "message":
                ""
        }

    except Exception as e:

        return {

            "success":
                False,

            "size_bytes":
                0,

            "size_mb":
                0,

            "size_gb":
                0,

            "message":
                str(e)
        }


# =========================================================
# 경기 저장
# =========================================================

def save_match(
    schedule_id,
    match_date,
    home_team,
    away_team,
    home_score,
    away_score,
    result,
    source="Scoreman"
):

    conn = get_connection()

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
            source,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)

        ON CONFLICT(schedule_id)
        DO UPDATE SET
            match_date = excluded.match_date,
            home_team = excluded.home_team,
            away_team = excluded.away_team,
            home_score = excluded.home_score,
            away_score = excluded.away_score,
            result = excluded.result,
            source = excluded.source,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            str(schedule_id),
            match_date,
            home_team,
            away_team,
            home_score,
            away_score,
            result,
            source
        )
    )

    conn.commit()

    return True


# =========================================================
# 단일 배당 저장
# =========================================================

def save_odds(
    schedule_id,
    company_id,
    company_name,
    final_home,
    final_draw,
    final_away
):

    conn = get_connection()

    conn.execute(
        """
        INSERT INTO odds (
            schedule_id,
            bookmaker,
            home_odds,
            draw_odds,
            away_odds,
            odds_type
        )
        VALUES (?, ?, ?, ?, ?, 'final')

        ON CONFLICT(
            schedule_id,
            bookmaker,
            odds_type
        )
        DO UPDATE SET
            home_odds = excluded.home_odds,
            draw_odds = excluded.draw_odds,
            away_odds = excluded.away_odds
        """,
        (
            str(schedule_id),
            str(company_name or ""),
            (
                float(final_home)
                if final_home is not None
                else None
            ),
            (
                float(final_draw)
                if final_draw is not None
                else None
            ),
            (
                float(final_away)
                if final_away is not None
                else None
            )
        )
    )

    conn.commit()

    return True


# =========================================================
# 경기 + 배당 일괄 저장
# =========================================================

def save_match_with_odds(
    match,
    odds_list
):

    conn = get_connection()

    schedule_id = str(
        match["schedule_id"]
    )

    # -----------------------------------------------------
    # 경기 저장
    # -----------------------------------------------------

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
            source,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)

        ON CONFLICT(schedule_id)
        DO UPDATE SET
            match_date = excluded.match_date,
            home_team = excluded.home_team,
            away_team = excluded.away_team,
            home_score = excluded.home_score,
            away_score = excluded.away_score,
            result = excluded.result,
            source = excluded.source,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            schedule_id,
            match.get("match_date", ""),
            match.get("home_team", ""),
            match.get("away_team", ""),
            match.get("home_score"),
            match.get("away_score"),
            match.get("result", ""),
            match.get("source", "Scoreman")
        )
    )

    # -----------------------------------------------------
    # 배당 저장
    # -----------------------------------------------------

    saved = 0

    for odds in (
        odds_list or []
    ):

        company_name = str(
            odds.get(
                "company_name",
                ""
            )
            or ""
        ).strip()

        if not company_name:
            continue

        conn.execute(
            """
            INSERT INTO odds (
                schedule_id,
                bookmaker,
                home_odds,
                draw_odds,
                away_odds,
                odds_type
            )
            VALUES (?, ?, ?, ?, ?, 'final')

            ON CONFLICT(
                schedule_id,
                bookmaker,
                odds_type
            )
            DO UPDATE SET
                home_odds = excluded.home_odds,
                draw_odds = excluded.draw_odds,
                away_odds = excluded.away_odds
            """,
            (
                schedule_id,
                company_name,
                odds.get("final_home"),
                odds.get("final_draw"),
                odds.get("final_away")
            )
        )

        saved += 1

    conn.commit()

    return saved


# =========================================================
# 경기 조회
# =========================================================

def get_match(
    schedule_id
):

    conn = get_connection()

    row = conn.execute(
        """
        SELECT *
        FROM matches
        WHERE schedule_id = ?
        LIMIT 1
        """,
        (
            str(schedule_id),
        )
    ).fetchone()

    if not row:
        return None

    columns = [
        "id",
        "schedule_id",
        "match_date",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "result",
        "source",
        "created_at",
        "updated_at"
    ]

    return dict(
        zip(columns, row)
    )


# =========================================================
# 전체 경기
# =========================================================

def get_all_matches():

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM matches
        ORDER BY match_date DESC
        """
    ).fetchall()

    columns = [
        "id",
        "schedule_id",
        "match_date",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "result",
        "source",
        "created_at",
        "updated_at"
    ]

    return [
        dict(zip(columns, row))
        for row in rows
    ]


# =========================================================
# 전체 배당
# =========================================================

def get_all_odds():

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM odds
        ORDER BY schedule_id DESC
        """
    ).fetchall()

    columns = [
        "id",
        "schedule_id",
        "bookmaker",
        "home_odds",
        "draw_odds",
        "away_odds",
        "odds_type",
        "created_at"
    ]

    return [
        dict(zip(columns, row))
        for row in rows
    ]


# =========================================================
# 특정 경기 배당
# =========================================================

def get_match_final_odds(
    schedule_id
):

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM odds
        WHERE schedule_id = ?
        AND odds_type = 'final'
        ORDER BY bookmaker
        """,
        (
            str(schedule_id),
        )
    ).fetchall()

    columns = [
        "id",
        "schedule_id",
        "bookmaker",
        "home_odds",
        "draw_odds",
        "away_odds",
        "odds_type",
        "created_at"
    ]

    return [
        dict(zip(columns, row))
        for row in rows
    ]


# =========================================================
# 경기 수
# =========================================================

def get_match_count():

    conn = get_connection()

    return int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM matches
            """
        ).fetchone()[0]
    )


# =========================================================
# 배당 수
# =========================================================

def get_odds_count():

    conn = get_connection()

    return int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM odds
            """
        ).fetchone()[0]
    )


# =========================================================
# 업체 목록
# =========================================================

def get_company_names():

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT DISTINCT bookmaker
        FROM odds
        WHERE bookmaker IS NOT NULL
        AND bookmaker != ''
        ORDER BY bookmaker
        """
    ).fetchall()

    return [
        str(row[0])
        for row in rows
    ]


# =========================================================
# 업체별 저장량
# =========================================================

def get_company_counts():

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            bookmaker,
            COUNT(*) AS cnt
        FROM odds
        WHERE bookmaker IS NOT NULL
        AND bookmaker != ''
        GROUP BY bookmaker
        ORDER BY cnt DESC
        """
    ).fetchall()

    return {
        str(row[0]): int(row[1])
        for row in rows
    }


# =========================================================
# 동일 배당 검색
# =========================================================

def search_multiple_final_odds(
    company_odds
):

    if not company_odds:
        return []

    conn = get_connection()

    schedule_ids = None

    tolerance = 0.00001

    for company_name, odds in (
        company_odds.items()
    ):

        home = float(
            odds["home"]
        )

        draw = float(
            odds["draw"]
        )

        away = float(
            odds["away"]
        )

        rows = conn.execute(
            """
            SELECT schedule_id
            FROM odds
            WHERE bookmaker = ?
            AND odds_type = 'final'

            AND home_odds >= ?
            AND home_odds <= ?

            AND draw_odds >= ?
            AND draw_odds <= ?

            AND away_odds >= ?
            AND away_odds <= ?
            """,
            (
                company_name,

                home - tolerance,
                home + tolerance,

                draw - tolerance,
                draw + tolerance,

                away - tolerance,
                away + tolerance
            )
        ).fetchall()

        ids = {
            str(row[0])
            for row in rows
        }

        if schedule_ids is None:

            schedule_ids = ids

        else:

            schedule_ids &= ids

        if not schedule_ids:
            return []

    if not schedule_ids:
        return []

    placeholders = ",".join(
        ["?"] * len(schedule_ids)
    )

    rows = conn.execute(
        f"""
        SELECT *
        FROM matches
        WHERE schedule_id IN (
            {placeholders}
        )
        ORDER BY match_date DESC
        """,
        tuple(schedule_ids)
    ).fetchall()

    columns = [
        "id",
        "schedule_id",
        "match_date",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "result",
        "source",
        "created_at",
        "updated_at"
    ]

    matches = [
        dict(zip(columns, row))
        for row in rows
    ]

    # -----------------------------------------------------
    # 업체별 배당 붙이기
    # -----------------------------------------------------

    for match in matches:

        sid = str(
            match["schedule_id"]
        )

        odds_rows = conn.execute(
            """
            SELECT
                bookmaker,
                home_odds,
                draw_odds,
                away_odds
            FROM odds
            WHERE schedule_id = ?
            AND odds_type = 'final'
            """,
            (sid,)
        ).fetchall()

        match["company_odds"] = {}

        for row in odds_rows:

            company = row[0]

            if company:

                match[
                    "company_odds"
                ][company] = {

                    "home":
                        row[1],

                    "draw":
                        row[2],

                    "away":
                        row[3]
                }

    return matches


# =========================================================
# DB 전체 삭제
# =========================================================

def clear_database():

    conn = get_connection()

    conn.execute(
        "DELETE FROM odds"
    )

    conn.execute(
        "DELETE FROM matches"
    )

    conn.commit()


# =========================================================
# 경기 존재 확인
# =========================================================

def match_exists(
    schedule_id
):

    return (
        get_match(
            schedule_id
        )
        is not None
    )


# =========================================================
# 배당 존재 확인
# =========================================================

def odds_exists(
    schedule_id,
    company_name
):

    conn = get_connection()

    row = conn.execute(
        """
        SELECT id
        FROM odds
        WHERE schedule_id = ?
        AND bookmaker = ?
        AND odds_type = 'final'
        LIMIT 1
        """,
        (
            str(schedule_id),
            str(company_name)
        )
    ).fetchone()

    return row is not None


# =========================================================
# 결과별 경기 조회
# =========================================================

def get_matches_by_result(
    result_value
):

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM matches
        WHERE result = ?
        ORDER BY match_date DESC
        """,
        (
            result_value,
        )
    ).fetchall()

    columns = [
        "id",
        "schedule_id",
        "match_date",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "result",
        "source",
        "created_at",
        "updated_at"
    ]

    return [
        dict(zip(columns, row))
        for row in rows
    ]


# =========================================================
# 특정 업체 배당
# =========================================================

def get_odds_by_company(
    company_name
):

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM odds
        WHERE bookmaker = ?
        AND odds_type = 'final'
        ORDER BY schedule_id DESC
        """,
        (
            company_name,
        )
    ).fetchall()

    columns = [
        "id",
        "schedule_id",
        "bookmaker",
        "home_odds",
        "draw_odds",
        "away_odds",
        "odds_type",
        "created_at"
    ]

    return [
        dict(zip(columns, row))
        for row in rows
    ]


# =========================================================
# 테스트
# =========================================================

if __name__ == "__main__":

    try:

        ok = init_database()

        if ok:

            print(
                "Turso 연결 성공"
            )

            print(
                get_database_status()
            )

            print(
                get_storage_usage()
            )

        else:

            print(
                "Turso 연결 실패"
            )

    except Exception as e:

        print(
            "오류:",
            e
        )
