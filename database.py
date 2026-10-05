# ============================================================
# database.py
# 스코어맨 분석기
# Turso Cloud SQLite HTTP API 버전
#
# Python 3.14 호환
# libsql-experimental 사용 안 함
# requests만 사용
# ============================================================

import streamlit as st
import requests


# =========================================================
# Turso 연결
# =========================================================

@st.cache_resource
def get_connection():

    url = st.secrets.get(
        "TURSO_DATABASE_URL",
        ""
    ).strip()

    token = st.secrets.get(
        "TURSO_AUTH_TOKEN",
        ""
    ).strip()

    if not url:
        raise RuntimeError(
            "TURSO_DATABASE_URL이 없습니다.\n"
            "Streamlit Cloud → Manage app → Settings → Secrets를 확인하세요."
        )

    if not token:
        raise RuntimeError(
            "TURSO_AUTH_TOKEN이 없습니다.\n"
            "Streamlit Cloud → Manage app → Settings → Secrets를 확인하세요."
        )

    # -----------------------------------------------------
    # libsql:// → https://
    # -----------------------------------------------------

    if url.startswith("libsql://"):
        url = (
            "https://"
            + url[len("libsql://"):]
        )

    # -----------------------------------------------------
    # Turso HTTP Pipeline
    # -----------------------------------------------------

    if not url.endswith("/v2/pipeline"):
        url = (
            url.rstrip("/")
            + "/v2/pipeline"
        )

    return {
        "url": url,
        "token": token
    }


# =========================================================
# 숫자 변환
# =========================================================

