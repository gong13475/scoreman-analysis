import sqlite3
from pathlib import Path


# =========================================================
# DB 파일
# =========================================================

DB_FILE = (
    Path(__file__).resolve().parent
    / "historical_odds.db"
)


# =========================================================
# DB 연결
# =========================================================

def get_connection():

    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


# =========================================================
# DB 초기화
# =========================================================

def init_database():

    conn = get_connection()
    cursor = conn.cursor()

    # -----------------------------------------------------
    # 경기 테이블
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            schedule_id TEXT UNIQUE,

            match_date TEXT,

            home_team TEXT,

            away_team TEXT,

            home_score INTEGER,

            away_score INTEGER,

            result TEXT,

            source TEXT DEFAULT 'Scoreman',

            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -----------------------------------------------------
    # 배당 테이블
    #
    # 기존 구조와 호환
    # 초기배당 컬럼은 남겨두지만
    # 현재 크롤러에서는 NULL만 저장
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS odds (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            schedule_id TEXT,

            company_id TEXT,

            company_name TEXT,

            initial_home REAL,

            initial_draw REAL,

            initial_away REAL,

            final_home REAL,

            final_draw REAL,

            final_away REAL,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(
                schedule_id,
                company_id
            )
        )
    """)

    # -----------------------------------------------------
    # 인덱스
    # -----------------------------------------------------

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_matches_schedule
        ON matches(schedule_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_matches_date
        ON matches(match_date)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_odds_schedule
        ON odds(schedule_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_odds_company
        ON odds(company_name)
    """)

    conn.commit()
    conn.close()


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
    cursor = conn.cursor()

    cursor.execute("""
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
                excluded.match_date,

            home_team =
                excluded.home_team,

            away_team =
                excluded.away_team,

            home_score =
                excluded.home_score,

            away_score =
                excluded.away_score,

            result =
                excluded.result,

            source =
                excluded.source
    """, (

        str(schedule_id),

        match_date,

        home_team,

        away_team,

        home_score,

        away_score,

        result,

        source
    ))

    conn.commit()
    conn.close()


# =========================================================
# 최종배당 저장
#
# 초기배당은 사용하지 않음
# =========================================================

def save_odds(
    schedule_id,
    company_id,
    company_name,
    initial_home=None,
    initial_draw=None,
    initial_away=None,
    final_home=None,
    final_draw=None,
    final_away=None
):

    conn = get_connection()
    cursor = conn.cursor()

    # -----------------------------------------------------
    # 현재 정책:
    # 초기배당은 무조건 NULL
    # -----------------------------------------------------

    initial_home = None
    initial_draw = None
    initial_away = None

    cursor.execute("""
        INSERT INTO odds (

            schedule_id,
            company_id,
            company_name,

            initial_home,
            initial_draw,
            initial_away,

            final_home,
            final_draw,
            final_away

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(
            schedule_id,
            company_id
        )

        DO UPDATE SET

            company_name =
                excluded.company_name,

            initial_home = NULL,

            initial_draw = NULL,

            initial_away = NULL,

            final_home =
                excluded.final_home,

            final_draw =
                excluded.final_draw,

            final_away =
                excluded.final_away
    """, (

        str(schedule_id),

        (
            str(company_id)
            if company_id is not None
            else ""
        ),

        company_name,

        None,
        None,
        None,

        final_home,
        final_draw,
        final_away
    ))

    conn.commit()
    conn.close()


# =========================================================
# 경기 개수
# =========================================================

def get_match_count():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM matches
    """)

    count = cursor.fetchone()[0]

    conn.close()

    return count


# =========================================================
# 배당 개수
# =========================================================

def get_odds_count():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM odds
    """)

    count = cursor.fetchone()[0]

    conn.close()

    return count


# =========================================================
# 전체 경기
# =========================================================

def get_all_matches():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
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

        ORDER BY

            CASE
                WHEN match_date IS NULL
                THEN 1
                ELSE 0
            END,

            match_date DESC,

            id DESC
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# 전체 배당
#
# 최종배당만 반환
# =========================================================

def get_all_odds():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT

            schedule_id,

            company_id,

            company_name,

            final_home,
            final_draw,
            final_away

        FROM odds

        ORDER BY id DESC
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# 특정 경기
# =========================================================

def get_match(schedule_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *

        FROM matches

        WHERE schedule_id = ?

        LIMIT 1
    """, (
        str(schedule_id),
    ))

    row = cursor.fetchone()

    conn.close()

    return row


# =========================================================
# 특정 경기 배당
#
# 최종배당만 반환
# =========================================================

def get_match_odds(schedule_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT

            schedule_id,

            company_id,

            company_name,

            final_home,
            final_draw,
            final_away

        FROM odds

        WHERE schedule_id = ?

        ORDER BY company_name
    """, (
        str(schedule_id),
    ))

    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# 업체 목록
