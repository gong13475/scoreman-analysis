import sqlite3
import os
from datetime import datetime


DB_FILE = "historical_odds.db"


def get_connection():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id TEXT UNIQUE,
            sport TEXT,
            league TEXT,
            match_date TEXT,
            home_team TEXT,
            away_team TEXT,
            home_score INTEGER,
            away_score INTEGER,
            result TEXT,
            source TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS odds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id TEXT,
            company_id INTEGER,
            company_name TEXT,

            initial_home REAL,
            initial_draw REAL,
            initial_away REAL,

            final_home REAL,
            final_draw REAL,
            final_away REAL,

            result TEXT,
            created_at TEXT,

            UNIQUE(
                schedule_id,
                company_id
            )
        )
    """)

    conn.commit()
    conn.close()


def save_match(
    schedule_id,
    sport,
    league,
    match_date,
    home_team,
    away_team,
    home_score,
    away_score,
    result,
    source="Scoreman"
):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO matches (
            schedule_id,
            sport,
            league,
            match_date,
            home_team,
            away_team,
            home_score,
            away_score,
            result,
            source,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(schedule_id)
        DO UPDATE SET
            sport=excluded.sport,
            league=excluded.league,
            match_date=excluded.match_date,
            home_team=excluded.home_team,
            away_team=excluded.away_team,
            home_score=excluded.home_score,
            away_score=excluded.away_score,
            result=excluded.result,
            source=excluded.source
    """, (
        str(schedule_id),
        sport,
        league,
        match_date,
        home_team,
        away_team,
        home_score,
        away_score,
        result,
        source,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


def save_odds(
    schedule_id,
    company_id,
    company_name,
    initial_home,
    initial_draw,
    initial_away,
    final_home,
    final_draw,
    final_away,
    result
):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
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

            result,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(schedule_id, company_id)
        DO UPDATE SET

            company_name=excluded.company_name,

            initial_home=excluded.initial_home,
            initial_draw=excluded.initial_draw,
            initial_away=excluded.initial_away,

            final_home=excluded.final_home,
            final_draw=excluded.final_draw,
            final_away=excluded.final_away,

            result=excluded.result
    """, (
        str(schedule_id),
        company_id,
        company_name,

        initial_home,
        initial_draw,
        initial_away,

        final_home,
        final_draw,
        final_away,

        result,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


def get_match_count():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM matches
    """)

    count = cur.fetchone()[0]

    conn.close()

    return count


def get_odds_count():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM odds
    """)

    count = cur.fetchone()[0]

    conn.close()

    return count


def get_all_matches():
    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT
            schedule_id,
            sport,
            league,
            match_date,
            home_team,
            away_team,
            home_score,
            away_score,
            result,
            source
        FROM matches
        ORDER BY match_date DESC
    """)

    rows = cur.fetchall()

    conn.close()

    return rows


def get_all_odds():
    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT
            schedule_id,
            company_id,
            company_name,

            initial_home,
            initial_draw,
            initial_away,

            final_home,
            final_draw,
            final_away,

            result
        FROM odds
        ORDER BY schedule_id DESC, company_id
    """)

    rows = cur.fetchall()

    conn.close()

    return rows


def clear_database():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM odds")
    cur.execute("DELETE FROM matches")

    conn.commit()
    conn.close()


# 프로그램 시작 시 DB 자동 생성
init_db()
