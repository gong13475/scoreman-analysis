import sqlite3
import os


# =========================================================
# DB 설정
# =========================================================

DB_FILE = "historical_odds.db"


# =========================================================
# DB 연결
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
# 데이터베이스 초기화
# =========================================================

def init_database():

    conn = get_connection()

    cur = conn.cursor()

    # -----------------------------------------------------
    # 경기 테이블
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # 배당 테이블
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # 인덱스
    # -----------------------------------------------------

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

    company_name = str(
        company_name or ""
    ).strip()

    if not company_name:

        conn.close()

        return False

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

        ON CONFLICT(schedule_id, company_name)

        DO UPDATE SET

            company_id=excluded.company_id,

            final_home=excluded.final_home,

            final_draw=excluded.final_draw,

            final_away=excluded.final_away

    """, (

        str(schedule_id),

        str(company_id or ""),

        company_name,

        final_home,

        final_draw,

        final_away

    ))

    conn.commit()

    conn.close()

    return True


# =========================================================
# 경기 1개
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

        ORDER BY
            match_date DESC,
            schedule_id DESC
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

        ORDER BY
            schedule_id DESC,
            company_name
    """).fetchall()

    conn.close()

    return rows


# =========================================================
# 특정 경기의 전체 업체 배당
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
# 업체명 전체
#
# 중요:
# 업체를 3개로 제한하지 않는다.
#
# DB에 저장되어 있는 모든 업체를 반환한다.
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

    result = []

    seen = set()

    for row in rows:

        company = str(
            row[0]
        ).strip()

        if not company:
            continue

        key = company.lower()

        if key in seen:
            continue

        seen.add(key)

        result.append(company)

    return result


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
# 업체명 정규화
#
# 예:
#
# Bet365
# bet365
# Bet 365
# Bet-365
#
# → bet365
# =========================================================

def normalize_company_name(
    name
):

    if name is None:

        return ""

    value = str(
        name
    ).strip().lower()

    value = value.replace(
        " ",
        ""
    )

    value = value.replace(
        "_",
        ""
    )

    value = value.replace(
        "-",
        ""
    )

    value = value.replace(
        ".",
        ""
    )

    return value


# =========================================================
# 실제 DB 업체명 찾기
# =========================================================

def find_company_name(
    company_name
):

    target = normalize_company_name(
        company_name
    )

    if not target:

        return None

    companies = get_company_names()

    for company in companies:

        if (
            normalize_company_name(
                company
            )
            ==
            target
        ):

            return company

    return None


# =========================================================
# 여러 업체 + 배당 검색
#
# 선택한 모든 업체가 같은 경기에서
# 입력한 배당과 일치하는 경기만 검색
#
# 업체 수 제한 없음
# =========================================================

def search_multiple_final_odds(
    company_odds
):

    if not company_odds:

        return []

    conn = get_connection()

    cur = conn.cursor()

    schedule_ids = None

    # -----------------------------------------------------
    # 업체별 검색
    # -----------------------------------------------------

    for requested_company, odds in company_odds.items():

        # -------------------------------------------------
        # 입력 업체명과 DB 업체명 정규화
        # -------------------------------------------------

        normalized_requested = (
            normalize_company_name(
                requested_company
            )
        )

        if not normalized_requested:

            continue

        # -------------------------------------------------
        # 실제 DB 업체명 전체 조회
        # -------------------------------------------------

        company_rows = cur.execute("""
            SELECT DISTINCT company_name
            FROM odds
            WHERE company_name IS NOT NULL
            AND TRIM(company_name) != ''
        """).fetchall()

        matching_company_names = []

        for row in company_rows:

            db_company = str(
                row["company_name"]
            ).strip()

            if (
                normalize_company_name(
                    db_company
                )
                ==
                normalized_requested
            ):

                matching_company_names.append(
                    db_company
                )

        # -------------------------------------------------
        # 해당 업체가 DB에 없으면 결과 없음
        # -------------------------------------------------

        if not matching_company_names:

            schedule_ids = set()

            break

        # -------------------------------------------------
        # 업체명 IN 조건 생성
        # -------------------------------------------------

        placeholders = ",".join(
            "?"
            for _ in matching_company_names
        )

        try:

            home = float(
                odds["home"]
            )

            draw = float(
                odds["draw"]
            )

            away = float(
                odds["away"]
            )

        except Exception:

            schedule_ids = set()

            break

        query = f"""
            SELECT DISTINCT schedule_id

            FROM odds

            WHERE company_name IN (
                {placeholders}
            )

            AND ABS(
                final_home - ?
            ) < 0.00001

            AND ABS(
                final_draw - ?
            ) < 0.00001

            AND ABS(
                final_away - ?
            ) < 0.00001
        """

        params = (
            matching_company_names
            + [
                home,
                draw,
                away
            ]
        )

        cur.execute(
            query,
            params
        )

        ids = {

            row["schedule_id"]

            for row in cur.fetchall()

        }

        # -------------------------------------------------
        # 첫 업체
        # -------------------------------------------------

        if schedule_ids is None:

            schedule_ids = ids

        # -------------------------------------------------
        # 여러 업체
        # 같은 경기만 유지
        # -------------------------------------------------

        else:

            schedule_ids &= ids

        if not schedule_ids:

            break

    # -----------------------------------------------------
    # 결과 없음
    # -----------------------------------------------------

    if not schedule_ids:

        conn.close()

        return []

    # -----------------------------------------------------
    # 경기 정보 조회
    # -----------------------------------------------------

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

        ORDER BY
            match_date DESC,
            schedule_id DESC
        """,

        tuple(schedule_ids)

    ).fetchall()

    conn.close()

    return rows


# =========================================================
# 경기 존재 여부
# =========================================================

def match_exists(
    schedule_id
):

    conn = get_connection()

    row = conn.execute("""
        SELECT 1

        FROM matches

        WHERE schedule_id=?

        LIMIT 1
    """, (

        str(schedule_id),

    )).fetchone()

    conn.close()

    return row is not None


# =========================================================
# 마지막 저장 경기 ID
# =========================================================

def get_last_saved_schedule_id():

    conn = get_connection()

    row = conn.execute("""
        SELECT schedule_id

        FROM matches

        ORDER BY
            CAST(schedule_id AS INTEGER) DESC

        LIMIT 1
    """).fetchone()

    conn.close()

    if not row:

        return None

    return row["schedule_id"]


# =========================================================
# 가장 큰 경기 ID
# =========================================================

def get_max_schedule_id():

    conn = get_connection()

    row = conn.execute("""
        SELECT MAX(
            CAST(schedule_id AS INTEGER)
        ) AS max_id

        FROM matches
    """).fetchone()

    conn.close()

    if not row:

        return None

    return row["max_id"]


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

    conn.close()


# =========================================================
# 직접 실행
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
        "DB 위치:",
        os.path.abspath(DB_FILE)
    )

    print(
        "저장 경기:",
        get_match_count()
    )

    print(
        "저장 배당:",
        get_odds_count()
    )

    print(
        "업체 수:",
        len(
            get_company_names()
        )
    )

    print(
        "업체 목록:"
    )

    for company in get_company_names():

        print(
            "-",
            company
    )
