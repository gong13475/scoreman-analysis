import os
import math
import requests


TURSO_DATABASE_URL = os.getenv(
    "TURSO_DATABASE_URL", ""
).strip()

TURSO_AUTH_TOKEN = os.getenv(
    "TURSO_AUTH_TOKEN", ""
).strip()

_initialized = False


# =========================================================
# Turso URL
# =========================================================

def _get_http_url():

    url = TURSO_DATABASE_URL.strip()

    if not url:
        raise RuntimeError(
            "TURSO_DATABASE_URL 환경변수가 없습니다."
        )

    if url.startswith("libsql://"):
        return (
            "https://"
            + url[len("libsql://"):].rstrip("/")
        )

    if url.startswith("https://"):
        return url.rstrip("/")

    if url.startswith("http://"):
        return url.rstrip("/")

    return "https://" + url.rstrip("/")


# =========================================================
# Header
# =========================================================

def _headers():

    if not TURSO_AUTH_TOKEN:
        raise RuntimeError(
            "TURSO_AUTH_TOKEN 환경변수가 없습니다."
        )

    return {
        "Authorization":
            f"Bearer {TURSO_AUTH_TOKEN}",
        "Content-Type":
            "application/json"
    }


# =========================================================
# Turso parameter
#
# 중요:
# Turso /v2/pipeline 에서는 args의 value를
# 문자열로 보내는 것이 안전합니다.
#
# REAL 컬럼의 경우 SQL에서 CAST 합니다.
# =========================================================

def _turso_param(value):

    if value is None:
        return {
            "type": "null"
        }

    if isinstance(value, bool):
        return {
            "type": "integer",
            "value": "1" if value else "0"
        }

    if isinstance(value, int):
        return {
            "type": "integer",
            "value": str(value)
        }

    if isinstance(value, float):

        if not math.isfinite(value):
            return {
                "type": "null"
            }

        # API에서 숫자 value를 직접 보내지 않고
        # 문자열로 전달
        return {
            "type": "text",
            "value": format(value, ".15g")
        }

    return {
        "type": "text",
        "value": str(value)
    }


# =========================================================
# Cell 값
# =========================================================

def _value_from_cell(cell):

    if cell is None:
        return None

    if isinstance(cell, dict):

        if "value" in cell:
            return cell["value"]

        if "text" in cell:
            return cell["text"]

        if "integer" in cell:
            return cell["integer"]

        if "real" in cell:
            return cell["real"]

    return cell


# =========================================================
# 실행
# =========================================================

def _execute(sql, args=None):

    url = _get_http_url()

    params = [
        _turso_param(x)
        for x in (args or [])
    ]

    payload = {
        "requests": [
            {
                "type": "execute",
                "stmt": {
                    "sql": sql,
                    "args": params
                }
            },
            {
                "type": "close"
            }
        ]
    }

    response = requests.post(
        f"{url}/v2/pipeline",
        headers=_headers(),
        json=payload,
        timeout=60
    )

    if response.status_code >= 400:

        raise RuntimeError(
            f"Turso HTTP 오류 "
            f"{response.status_code}: "
            f"{response.text}"
        )

    try:
        data = response.json()

    except Exception:
        raise RuntimeError(
            "Turso 응답 JSON 파싱 실패: "
            + response.text
        )

    results = data.get(
        "results",
        []
    )

    for item in results:

        if not isinstance(item, dict):
            continue

        if item.get("type") == "error":

            raise RuntimeError(
                "Turso SQL 오류: "
                + str(item)
            )

    return data


# =========================================================
# 결과 rows
# =========================================================

def _result_rows(data):

    if not data:
        return []

    try:

        for item in data.get(
            "results",
            []
        ):

            if not isinstance(item, dict):
                continue

            if item.get("type") != "ok":
                continue

            response = item.get(
                "response",
                {}
            )

            result = response.get(
                "result",
                {}
            )

            rows = result.get(
                "rows",
                []
            )

            if rows:
                return rows

    except Exception:
        pass

    return []


