import sqlite3
import os


DB_FILE = "historical_odds.db"


# =========================================================
# 연결
# =========================================================

def get_connection():

    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False,
        timeout=30
    )

    conn.row_factory = sqlite3.Row

    return conn


# =========================================================
# DB 초기화
# =========================================================

def init_database():

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        PRAGMA journal_mode=WAL
    """)

    cur.execute("""
        PRAGMA synchronous=NORMAL
    """)

    cur.execute("""
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

    cur.execute("""
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
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_matches_date
        ON matches(match_date)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_odds_schedule
        ON odds(schedule_id)
    """)

    cur.execute("""
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

    try:

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

    finally:

        conn.close()


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

    try:

        conn.execute("""
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

    finally:

        conn.close()


# =========================================================
# 경기 + 배당 일괄 저장
#
# 속도 개선 핵심
# =========================================================

def save_match_with_odds(
    match,
    odds_list
):

    conn = get_connection()

    try:

        cur = conn.cursor()

        # -----------------------------------------------
        # 경기
        # -----------------------------------------------

        cur.execute("""
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
            str(match["schedule_id"]),
            match.get("match_date", ""),
            match.get("home_team", ""),
            match.get("away_team", ""),
            match.get("home_score"),
            match.get("away_score"),
            match.get("result", ""),
            "Scoreman"
        ))


        # -----------------------------------------------
        # 배당 전체
        # -----------------------------------------------

        rows = []

        for odds in odds_list:

            rows.append((
                str(match["schedule_id"]),
                str(
                    odds.get(
                        "company_id",
                        ""
                    )
                    or ""
                ),
                str(
                    odds.get(
                        "company_name",
                        ""
                    )
                ),
                odds.get("final_home"),
                odds.get("final_draw"),
                odds.get("final_away")
            ))


        if rows:

            cur.executemany("""
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
            """, rows)


        # -----------------------------------------------
        # 한 번만 commit
        # -----------------------------------------------

        conn.commit()

        return len(rows)

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# =========================================================
# 경기 조회
# =========================================================

def get_match(schedule_id):

    conn = get_connection()

    row = conn.execute("""
        SELECT *
        FROM matches
        WHERE schedule_id=?
    """, (
        str(schedule_id),
    )).fetchone()

    conn.close()

    return row


# =========================================================
# 전체 경기
# =========================================================

def get_all_matches():

    conn = get_connection()

    rows = conn.execute("""
        SELECT *
        FROM matches
        ORDER BY match_date DESC, schedule_id DESC
    """).fetchall()

    conn.close()

    return rows


# =========================================================
# 전체 배당
# =========================================================

def get_all_odds():

    conn = get_connection()

    rows = conn.execute("""
        SELECT *
        FROM odds
        ORDER BY schedule_id DESC, company_name
    """).fetchall()

    conn.close()

    return rows


# =========================================================
# 특정 경기 배당
# =========================================================

def get_match_final_odds(
    schedule_id
):

    conn = get_connection()

    rows = conn.execute("""
        SELECT *
        FROM odds
        WHERE schedule_id=?
        ORDER BY company_name
    """, (
        str(schedule_id),
    )).fetchall()

    conn.close()

    return rows


# =========================================================
# 경기 수
# =========================================================

def get_match_count():

    conn = get_connection()

    value = conn.execute(
        "SELECT COUNT(*) FROM matches"
    ).fetchone()[0]

    conn.close()

    return int(value)


# =========================================================
# 배당 수
# =========================================================

def get_odds_count():

    conn = get_connection()

    value = conn.execute(
        "SELECT COUNT(*) FROM odds"
    ).fetchone()[0]

    conn.close()

    return int(value)


# =========================================================
# 업체 목록
# =========================================================

def get_company_names():

    conn = get_connection()

    rows = conn.execute("""
        SELECT DISTINCT company_name
        FROM odds
        WHERE company_name IS NOT NULL
        AND TRIM(company_name) != ''
        ORDER BY company_name
    """).fetchall()

    conn.close()

    return [
        row[0]
        for row in rows
    ]


# =========================================================
# 업체별 저장량
# =========================================================

def get_company_counts():

    conn = get_connection()

    rows = conn.execute("""
        SELECT
            company_name,
            COUNT(*) AS count
        FROM odds
        GROUP BY company_name
        ORDER BY count DESC
    """).fetchall()

    conn.close()

    return {
        row["company_name"]:
            int(row["count"])
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

    cur = conn.cursor()

    schedule_ids = None


    for company_name, odds in company_odds.items():

        cur.execute("""
            SELECT DISTINCT schedule_id
            FROM odds
            WHERE company_name = ?

              AND ABS(
                  final_home - ?
              ) < 0.00001

              AND ABS(
                  final_draw - ?
              ) < 0.00001

              AND ABS(
                  final_away - ?
              ) < 0.00001
        """, (
            company_name,
            float(odds["home"]),
            float(odds["draw"]),
            float(odds["away"])
        ))


        ids = {
            row["schedule_id"]
            for row in cur.fetchall()
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


    rows = cur.execute(
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


    conn.close()

    return rows


# =========================================================
# DB 초기화
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

    conn.close()


# =========================================================
# 실행
# =========================================================

if __name__ == "__main__":

    init_database()

    print(
        os.path.abspath(
            DB_FILE
        )
                    )
