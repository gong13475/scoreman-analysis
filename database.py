import sqlite3
from pathlib import Path
from datetime import datetime


DB_FILE = Path(__file__).parent / "historical_odds.db"


def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def create_database():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            source TEXT,
            bookmaker TEXT,

            sport TEXT,
            league TEXT,

            match_date TEXT,
            match_time TEXT,

            home_team TEXT,
            away_team TEXT,

            home_odds REAL,
            draw_odds REAL,
            away_odds REAL,

            result TEXT,

            created_at TEXT,

            UNIQUE(
                source,
                bookmaker,
                match_date,
                match_time,
                home_team,
                away_team
            )
        )
    """)

    conn.commit()
    conn.close()


def save_match(
    source="Scoreman",
    bookmaker="",
    sport="축구",
    league="",
    match_date="",
    match_time="",
    home_team="",
    away_team="",
    home_odds=0,
    draw_odds=0,
    away_odds=0,
    result=""
):

    create_database()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO matches (
            source,
            bookmaker,
            sport,
            league,
            match_date,
            match_time,
            home_team,
            away_team,
            home_odds,
            draw_odds,
            away_odds,
            result,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        source,
        bookmaker,
        sport,
        league,
        match_date,
        match_time,
        home_team,
        away_team,
        home_odds,
        draw_odds,
        away_odds,
        result,
        datetime.now().isoformat()
    ))

    inserted = cur.rowcount

    conn.commit()
    conn.close()

    return inserted


def save_matches(matches):

    count = 0

    for match in matches:

        count += save_match(
            source=match.get(
                "source",
                "Scoreman"
            ),

            bookmaker=match.get(
                "bookmaker",
                ""
            ),

            sport=match.get(
                "sport",
                "축구"
            ),

            league=match.get(
                "league",
                ""
            ),

            match_date=match.get(
                "match_date",
                ""
            ),

            match_time=match.get(
                "match_time",
                ""
            ),

            home_team=match.get(
                "home_team",
                ""
            ),

            away_team=match.get(
                "away_team",
                ""
            ),

            home_odds=match.get(
                "home_odds",
                0
            ),

            draw_odds=match.get(
                "draw_odds",
                0
            ),

            away_odds=match.get(
                "away_odds",
                0
            ),

            result=match.get(
                "result",
                ""
            )
        )

    return count


def get_matches(
    limit=10000,
    source="",
    bookmaker="",
    sport="",
    league=""
):

    create_database()

    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT *
        FROM matches
        WHERE 1=1
    """

    params = []

    if source:

        query += """
            AND source = ?
        """

        params.append(source)

    if bookmaker:

        query += """
            AND bookmaker = ?
        """

        params.append(bookmaker)

    if sport:

        query += """
            AND sport = ?
        """

        params.append(sport)

    if league:

        query += """
            AND league = ?
        """

        params.append(league)

    query += """
        ORDER BY match_date DESC,
                 match_time DESC
        LIMIT ?
    """

    params.append(limit)

    cur.execute(
        query,
        params
    )

    rows = cur.fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


def get_database_status():

    create_database()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) AS cnt
        FROM matches
    """)

    total = cur.fetchone()["cnt"]

    cur.execute("""
        SELECT COUNT(DISTINCT bookmaker) AS cnt
        FROM matches
        WHERE bookmaker != ''
    """)

    bookmakers = cur.fetchone()["cnt"]

    conn.close()

    return {
        "matches": total,
        "bookmakers": bookmakers,
        "database": str(DB_FILE)
    }


def clear_database():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM matches"
    )

    conn.commit()
    conn.close()


if __name__ == "__main__":

    create_database()

    print(
        get_database_status()
    )
