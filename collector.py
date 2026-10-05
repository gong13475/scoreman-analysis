import time
import re
import json
import html as html_lib
import requests
import threading
import traceback


import database


# =========================================================
# 기본 설정
# =========================================================

BASE_URL = "https://www.scoreman123.com"


HEADERS = {

    "User-Agent":
        (
            "Mozilla/5.0 "
            "(Linux; Android 10; K) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/130.0 Mobile Safari/537.36"
        ),

    "Accept":
        (
            "text/html,"
            "application/xhtml+xml,"
            "application/xml;q=0.9,"
            "image/avif,"
            "image/webp,"
            "*/*;q=0.8"
        ),

    "Accept-Language":
        "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",

    "Referer":
        BASE_URL + "/"
}


# =========================================================
# 상태
# =========================================================

_JOB_LOCK = threading.RLock()

_STOP_EVENT = threading.Event()


_JOB = {

    "running":
        False,

    "finished":
        False,

    "stopped":
        False,

    "current":
        0,

    "total":
        0,

    "success":
        0,

    "exists":
        0,

    "failed":
        0,

    "odds":
        0,

    "start_id":
        None,

    "end_id":
        None,

    "last_completed_id":
        None,

    "selected_companies":
        [],

    "log":
        "",

    "result":
        None,

    "error":
        ""
}


# =========================================================
# 상태
# =========================================================

def get_job_status():

    with _JOB_LOCK:

        return dict(_JOB)


def _set_job(**kwargs):

    with _JOB_LOCK:

        _JOB.update(
            kwargs
        )


# =========================================================
# 로그
# =========================================================

def _append_log(message):

    with _JOB_LOCK:

        _JOB["log"] += (
            str(message)
            + "\n"
        )

        # 너무 커지는 것 방지
        if len(_JOB["log"]) > 100000:

            _JOB["log"] = (
                _JOB["log"][-100000:]
            )


# =========================================================
# 숫자
# =========================================================

def to_float(value):

    try:

        if value is None:
            return None

        value = str(
            value
        ).strip()

        if not value:
            return None

        value = value.replace(
            ",",
            ""
        )

        return float(value)

    except Exception:

        return None


def to_int(value):

    try:

        return int(
            float(value)
        )

    except Exception:

        return None


# =========================================================
# 문자열
# =========================================================

