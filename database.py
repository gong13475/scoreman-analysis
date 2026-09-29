import sqlite3
from pathlib import Path


# =========================================================
# DB 설정
# =========================================================

DB_PATH = Path(__file__).resolve().parent / "scoreman.db"


# =========================================================
# 연결
# =========================================================

def get_connection():

    conn = sqlite3.connect(
        str(DB_PATH),
        timeout=30,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


# =========================================================
# 초기화
# =========================================================

def init_database():

    conn = get_connection()

    try:

        cursor = conn.cursor()

        # -------------------------------------------------
        # 경기
        # -------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS matches (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                schedule_id TEXT NOT NULL UNIQUE,

                match_date TEXT,

                home_team TEXT,

                away_team TEXT,

                home_score INTEGER,

                away_score INTEGER,

                result TEXT,

                source TEXT,

                created_at TEXT
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT
                    DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # -------------------------------------------------
        # 최종배당
        # -------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS odds (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                schedule_id TEXT NOT NULL,

                company_id TEXT,

                company_name TEXT NOT NULL,

                final_home REAL,

                final_draw REAL,

                final_away REAL,

                created_at TEXT
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT
                    DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(
                    schedule_id,
                    company_name
                )
            )
            """
        )

        # -------------------------------------------------
        # 기존 DB가 예전 구조인 경우
        # 초기배당 컬럼이 있어도 그대로 두어도 됨.
        # 현재 프로그램에서는 사용하지 않음.
        # -------------------------------------------------

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_matches_schedule
            ON matches(schedule_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_odds_schedule
            ON odds(schedule_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_odds_company
            ON odds(company_name)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_odds_company_values
            ON odds(
                company_name,
                final_home,
                final_draw,
                final_away
            )
            """
        )

        conn.commit()

    finally:

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

    init_database()

    conn = get_connection()

    try:

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
            VALUES (

                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
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

    finally:

        conn.close()


# =========================================================
# 최종배당 저장
# =========================================================

def save_odds(
    schedule_id,
    company_id,
    company_name,
    final_home,
    final_draw,
    final_away
):

    init_database()

    conn = get_connection()

    try:

        conn.execute(
            """
            INSERT INTO odds (

                schedule_id,
                company_id,
                company_name,
                final_home,
                final_draw,
                final_away,
                updated_at

            )
            VALUES (

                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                CURRENT_TIMESTAMP

            )

            ON CONFLICT(
                schedule_id,
                company_name
            )
            DO UPDATE SET

                company_id =
                    excluded.company_id,

                final_home =
                    excluded.final_home,

                final_draw =
                    excluded.final_draw,

                final_away =
                    excluded.final_away,

                updated_at =
                    CURRENT_TIMESTAMP
            """,

            (
                str(schedule_id),
                str(company_id or ""),
                str(company_name),
                final_home,
                final_draw,
                final_away
            )
        )

        conn.commit()

    finally:

        conn.close()


# =========================================================
# 경기 조회
# =========================================================

def get_match(
    schedule_id
):

    init_database()

    conn = get_connection()

    try:

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

        return row

    finally:

        conn.close()


# =========================================================
# 전체 경기
# =========================================================

def get_all_matches():

    init_database()

    conn = get_connection()

    try:

        return conn.execute(
            """
            SELECT *
            FROM matches
            ORDER BY
                match_date DESC,
                id DESC
            """
        ).fetchall()

    finally:

        conn.close()


# =========================================================
# 경기 수
# =========================================================

def get_match_count():

    init_database()

    conn = get_connection()

    try:

        row = conn.execute(
            """
            SELECT COUNT(*)
            AS count
            FROM matches
            """
        ).fetchone()

        return int(
            row["count"]
        )

    finally:

        conn.close()


# =========================================================
# 배당 수
# =========================================================

def get_odds_count():

    init_database()

    conn = get_connection()

    try:

        row = conn.execute(
            """
            SELECT COUNT(*)
            AS count
            FROM odds
            """
        ).fetchone()

        return int(
            row["count"]
        )

    finally:

        conn.close()


# =========================================================
# 전체 배당
# =========================================================

def get_all_odds():

    init_database()

    conn = get_connection()

    try:

        return conn.execute(
            """
            SELECT
                schedule_id,
                company_id,
                company_name,
                final_home,
                final_draw,
                final_away
            FROM odds
            ORDER BY
                schedule_id DESC,
                company_name ASC
            """
        ).fetchall()

    finally:

        conn.close()


# =========================================================
# 업체 목록
# =========================================================

def get_company_names():

    init_database()

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT DISTINCT
                company_name
            FROM odds
            WHERE
                company_name IS NOT NULL
                AND TRIM(company_name) <> ''
            ORDER BY
                company_name
            """
        ).fetchall()

        return [
            row["company_name"]
            for row in rows
        ]

    finally:

        conn.close()


# =========================================================
# 특정 경기 최종배당
# =========================================================

def get_match_final_odds(
    schedule_id
):

    init_database()

    conn = get_connection()

    try:

        return conn.execute(
            """
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
            """,
            (
                str(schedule_id),
            )
        ).fetchall()

    finally:

        conn.close()


# =========================================================
# 단일 업체 최종배당 검색
# =========================================================

def search_final_odds(
    company_name,
    final_home,
    final_draw,
    final_away
):

    init_database()

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT
                m.*,

                o.company_name,

                o.final_home,

                o.final_draw,

                o.final_away

            FROM matches m

            INNER JOIN odds o

                ON m.schedule_id =
                   o.schedule_id

            WHERE
                LOWER(TRIM(o.company_name))
                =
                LOWER(TRIM(?))

                AND ABS(
                    o.final_home - ?
                ) < 0.000001

                AND ABS(
                    o.final_draw - ?
                ) < 0.000001

                AND ABS(
                    o.final_away - ?
                ) < 0.000001

            ORDER BY
                m.match_date DESC
            """,

            (
                company_name,
                float(final_home),
                float(final_draw),
                float(final_away)
            )
        ).fetchall()

        return rows

    finally:

        conn.close()