# =========================================================
# 안전한 문자열
# =========================================================

def _safe_text(value):

    value = _value_from_cell(value)

    if value is None:
        return None

    value = str(value).strip()

    return value if value else None


# =========================================================
# 안전한 정수
# =========================================================

def _safe_int(value):

    value = _value_from_cell(value)

    if value is None:
        return None

    try:

        if isinstance(value, str):
            value = value.strip()

            if not value:
                return None

        return int(float(value))

    except Exception:
        return None


# =========================================================
# 안전한 float
# =========================================================

def _safe_float(value):

    value = _value_from_cell(value)

    if value is None:
        return None

    try:

        if isinstance(value, str):
            value = value.strip()
            value = value.replace(",", "")

        result = float(value)

        if not math.isfinite(result):
            return None

        return result

    except Exception:
        return None


# =========================================================
# 배당
# =========================================================

def _safe_odds(value):

    value = _safe_float(value)

    if value is None:
        return None

    if value <= 0:
        return None

    return value


# =========================================================
# 첫 번째 값
# =========================================================

def _result_value(data):

    rows = _result_rows(data)

    if not rows:
        return None

    if not rows[0]:
        return None

    return _value_from_cell(
        rows[0][0]
    )


# =========================================================
# 초기화
# =========================================================

def init_database():

    global _initialized

    if _initialized:
        return True

    _execute(
        """
        CREATE TABLE IF NOT EXISTS matches (
            schedule_id INTEGER PRIMARY KEY,
            match_date TEXT,
            home_team TEXT,
            away_team TEXT,
            home_score INTEGER,
            away_score INTEGER,
            result TEXT,
            source TEXT
        )
        """
    )

    _execute(
        """
        CREATE TABLE IF NOT EXISTS odds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id INTEGER NOT NULL,
            bookmaker TEXT NOT NULL,
            home_odds REAL,
            draw_odds REAL,
            away_odds REAL,
            UNIQUE(schedule_id, bookmaker)
        )
        """
    )

    _execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_odds_schedule_id
        ON odds(schedule_id)
        """
    )

    _execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_odds_bookmaker
        ON odds(bookmaker)
        """
    )

    _initialized = True

    return True


# =========================================================
# DB 상태
# =========================================================

def get_database_status():

    data = _execute(
        """
        SELECT
            (SELECT COUNT(*) FROM matches),
            (SELECT COUNT(*) FROM odds),
            (SELECT COUNT(DISTINCT bookmaker) FROM odds)
        """
    )

    rows = _result_rows(data)

    if not rows:
        return {
            "matches": 0,
            "odds": 0,
            "bookmakers": 0
        }

    values = [
        _value_from_cell(x)
        for x in rows[0]
    ]

    while len(values) < 3:
        values.append(0)

    return {
        "matches":
            _safe_int(values[0]) or 0,

        "odds":
            _safe_int(values[1]) or 0,

        "bookmakers":
            _safe_int(values[2]) or 0
    }


# =========================================================
# 경기 존재
# =========================================================

def match_exists(schedule_id):

    schedule_id = _safe_int(
        schedule_id
    )

    if schedule_id is None:
        return False

    data = _execute(
        """
        SELECT schedule_id
        FROM matches
        WHERE schedule_id = ?
        LIMIT 1
        """,
        [schedule_id]
    )

    return bool(
        _result_rows(data)
    )


# =========================================================
# 경기 조회
# =========================================================