def _to_float(value):
    """
    배당값을 안전하게 float로 변환합니다.

    예:
        "1.38"   → 1.38
        " 1.38 " → 1.38
        1.38     → 1.38
        ""       → None
        None     → None
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, str):

        value = value.strip()

        if not value:
            return None

        value = value.replace(",", "")

    try:

        return float(value)

    except (
        TypeError,
        ValueError
    ):

        return None


# =========================================================
# 정수 변환
# =========================================================

def _to_int(value):

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        return int(value)

    except (
        TypeError,
        ValueError
    ):

        try:
            return int(
                float(
                    str(value).strip()
                )
            )

        except Exception:

            return None


# =========================================================
# Turso HTTP 타입 변환
# =========================================================

def _encode_value(value):

    if value is None:

        return {
            "type": "null"
        }

    if isinstance(value, bool):

        return {
            "type": "integer",
            "value": (
                "1"
                if value
                else "0"
            )
        }

    if isinstance(value, int):

        return {
            "type": "integer",
            "value": str(value)
        }

    if isinstance(value, float):

        return {
            "type": "float",
            "value": str(value)
        }

    return {
        "type": "text",
        "value": str(value)
    }


# =========================================================
# Turso HTTP 요청
# =========================================================

def _request(
    sql,
    params=()
):

    conn = get_connection()

    args = [
        _encode_value(value)
        for value in params
    ]

    payload = {

        "requests": [

            {
                "type": "execute",

                "stmt": {

                    "sql":
                        sql,

                    "args":
                        args
                }
            },

            {
                "type":
                    "close"
            }
        ]
    }

    headers = {

        "Authorization":
            "Bearer "
            + conn["token"],

        "Content-Type":
            "application/json"
    }

    response = requests.post(
        conn["url"],
        headers=headers,
        json=payload,
        timeout=60
    )

    if response.status_code != 200:

        raise RuntimeError(
            "Turso HTTP 오류 "
            f"{response.status_code}: "
            f"{response.text[:2000]}"
        )

    try:

        data = response.json()

    except Exception as e:

        raise RuntimeError(
            "Turso 응답 JSON 오류: "
            + str(e)
        )

    if "results" not in data:

        raise RuntimeError(
            "Turso 응답 오류: "
            + str(data)[:3000]
        )

    results = data.get(
        "results",
        []
    )

    if not results:

        raise RuntimeError(
            "Turso 응답에 results가 없습니다."
        )

    first = results[0]

    if first.get("type") == "error":

        raise RuntimeError(
            "Turso SQL 오류: "
            + str(first)
        )

    result = first.get(
        "result",
        {}
    )

    if result.get("type") == "error":

        raise RuntimeError(
            "Turso SQL 오류: "
            + str(result)
        )

    return result


# =========================================================
# 여러 SQL 일괄 실행
# =========================================================

def _request_many(
    statements
):

    if not statements:
        return True

    conn = get_connection()

    requests_data = []

    for sql, params in statements:

        requests_data.append({

            "type":
                "execute",

            "stmt": {

                "sql":
                    sql,

                "args": [
                    _encode_value(value)
                    for value in params
                ]
            }
        })

    requests_data.append({
        "type": "close"
    })

    payload = {
        "requests":
            requests_data
    }

    headers = {

        "Authorization":
            "Bearer "
            + conn["token"],

        "Content-Type":
            "application/json"
    }

    response = requests.post(
        conn["url"],
        headers=headers,
        json=payload,
        timeout=120
    )

    if response.status_code != 200:

        raise RuntimeError(
            "Turso HTTP 오류 "
            f"{response.status_code}: "
            f"{response.text[:2000]}"
        )

    try:

        data = response.json()

    except Exception as e:

        raise RuntimeError(
            "Turso 응답 JSON 오류: "
            + str(e)
        )

    if "results" not in data:

        raise RuntimeError(
            "Turso 응답 오류: "
            + str(data)[:3000]
        )

    for item in data["results"]:

        if item.get("type") == "error":

            raise RuntimeError(
                "Turso SQL 오류: "
                + str(item)
            )

        result = item.get(
            "result",
            {}
        )

        if result.get("type") == "error":

            raise RuntimeError(
                "Turso SQL 오류: "
                + str(result)
            )

    return data


# =========================================================
# Turso 값 변환
# =========================================================

def _decode_value(value):

    if value is None:
        return None

    if not isinstance(value, dict):
        return value

    value_type = value.get(
        "type"
    )

    raw = value.get(
        "value"
    )

    if value_type == "null":

        return None

    if value_type == "integer":

        try:
            return int(raw)

        except Exception:
            return raw

    if value_type == "float":

        try:
            return float(raw)

        except Exception:
            return raw

    if value_type == "blob":

        return raw

    return raw


# =========================================================
# Turso 결과 → Python dict
# =========================================================

def _get_rows(result):

    cols = result.get(
        "cols",
        []
    )

    rows = result.get(
        "rows",
        []
    )

    column_names = []

    for col in cols:

        if isinstance(col, dict):

            column_names.append(
                col.get(
                    "name",
                    ""
                )
            )

        else:

            column_names.append(
                str(col)
            )

    output = []

    for row in rows:

        values = [
            _decode_value(value)
            for value in row
        ]

        output.append(
            dict(
                zip(
                    column_names,
                    values
                )
            )
        )

    return output


# =========================================================
# SELECT
# =========================================================

def _select(
    sql,
    params=()
):

    result = _request(
        sql,
        params
    )

    return _get_rows(
        result
    )


# =========================================================
# DB 초기화
# =========================================================

def init_database():

    try:

        statements = [

            # -------------------------------------------------
            # 경기 테이블
            # -------------------------------------------------

            (
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
                    source TEXT DEFAULT 'Scoreman',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """,
                ()
            ),

            # -------------------------------------------------
            # 배당 테이블
            # -------------------------------------------------

            (
                """
                CREATE TABLE IF NOT EXISTS odds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule_id TEXT NOT NULL,
                    bookmaker TEXT NOT NULL,
                    home_odds REAL,
                    draw_odds REAL,
                    away_odds REAL,
                    odds_type TEXT DEFAULT 'final',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                    UNIQUE (
                        schedule_id,
                        bookmaker,
                        odds_type
                    )
                )
                """,
                ()
            ),

            # -------------------------------------------------
            # 경기 날짜 인덱스
            # -------------------------------------------------

            (
                """
                CREATE INDEX IF NOT EXISTS
                idx_matches_date
                ON matches(match_date)
                """,
                ()
            ),

            # -------------------------------------------------
            # 결과 인덱스
            # -------------------------------------------------

            (
                """
                CREATE INDEX IF NOT EXISTS
                idx_matches_result
                ON matches(result)
                """,
                ()
            ),

            # -------------------------------------------------
            # 배당 경기 ID 인덱스
            # -------------------------------------------------

            (
                """
                CREATE INDEX IF NOT EXISTS
                idx_odds_schedule
                ON odds(schedule_id)
                """,
                ()
            ),

            # -------------------------------------------------
            # 업체 인덱스
            # -------------------------------------------------

            (
                """
                CREATE INDEX IF NOT EXISTS
                idx_odds_bookmaker
                ON odds(bookmaker)
                """,
                ()
            ),

            # -------------------------------------------------
            # 배당 검색 인덱스
            # -------------------------------------------------

            (
                """
                CREATE INDEX IF NOT EXISTS
                idx_odds_values
                ON odds(
                    bookmaker,
                    home_odds,
                    draw_odds,
                    away_odds
                )
                """,
                ()
            )
        ]

        _request_many(
            statements
        )

        # 연결 확인

        _select(
            "SELECT 1 AS test"
        )

        return True

    except Exception as e:

        print(
            "Turso DB 초기화 오류:",
            e
        )

        return False


