import sqlite3
from pathlib import Path
from datetime import datetime


# ==========================================
# DB 파일 위치
# ==========================================

DB_FILE = Path(__file__).parent / "historical_odds.db"


# ==========================================
# DB 연결
# ==========================================

def get_connection():

    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


# ==========================================
# DB 생성
# ==========================================

def create_database():

    conn = get_connection()

    cur = conn.cursor()


    # ======================================
    # 경기 정보 테이블
    # ======================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (

            match_id TEXT PRIMARY KEY,

            sport TEXT NOT NULL,

            country TEXT,

            league TEXT,

            match_date TEXT,

            home_team TEXT NOT NULL,

            away_team TEXT NOT NULL,

            home_score INTEGER,

            away_score INTEGER,

            result TEXT,

            detail_url TEXT,

            source TEXT DEFAULT 'scoreman',

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)


    # ======================================
    # 배당 정보 테이블
    # ======================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS odds (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            match_id TEXT NOT NULL,

            bookmaker TEXT NOT NULL,

            market TEXT NOT NULL,

            initial_home REAL,

            initial_draw REAL,

            initial_away REAL,

            final_home REAL,

            final_draw REAL,

            final_away REAL,

            change_home REAL,

            change_draw REAL,

            change_away REAL,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

            UNIQUE (
                match_id,
                bookmaker,
                market
            ),

            FOREIGN KEY (match_id)
                REFERENCES matches(match_id)
        )
    """)


    # ======================================
    # 크롤링 기록 테이블
    # ======================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS crawl_log (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            crawl_type TEXT,

            start_date TEXT,

            end_date TEXT,

            total_found INTEGER DEFAULT 0,

            total_saved INTEGER DEFAULT 0,

            total_updated INTEGER DEFAULT 0,

            total_error INTEGER DEFAULT 0,

            started_at TEXT,

            finished_at TEXT,

            message TEXT
        )
    """)


    # ======================================
    # 검색 속도 향상용 인덱스
    # ======================================

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_matches_date
        ON matches(match_date)
    """)


    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_matches_league
        ON matches(league)
    """)


    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_matches_teams
        ON matches(home_team, away_team)
    """)


    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_odds_match
        ON odds(match_id)
    """)


    conn.commit()

    conn.close()


# ==========================================
# 경기 저장
# ==========================================

def save_match(data):

    conn = get_connection()

    cur = conn.cursor()


    cur.execute("""
        INSERT INTO matches (

            match_id,
            sport,
            country,
            league,
            match_date,
            home_team,
            away_team,
            home_score,
            away_score,
            result,
            detail_url,
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
            ?,
            ?,
            ?,
            ?,
            ?

        )

        ON CONFLICT(match_id)

        DO UPDATE SET

            home_score =
                COALESCE(
                    excluded.home_score,
                    matches.home_score
                ),

            away_score =
                COALESCE(
                    excluded.away_score,
                    matches.away_score
                ),

            result =
                COALESCE(
                    excluded.result,
                    matches.result
                ),

            detail_url =
                COALESCE(
                    excluded.detail_url,
                    matches.detail_url
                ),

            updated_at =
                CURRENT_TIMESTAMP
    """, (

        data["match_id"],

        data.get(
            "sport",
            "축구"
        ),

        data.get(
            "country"
        ),

        data.get(
            "league"
        ),

        data.get(
            "match_date"
        ),

        data.get(
            "home_team"
        ),

        data.get(
            "away_team"
        ),

        data.get(
            "home_score"
        ),

        data.get(
            "away_score"
        ),

        data.get(
            "result"
        ),

        data.get(
            "detail_url"
        ),

        data.get(
            "source",
            "scoreman"
        )
    ))


    conn.commit()

    conn.close()


# ==========================================
# 배당 저장
# ==========================================

def save_odds(data):

    conn = get_connection()

    cur = conn.cursor()


    initial_home = data.get(
        "initial_home"
    )

    initial_draw = data.get(
        "initial_draw"
    )

    initial_away = data.get(
        "initial_away"
    )


    final_home = data.get(
        "final_home"
    )

    final_draw = data.get(
        "final_draw"
    )

    final_away = data.get(
        "final_away"
    )


    # ======================================
    # 배당 변동 계산
    # ======================================

    change_home = None

    change_draw = None

    change_away = None


    if (
        initial_home is not None
        and final_home is not None
    ):

        change_home = (
            final_home
            - initial_home
        )


    if (
        initial_draw is not None
        and final_draw is not None
    ):

        change_draw = (
            final_draw
            - initial_draw
        )


    if (
        initial_away is not None
        and final_away is not None
    ):

        change_away = (
            final_away
            - initial_away
        )


    # ======================================
    # DB 저장
    # ======================================

    cur.execute("""
        INSERT INTO odds (

            match_id,

            bookmaker,

            market,

            initial_home,

            initial_draw,

            initial_away,

            final_home,

            final_draw,

            final_away,

            change_home,

            change_draw,

            change_away

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
            ?,

            ?,
            ?,
            ?

        )

        ON CONFLICT(
            match_id,
            bookmaker,
            market
        )

        DO UPDATE SET

            final_home =
                COALESCE(
                    excluded.final_home,
                    odds.final_home
                ),

            final_draw =
                COALESCE(
                    excluded.final_draw,
                    odds.final_draw
                ),

            final_away =
                COALESCE(
                    excluded.final_away,
                    odds.final_away
                ),

            change_home =
                excluded.change_home,

            change_draw =
                excluded.change_draw,

            change_away =
                excluded.change_away,

            updated_at =
                CURRENT_TIMESTAMP

    """, (

        data["match_id"],

        data.get(
            "bookmaker",
            "unknown"
        ),

        data.get(
            "market",
            "1X2"
        ),

        initial_home,

        initial_draw,

        initial_away,

        final_home,

        final_draw,

        final_away,

        change_home,

        change_draw,

        change_away

    ))


    conn.commit()

    conn.close()


# ==========================================
# 경기 결과 계산
# ==========================================

def calculate_result(
    home_score,
    away_score
):

    if (
        home_score is None
        or away_score is None
    ):

        return None


    if home_score > away_score:

        return "승"


    elif home_score < away_score:

        return "패"


    else:

        return "무"


# ==========================================
# 경기 ID 생성
# ==========================================

def make_match_id(
    match_date,
    home_team,
    away_team
):

    text = (
        f"{match_date}_"
        f"{home_team}_"
        f"{away_team}"
    )

    return text.replace(
        " ",
        "_"
    )


# ==========================================
# DB 상태 확인
# ==========================================

def get_database_status():

    conn = get_connection()

    cur = conn.cursor()


    cur.execute(
        "SELECT COUNT(*) FROM matches"
    )

    match_count = cur.fetchone()[0]


    cur.execute(
        "SELECT COUNT(*) FROM odds"
    )

    odds_count = cur.fetchone()[0]


    conn.close()


    return {
        "matches": match_count,
        "odds": odds_count
    }


# ==========================================
# 직접 실행했을 때 DB 생성
# ==========================================

if __name__ == "__main__":

    print("DB 생성 시작...")

    create_database()

    status = get_database_status()


    print(
        "================================"
    )

    print(
        "historical_odds.db 생성 완료"
    )

    print(
        f"경기 데이터: {status['matches']}건"
    )

    print(
        f"배당 데이터: {status['odds']}건"
    )

    print(
        f"파일 위치: {DB_FILE}"
    )

    print(
        "================================"
    )
