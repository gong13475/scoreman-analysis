# database.py

import os
import math
import requests


# =========================================================
# 환경변수
# =========================================================

TURSO_DATABASE_URL = os.getenv(
    "TURSO_DATABASE_URL",
    ""
).strip()

TURSO_AUTH_TOKEN = os.getenv(
    "TURSO_AUTH_TOKEN",
    ""
).strip()


# =========================================================
# 전역 상태
# =========================================================

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

        host = url[len("libsql://"):].rstrip("/")

        return f"https://{host}"

    if url.startswith("https://"):

        return url.rstrip("/")

    if url.startswith("http://"):

        return url.rstrip("/")

    return f"https://{url.rstrip('/')}"


# =========================================================
# HTTP Header
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
# Turso 파라미터 변환
# =========================================================

def _turso_param(value):
    """
    Turso HTTP Pipeline의 args 형식으로 변환합니다.

    핵심:
        "1.38"
            ↓
        _safe_odds()
            ↓
        1.38 (Python float)
            ↓
        JSON number

    문자열 "1.38"을 REAL 컬럼에 text로 보내지 않습니다.
    """

    if value is None:

        return {
            "type": "null"
        }


    if isinstance(value, bool):

        return {
            "type": "integer",
            "value": 1 if value else 0
        }


    if isinstance(value, int):

        return {
            "type": "integer",
            "value": value
        }


    if isinstance(value, float):

        if not math.isfinite(value):

            return {
                "type": "null"
            }

        return {
            "type": "float",
            "value": value
        }


    # 나머지는 문자열
    return {
        "type": "text",
        "value": str(value)
    }


# =========================================================
# Turso cell 값 추출
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

        if "float" in cell:
            return cell["float"]


    return cell


# =========================================================
# Turso HTTP 실행
# =========================================================

def _execute(
    sql,
    args=None
):

    url = _get_http_url()


    params = [
        _turso_param(value)
        for value in (args or [])
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


    # =====================================================
    # Pipeline 내부 오류 확인
    # =====================================================

    if isinstance(data, dict):

        results = data.get(
            "results",
            []
        )


        for item in results:

            if not isinstance(
                item,
                dict
            ):
                continue


            if item.get("type") == "error":

                raise RuntimeError(

                    "Turso SQL 오류: "
                    + str(item)
                )


    return data


# =========================================================
# 결과 행 추출
# =========================================================

def _result_rows(data):

    if not data:
        return []


    try:

        results = data.get(
            "results",
            []
        )


        for item in results:

            if not isinstance(
                item,
                dict
            ):
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
# 문자열
# =========================================================

def _safe_text(value):

    if value is None:
        return None


    if isinstance(value, str):

        value = value.strip()

        if not value:
            return None

        return value


    return str(value)


# =========================================================
# 정수
# =========================================================

def _safe_int(value):

    value = _value_from_cell(value)


    if value is None:
        return None


    if isinstance(value, bool):
        return int(value)


    try:

        if isinstance(value, str):

            value = value.strip()

            if not value:
                return None


        return int(
            float(value)
        )


    except Exception:

        return None


# =========================================================
# 실수
# =========================================================

def _safe_float(value):

    value = _value_from_cell(value)


    if value is None:
        return None


    if isinstance(value, bool):
        return None


    try:

        if isinstance(value, str):

            value = value.strip()

            if not value:
                return None

            value = value.replace(
                ",",
                ""
            )


        number = float(value)


        if not math.isfinite(number):
            return None


        return number


    except Exception:

        return None


# =========================================================
# 배당
# =========================================================

def _safe_odds(value):

    number = _safe_float(value)


    if number is None:
        return None


    if number <= 0:
        return None


    return number


# =========================================================
# 첫 번째 결과값
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
# DB 초기화
# =========================================================

def init_database():

    global _initialized


    if _initialized:
        return True


    if not TURSO_DATABASE_URL:

        raise RuntimeError(
            "TURSO_DATABASE_URL 환경변수가 없습니다."
        )


    if not TURSO_AUTH_TOKEN:

        raise RuntimeError(
            "TURSO_AUTH_TOKEN 환경변수가 없습니다."
        )


    # =====================================================
    # 경기
    # =====================================================

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


    # =====================================================
    # 배당
    # =====================================================

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


    # =====================================================
    # 인덱스
    # =====================================================

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
# 경기 존재 여부
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
        [
            schedule_id
        ]
    )


    return len(
        _result_rows(data)
    ) > 0


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
        [
            schedule_id
        ]
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


    home_score = _safe_int(
        home_score
    )

    away_score = _safe_int(
        away_score
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

            home_score,

            away_score,

            _safe_text(result),

            _safe_text(source)

        ]
    )


    return True