# =========================================================
# 여러 업체 최종배당 완전일치 검색
# =========================================================

def search_multiple_final_odds(
    company_odds
):

    init_database()

    if not company_odds:

        return []

    conn = get_connection()

    try:

        # -------------------------------------------------
        # 업체별 조건을 모두 만족하는 경기만 찾음
        # -------------------------------------------------

        conditions = []

        params = []

        for company_name, odds in (
            company_odds.items()
        ):

            conditions.append(
                """
                EXISTS (

                    SELECT 1

                    FROM odds o

                    WHERE
                        o.schedule_id =
                        m.schedule_id

                        AND LOWER(
                            TRIM(o.company_name)
                        )
                        =
                        LOWER(
                            TRIM(?)
                        )

                        AND ABS(
                            o.final_home - ?
                        ) < 0.000001

                        AND ABS(
                            o.final_draw - ?
                        ) < 0.000001

                        AND ABS(
                            o.final_away - ?
                        ) < 0.000001
                )
                """
            )

            params.extend(
                [
                    company_name,

                    float(
                        odds["home"]
                    ),

                    float(
                        odds["draw"]
                    ),

                    float(
                        odds["away"]
                    )
                ]
            )

        sql = """
            SELECT m.*
            FROM matches m
            WHERE
        """

        sql += "\nAND\n".join(
            conditions
        )

        sql += """
            ORDER BY
                m.match_date DESC,
                m.id DESC
        """

        rows = conn.execute(
            sql,
            params
        ).fetchall()

        return rows

    finally:

        conn.close()


# =========================================================
# 최종배당 검색 + 업체 데이터
# =========================================================

def search_final_odds_with_companies(
    company_odds
):

    matches = (
        search_multiple_final_odds(
            company_odds
        )
    )

    result = []

    for match in matches:

        item = dict(
            match
        )

        item[
            "odds"
        ] = {}

        rows = get_match_final_odds(
            match["schedule_id"]
        )

        for row in rows:

            item[
                "odds"
            ][
                row["company_name"]
            ] = {

                "home":
                    row["final_home"],

                "draw":
                    row["final_draw"],

                "away":
                    row["final_away"]
            }

        result.append(
            item
        )

    return result


# =========================================================
# 경기 존재 여부
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
# DB 전체 삭제
# =========================================================

def clear_database():

    conn = get_connection()

    try:

        conn.execute(
            "DELETE FROM odds"
        )

        conn.execute(
            "DELETE FROM matches"
        )

        conn.commit()

    finally:

        conn.close()


# =========================================================
# 테스트
# =========================================================

if __name__ == "__main__":

    init_database()

    print(
        "========================================"
    )

    print(
        "Scoreman Database"
    )

    print(
        "========================================"
    )

    print(
        "DB:",
        DB_PATH
    )

    print(
        "경기:",
        get_match_count()
    )

    print(
        "최종배당:",
        get_odds_count()
    )

    print(
        "업체:"
    )

    for company in get_company_names():

        print(
            " -",
            company
            )
