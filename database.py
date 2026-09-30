import sqlite3
import os


DB_FILE = "historical_odds.db"


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

    cursor.execute("""
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS odds (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            schedule_id TEXT NOT NULL,

            company_id TEXT,

            company_name TEXT NOT NULL,

            final_home REAL,

            final_draw REAL,

            final_away REAL,

            UNIQUE(
                schedule_id,
                company_name
            )

        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_matches_date
        ON matches(match_date)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_odds_schedule
        ON odds(schedule_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_odds_company
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

            match_date=excluded.match_date,

            home_team=excluded.home_team,

            away_team=excluded.away_team,

            home_score=excluded.home_score,

            away_score=excluded.away_score,

            result=excluded.result,

            source=excluded.source
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
# 배당 저장
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

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO odds (
            schedule_id,
            company_id,
            company_name,
            final_home,
            final_draw,
            final_away
        )

        VALUES (?, ?, ?, ?, ?, ?)

        ON CONFLICT(
            schedule_id,
            company_name
        )

        DO UPDATE SET

            company_id=excluded.company_id,

            final_home=excluded.final_home,

            final_draw=excluded.final_draw,

            final_away=excluded.final_away
    """, (

        str(schedule_id),

        str(company_id or ""),

        str(company_name),

        final_home,

        final_draw,

        final_away

    ))

    conn.commit()

    conn.close()


# =========================================================
# 경기 1개 조회
# =========================================================

def get_match(schedule_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM matches
        WHERE schedule_id = ?
    """, (
        str(schedule_id),
    ))

    row = cursor.fetchone()

    conn.close()

    return row


# =========================================================
# 전체 경기
# =========================================================

def get_all_matches():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM matches
        ORDER BY match_date DESC, schedule_id DESC
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
        SELECT *
        FROM odds
        ORDER BY schedule_id DESC, company_name
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# 특정 경기의 업체별 최종배당
# =========================================================

def get_match_final_odds(
    schedule_id
):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
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

    return int(count)


# =========================================================
# 배당 수
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

    return int(count)


# =========================================================
# 업체 목록
# =========================================================

def get_company_names():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT company_name
        FROM odds
        WHERE company_name IS NOT NULL
        AND TRIM(company_name) != ''
        ORDER BY company_name
    """)

    rows = cursor.fetchall()

    conn.close()

    return [
        row[0]
        for row in rows
    ]


# =========================================================
# 업체별 저장 개수
# =========================================================

def get_company_counts():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            company_name,
            COUNT(*) AS count
        FROM odds
        GROUP BY company_name
        ORDER BY count DESC
    """)

    rows = cursor.fetchall()

    conn.close()

    return {
        row["company_name"]:
            int(row["count"])
        for row in rows
    }


# =========================================================
# 배당 검색
#
# 여러 업체를 선택하면
# 선택한 모든 업체가 같은 경기에서
# 입력 배당과 일치해야 검색
# =========================================================

def search_multiple_final_odds(
    company_odds
):

    if not company_odds:

        return []


    conn = get_connection()

    cursor = conn.cursor()


    schedule_ids = None


    for company_name, odds in company_odds.items():

        cursor.execute("""
            SELECT DISTINCT schedule_id
            FROM odds
            WHERE company_name = ?
              AND ABS(final_home - ?) < 0.00001
              AND ABS(final_draw - ?) < 0.00001
              AND ABS(final_away - ?) < 0.00001
        """, (

            company_name,

            float(odds["home"]),

            float(odds["draw"]),

            float(odds["away"])

        ))


        ids = {
            row["schedule_id"]
            for row in cursor.fetchall()
        }


        if schedule_ids is None:

            schedule_ids = ids

        else:

            schedule_ids &= ids


        if not schedule_ids:

            break


    if not schedule_ids:

        conn.close()

        return []


    placeholders = ",".join(
        "?"
        for _ in schedule_ids
    )


    cursor.execute(
        f"""
        SELECT *
        FROM matches
        WHERE schedule_id IN (
            {placeholders}
        )
        ORDER BY match_date DESC
        """,
        tuple(schedule_ids)
    )


    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# DB 삭제
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
# 실행
# =========================================================

if __name__ == "__main__":

    init_database()

    print(
        "DB 초기화 완료:"
    )

    print(
        os.path.abspath(DB_FILE)
    )
