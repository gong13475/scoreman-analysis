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
# 연결
# =========================================================

def get_connection():

    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


# =========================================================
# 초기화
# =========================================================

def init_database():

    conn = get_connection()
    cursor = conn.cursor()

    # -----------------------------------------------------
    # 경기
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
    # 업체별 배당
    #
    # 기존 초기배당 컬럼은 호환성을 위해 유지
    # 실제 신규 수집에서는 최종배당만 사용
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
# =========================================================
#
# 중요:
# 신규 크롤링에서는 초기배당을 저장하지 않는다.
#
# initial_home/draw/away
# → 항상 None
#
# final_home/draw/away
# → 실제 최종배당 저장
#
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

            initial_home =
                excluded.initial_home,

            initial_draw =
                excluded.initial_draw,

            initial_away =
                excluded.initial_away,

            final_home =
                excluded.final_home,

            final_draw =
                excluded.final_draw,

            final_away =
                excluded.final_away

    """, (

        str(schedule_id),

        str(company_id)
        if company_id is not None
        else "",

        company_name,

        # -------------------------------------------------
        # 초기배당은 저장하지 않음
        # -------------------------------------------------

        None,
        None,
        None,

        # -------------------------------------------------
        # 최종배당만 저장
        # -------------------------------------------------

        final_home,
        final_draw,
        final_away

    ))

    conn.commit()
    conn.close()


# =========================================================
# 경기 수
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
# 배당 수
# =========================================================

def get_odds_count():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM odds
        WHERE
            final_home IS NOT NULL
            AND final_draw IS NOT NULL
            AND final_away IS NOT NULL
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
                OR match_date = ''
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
# 전체 최종배당
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

        WHERE
            final_home IS NOT NULL
            AND final_draw IS NOT NULL
            AND final_away IS NOT NULL

        ORDER BY id DESC
    """)

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

        WHERE
            company_name IS NOT NULL
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
# 특정 경기 최종배당
# =========================================================

def get_match_odds(schedule_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT

            id,
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
# 최종배당 완전일치 검색
# =========================================================
#
# 선택한 업체들의
#
# final_home
# final_draw
# final_away
#
# 3개가 모두 일치하는 경기만 반환
#
# =========================================================

def search_exact_final_odds(
    company_odds
):

    """
    company_odds 예:

    [
        {
            "company_name": "Bet365",
            "home": 1.50,
            "draw": 3.50,
            "away": 5.00
        },

        {
            "company_name": "William Hill",
            "home": 1.55,
            "draw": 3.45,
            "away": 4.90
        }
    ]
    """

    if not company_odds:
        return []

    conn = get_connection()
    cursor = conn.cursor()

    conditions = []
    params = []

    for item in company_odds:

        company_name = str(
            item.get(
                "company_name",
                ""
            )
        ).strip()

        home = item.get("home")
        draw = item.get("draw")
        away = item.get("away")

        if (
            not company_name
            or home is None
            or draw is None
            or away is None
        ):
            continue

        conditions.append("""
            EXISTS (

                SELECT 1

                FROM odds o

                WHERE

                    o.schedule_id =
                        m.schedule_id

                    AND LOWER(
                        TRIM(o.company_name)
                    ) = LOWER(
                        TRIM(?)
                    )

                    AND o.final_home = ?
                    AND o.final_draw = ?
                    AND o.final_away = ?
            )
        """)

        params.extend([
            company_name,
            float(home),
            float(draw),
            float(away)
        ])

    if not conditions:

        conn.close()

        return []

    sql = f"""
        SELECT

            m.schedule_id,
            m.match_date,
            m.home_team,
            m.away_team,
            m.home_score,
            m.away_score,
            m.result,
            m.source

        FROM matches m

        WHERE

            {" AND ".join(conditions)}

        ORDER BY

            CASE
                WHEN m.match_date IS NULL
                OR m.match_date = ''
                THEN 1
                ELSE 0
            END,

            m.match_date DESC,

            m.id DESC
    """

    cursor.execute(
        sql,
        params
    )

    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# 경기 + 최종배당 상세
# =========================================================

def get_match_with_odds(
    schedule_id
):

    match = get_match(
        schedule_id
    )

    if match is None:
        return None

    odds = get_match_odds(
        schedule_id
    )

    return {
        "match": match,
        "odds": odds
    }


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
# 초기화
# =========================================================

init_database()


# =========================================================
# 직접 실행
# =========================================================

if __name__ == "__main__":

    init_database()

    print(
        "================================"
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
        "경기 수:",
        get_match_count()
    )

    print(
        "최종배당 수:",
        get_odds_count()
    )

    print(
        "업체 수:",
        len(get_companies())
    )

    print(
        "================================"
    )