# =========================================================

def get_companies():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT

            company_id,

            company_name,

            COUNT(*) AS match_count

        FROM odds

        WHERE company_name IS NOT NULL

        AND TRIM(company_name) != ''

        GROUP BY
            company_id,
            company_name

        ORDER BY
            company_name
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# 업체명만 가져오기
# =========================================================

def get_company_names():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT
            company_name

        FROM odds

        WHERE company_name IS NOT NULL

        AND TRIM(company_name) != ''

        ORDER BY company_name
    """)

    rows = cursor.fetchall()

    conn.close()

    return [
        row["company_name"]
        for row in rows
    ]


# =========================================================
# 최종배당 검색
#
# 업체 1개
# 최종 승/무/패 일치
# =========================================================

def search_final_odds(
    company_name,
    final_home,
    final_draw,
    final_away
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
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

            o.final_home,
            o.final_draw,
            o.final_away

        FROM odds o

        INNER JOIN matches m
            ON m.schedule_id = o.schedule_id

        WHERE

            o.company_name = ?

            AND o.final_home = ?

            AND o.final_draw = ?

            AND o.final_away = ?

        ORDER BY
            m.match_date DESC
    """, (

        company_name,

        final_home,

        final_draw,

        final_away
    ))

    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# 여러 업체 최종배당 완전 일치 검색
#
# 업체별:
#
# {
#     "Bet365": {
#         "home": 1.5,
#         "draw": 3.5,
#         "away": 5.0
#     },
#
#     "William Hill": {
#         ...
#     }
# }
#
# 선택한 모든 업체의 배당이
# 같은 경기에서 전부 일치해야 반환
# =========================================================

def search_multiple_final_odds(
    company_odds
):

    if not company_odds:
        return []

    conn = get_connection()
    cursor = conn.cursor()

    conditions = []
    params = []

    for company_name, odds in company_odds.items():

        if not isinstance(
            odds,
            dict
        ):
            continue

        final_home = odds.get(
            "home"
        )

        final_draw = odds.get(
            "draw"
        )

        final_away = odds.get(
            "away"
        )

        if (
            final_home is None
            or final_draw is None
            or final_away is None
        ):
            continue

        conditions.append("""
            EXISTS (

                SELECT 1

                FROM odds o

                WHERE

                    o.schedule_id = m.schedule_id

                    AND o.company_name = ?

                    AND o.final_home = ?

                    AND o.final_draw = ?

                    AND o.final_away = ?
            )
        """)

        params.extend([

            company_name,

            final_home,

            final_draw,

            final_away
        ])

    if not conditions:

        conn.close()

        return []

    query = f"""
        SELECT

            m.schedule_id,
            m.match_date,
            m.home_team,
            m.away_team,
            m.home_score,
            m.away_score,
            m.result

        FROM matches m

        WHERE

            {" AND ".join(conditions)}

        ORDER BY

            m.match_date DESC,

            m.id DESC
    """

    cursor.execute(
        query,
        params
    )

    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# 경기별 업체 최종배당
# =========================================================

def get_match_final_odds(
    schedule_id
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT

            company_id,
            company_name,

            final_home,
            final_draw,
            final_away

        FROM odds

        WHERE schedule_id = ?

        ORDER BY company_name
    """, (
        str(schedule_id),
    ))

    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# DB 전체 삭제
# =========================================================

def clear_database():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM odds
    """)

    cursor.execute("""
        DELETE FROM matches
    """)

    conn.commit()
    conn.close()


# =========================================================
# 초기배당 데이터 정리
#
# 기존 DB에 남아 있는 초기배당을 NULL로 변경
# =========================================================

def clear_initial_odds():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE odds

        SET

            initial_home = NULL,

            initial_draw = NULL,

            initial_away = NULL
    """)

    changed = cursor.rowcount

    conn.commit()
    conn.close()

    return changed


# =========================================================
# 최종배당이 없는 데이터 개수
# =========================================================

def get_empty_final_odds_count():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)

        FROM odds

        WHERE

            final_home IS NULL

            OR final_draw IS NULL

            OR final_away IS NULL
    """)

    count = cursor.fetchone()[0]

    conn.close()

    return count


# =========================================================
# DB 테스트
# =========================================================

if __name__ == "__main__":

    init_database()

    print(
        "========================================"
    )

    print(
        "SQLite DB 초기화 완료"
    )

    print(
        "DB 위치:"
    )

    print(
        DB_FILE
    )

    print(
        "전체 경기:",
        get_match_count()
    )

    print(
        "전체 배당:",
        get_odds_count()
    )

    print(
        "업체 수:",
        len(get_company_names())
    )

    print(
        "최종배당 누락:",
        get_empty_final_odds_count()
    )

    print(
        "========================================"
    )