def get_match(schedule_id):

    schedule_id = _safe_int(
        schedule_id
    )

    if schedule_id is None:
        return None

    data = _execute(
        """
        SELECT
            schedule_id,
            match_date,
            home_team,
            away_team,
            home_score,
            away_score,
            result,
            source
        FROM matches
        WHERE schedule_id = ?
        LIMIT 1
        """,
        [schedule_id]
    )

    rows = _result_rows(data)

    if not rows:
        return None

    values = [
        _value_from_cell(x)
        for x in rows[0]
    ]

    while len(values) < 8:
        values.append(None)

    return {
        "schedule_id":
            _safe_int(values[0]),

        "match_date":
            values[1],

        "home_team":
            values[2],

        "away_team":
            values[3],

        "home_score":
            _safe_int(values[4]),

        "away_score":
            _safe_int(values[5]),

        "result":
            values[6],

        "source":
            values[7]
    }


# =========================================================
# 경기 저장
# =========================================================

def save_match(
    schedule_id,
    match_date=None,
    home_team=None,
    away_team=None,
    home_score=None,
    away_score=None,
    result=None,
    source="scoreman"
):

    schedule_id = _safe_int(
        schedule_id
    )

    if schedule_id is None:
        raise ValueError(
            "schedule_id가 올바르지 않습니다."
        )

    _execute(
        """
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
            match_date = excluded.match_date,
            home_team = excluded.home_team,
            away_team = excluded.away_team,
            home_score = excluded.home_score,
            away_score = excluded.away_score,
            result = excluded.result,
            source = excluded.source
        """,
        [
            schedule_id,
            _safe_text(match_date),
            _safe_text(home_team),
            _safe_text(away_team),
            _safe_int(home_score),
            _safe_int(away_score),
            _safe_text(result),
            _safe_text(source)
        ]
    )

    return True


# =========================================================
# 배당 저장
#
# 핵심:
# CAST(? AS REAL)
#
# API에는 문자열로 전달하되
# SQLite/Turso SQL 단계에서 REAL로 변환합니다.
# =========================================================

def save_odds(
    schedule_id,
    bookmaker,
    home_odds,
    draw_odds,
    away_odds
):

    schedule_id = _safe_int(
        schedule_id
    )

    bookmaker = _safe_text(
        bookmaker
    )

    if schedule_id is None:
        raise ValueError(
            "schedule_id가 올바르지 않습니다."
        )

    if not bookmaker:
        raise ValueError(
            "bookmaker가 없습니다."
        )

    home_odds = _safe_odds(
        home_odds
    )

    draw_odds = _safe_odds(
        draw_odds
    )

    away_odds = _safe_odds(
        away_odds
    )

    if (
        home_odds is None
        and draw_odds is None
        and away_odds is None
    ):
        return False

    _execute(
        """
        INSERT INTO odds (
            schedule_id,
            bookmaker,
            home_odds,
            draw_odds,
            away_odds
        )
        VALUES (
            ?,
            ?,
            CAST(? AS REAL),
            CAST(? AS REAL),
            CAST(? AS REAL)
        )

        ON CONFLICT(schedule_id, bookmaker)
        DO UPDATE SET
            home_odds = excluded.home_odds,
            draw_odds = excluded.draw_odds,
            away_odds = excluded.away_odds
        """,
        [
            schedule_id,
            bookmaker,

            None
            if home_odds is None
            else format(home_odds, ".15g"),

            None
            if draw_odds is None
            else format(draw_odds, ".15g"),

            None
            if away_odds is None
            else format(away_odds, ".15g")
        ]
    )

    return True


# =========================================================
# 배당 일괄 저장
# =========================================================

def save_odds_bulk(
    schedule_id,
    odds_list
):

    if not odds_list:
        return 0

    saved = 0

    for item in odds_list:

        if not isinstance(item, dict):
            continue

        bookmaker = (
            item.get("bookmaker")
            or item.get("company")
            or item.get("company_name")
            or item.get("name")
        )

        home_odds = (
            item.get("home_odds")
            if "home_odds" in item
            else item.get(
                "final_home",
                item.get("home")
            )
        )

        draw_odds = (
            item.get("draw_odds")
            if "draw_odds" in item
            else item.get(
                "final_draw",
                item.get("draw")
            )
        )

        away_odds = (
            item.get("away_odds")
            if "away_odds" in item
            else item.get(
                "final_away",
                item.get("away")
            )
        )

        try:

            if save_odds(
                schedule_id,
                bookmaker,
                home_odds,
                draw_odds,
                away_odds
            ):
                saved += 1

        except Exception:
            continue

    return saved


