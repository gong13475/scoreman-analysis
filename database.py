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
# 업체명 정규화
#
# 예:
# Bet365
# bet365
# Bet 365
# BET-365
#
# 모두 동일 업체로 비교할 수 있도록 처리
# =========================================================

def normalize_company_name(name):

    if name is None:
        return ""

    value = str(name).strip().lower()

    value = value.replace(" ", "")
    value = value.replace("_", "")
    value = value.replace("-", "")
    value = value.replace(".", "")
    value = value.replace("/", "")

    return value


# =========================================================
# 데이터베이스 초기화
# =========================================================

def init_database():

    conn = get_connection()

    cur = conn.cursor()

    # -----------------------------------------------------
    # 경기
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
    # 배당
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

            UNIQUE(
                schedule_id,
                company_name
            )

        )
    """)

    # -----------------------------------------------------
    # 인덱스
    # -----------------------------------------------------

    cur.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_matches_date
        ON matches(match_date)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_odds_schedule
        ON odds(schedule_id)
    """)

    cur.execute("""
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
#
# 같은 경기 + 같은 업체면 UPDATE
# 새로운 업체면 INSERT
# =========================================================

def save_odds(
    schedule_id,
    company_id,
    company_name,
    final_home,
    final_draw,
    final_away
):

    if not company_name:

        return False

    company_name = str(
        company_name
    ).strip()

    if not company_name:

        return False

    conn = get_connection()

    try:

        # -------------------------------------------------
        # 기존 업체 확인
        # -------------------------------------------------

        existing = conn.execute("""
            SELECT id

            FROM odds

            WHERE schedule_id = ?

              AND company_name = ?

        """, (

            str(schedule_id),

            company_name

        )).fetchone()

        # -------------------------------------------------
        # 기존 데이터 UPDATE
        # -------------------------------------------------

        if existing:

            conn.execute("""
                UPDATE odds

                SET

                    company_id = ?,

                    final_home = ?,

                    final_draw = ?,

                    final_away = ?

                WHERE id = ?

            """, (

                str(company_id or ""),

                final_home,

                final_draw,

                final_away,

                existing["id"]

            ))

        # -------------------------------------------------
        # 새로운 업체 INSERT
        # -------------------------------------------------

        else:

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

            """, (

                str(schedule_id),

                str(company_id or ""),

                company_name,

                final_home,

                final_draw,

                final_away

            ))

        conn.commit()

        return True

    except Exception:

        conn.rollback()

        return False

    finally:

        conn.close()


# =========================================================
# 경기 존재 여부
# =========================================================

def match_exists(schedule_id):

    conn = get_connection()

    row = conn.execute("""
        SELECT schedule_id

        FROM matches

        WHERE schedule_id = ?

    """, (

        str(schedule_id),

    )).fetchone()

    conn.close()

    return row is not None


# =========================================================
# 경기 하나
# =========================================================

def get_match(schedule_id):

    conn = get_connection()

    row = conn.execute("""
        SELECT *

        FROM matches

        WHERE schedule_id = ?

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
# 특정 경기 배당
# =========================================================

def get_match_final_odds(schedule_id):

    conn = get_connection()

    rows = conn.execute("""
        SELECT *

        FROM odds

        WHERE schedule_id = ?

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
# 실제 DB에 존재하는 모든 업체
#
# 중요:
# 여기에는 3개 업체 제한이 없음
# =========================================================

def get_company_names():

    conn = get_connection()

    rows = conn.execute("""
        SELECT DISTINCT company_name

        FROM odds

        WHERE company_name IS NOT NULL

          AND TRIM(company_name) != ''

        ORDER BY company_name COLLATE NOCASE

    """).fetchall()

    conn.close()

    result = []

    seen = set()

    for row in rows:

        name = str(
            row["company_name"]
        ).strip()

        if not name:
            continue

        normalized = normalize_company_name(
            name
        )

        if not normalized:
            continue

        if normalized in seen:
            continue

        seen.add(normalized)

        result.append(name)

    return result


# =========================================================
# 업체별 저장 개수
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
# 업체명 실제 DB 이름 찾기
#
# 예:
# 입력: bet365
# DB: Bet365
#
# → Bet365 반환
# =========================================================

def find_company_name(company_name):

    if not company_name:

        return None

    wanted = normalize_company_name(
        company_name
    )

    if not wanted:

        return None

    conn = get_connection()

    rows = conn.execute("""
        SELECT DISTINCT company_name

        FROM odds

        WHERE company_name IS NOT NULL

          AND TRIM(company_name) != ''

    """).fetchall()

    conn.close()

    for row in rows:

        actual = str(
            row["company_name"]
        ).strip()

        if normalize_company_name(
            actual
        ) == wanted:

            return actual

    return None


# =========================================================
# 여러 업체 배당 검색
#
# 선택한 업체들의 배당이
# 모두 일치하는 경기만 검색
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

    for input_company_name, odds in company_odds.items():

        actual_company_name = (
            find_company_name(
                input_company_name
            )
        )

        if not actual_company_name:

            conn.close()

            return []

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

            conn.close()

            return []

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

            actual_company_name,

            home,

            draw,

            away

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

    # -----------------------------------------------------
    # 결과 없음
    # -----------------------------------------------------

    if not schedule_ids:

        conn.close()

        return []

    # -----------------------------------------------------
    # 경기 가져오기
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
# 특정 업체의 모든 배당
# =========================================================

def get_company_odds(company_name):

    actual_name = find_company_name(
        company_name
    )

    if not actual_name:

        return []

    conn = get_connection()

    rows = conn.execute("""
        SELECT *

        FROM odds

        WHERE company_name = ?

        ORDER BY schedule_id DESC

    """, (

        actual_name,

    )).fetchall()

    conn.close()

    return rows


# =========================================================
# DB 삭제
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
# DB 위치
# =========================================================

def get_database_path():

    return os.path.abspath(
        DB_FILE
    )


# =========================================================
# 직접 실행
# =========================================================

if __name__ == "__main__":

    init_database()

    print(
        "DB:",
        get_database_path()
    )

    print(
        "경기:",
        get_match_count()
    )

    print(
        "배당:",
        get_odds_count()
    )

    print(
        "업체:"
    )

    for company in get_company_names():

        print(
            "-",
            company
    )