# =========================================================
# DB 상태
# =========================================================

def get_database_status():

    match_rows = _select(
        """
        SELECT COUNT(*) AS count
        FROM matches
        """
    )

    odds_rows = _select(
        """
        SELECT COUNT(*) AS count
        FROM odds
        """
    )

    bookmaker_rows = _select(
        """
        SELECT COUNT(
            DISTINCT bookmaker
        ) AS count
        FROM odds
        """
    )

    return {

        "matches":
            int(
                match_rows[0]["count"]
                if match_rows
                else 0
            ),

        "odds":
            int(
                odds_rows[0]["count"]
                if odds_rows
                else 0
            ),

        "bookmakers":
            int(
                bookmaker_rows[0]["count"]
                if bookmaker_rows
                else 0
            ),

        "db_exists":
            True,

        "db_file":
            "Turso Cloud SQLite"
    }


# =========================================================
# DB 저장용량
# =========================================================

def get_storage_usage():

    try:

        page_rows = _select(
            "PRAGMA page_count"
        )

        size_rows = _select(
            "PRAGMA page_size"
        )

        page_count = int(
            page_rows[0]["page_count"]
        )

        page_size = int(
            size_rows[0]["page_size"]
        )

        size_bytes = (
            page_count
            * page_size
        )

        return {

            "success":
                True,

            "size_bytes":
                size_bytes,

            "size_mb":
                size_bytes
                / 1024
                / 1024,

            "size_gb":
                size_bytes
                / 1024
                / 1024
                / 1024,

            "message":
                ""
        }

    except Exception as e:

        return {

            "success":
                False,

            "size_bytes":
                0,

            "size_mb":
                0,

            "size_gb":
                0,

            "message":
                str(e)
        }


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

    _request(

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
            ?, ?, ?, ?, ?, ?, ?, ?,
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

            _to_int(home_score),

            _to_int(away_score),

            result,

            source
        )
    )

    return True


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

    home_odds = _to_float(
        final_home
    )

    draw_odds = _to_float(
        final_draw
    )

    away_odds = _to_float(
        final_away
    )

    # -----------------------------------------------------
    # 정상적인 승/무/패 숫자가 없으면 저장하지 않음
    # -----------------------------------------------------

    if (
        home_odds is None
        or draw_odds is None
        or away_odds is None
    ):

        return False

    _request(

        """
        INSERT INTO odds (
            schedule_id,
            bookmaker,
            home_odds,
            draw_odds,
            away_odds,
            odds_type
        )
        VALUES (
            ?, ?, ?, ?, ?, 'final'
        )

        ON CONFLICT(
            schedule_id,
            bookmaker,
            odds_type
        )

        DO UPDATE SET

            home_odds =
                excluded.home_odds,

            draw_odds =
                excluded.draw_odds,

            away_odds =
                excluded.away_odds
        """,

        (
            str(schedule_id),

            str(
                company_name or ""
            ),

            home_odds,

            draw_odds,

            away_odds
        )
    )

    return True


# =========================================================
# 경기 + 배당 일괄 저장
# =========================================================