def clean_text(value):

    if value is None:
        return ""

    value = html_lib.unescape(
        str(value)
    )

    value = value.replace(
        "\\/",
        "/"
    )

    value = value.replace(
        '\\"',
        '"'
    )

    value = re.sub(
        r"<[^>]+>",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# =========================================================
# 업체명 정규화
# =========================================================

def normalize_company_name(name):

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
# 결과
# =========================================================

def calculate_result(
    home_score,
    away_score
):

    if (
        home_score is None
        or away_score is None
    ):

        return ""

    if home_score > away_score:
        return "승"

    if home_score < away_score:
        return "패"

    return "무"


# =========================================================
# Session
# =========================================================

def create_session():

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    return session


# =========================================================
# 경기 페이지
# =========================================================

def get_match_page(
    schedule_id,
    session
):

    url = (
        f"{BASE_URL}"
        f"/match/data-{schedule_id}"
    )

    try:

        response = session.get(
            url,
            timeout=20
        )

        _append_log(
            f"[페이지] "
            f"ID={schedule_id} "
            f"HTTP={response.status_code} "
            f"SIZE={len(response.text):,}"
        )

        if response.status_code != 200:

            return None

        if len(response.text) < 300:

            _append_log(
                f"[페이지 너무 짧음] "
                f"ID={schedule_id}"
            )

            return None

        # 디버깅용
        _append_log(
            "[HTML 확인] "
            + response.text[:300].replace(
                "\n",
                " "
            )
        )

        return response.text

    except Exception as e:

        _append_log(
            f"[페이지 오류] "
            f"ID={schedule_id}: {e}"
        )

        return None


# =========================================================
# 일반 값 검색
# =========================================================

def find_value(
    html,
    keys
):

    for key in keys:

        patterns = [

            rf'"{re.escape(key)}"\s*:\s*"([^"]*)"',


            rf'"{re.escape(key)}"\s*:\s*([^,}}\s]+)',


            rf"'{re.escape(key)}'\s*:\s*'([^']*)'",


            rf"{re.escape(key)}\s*=\s*[\"']([^\"']+)[\"']"

        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                html,
                re.I | re.S
            )

            if match:

                value = clean_text(
                    match.group(1)
                )

                if value:

                    return value

    return ""


# =========================================================
# JSON 객체 추출
# =========================================================

def search_json_objects(html):

    objects = []

    scripts = re.findall(
        r"<script[^>]*>(.*?)</script>",
        html,
        re.I | re.S
    )

    for script in scripts:

        script = script.strip()

        if not script:
            continue

        try:

            objects.append(
                json.loads(script)
            )

        except Exception:

            pass

        # 비교적 작은 JSON 객체
        for match in re.finditer(
            r"\{[^{}]{20,20000}\}",
            script,
            re.S
        ):

            try:

                objects.append(
                    json.loads(
                        match.group(0)
                    )
                )

            except Exception:

                pass

    return objects


# =========================================================
# 재귀 JSON 검색
# =========================================================

def recursive_find(
    obj,
    wanted_keys
):

    wanted = {
        str(x).lower()
        for x in wanted_keys
    }

    if isinstance(
        obj,
        dict
    ):

        for key, value in obj.items():

            key_lower = str(
                key
            ).lower()

            if key_lower in wanted:

                if isinstance(
                    value,
                    (
                        str,
                        int,
                        float
                    )
                ):

                    value = clean_text(
                        value
                    )

                    if value:

                        return value

            result = recursive_find(
                value,
                wanted
            )

            if result:

                return result

    elif isinstance(
        obj,
        list
    ):

        for item in obj:

            result = recursive_find(
                item,
                wanted
            )

            if result:

                return result

    return ""


# =========================================================
# 팀명
# =========================================================

def find_team_names(html):

    home_keys = [

        "hometeamname",
        "home_team_name",
        "hometeam",
        "home_team",
        "homename",
        "hname",
        "homeName",
        "homeTeam",
        "home"

    ]

    away_keys = [

        "awayteamname",
        "away_team_name",
        "awayteam",
        "away_team",
        "awayname",
        "aname",
        "awayName",
        "awayTeam",
        "away"

    ]

    home = find_value(
        html,
        home_keys
    )

    away = find_value(
        html,
        away_keys
    )

    if not home or not away:

        for obj in search_json_objects(
            html
        ):

            if not home:

                home = recursive_find(
                    obj,
                    home_keys
                )

            if not away:

                away = recursive_find(
                    obj,
                    away_keys
                )

            if home and away:

                break

    # -----------------------------------------------------
    # HTML의 일반적인 팀 영역
    # -----------------------------------------------------

    if not home or not away:

        patterns = [

            r'class=["\'][^"\']*(?:home|team)[^"\']*["\'][^>]*>'
            r'\s*([^<]{2,100})',

            r'class=["\'][^"\']*(?:away|team)[^"\']*["\'][^>]*>'
            r'\s*([^<]{2,100})'
        ]

        found = []

        for pattern in patterns:

            matches = re.findall(
                pattern,
                html,
                re.I | re.S
            )

            for value in matches:

                value = clean_text(
                    value
                )

                if value:

                    found.append(
                        value
                    )

        if len(found) >= 2:

            if not home:
                home = found[0]

            if not away:
                away = found[1]

    return (
        clean_text(home),
        clean_text(away)
    )


# =========================================================
# 점수
# =========================================================

def find_scores(html):

    patterns = [

        (
            r'"homeScore"\s*:\s*["\']?(\d+)'
            r'.{0,1000}?'
            r'"awayScore"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"home_score"\s*:\s*["\']?(\d+)'
            r'.{0,1000}?'
            r'"away_score"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"hscore"\s*:\s*["\']?(\d+)'
            r'.{0,1000}?'
            r'"ascore"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"HomeScore"\s*:\s*["\']?(\d+)'
            r'.{0,1000}?'
            r'"AwayScore"\s*:\s*["\']?(\d+)'
        )
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.I | re.S
        )

        if match:

            return (

                to_int(
                    match.group(1)
                ),

                to_int(
                    match.group(2)
                )
            )

    # JSON 탐색
    for obj in search_json_objects(
        html
    ):

        home = recursive_find(
            obj,
            [
                "homeScore",
                "home_score",
                "hscore"
            ]
        )

        away = recursive_find(
            obj,
            [
                "awayScore",
                "away_score",
                "ascore"
            ]
        )

        if home is not None and away is not None:

            hs = to_int(home)
            aws = to_int(away)

            if (
                hs is not None
                and aws is not None
            ):

                return hs, aws

    # 일반적인 표시
    for pattern in [

        r">\s*(\d{1,2})\s*-\s*(\d{1,2})\s*<",

        r">\s*(\d{1,2})\s*:\s*(\d{1,2})\s*<",

        r"(\d{1,2})\s*-\s*(\d{1,2})"

    ]:

        matches = re.findall(
            pattern,
            html,
            re.I | re.S
        )

        if matches:

            hs, aws = matches[-1]

            return (
                to_int(hs),
                to_int(aws)
            )

    return None, None


# =========================================================
# 날짜
# =========================================================

def find_match_date(html):

    value = find_value(
        html,
        [
            "matchTime",
            "matchDate",
            "startTime",
            "MatchTime",
            "MatchDate",
            "date"
        ]
    )

    if value:

        return value

    match = re.search(
        r"(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}"
        r"(?:\s+\d{1,2}:\d{2})?)",
        html
    )

    if match:

        return clean_text(
            match.group(1)
        )

    return ""


# =========================================================
# 경기 파싱
# =========================================================

def parse_match_info(
    html,
    schedule_id
):

    home, away = find_team_names(
        html
    )

    hs, aws = find_scores(
        html
    )

    match_date = find_match_date(
        html
    )

    result = calculate_result(
        hs,
        aws
    )

    _append_log(
        f"[파싱 결과] "
        f"ID={schedule_id} "
        f"HOME={home or '-'} "
        f"AWAY={away or '-'} "
        f"SCORE={hs}:{aws} "
        f"RESULT={result or '-'}"
    )

    if not home or not away:

        _append_log(
            f"[파싱 실패] "
            f"ID={schedule_id} "
            f"팀 정보 없음"
        )

        return None

    return {

        "schedule_id":
            str(schedule_id),

        "match_date":
            match_date,

        "home_team":
            home,

        "away_team":
            away,

        "home_score":
            hs,

        "away_score":
            aws,

        "result":
            result,

        "source":
            "scoreman"
    }


# =========================================================
# 재귀 값
# =========================================================

def _recursive_find_value(
    obj,
    keys
):

    wanted = {
        str(k).lower()
        for k in keys
    }

    if isinstance(
        obj,
        dict
    ):

        for key, value in obj.items():

            key_lower = str(
                key
            ).lower()

            if key_lower in wanted:

                if isinstance(
                    value,
                    (
                        str,
                        int,
                        float
                    )
                ):

                    return value

            found = _recursive_find_value(
                value,
                wanted
            )

            if found is not None:

                return found

    elif isinstance(
        obj,
        list
    ):

        for item in obj:

            found = _recursive_find_value(
                item,
                wanted
            )

            if found is not None:

                return found

    return None


# =========================================================
# 업체 하나
# =========================================================

def _parse_bookmaker_item(
    item
):

    if not isinstance(
        item,
        dict
    ):

        return None

    company_name = _recursive_find_value(
        item,
        [
            "cn",
            "companyname",
            "company_name",
            "bookmaker",
            "bookmakername",
            "name"
        ]
    )

    if company_name is None:

        company_name = ""

    company_name = clean_text(
        company_name
    )

    if not company_name:

        return None

    company_id = _recursive_find_value(
        item,
        [
            "cid",
            "companyid",
            "company_id",
            "id"
        ]
    )

    # -----------------------------------------------------
    # Scoreman 구조
    # euro -> l -> u/g/d
    # -----------------------------------------------------

    final = None

    euro = item.get(
        "euro"
    )

    if isinstance(
        euro,
        dict
    ):

        final = euro.get(
            "l"
        )

    if not isinstance(
        final,
        dict
    ):

        final = item.get(
            "l"
        )

    if not isinstance(
        final,
        dict
    ):

        final = item.get(
            "final"
        )

    home = None
    draw = None
    away = None

    if isinstance(
        final,
        dict
    ):

        home = final.get(
            "u"
        )

        draw = final.get(
            "g"
        )

        away = final.get(
            "d"
        )

    # -----------------------------------------------------
    # 다른 구조
    # -----------------------------------------------------

    if home is None:

        home = _recursive_find_value(
            item,
            [
                "final_home",
                "homeodds",
                "home_odds",
                "home"
            ]
        )

    if draw is None:

        draw = _recursive_find_value(
            item,
            [
                "final_draw",
                "drawodds",
                "draw_odds",
                "draw"
            ]
        )

    if away is None:

        away = _recursive_find_value(
            item,
            [
                "final_away",
                "awayodds",
                "away_odds",
                "away"
            ]
        )

    home = to_float(home)
    draw = to_float(draw)
    away = to_float(away)

    if (
        home is None
        or draw is None
        or away is None
    ):

        return None

    if (
        home <= 0
        or draw <= 0
        or away <= 0
    ):

        return None

    return {

        "company_id":
            (
                str(company_id)
                if company_id is not None
                else ""
            ),

        "company_name":
            company_name,

        "final_home":
            home,

        "final_draw":
            draw,

        "final_away":
            away
    }


# =========================================================
# mixodds 탐색
# =========================================================

def _find_mixodds(data):

    if isinstance(
        data,
        dict
    ):

        for key in [
            "mixodds",
            "MixOdds",
            "mixOdds"
        ]:

            mixodds = data.get(
                key
            )

            if isinstance(
                mixodds,
                list
            ):

                return mixodds

        for value in data.values():

            result = _find_mixodds(
                value
            )

            if result:

                return result

    elif isinstance(
        data,
        list
    ):

        parsed = []

        for item in data:

            if isinstance(
                item,
                dict
            ):

                if (
                    item.get("cn")
                    or item.get("companyName")
                    or item.get("company_name")
                    or item.get("bookmaker")
                ):

                    parsed.append(
                        item
                    )

        if parsed:

            return parsed

        for item in data:

            result = _find_mixodds(
                item
            )

            if result:

                return result

    return []


# =========================================================
# 배당 JSON
# =========================================================

def _parse_odds_json(
    data,
    schedule_id
):

    if isinstance(
        data,
        dict
    ):

        err_code = data.get(
            "ErrCode"
        )

        if (
            err_code is not None
            and str(err_code) != "0"
        ):

            _append_log(
                f"[배당 API 오류] "
                f"ID={schedule_id} "
                f"ErrCode={err_code}"
            )

    mixodds = _find_mixodds(
        data
    )

    if not mixodds:

        _append_log(
            f"[배당 API] "
            f"ID={schedule_id} "
            f"mixodds 없음"
        )

        return []

    result = []

    for item in mixodds:

        parsed = _parse_bookmaker_item(
            item
        )

        if parsed:

            result.append(
                parsed
            )

    return result


# =========================================================
# 배당 수집
# =========================================================

def get_odds(
    schedule_id,
    session,
    selected_companies=None
):

    url = (
        f"{BASE_URL}"
        f"/ajax/soccerajax"
        f"?type=14"
        f"&t=1"
        f"&id={schedule_id}"
        f"&h=0"
    )

    headers = {

        "Accept":
            "application/json, text/plain, */*",

        "X-Requested-With":
            "XMLHttpRequest",

        "Referer":
            (
                f"{BASE_URL}"
                f"/match/data-{schedule_id}"
            )
    }

    try:

        response = session.get(
            url,
            headers=headers,
            timeout=20
        )

        _append_log(
            f"[배당 HTTP] "
            f"ID={schedule_id} "
            f"HTTP={response.status_code} "
            f"SIZE={len(response.text):,}"
        )

        if response.status_code != 200:

            return []

        text = response.text.strip()

        if not text:

            return []

        try:

            data = response.json()

        except Exception:

            try:

                data = json.loads(
                    text
                )

            except Exception as e:

                _append_log(
                    f"[배당 JSON 오류] "
                    f"ID={schedule_id}: {e}"
                )

                _append_log(
                    "[배당 응답] "
                    + text[:1000]
                )

                return []

        odds = _parse_odds_json(
            data,
            schedule_id
        )

    except Exception as e:

        _append_log(
            f"[배당 요청 오류] "
            f"ID={schedule_id}: {e}"
        )

        return []

    # -----------------------------------------------------
    # 업체 필터
    # -----------------------------------------------------

    if selected_companies:

        wanted = {
            normalize_company_name(
                x
            )
            for x in selected_companies
        }

        filtered = []

        for row in odds:

            normalized = (
                normalize_company_name(
                    row["company_name"]
                )
            )

            if normalized in wanted:

                filtered.append(
                    row
                )

        odds = filtered

    # -----------------------------------------------------
    # 중복 제거
    # -----------------------------------------------------

    unique = {}

    for row in odds:

        key = normalize_company_name(
            row["company_name"]
        )

        unique[key] = row

    odds = list(
        unique.values()
    )

    _append_log(
        f"[배당 결과] "
        f"ID={schedule_id} "
        f"수집업체={len(odds)}"
    )

    if odds:

        names = [
            x["company_name"]
            for x in odds
        ]

        _append_log(
            "[업체] "
            + " / ".join(names)
        )

    return odds


# =========================================================
# 저장
# =========================================================

def save_match_data(
    match,
    odds_list
):

    return database.save_match_with_odds(
        match,
        odds_list
    )


# =========================================================
# 한 경기
# =========================================================

def collect_one(
    schedule_id,
    selected_companies,
    session
):

    if _STOP_EVENT.is_set():

        return {
            "status":
                "stopped",

            "odds":
                0
        }

    _append_log(
        f"[수집 시작] ID={schedule_id}"
    )

    # -----------------------------------------------------
    # 페이지
    # -----------------------------------------------------

    html = get_match_page(
        schedule_id,
        session
    )

    if not html:

        return {
            "status":
                "skip",

            "odds":
                0
        }

    if _STOP_EVENT.is_set():

        return {
            "status":
                "stopped",

            "odds":
                0
        }

    # -----------------------------------------------------
    # 경기 파싱
    # -----------------------------------------------------

    _append_log(
        f"[경기 파싱 시작] ID={schedule_id}"
    )

    parsed_match = parse_match_info(
        html,
        schedule_id
    )

    if not parsed_match:

        return {
            "status":
                "skip",

            "odds":
                0
        }

    # -----------------------------------------------------
    # 기존 경기
    # -----------------------------------------------------

    existing_row = database.get_match(
        schedule_id
    )

    existing = (
        existing_row is not None
    )

    match = parsed_match

    if existing:

        old = dict(
            existing_row
        )

        if not match.get(
            "match_date"
        ):

            match["match_date"] = old.get(
                "match_date",
                ""
            )

    # -----------------------------------------------------
    # 완료 경기
    # -----------------------------------------------------

    if match.get("result") not in {
        "승",
        "무",
        "패"
    }:

        _append_log(
            f"[경기 제외] "
            f"ID={schedule_id} "
            f"완료 결과 없음"
        )

        return {
            "status":
                "skip",

            "odds":
                0
        }

    if _STOP_EVENT.is_set():

        return {
            "status":
                "stopped",

            "odds":
                0
        }

    # -----------------------------------------------------
    # 배당
    # -----------------------------------------------------

    _append_log(
        f"[배당 수집 시작] ID={schedule_id}"
    )

    odds_list = get_odds(
        schedule_id,
        session,
        selected_companies
    )

    _append_log(
        f"[배당 수집 완료] "
        f"ID={schedule_id} "
        f"업체={len(odds_list)}"
    )

    if not odds_list:

        _append_log(
            f"[배당 없음] ID={schedule_id}"
        )

        return {
            "status":
                "skip",

            "odds":
                0
        }

    if _STOP_EVENT.is_set():

        return {
            "status":
                "stopped",

            "odds":
                0
        }

    # -----------------------------------------------------
    # 저장
    # -----------------------------------------------------

    saved = save_match_data(
        match,
        odds_list
    )

    _append_log(
        f"[저장 완료] "
        f"ID={schedule_id} "
        f"{match.get('home_team')} "
        f"vs "
        f"{match.get('away_team')} "
        f"/ 결과={match.get('result')} "
        f"/ 최종배당={saved}개"
    )

    return {

        "status":
            (
                "exists"
                if existing
                else "success"
            ),

        "odds":
            saved
    }


# =========================================================
# 백그라운드
# =========================================================

def _run_background(
    start_id,
    end_id,
    selected_companies,
    delay
):

    session = create_session()

    total = (
        end_id
        - start_id
        + 1
    )

    display_companies = (
        list(selected_companies)
        if selected_companies
        else ["전체 업체 자동수집"]
    )

    _STOP_EVENT.clear()

    _set_job(

        running=True,

        finished=False,

        stopped=False,

        current=0,

        total=total,

        success=0,

        exists=0,

        failed=0,

        odds=0,

        start_id=start_id,

        end_id=end_id,

        last_completed_id=None,

        selected_companies=
            display_companies,

        log="",

        result=None,

        error=""
    )

    _append_log(
        "========================================"
    )

    _append_log(
        "⚽ Scoreman 백그라운드 수집 시작"
    )

    _append_log(
        f"범위: "
        f"{start_id:,} ~ "
        f"{end_id:,}"
    )

    if selected_companies:

        _append_log(
            "수집 업체: "
            + " / ".join(
                selected_companies
            )
        )

    else:

        _append_log(
            "수집 업체: 전체 업체 자동수집"
        )

    _append_log(
        "최종배당 저장"
    )

    _append_log(
        "========================================"
    )

    success = 0
    exists = 0
    failed = 0
    odds_total = 0

    try:

        for index, schedule_id in enumerate(

            range(
                start_id,
                end_id + 1
            ),

            start=1
        ):

            if _STOP_EVENT.is_set():

                break

            status_name = "skip"

            try:

                result = collect_one(

                    schedule_id,

                    selected_companies,

                    session
                )

                status_name = result.get(
                    "status",
                    "skip"
                )

                odds = int(
                    result.get(
                        "odds",
                        0
                    )
                )

                if status_name == "success":

                    success += 1

                    odds_total += odds

                    _set_job(
                        last_completed_id=
                            schedule_id
                    )

                elif status_name == "exists":

                    exists += 1

                    odds_total += odds

                    _set_job(
                        last_completed_id=
                            schedule_id
                    )

                elif status_name == "stopped":

                    break

                else:

                    failed += 1

            except Exception as e:

                failed += 1

                _append_log(
                    f"[수집 오류] "
                    f"ID={schedule_id}: {e}"
                )

                _append_log(
                    traceback.format_exc()
                )

            _set_job(

                current=index,

                success=success,

                exists=exists,

                failed=failed,

                odds=odds_total
            )

            if _STOP_EVENT.is_set():

                break

            if delay > 0:

                if _STOP_EVENT.wait(
                    timeout=delay
                ):

                    break

        stopped = _STOP_EVENT.is_set()

        result = {

            "total":
                total,

            "success":
                success,

            "exists":
                exists,

            "failed":
                failed,

            "odds":
                odds_total
        }

        _append_log(
            "========================================"
        )

        if stopped:

            _append_log(
                "🛑 수집 중지됨"
            )

        else:

            _append_log(
                "✅ 백그라운드 수집 완료"
            )

        _append_log(
            f"전체: {total:,}"
        )

        _append_log(
            f"신규: {success:,}"
        )

        _append_log(
            f"기존: {exists:,}"
        )

        _append_log(
            f"실패/배당없음: {failed:,}"
        )

        _append_log(
            f"최종배당: {odds_total:,}"
        )

        _append_log(
            "========================================"
        )

        _set_job(

            running=False,

            finished=True,

            stopped=stopped,

            result=result
        )

    except Exception as e:

        _append_log(
            "[백그라운드 치명적 오류]"
        )

        _append_log(
            traceback.format_exc()
        )

        _set_job(

            running=False,

            finished=True,

            stopped=False,

            error=str(e)
        )

    finally:

        session.close()


# =========================================================
# 시작
# =========================================================

def start_background_collection(
    start_id,
    end_id,
    selected_companies=None,
    delay=0.5
):

    with _JOB_LOCK:

        if _JOB["running"]:

            return False

    try:

        start_id = int(
            start_id
        )

        end_id = int(
            end_id
        )

    except Exception:

        return False

    if end_id < start_id:

        return False

    database.init_database()

    _STOP_EVENT.clear()

    companies = (
        list(selected_companies)
        if selected_companies
        else None
    )

    thread = threading.Thread(

        target=_run_background,

        args=(

            start_id,

            end_id,

            companies,

            float(delay)
        ),

        daemon=True
    )

    thread.start()

    return True


# =========================================================
# 중지
# =========================================================

def stop_background_collection():

    with _JOB_LOCK:

        running = bool(
            _JOB["running"]
        )

    if not running:

        return False

    _STOP_EVENT.set()

    _append_log(
        "🛑 수집 중지 요청..."
    )

    return True


# =========================================================
# 실행 여부
# =========================================================

def is_running():

    with _JOB_LOCK:

        return bool(
            _JOB["running"]
        )


# =========================================================
# 초기화
# =========================================================

def reset_job():

    with _JOB_LOCK:

        if _JOB["running"]:

            return False

        _STOP_EVENT.clear()

        _JOB.update({

            "running":
                False,

            "finished":
                False,

            "stopped":
                False,

            "current":
                0,

            "total":
                0,

            "success":
                0,

            "exists":
                0,

            "failed":
                0,

            "odds":
                0,

            "start_id":
                None,

            "end_id":
                None,

            "last_completed_id":
                None,

            "selected_companies":
                [],

            "log":
                "",

            "result":
                None,

            "error":
                ""
        })

    return True


# =========================================================
# 직접 실행
# =========================================================

if __name__ == "__main__":

    database.init_database()

    start = int(
        input(
            "시작 ID: "
        )
    )

    end = int(
        input(
            "마지막 ID: "
        )
    )

    mode = input(
        "전체 업체면 엔터, "
        "특정 업체면 업체명 입력: "
    ).strip()

    if mode:

        companies = [

            x.strip()

            for x in mode.split(",")

            if x.strip()
        ]

    else:

        companies = None

    started = start_background_collection(

        start,

        end,

        companies,

        0.5
    )

    if not started:

        print(
            "수집 시작 실패"
        )

    else:

        while is_running():

            time.sleep(1)

        print(
            get_job_status()
    )