# =========================================================
# 경기 + 배당
# =========================================================

def save_match_with_odds(
    match,
    odds_list
):

    if not isinstance(match, dict):
        raise ValueError(
            "match 데이터가 올바르지 않습니다."
        )

    schedule_id = match.get(
        "schedule_id"
    )

    save_match(
        schedule_id,
        match.get("match_date"),
        match.get("home_team"),
        match.get("away_team"),
        match.get("home_score"),
        match.get("away_score"),
        match.get("result"),
        match.get(
            "source",
            "scoreman"
        )
    )

    return save_odds_bulk(
        schedule_id,
        odds_list
    )


# =========================================================
# 전체 경기
# =========================================================

def get_all_matches():

    data = _execute(
        """
        SELECT
            schedule_id,
            match_date,
            home_team,
            away_team,
            home_score,
            away_score,
            result,
            source
        FROM matches
        ORDER BY schedule_id DESC
        """
    )

    rows = _result_rows(data)

    result = []

    for row in rows:

        values = [
            _value_from_cell(x)
            for x in row
        ]

        while len(values) < 8:
            values.append(None)

        result.append({
            "schedule_id":
                _safe_int(values[0]),

            "match_date":
                values[1],

            "home_team":
                values[2],

            "away_team":
                values[3],

            "home_score":
                _safe_int(values[4]),

            "away_score":
                _safe_int(values[5]),

            "result":
                values[6],

            "source":
                values[7]
        })

    return result


# =========================================================
# 전체 배당
# =========================================================

def get_all_odds():

    data = _execute(
        """
        SELECT
            schedule_id,
            bookmaker,
            home_odds,
            draw_odds,
            away_odds
        FROM odds
        ORDER BY schedule_id DESC, bookmaker
        """
    )

    rows = _result_rows(data)

    result = []

    for row in rows:

        values = [
            _value_from_cell(x)
            for x in row
        ]

        while len(values) < 5:
            values.append(None)

        result.append({
            "schedule_id":
                _safe_int(values[0]),

            "bookmaker":
                values[1],

            "home_odds":
                _safe_float(values[2]),

            "draw_odds":
                _safe_float(values[3]),

            "away_odds":
                _safe_float(values[4])
        })

    return result


# =========================================================
# 경기 수
# =========================================================

def get_match_count():

    data = _execute(
        """
        SELECT COUNT(*)
        FROM matches
        """
    )

    return _safe_int(
        _result_value(data)
    ) or 0


# =========================================================
# 배당 수
# =========================================================

def get_odds_count():

    data = _execute(
        """
        SELECT COUNT(*)
        FROM odds
        """
    )

    return _safe_int(
        _result_value(data)
    ) or 0


# =========================================================
# 업체명
# =========================================================

def get_company_names():

    data = _execute(
        """
        SELECT DISTINCT bookmaker
        FROM odds
        WHERE bookmaker IS NOT NULL
          AND bookmaker != ''
        ORDER BY bookmaker
        """
    )

    rows = _result_rows(data)

    result = []

    for row in rows:

        if not row:
            continue

        value = _value_from_cell(
            row[0]
        )

        if value:
            result.append(
                str(value)
            )

    return result


# =========================================================
# 업체별 개수
# =========================================================