def save_match_with_odds(
    match,
    odds_list
):

    schedule_id = str(
        match["schedule_id"]
    )

    statements = []

    # =====================================================
    # 경기 저장
    # =====================================================

    statements.append((

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
            ?, ?, ?, ?, ?, ?, ?, ?,
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
            schedule_id,

            match.get(
                "match_date",
                ""
            ),

            match.get(
                "home_team",
                ""
            ),

            match.get(
                "away_team",
                ""
            ),

            _to_int(
                match.get(
                    "home_score"
                )
            ),

            _to_int(
                match.get(
                    "away_score"
                )
            ),

            match.get(
                "result",
                ""
            ),

            match.get(
                "source",
                "Scoreman"
            )
        )
    ))

    # =====================================================
    # 배당 저장
    # =====================================================

    saved = 0

    for odds in (
        odds_list or []
    ):

        company_name = str(
            odds.get(
                "company_name",
                ""
            )
            or ""
        ).strip()

        if not company_name:
            continue

        # -------------------------------------------------
        # 중요:
        # Scoreman에서 "1.38"이 문자열로 들어와도
        # 여기서 float 1.38로 변환합니다.
        # -------------------------------------------------

        home_odds = _to_float(
            odds.get(
                "final_home"
            )
        )

        draw_odds = _to_float(
            odds.get(
                "final_draw"
            )
        )

        away_odds = _to_float(
            odds.get(
                "final_away"
            )
        )

        # -------------------------------------------------
        # 숫자로 변환되지 않는 배당은 저장하지 않음
        # -------------------------------------------------

        if (
            home_odds is None
            or draw_odds is None
            or away_odds is None
        ):

            continue

        statements.append((

            """
            INSERT INTO odds (
                schedule_id,
                bookmaker,
                home_odds,
                draw_odds,
                away_odds,
                odds_type
            )
            VALUES (
                ?, ?, ?, ?, ?, 'final'
            )

            ON CONFLICT(
                schedule_id,
                bookmaker,
                odds_type
            )

            DO UPDATE SET

                home_odds =
                    excluded.home_odds,

                draw_odds =
                    excluded.draw_odds,

                away_odds =
                    excluded.away_odds
            """,

            (
                schedule_id,

                company_name,

                home_odds,

                draw_odds,

                away_odds
            )
        ))

        saved += 1

    # =====================================================
    # Turso 일괄 저장
    # =====================================================

    _request_many(
        statements
    )

    return saved


# =========================================================
# 경기 조회
# =========================================================

def get_match(
    schedule_id
):

    rows = _select(

        """
        SELECT *
        FROM matches
        WHERE schedule_id = ?
        LIMIT 1
        """,

        (
            str(schedule_id),
        )
    )

    if rows:
        return rows[0]

    return None


# =========================================================
# 전체 경기
# =========================================================

def get_all_matches():

    return _select(

        """
        SELECT *
        FROM matches
        ORDER BY match_date DESC
        """
    )


# =========================================================
# 전체 배당
# =========================================================

def get_all_odds():

    return _select(

        """
        SELECT *
        FROM odds
        ORDER BY schedule_id DESC
        """
    )


# =========================================================
# 특정 경기 최종배당
# =========================================================

def get_match_final_odds(
    schedule_id
):

    return _select(

        """
        SELECT *
        FROM odds
        WHERE schedule_id = ?
        AND odds_type = 'final'
        ORDER BY bookmaker
        """,

        (
            str(schedule_id),
        )
    )


# =========================================================
# 경기 수
# =========================================================

def get_match_count():

    rows = _select(

        """
        SELECT COUNT(*) AS count
        FROM matches
        """
    )

    return int(
        rows[0]["count"]
        if rows
        else 0
    )


# =========================================================
# 배당 수
# =========================================================

def get_odds_count():

    rows = _select(

        """
        SELECT COUNT(*) AS count
        FROM odds
        """
    )

    return int(
        rows[0]["count"]
        if rows
        else 0
    )


# =========================================================
# 업체 목록
# =========================================================

def get_company_names():

    rows = _select(

        """
        SELECT DISTINCT bookmaker
        FROM odds
        WHERE bookmaker IS NOT NULL
        AND bookmaker != ''
        ORDER BY bookmaker
        """
    )

    return [

        str(
            row["bookmaker"]
        )

        for row in rows

    ]


# =========================================================
# 업체별 저장량
# =========================================================

