# database.py
# -*- coding: utf-8 -*-

import sqlite3
import os
from typing import Optional, Dict, Any, List


# =========================================================
# DB 경로
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "scoreman.db")


# =========================================================
# DB 연결
# =========================================================

def get_connection():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    # SQLite 안정성
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

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
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            schedule_id TEXT UNIQUE,

            home_team TEXT,
            away_team TEXT,

            match_date TEXT,

            home_score INTEGER,
            away_score INTEGER,

            result TEXT,

            page_url TEXT,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -----------------------------------------------------
    # 배당 테이블
    # -----------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS odds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            schedule_id TEXT,

            company_id INTEGER,
            company_name TEXT,

            -- 초기 승무패 배당
            euro_f_home REAL,
            euro_f_draw REAL,
            euro_f_away REAL,

            -- 최종 승무패 배당
            euro_l_home REAL,
            euro_l_draw REAL,
            euro_l_away REAL,

            -- 초기 O/U
            ou_f_home REAL,
            ou_f_goal REAL,
            ou_f_away REAL,

            -- 최종 O/U
            ou_l_home REAL,
            ou_l_goal REAL,
            ou_l_away REAL,

            -- 초기 핸디캡
            ah_f_home REAL,
            ah_f_goal REAL,
            ah_f_away REAL,

            -- 최종 핸디캡
            ah_l_home REAL,
            ah_l_goal REAL,
            ah_l_away REAL,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(schedule_id, company_id)
        )
    """)

    # -----------------------------------------------------
    # 안전한 인덱스 생성
    # -----------------------------------------------------

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_matches_schedule
        ON matches(schedule_id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_odds_schedule
        ON odds(schedule_id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_odds_company
        ON odds(company_id)
    """)

    conn.commit()
    conn.close()


# =========================================================
# 경기 저장
# =========================================================

def save_match(
    schedule_id,
    home_team,
    away_team,
    match_date="",
    home_score=None,
    away_score=None,
    result="",
    page_url=""
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO matches (
            schedule_id,
            home_team,
            away_team,
            match_date,
            home_score,
            away_score,
            result,
            page_url
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(schedule_id)
        DO UPDATE SET
            home_team=excluded.home_team,
            away_team=excluded.away_team,
            match_date=excluded.match_date,
            home_score=excluded.home_score,
            away_score=excluded.away_score,
            result=excluded.result,
            page_url=excluded.page_url,
            updated_at=CURRENT_TIMESTAMP
    """, (
        str(schedule_id),
        home_team,
        away_team,
        match_date,
        home_score,
        away_score,
        result,
        page_url
    ))

    conn.commit()
    conn.close()


# =========================================================
# 배당 숫자 변환
# =========================================================

def to_float(value):

    if value is None:
        return None

    try:

        value = str(value).strip()

        if value == "":
            return None

        if value in ("-", "null", "None"):
            return None

        return float(value)

    except Exception:
        return None


# =========================================================
# 배당 저장
# =========================================================

def save_odds(
    schedule_id,
    company_id,
    company_name,
    euro_f=None,
    euro_l=None,
    ou_f=None,
    ou_l=None,
    ah_f=None,
    ah_l=None
):

    euro_f = euro_f or {}
    euro_l = euro_l or {}

    ou_f = ou_f or {}
    ou_l = ou_l or {}

    ah_f = ah_f or {}
    ah_l = ah_l or {}

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO odds (
            schedule_id,
            company_id,
            company_name,

            euro_f_home,
            euro_f_draw,
            euro_f_away,

            euro_l_home,
            euro_l_draw,
            euro_l_away,

            ou_f_home,
            ou_f_goal,
            ou_f_away,

            ou_l_home,
            ou_l_goal,
            ou_l_away,

            ah_f_home,
            ah_f_goal,
            ah_f_away,

            ah_l_home,
            ah_l_goal,
            ah_l_away
        )

        VALUES (
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?
        )

        ON CONFLICT(schedule_id, company_id)
        DO UPDATE SET

            company_name=excluded.company_name,

            euro_f_home=excluded.euro_f_home,
            euro_f_draw=excluded.euro_f_draw,
            euro_f_away=excluded.euro_f_away,

            euro_l_home=excluded.euro_l_home,
            euro_l_draw=excluded.euro_l_draw,
            euro_l_away=excluded.euro_l_away,

            ou_f_home=excluded.ou_f_home,
            ou_f_goal=excluded.ou_f_goal,
            ou_f_away=excluded.ou_f_away,

            ou_l_home=excluded.ou_l_home,
            ou_l_goal=excluded.ou_l_goal,
            ou_l_away=excluded.ou_l_away,

            ah_f_home=excluded.ah_f_home,
            ah_f_goal=excluded.ah_f_goal,
            ah_f_away=excluded.ah_f_away,

            ah_l_home=excluded.ah_l_home,
            ah_l_goal=excluded.ah_l_goal,
            ah_l_away=excluded.ah_l_away
    """, (

        str(schedule_id),
        company_id,
        company_name,

        to_float(euro_f.get("u")),
        to_float(euro_f.get("g")),
        to_float(euro_f.get("d")),

        to_float(euro_l.get("u")),
        to_float(euro_l.get("g")),
        to_float(euro_l.get("d")),

        to_float(ou_f.get("u")),
        to_float(ou_f.get("g")),
        to_float(ou_f.get("d")),

        to_float(ou_l.get("u")),
        to_float(ou_l.get("g")),
        to_float(ou_l.get("d")),

        to_float(ah_f.get("u")),
        to_float(ah_f.get("g")),
        to_float(ah_f.get("d")),

        to_float(ah_l.get("u")),
        to_float(ah_l.get("g")),
        to_float(ah_l.get("d"))
    ))

    conn.commit()
    conn.close()


# =========================================================
# 여러 배당업체 한 번에 저장
# =========================================================

def save_all_odds(schedule_id, mixodds):

    if not mixodds:
        return 0

    count = 0

    for item in mixodds:

        try:

            save_odds(
                schedule_id=schedule_id,

                company_id=item.get("cid"),

                company_name=item.get("cn", ""),

                euro_f=item.get("euro", {}).get("f", {}),
                euro_l=item.get("euro", {}).get("l", {}),

                ou_f=item.get("ou", {}).get("f", {}),
                ou_l=item.get("ou", {}).get("l", {}),

                ah_f=item.get("ah", {}).get("f", {}),
                ah_l=item.get("ah", {}).get("l", {})
            )

            count += 1

        except Exception:
            continue

    return count


# =========================================================
# 경기 조회
# =========================================================

def get_match(schedule_id):

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM matches
        WHERE schedule_id = ?
        LIMIT 1
    """, (str(schedule_id),))

    row = cur.fetchone()

    conn.close()

    if row:
        return dict(row)

    return None


# =========================================================
# 경기의 배당 조회
# =========================================================

def get_odds(schedule_id):

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM odds
        WHERE schedule_id = ?
        ORDER BY company_id
    """, (str(schedule_id),))

    rows = cur.fetchall()

    conn.close()

    return [dict(row) for row in rows]


