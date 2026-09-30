import sqlite3
from pathlib import Path


# =========================================================
# DB 설정
# =========================================================

DB_PATH = Path(__file__).resolve().parent / "scoreman.db"


# =========================================================
# DB 연결
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
# DB 초기화
# =========================================================

def init_database():

    conn = get_connection()

    try:

        cursor = conn.cursor()

        # =================================================
        # 경기 테이블
        # =================================================

        cursor.execute("""
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
        """)

        # =================================================
        # 최종배당 테이블
        # =================================================

        cursor.execute("""
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
        """)

        # =================================================
        # 수집 상태 테이블 추가
        # 기존 DB가 있어도 자동 생성
        # =================================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawler_state (

                id INTEGER PRIMARY KEY,

                last_saved_schedule_id TEXT,

                last_saved_match_date TEXT,

                last_saved_home_team TEXT,

                last_saved_away_team TEXT,

                last_saved_result TEXT,

                last_saved_odds_count INTEGER
                    DEFAULT 0,

                updated_at TEXT
                    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # =================================================
        # 인덱스
        # =================================================

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_matches_schedule
            ON matches(schedule_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_matches_result
            ON matches(result)
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

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_odds_company_values
            ON odds(
                company_name,
                final_home,
                final_draw,
                final_away
            )
        """)

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

        conn.execute("""
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
# 신규 경기 전용 저장
#
# 이미 존재하면 저장하지 않음
# True  = 신규 저장
# False = 이미 존재
# =========================================================

def save_match_if_new(
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

        existing = conn.execute("""
            SELECT 1

            FROM matches

            WHERE schedule_id = ?

            LIMIT 1
        """, (
            str(schedule_id),
        )).fetchone()

        if existing is not None:

            return False

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
            VALUES (

                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?

            )
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

        return True

    finally:

        conn.close()


# =========================================================
# 최종배당 저장
#
# 초기배당은 저장하지 않음
# 최종배당만 저장
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

    if not company_name:

        return False

    conn = get_connection()

    try:

        conn.execute("""
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
        """, (
            str(schedule_id),
            str(company_id or ""),
            str(company_name).strip(),
            final_home,
            final_draw,
            final_away
        ))

        conn.commit()

        return True

    finally:

        conn.close()


# =========================================================
# 신규 경기의 업체별 최종배당 저장
#
# 기존 경기에는 사용하지 않음
# =========================================================

def save_odds_if_new_match(
    schedule_id,
    company_id,
    company_name,
    final_home,
    final_draw,
    final_away
):

    init_database()

    if not company_name:

        return False

    conn = get_connection()

    try:

        match = conn.execute("""
            SELECT 1

            FROM matches

            WHERE schedule_id = ?

            LIMIT 1
        """, (
            str(schedule_id),
        )).fetchone()

        if match is None:

            return False

        conn.execute("""
            INSERT OR IGNORE INTO odds (

                schedule_id,
                company_id,
                company_name,
                final_home,
                final_draw,
                final_away

            )
            VALUES (

                ?,
                ?,
                ?,
                ?,
                ?,
                ?

            )
        """, (
            str(schedule_id),
            str(company_id or ""),
            str(company_name).strip(),
            final_home,
            final_draw,
            final_away
        ))

        conn.commit()

        return True

    finally:

        conn.close()


# =========================================================
# 경기 1건 조회
# =========================================================

def get_match(schedule_id):

    init_database()

    conn = get_connection()

    try:

        return conn.execute("""
            SELECT *
            FROM matches
            WHERE schedule_id = ?
            LIMIT 1
        """, (
            str(schedule_id),
        )).fetchone()

    finally:

        conn.close()


# =========================================================
# 전체 경기 조회
# =========================================================

def get_all_matches():

    init_database()

    conn = get_connection()

    try:

        return conn.execute("""
            SELECT *
            FROM matches
            ORDER BY
                match_date DESC,
                id DESC
        """).fetchall()

    finally:

        conn.close()


# =========================================================
# 전체 경기 수
# =========================================================

def get_match_count():

    init_database()

    conn = get_connection()

    try:

        row = conn.execute("""
            SELECT COUNT(*) AS count
            FROM matches
        """).fetchone()

        return int(
            row["count"]
        )

    finally:

        conn.close()


# =========================================================
# 전체 배당 수
# =========================================================

def get_odds_count():

    init_database()

    conn = get_connection()

    try:

        row = conn.execute("""
            SELECT COUNT(*) AS count
            FROM odds
        """).fetchone()

        return int(
            row["count"]
        )

    finally:

        conn.close()


# =========================================================
# 전체 최종배당 조회
# =========================================================

def get_all_odds():

    init_database()

    conn = get_connection()

    try:

        return conn.execute("""
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
        """).fetchall()

    finally:

        conn.close()


# =========================================================
# 업체 목록
# =========================================================

def get_company_names():

    init_database()

    conn = get_connection()

    try:

        rows = conn.execute("""
            SELECT DISTINCT

                company_name

            FROM odds

            WHERE
                company_name IS NOT NULL

                AND
                TRIM(company_name) <> ''

            ORDER BY
                company_name COLLATE NOCASE
        """).fetchall()

        return [
            row["company_name"]
            for row in rows
        ]

    finally:

        conn.close()


# =========================================================
# 업체별 저장 개수
# =========================================================

def get_company_counts():

    init_database()

    conn = get_connection()

    try:

        rows = conn.execute("""
            SELECT

                company_name,

                COUNT(*) AS count

            FROM odds

            WHERE
                company_name IS NOT NULL

                AND
                TRIM(company_name) <> ''

            GROUP BY
                company_name

            ORDER BY
                company_name COLLATE NOCASE
        """).fetchall()

        return {

            row["company_name"]:
                int(row["count"])

            for row in rows

        }

    finally:

        conn.close()


# =========================================================
# 특정 업체 저장 개수
# =========================================================

def get_company_count(
    company_name
):

    init_database()

    conn = get_connection()

    try:

        row = conn.execute("""
            SELECT COUNT(*) AS count

            FROM odds

            WHERE
                LOWER(
                    TRIM(company_name)
                )
                =
                LOWER(
                    TRIM(?)
                )
        """, (
            company_name,
        )).fetchone()

        return int(
            row["count"]
        )

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

        return conn.execute("""
            SELECT

                schedule_id,

                company_id,

                company_name,

                final_home,

                final_draw,

                final_away

            FROM odds

            WHERE
                schedule_id = ?

            ORDER BY
                company_name COLLATE NOCASE
        """, (
            str(schedule_id),
        )).fetchall()

    finally:

        conn.close()


# =========================================================
# 단일 업체 최종배당 완전일치 검색
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

        return conn.execute("""
            SELECT

                m.*,

                o.company_name,

                o.final_home,

                o.final_draw,

                o.final_away

            FROM matches m

            INNER JOIN odds o

                ON
                    m.schedule_id =
                    o.schedule_id

            WHERE

                LOWER(
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

            ORDER BY

                m.match_date DESC,

                m.id DESC
        """, (
            company_name,
            float(final_home),
            float(final_draw),
            float(final_away)
        )).fetchall()

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

        conditions = []

        params = []

        for company_name, odds in (
            company_odds.items()
        ):

            conditions.append("""

                EXISTS (

                    SELECT 1

                    FROM odds o

                    WHERE

                        o.schedule_id =
                        m.schedule_id

                        AND LOWER(
                            TRIM(
                                o.company_name
                            )
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

            """)

            params.extend([

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

            ])

        sql = """

            SELECT
                m.*

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

        return conn.execute(
            sql,
            params
        ).fetchall()

    finally:

        conn.close()


# =========================================================
# 검색 + 업체별 배당
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

        item["odds"] = {}

        rows = (
            get_match_final_odds(
                match["schedule_id"]
            )
        )

        for row in rows:

            item["odds"][
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

    init_database()

    conn = get_connection()

    try:

        row = conn.execute("""
            SELECT 1

            FROM matches

            WHERE schedule_id = ?

            LIMIT 1
        """, (
            str(schedule_id),
        )).fetchone()

        return row is not None

    finally:

        conn.close()


# =========================================================
# 마지막 저장 경기 저장
# =========================================================

def save_last_crawler_state(
    schedule_id,
    match_date="",
    home_team="",
    away_team="",
    result="",
    odds_count=0
):

    init_database()

    conn = get_connection()

    try:

        conn.execute("""
            INSERT INTO crawler_state (

                id,

                last_saved_schedule_id,

                last_saved_match_date,

                last_saved_home_team,

                last_saved_away_team,

                last_saved_result,

                last_saved_odds_count,

                updated_at

            )
            VALUES (

                1,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                CURRENT_TIMESTAMP

            )

            ON CONFLICT(id)
            DO UPDATE SET

                last_saved_schedule_id =
                    excluded.last_saved_schedule_id,

                last_saved_match_date =
                    excluded.last_saved_match_date,

                last_saved_home_team =
                    excluded.last_saved_home_team,

                last_saved_away_team =
                    excluded.last_saved_away_team,

                last_saved_result =
                    excluded.last_saved_result,

                last_saved_odds_count =
                    excluded.last_saved_odds_count,

                updated_at =
                    CURRENT_TIMESTAMP
        """, (
            str(schedule_id),
            match_date,
            home_team,
            away_team,
            result,
            int(odds_count or 0)
        ))

        conn.commit()

    finally:

        conn.close()


# =========================================================
# 마지막 저장 경기 조회
# =========================================================

def get_last_crawler_state():

    init_database()

    conn = get_connection()

    try:

        row = conn.execute("""
            SELECT *

            FROM crawler_state

            WHERE id = 1

            LIMIT 1
        """).fetchone()

        if row is None:

            return None

        return dict(row)

    finally:

        conn.close()


# =========================================================
# DB에 실제 저장된 가장 최근 경기
# =========================================================

def get_last_saved_match():

    init_database()

    conn = get_connection()

    try:

        row = conn.execute("""
            SELECT *

            FROM matches

            ORDER BY id DESC

            LIMIT 1
        """).fetchone()

        if row is None:

            return None

        return dict(row)

    finally:

        conn.close()


# =========================================================
# 마지막 저장 경기 ID
# =========================================================

def get_last_saved_schedule_id():

    row = get_last_saved_match()

    if not row:

        return None

    return row.get(
        "schedule_id"
    )


# =========================================================
# 마지막 저장 ID 이후의 다음 ID
# =========================================================

def get_next_schedule_id():

    last_id = get_last_saved_schedule_id()

    if last_id is None:

        return None

    try:

        return int(
            last_id
        ) + 1

    except Exception:

        return None


# =========================================================
# 특정 업체 존재 여부
# =========================================================

def company_exists(
    company_name
):

    init_database()

    if not company_name:

        return False

    conn = get_connection()

    try:

        row = conn.execute("""
            SELECT 1

            FROM odds

            WHERE
                LOWER(
                    TRIM(company_name)
                )
                =
                LOWER(
                    TRIM(?)
                )

            LIMIT 1
        """, (
            company_name,
        )).fetchone()

        return row is not None

    finally:

        conn.close()


# =========================================================
# 업체 선택 필터
# =========================================================

def filter_odds_by_companies(
    odds_list,
    selected_companies=None
):

    if not selected_companies:

        return odds_list

    selected = {

        str(company).strip().lower()

        for company in selected_companies

        if company

    }

    result = []

    for odds in odds_list:

        name = str(
            odds.get(
                "company_name",
                ""
            )
        ).strip().lower()

        if name in selected:

            result.append(
                odds
            )

    return result


# =========================================================
# DB 전체 삭제
# =========================================================

def clear_database():

    init_database()

    conn = get_connection()

    try:

        conn.execute(
            "DELETE FROM odds"
        )

        conn.execute(
            "DELETE FROM matches"
        )

        conn.execute(
            "DELETE FROM crawler_state"
        )

        conn.commit()

    finally:

        conn.close()


# =========================================================
# DB 상태
# =========================================================

def get_database_status():

    init_database()

    conn = get_connection()

    try:

        match_row = conn.execute("""
            SELECT COUNT(*) AS count
            FROM matches
        """).fetchone()

        odds_row = conn.execute("""
            SELECT COUNT(*) AS count
            FROM odds
        """).fetchone()

        company_row = conn.execute("""
            SELECT COUNT(
                DISTINCT company_name
            ) AS count

            FROM odds

            WHERE
                company_name IS NOT NULL

                AND
                TRIM(company_name) <> ''
        """).fetchone()

        result_rows = conn.execute("""
            SELECT

                result,

                COUNT(*) AS count

            FROM matches

            WHERE
                result IN (
                    '승',
                    '무',
                    '패'
                )

            GROUP BY
                result
        """).fetchall()

        result_counts = {

            "승": 0,
            "무": 0,
            "패": 0

        }

        for row in result_rows:

            result_counts[
                row["result"]
            ] = int(
                row["count"]
            )

        return {

            "matches":
                int(
                    match_row["count"]
                ),

            "odds":
                int(
                    odds_row["count"]
                ),

            "companies":
                int(
                    company_row["count"]
                ),

            "승":
                result_counts["승"],

            "무":
                result_counts["무"],

            "패":
                result_counts["패"]

        }

    finally:

        conn.close()


# =========================================================
# 실제 결과 통계
# =========================================================

def get_result_counts():

    init_database()

    conn = get_connection()

    try:

        rows = conn.execute("""
            SELECT

                result,

                COUNT(*) AS count

            FROM matches

            WHERE
                result IN (
                    '승',
                    '무',
                    '패'
                )

            GROUP BY
                result
        """).fetchall()

        result = {

            "승": 0,
            "무": 0,
            "패": 0

        }

        for row in rows:

            result[
                row["result"]
            ] = int(
                row["count"]
            )

        return result

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
        "마지막 경기 ID:",
        get_last_saved_schedule_id()
    )

    print()

    print(
        "업체별 저장 개수:"
    )

    counts = (
        get_company_counts()
    )

    for company, count in (
        counts.items()
    ):

        print(
            f" - {company}: {count:,}"
        )

    print()

    print(
        "실제 결과:"
    )

    result_counts = (
        get_result_counts()
    )

    print(
        "승:",
        result_counts["승"]
    )

    print(
        "무:",
        result_counts["무"]
    )

    print(
        "패:",
        result_counts["패"]
    )