def get_company_counts():

    rows = _select(

        """
        SELECT
            bookmaker,
            COUNT(*) AS cnt

        FROM odds

        WHERE bookmaker IS NOT NULL
        AND bookmaker != ''

        GROUP BY bookmaker

        ORDER BY cnt DESC
        """
    )

    return {

        str(
            row["bookmaker"]
        ):

        int(
            row["cnt"]
        )

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

    schedule_ids = None

    tolerance = 0.00001

    # =====================================================
    # 업체별 동일 배당 검색
    # =====================================================

    for company_name, odds in (
        company_odds.items()
    ):

        home = _to_float(
            odds.get("home")
        )

        draw = _to_float(
            odds.get("draw")
        )

        away = _to_float(
            odds.get("away")
        )

        if (
            home is None
            or draw is None
            or away is None
        ):

            return []

        rows = _select(

            """
            SELECT schedule_id

            FROM odds

            WHERE bookmaker = ?

            AND odds_type = 'final'

            AND home_odds >= ?
            AND home_odds <= ?

            AND draw_odds >= ?
            AND draw_odds <= ?

            AND away_odds >= ?
            AND away_odds <= ?
            """,

            (
                company_name,

                home - tolerance,
                home + tolerance,

                draw - tolerance,
                draw + tolerance,

                away - tolerance,
                away + tolerance
            )
        )

        ids = {

            str(
                row["schedule_id"]
            )

            for row in rows
        }

        if schedule_ids is None:

            schedule_ids = ids

        else:

            schedule_ids &= ids

        if not schedule_ids:

            return []

    # =====================================================
    # 검색 결과 없음
    # =====================================================

    if not schedule_ids:
        return []

    # =====================================================
    # 경기 조회
    # =====================================================

    placeholders = ",".join(
        ["?"] * len(schedule_ids)
    )

    matches = _select(

        f"""
        SELECT *
        FROM matches

        WHERE schedule_id IN (
            {placeholders}
        )

        ORDER BY match_date DESC
        """,

        tuple(schedule_ids)
    )

    # =====================================================
    # 업체별 배당 추가
    # =====================================================

    for match in matches:

        sid = str(
            match.get(
                "schedule_id"
            )
        )

        odds_rows = _select(

            """
            SELECT
                bookmaker,
                home_odds,
                draw_odds,
                away_odds

            FROM odds

            WHERE schedule_id = ?

            AND odds_type = 'final'
            """,

            (
                sid,
            )
        )

        match[
            "company_odds"
        ] = {}

        for row in odds_rows:

            company = row.get(
                "bookmaker"
            )

            if not company:
                continue

            match[
                "company_odds"
            ][company] = {

                "home":
                    row.get(
                        "home_odds"
                    ),

                "draw":
                    row.get(
                        "draw_odds"
                    ),

                "away":
                    row.get(
                        "away_odds"
                    )
            }

    return matches


# =========================================================
# DB 전체 삭제
# =========================================================

def clear_database():

    _request_many([

        (
            "DELETE FROM odds",
            ()
        ),

        (
            "DELETE FROM matches",
            ()
        )

    ])

    return True


# =========================================================
# 경기 존재 확인
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
# 배당 존재 확인
# =========================================================

def odds_exists(
    schedule_id,
    company_name
):

    rows = _select(

        """
        SELECT id

        FROM odds

        WHERE schedule_id = ?

        AND bookmaker = ?

        AND odds_type = 'final'

        LIMIT 1
        """,

        (
            str(schedule_id),
            str(company_name)
        )
    )

    return bool(rows)


# =========================================================
# 결과별 경기 조회
# =========================================================

def get_matches_by_result(
    result_value
):

    return _select(

        """
        SELECT *
        FROM matches

        WHERE result = ?

        ORDER BY match_date DESC
        """,

        (
            result_value,
        )
    )


# =========================================================
# 특정 업체 배당
# =========================================================

def get_odds_by_company(
    company_name
):

    return _select(

        """
        SELECT *

        FROM odds

        WHERE bookmaker = ?

        AND odds_type = 'final'

        ORDER BY schedule_id DESC
        """,

        (
            company_name,
        )
    )


# =========================================================
# 테스트
# =========================================================

if __name__ == "__main__":

    try:

        print(
            "========================================"
        )

        print(
            "Turso 연결 테스트"
        )

        print(
            "========================================"
        )

        ok = init_database()

        if ok:

            print(
                "Turso 연결 성공"
            )

            print(
                "DB 상태:"
            )

            print(
                get_database_status()
            )

            print(
                "저장용량:"
            )

            print(
                get_storage_usage()
            )

        else:

            print(
                "Turso 연결 실패"
            )

    except Exception as e:

        print(
            "오류:",
            e
        )