def get_company_counts():

    data = _execute(
        """
        SELECT
            bookmaker,
            COUNT(*)
        FROM odds
        WHERE bookmaker IS NOT NULL
        GROUP BY bookmaker
        ORDER BY COUNT(*) DESC
        """
    )

    rows = _result_rows(data)

    result = {}

    for row in rows:

        if len(row) < 2:
            continue

        bookmaker = _value_from_cell(
            row[0]
        )

        count = _value_from_cell(
            row[1]
        )

        if bookmaker:

            try:
                result[str(bookmaker)] = int(
                    count
                )

            except Exception:
                result[str(bookmaker)] = 0

    return result


# =========================================================
# 동일 배당 검색
# =========================================================

def find_matches_by_odds(
    bookmaker,
    home_odds,
    draw_odds,
    away_odds
):

    bookmaker = _safe_text(
        bookmaker
    )

    home_odds = _safe_odds(
        home_odds
    )

    draw_odds = _safe_odds(
        draw_odds
    )

    away_odds = _safe_odds(
        away_odds
    )

    if not bookmaker:
        return []

    if (
        home_odds is None
        or draw_odds is None
        or away_odds is None
    ):
        return []

    data = _execute(
        """
        SELECT
            m.schedule_id,
            m.match_date,
            m.home_team,
            m.away_team,
            m.home_score,
            m.away_score,
            m.result,
            m.source,
            o.bookmaker,
            o.home_odds,
            o.draw_odds,
            o.away_odds
        FROM matches m
        INNER JOIN odds o
            ON m.schedule_id = o.schedule_id
        WHERE o.bookmaker = ?
          AND o.home_odds = CAST(? AS REAL)
          AND o.draw_odds = CAST(? AS REAL)
          AND o.away_odds = CAST(? AS REAL)
        ORDER BY m.schedule_id DESC
        """,
        [
            bookmaker,
            format(home_odds, ".15g"),
            format(draw_odds, ".15g"),
            format(away_odds, ".15g")
        ]
    )

    rows = _result_rows(data)

    result = []

    for row in rows:

        values = [
            _value_from_cell(x)
            for x in row
        ]

        while len(values) < 12:
            values.append(None)

        result.append({
            "schedule_id":
                _safe_int(values[0]),

            "match_date":
                values[1],

            "home_team":
                values[2],

            "away_team":
                values[3],

            "home_score":
                _safe_int(values[4]),

            "away_score":
                _safe_int(values[5]),

            "result":
                values[6],

            "source":
                values[7],

            "bookmaker":
                values[8],

            "home_odds":
                _safe_float(values[9]),

            "draw_odds":
                _safe_float(values[10]),

            "away_odds":
                _safe_float(values[11])
        })

    return result


# =========================================================
# 저장용량
# =========================================================

def get_storage_usage():

    try:

        data = _execute(
            """
            SELECT
                page_count,
                page_size
            FROM pragma_page_count(),
                 pragma_page_size()
            """
        )

        rows = _result_rows(data)

        if not rows:

            return {
                "success": False,
                "size_mb": 0,
                "size_gb": 0,
                "message":
                    "DB 용량 정보를 가져오지 못했습니다."
            }

        page_count = _safe_int(
            rows[0][0]
        )

        page_size = _safe_int(
            rows[0][1]
        )

        if page_count is None or page_size is None:
            raise ValueError(
                "페이지 정보를 읽을 수 없습니다."
            )

        bytes_size = (
            page_count * page_size
        )

        size_mb = (
            bytes_size / 1024 / 1024
        )

        size_gb = (
            size_mb / 1024
        )

        return {
            "success": True,
            "size_mb": size_mb,
            "size_gb": size_gb
        }

    except Exception as e:

        return {
            "success": False,
            "size_mb": 0,
            "size_gb": 0,
            "message": str(e)
        }


# =========================================================
# Turso 연결/배당 테스트
# =========================================================

def test_odds_save():

    """
    999999999 / __TEST__ 레코드에
    1.38 / 3.50 / 5.20을 저장합니다.
    """

    return save_odds(
        999999999,
        "__TEST__",
        "1.38",
        "3.50",
        "5.20"
        )
