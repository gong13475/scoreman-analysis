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
# 작업 상태
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
# HTTP Session
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
            return None

        return response.text

    except Exception as e:

        _append_log(
            f"[페이지 오류] "
            f"ID={schedule_id}: {e}"
        )

        return None


# =========================================================
# 일반 값
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
# JSON 객체
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

        # 중괄호 하나짜리 객체
        for match in re.finditer(
            r"\{[^{}]{20,10000}\}",
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

    home_keys = {

        "hometeamname",
        "home_team_name",
        "hometeam",
        "home_team",
        "homename",
        "hname",
        "homeName"
    }


    away_keys = {

        "awayteamname",
        "away_team_name",
        "awayteam",
        "away_team",
        "awayname",
        "aname",
        "awayName"
    }


    home = find_value(
        html,
        list(home_keys)
    )

    away = find_value(
        html,
        list(away_keys)
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
            "MatchDate"
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
# 숫자 재귀 변환
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
# 업체 하나의 배당 추출
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
            "company_id"
        ]
    )


    # -----------------------------------------------------
    # 원래 Scoreman 구조
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


    # -----------------------------------------------------
    # 배당 직접 검색
    # -----------------------------------------------------

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


    # 다른 키 이름
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
# 배당 응답에서 업체 목록 찾기
# =========================================================

def _find_mixodds(
    data
):

    if isinstance(
        data,
        dict
    ):

        # 가장 일반적인 위치
        mixodds = data.get(
            "mixodds"
        )

        if isinstance(
            mixodds,
            list
        ):

            return mixodds


        block = data.get(
            "Data"
        )

        if isinstance(
            block,
            dict
        ):

            mixodds = block.get(
                "mixodds"
            )

            if isinstance(
                mixodds,
                list
            ):

                return mixodds


        # 재귀 탐색
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

        # 업체 배열인지 확인
        parsed = []

        for item in data:

            if isinstance(
                item,
                dict
            ):

                if (
                    item.get("cn")
                    or item.get("companyName")
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
# 배당 JSON 파싱
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
                f"[배당 API] "
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
            f"SIZE={len(response.text):,} "
            f"TYPE={response.headers.get('Content-Type', '')}"
        )


        if response.status_code != 200:

            return []


        text = response.text.strip()


        if not text:

            return []


        # -------------------------------------------------
        # JSON
        # -------------------------------------------------

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
                    "[배당 응답 앞부분] "
                    + text[:500]
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


    # =====================================================
    # 업체 필터
    # =====================================================

    if selected_companies:

        wanted = {

            str(x)
            .strip()
            .lower()

            for x in selected_companies
        }

        filtered = []

        for row in odds:

            if (
                row["company_name"]
                .strip()
                .lower()
                in wanted
            ):

                filtered.append(
                    row
                )

        odds = filtered


    # =====================================================
    # 중복 제거
    # =====================================================

    unique = {}

    for row in odds:

        key = (
            row["company_name"]
            .strip()
            .lower()
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
# 한 경기 수집
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


    # -----------------------------------------------------
    # 경기 페이지
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
    # 기존 경기
    # -----------------------------------------------------

    existing_row = database.get_match(
        schedule_id
    )


    existing = (
        existing_row is not None
    )


    if existing:

        match = dict(
            existing_row
        )

        # 혹시 기존 데이터에 결과가 없으면
        # 현재 페이지에서 다시 파싱
        if match.get("result") not in {
            "승",
            "무",
            "패"
        }:

            parsed = parse_match_info(
                html,
                schedule_id
            )

            if parsed:

                match = parsed

    else:

        match = parse_match_info(
            html,
            schedule_id
        )

        if not match:

            return {
                "status":
                    "skip",

                "odds":
                    0
            }


    # -----------------------------------------------------
    # 완료 경기만 저장
    # -----------------------------------------------------

    if match.get("result") not in {
        "승",
        "무",
        "패"
    }:

        _append_log(
            f"[경기 제외] "
            f"ID={schedule_id} "
            f"완료 경기 결과 없음"
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
    # ★ 핵심
    # 기존 경기라도 배당을 무조건 다시 확인
    # -----------------------------------------------------

    odds_list = get_odds(
        schedule_id,
        session,
        selected_companies
    )


    if not odds_list:

        _append_log(
            f"[배당 없음] "
            f"ID={schedule_id}"
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


    if selected_companies:

        display_companies = list(
            selected_companies
        )

    else:

        display_companies = [
            "전체 업체 자동수집"
        ]


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
        "초기배당: 저장하지 않음"
    )

    _append_log(
        "최종배당: 저장"
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


            _set_job(

                current=index,

                success=success,

                exists=exists,

                failed=failed,

                odds=odds_total
            )


            # -------------------------------------------------
            # 중지
            # -------------------------------------------------

            if _STOP_EVENT.is_set():

                break


            # -------------------------------------------------
            # 요청 간격
            # -------------------------------------------------

            if delay > 0:

                if _STOP_EVENT.wait(
                    timeout=delay
                ):

                    break


        # =====================================================
        # 종료 상태
        # =====================================================

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


    start_id = int(
        start_id
    )

    end_id = int(
        end_id
    )


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

        daemon=False
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
