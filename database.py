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
    