# =========================================================
# 전체 경기 조회
# =========================================================

def get_all_matches(limit=1000):

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM matches
        ORDER BY id DESC
        LIMIT ?
    """, (int(limit),))

    rows = cur.fetchall()

    conn.close()

    return [dict(row) for row in rows]


# =========================================================
# 전체 배당 조회
# =========================================================

def get_all_odds(limit=5000):

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM odds
        ORDER BY id DESC
        LIMIT ?
    """, (int(limit),))

    rows = cur.fetchall()

    conn.close()

    return [dict(row) for row in rows]


# =========================================================
# 경기 + 배당 통합 조회
# =========================================================

def get_match_with_odds(schedule_id):

    match = get_match(schedule_id)

    odds = get_odds(schedule_id)

    return {
        "match": match,
        "odds": odds
    }


# =========================================================
# DB 통계
# =========================================================

def get_database_stats():

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) AS cnt
        FROM matches
    """)

    match_count = cur.fetchone()["cnt"]

    cur.execute("""
        SELECT COUNT(*) AS cnt
        FROM odds
    """)

    odds_count = cur.fetchone()["cnt"]

    conn.close()

    return {
        "matches": match_count,
        "odds": odds_count
    }


# =========================================================
# 특정 경기 삭제
# =========================================================

def delete_match(schedule_id):

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        DELETE FROM odds
        WHERE schedule_id = ?
    """, (str(schedule_id),))

    cur.execute("""
        DELETE FROM matches
        WHERE schedule_id = ?
    """, (str(schedule_id),))

    conn.commit()
    conn.close()


# =========================================================
# 전체 DB 초기화
# =========================================================

def clear_database():

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("DELETE FROM odds")
    cur.execute("DELETE FROM matches")

    conn.commit()
    conn.close()


# =========================================================
# 모듈 직접 실행 테스트
# =========================================================

if __name__ == "__main__":

    print("Scoreman SQLite DB 초기화")

    init_database()

    stats = get_database_stats()

    print("경기 데이터:", stats["matches"])
    print("배당 데이터:", stats["odds"])
    print("DB:", DB_PATH)