# =========================================================
# 배당 저장
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


    # =====================================================
    # ★ 여기서 반드시 숫자로 변환
    # =====================================================

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


    # =====================================================
    # 디버깅용 타입 검증
    # =====================================================

    for value in (
        home_odds,
        draw_odds,
        away_odds
    ):

        if value is not None:

            if not isinstance(
                value,
                float
            ):

                raise TypeError(
                    "배당값이 Python float가 아닙니다: "
                    + repr(value)
                )


    # =====================================================
    # Turso 저장
    # =====================================================

    _execute(
        """
        INSERT INTO odds (
            schedule_id,
            bookmaker,
            home_odds,
            draw_odds,
            away_odds
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(schedule_id, bookmaker)
        DO UPDATE SET
            home_odds = excluded.home_odds,
            draw_odds = excluded.draw_odds,
            away_odds = excluded.away_odds
        """,
        [

            schedule_id,

            bookmaker,

            home_odds,

            draw_odds,

            away_odds

        ]
    )


    return True


# =========================================================
# 경기 + 배당 저장
# =========================================================

def save_match_with_odds(
    match,
    odds_list
):

    if not isinstance(
        match,
        dict
    ):

        raise ValueError(
            "match 데이터가 올바르지 않습니다."
        )


    schedule_id = _safe_int(
        match.get("schedule_id")
    )


    if schedule_id is None:

        raise ValueError(
            "match.schedule_id가 없습니다."
        )


    # 경기 저장
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


    # 배당 저장
    return save_odds_bulk(
        schedule_id,
        odds_list
    )


# =========================================================
# 여러 업체 배당 저장
# =========================================================

def save_odds_bulk(
    schedule_id,
    odds_list
):

    if not odds_list:
        return 0


    schedule_id = _safe_int(
        schedule_id
    )


    if schedule_id is None:
        raise ValueError(
            "schedule_id가 올바르지 않습니다."
        )


    saved = 0


    for index, item in enumerate(
        odds_list,
        start=1
    ):

        if not isinstance(
            item,
            dict
        ):
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

            else (

                item.get("home")

                if "home" in item

                else item.get("final_home")

            )

        )


        draw_odds = (

            item.get("draw_odds")

            if "draw_odds" in item

            else (

                item.get("draw")

                if "draw" in item

                else item.get("final_draw")

            )

        )


        away_odds = (

            item.get("away_odds")

            if "away_odds" in item

            else (

                item.get("away")

                if "away" in item

                else item.get("final_away")

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


        except Exception as e:

            # =================================================
            # 중요:
            # 여기서 조용히 삼키지 않고 상세 오류를 유지합니다.
            # =================================================

            raise RuntimeError(

                f"배당 저장 실패 "
                f"(업체={bookmaker}, "
                f"index={index}, "
                f"home={home_odds!r}, "
                f"draw={draw_odds!r}, "
                f"away={away_odds!r}): "
                f"{e}"

            ) from e


    return saved


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


    return (
        _safe_int(
            _result_value(data)
        )
        or 0
    )


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


    return (
        _safe_int(
            _result_value(data)
        )
        or 0
    )


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
# 업체별 저장량
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

                result[
                    str(bookmaker)
                ] = int(count)

            except Exception:

                result[
                    str(bookmaker)
                ] = 0


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
          AND o.home_odds = ?
          AND o.draw_odds = ?
          AND o.away_odds = ?
        ORDER BY m.schedule_id DESC
        """,
        [

            bookmaker,

            home_odds,

            draw_odds,

            away_odds

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

                "success":
                    False,

                "size_mb":
                    0,

                "size_gb":
                    0,

                "message":
                    "DB 용량 정보를 가져오지 못했습니다."
            }


        page_count = _value_from_cell(
            rows[0][0]
        )


        page_size = _value_from_cell(
            rows[0][1]
        )


        bytes_size = (
            int(page_count)
            * int(page_size)
        )


        size_mb = (
            bytes_size
            / 1024
            / 1024
        )


        size_gb = (
            size_mb
            / 1024
        )


        return {

            "success":
                True,

            "size_mb":
                size_mb,

            "size_gb":
                size_gb
        }


    except Exception as e:

        return {

            "success":
                False,

            "size_mb":
                0,

            "size_gb":
                0,

            "message":
                str(e)
        }


# =========================================================
# 배당 저장 테스트
# =========================================================

def test_odds_save():

    """
    실제 문자열 배당을 입력해도
    _safe_odds()에서 Python float로 변환되는지 테스트합니다.

    테스트 업체:
        __TEST__

    테스트 경기:
        999999999
    """

    return save_odds(

        999999999,

        "__TEST__",

        "1.38",

        "3.50",

        "5.20"

    )


# =========================================================
# 로컬 타입 테스트
# =========================================================

def test_odds_conversion():

    """
    네트워크를 사용하지 않고 배당 변환만 테스트합니다.
    """

    values = {

        "home":
            _safe_odds("1.38"),

        "draw":
            _safe_odds("3.50"),

        "away":
            _safe_odds("5.20")

    }


    assert isinstance(
        values["home"],
        float
    )

    assert isinstance(
        values["draw"],
        float
    )

    assert isinstance(
        values["away"],
        float
    )


    assert values["home"] == 1.38

    assert values["draw"] == 3.50

    assert values["away"] == 5.20


    return values
