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

            schedule_id TEXT UNIQUE NOT NULL,

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

    # -----------------------------------------------------
    # 배당 테이블
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS odds (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            schedule_id TEXT NOT NULL,

            company_id TEXT NOT NULL,

            company_name TEXT,

            initial_home REAL,

            initial_draw REAL,

            initial_away REAL,

            final_home REAL,

            final_draw REAL,

            final_away REAL,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(
                schedule_id,
                company_id
            )
        )
    """)

    # -----------------------------------------------------
    # 경기 인덱스
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

    # -----------------------------------------------------
    # 배당 인덱스
    # -----------------------------------------------------

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

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_odds_initial
        ON odds(
            initial_home,
            initial_draw,
            initial_away
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_odds_final
        ON odds(
            final_home,
            final_draw,
            final_away
        )
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
            source,
            updated_at

        )

        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?,
            CURRENT_TIMESTAMP
        )

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
                excluded.source,

            updated_at =
                CURRENT_TIMESTAMP
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
# 업체별 배당 저장
# =========================================================

def save_odds(
    schedule_id,
    company_id,
    company_name,
    initial_home,
    initial_draw,
    initial_away,
    final_home,
    final_draw,
    final_away
):

    if company_id is None:
        company_id = ""

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
            final_away,

            updated_at

        )

        VALUES (
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            CURRENT_TIMESTAMP
        )

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
                excluded.final_away,

            updated_at =
                CURRENT_TIMESTAMP
    """, (

        str(schedule_id),
        str(company_id),
        company_name,

        initial_home,
        initial_draw,
        initial_away,

        final_home,
        final_draw,
        final_away

    ))

    conn.commit()
    conn.close()


# =========================================================
# 경기 + 배당 한번에 저장
# =========================================================

def save_match_with_odds(
    match,
    odds_list
):

    save_match(

        schedule_id=match["schedule_id"],

        match_date=match.get(
            "match_date"
        ),

        home_team=match.get(
            "home_team"
        ),

        away_team=match.get(
            "away_team"
        ),

        home_score=match.get(
            "home_score"
        ),

        away_score=match.get(
            "away_score"
        ),

        result=match.get(
            "result"
        ),

        source=match.get(
            "source",
            "Scoreman"
        )
    )

    for odds in odds_list:

        save_odds(

            schedule_id=match["schedule_id"],

            company_id=odds.get(
                "company_id"
            ),

            company_name=odds.get(
                "company_name",
                ""
            ),

            initial_home=odds.get(
                "initial_home"
            ),

            initial_draw=odds.get(
                "initial_draw"
            ),

            initial_away=odds.get(
                "initial_away"
            ),

            final_home=odds.get(
                "final_home"
            ),

            final_draw=odds.get(
                "final_draw"
            ),

            final_away=odds.get(
                "final_away"
            )
        )


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

    result = cursor.fetchone()[0]

    conn.close()

    return int(result)


# =========================================================
# 배당 행 수
# =========================================================

def get_odds_count():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM odds
    """)

    result = cursor.fetchone()[0]

    conn.close()

    return int(result)


# =========================================================
# 업체 수
# =========================================================

def get_company_count():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(
            DISTINCT company_id
        )

        FROM odds

        WHERE company_id != ''
    """)

    result = cursor.fetchone()[0]

    conn.close()

    return int(result)


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

        GROUP BY
            company_id,
            company_name

        ORDER BY
            match_count DESC,
            company_name ASC
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows


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
# =========================================================

def get_all_odds():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT

            schedule_id,

            company_id,

            company_name,

            initial_home,
            initial_draw,
            initial_away,

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
# 특정 경기의 모든 업체 배당
# =========================================================

def get_match_odds(schedule_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *

        FROM odds

        WHERE schedule_id = ?

        ORDER BY company_name ASC
    """, (
        str(schedule_id),
    ))

    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# 특정 업체의 전체 배당
# =========================================================

def get_company_odds(company_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT

            o.*,

            m.match_date,
            m.home_team,
            m.away_team,
            m.home_score,
            m.away_score,
            m.result

        FROM odds o

        LEFT JOIN matches m
            ON o.schedule_id =
               m.schedule_id

        WHERE o.company_id = ?

        ORDER BY
            m.match_date DESC
    """, (
        str(company_id),
    ))

    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# 특정 연도의 경기
# =========================================================

def get_matches_by_year(year):

    year = str(year)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *

        FROM matches

        WHERE substr(
            match_date,
            1,
            4
        ) = ?

        ORDER BY match_date DESC
    """, (
        year,
    ))

    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# 특정 연도의 전체 배당
# =========================================================

def get_odds_by_year(year):

    year = str(year)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT

            o.*,

            m.match_date,
            m.home_team,
            m.away_team,
            m.home_score,
            m.away_score,
            m.result

        FROM odds o

        INNER JOIN matches m
            ON o.schedule_id =
               m.schedule_id

        WHERE substr(
            m.match_date,
            1,
            4
        ) = ?

        ORDER BY
            m.match_date DESC
    """, (
        year,
    ))

    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# 저장된 연도 목록
# =========================================================

def get_available_years():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT
            substr(match_date, 1, 4)
            AS year

        FROM matches

        WHERE match_date IS NOT NULL

        AND length(match_date) >= 4

        ORDER BY year DESC
    """)

    rows = cursor.fetchall()

    conn.close()

    return [
        row["year"]
        for row in rows
        if row["year"]
    ]


# =========================================================
# 경기 존재 여부
# =========================================================

def match_exists(schedule_id):

    return (
        get_match(schedule_id)
        is not None
    )


# =========================================================
# 특정 업체 배당 존재 여부
# =========================================================

def odds_exists(
    schedule_id,
    company_id
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 1

        FROM odds

        WHERE schedule_id = ?

        AND company_id = ?

        LIMIT 1
    """, (
        str(schedule_id),
        str(company_id)
    ))

    result = cursor.fetchone()

    conn.close()

    return result is not None


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
# DB 테스트
# =========================================================

if __name__ == "__main__":

    init_database()

    print(
        "================================"
    )

    print(
        "SQLite DB 정상 초기화"
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
        get_company_count()
    )

    print(
        "업체 목록:"
    )

    for company in get_companies():

        print(
            company["company_id"],
            company["company_name"],
            company["match_count"]
        )

    print(
        "================================"
    )
