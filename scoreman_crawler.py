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
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; K) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/130.0 Mobile Safari/537.36"
    ),
    "Referer": BASE_URL + "/"
}


# =========================================================
# 백그라운드 작업 상태
# =========================================================

_JOB_LOCK = threading.Lock()

_JOB = {
    "running": False,
    "finished": False,
    "current": 0,
    "total": 0,
    "success": 0,
    "exists": 0,
    "failed": 0,
    "odds": 0,
    "selected_companies": [],
    "found_companies": [],
    "log": "",
    "result": None,
    "error": ""
}


def get_job_status():
    with _JOB_LOCK:
        return dict(_JOB)


def _set_job(**kwargs):
    with _JOB_LOCK:
        _JOB.update(kwargs)


def _append_log(message):
    with _JOB_LOCK:
        _JOB["log"] += str(message) + "\n"


def _add_found_companies(companies):
    with _JOB_LOCK:

        current = list(
            _JOB.get("found_companies", [])
        )

        for company in companies:

            company = str(
                company
            ).strip()

            if not company:
                continue

            if company not in current:
                current.append(company)

        _JOB["found_companies"] = current


# =========================================================
# 업체명 정규화
# =========================================================

def normalize_company_name(name):

    if name is None:
        return ""

    value = str(
        name
    ).strip().lower()

    value = re.sub(
        r"[\s_\-.]+",
        "",
        value
    )

    return value


def company_matches(actual_name, selected_name):

    a = normalize_company_name(
        actual_name
    )

    b = normalize_company_name(
        selected_name
    )

    if not a or not b:
        return False

    return a == b


# =========================================================
# 변환
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
# 경기 페이지
# =========================================================

def get_match_page(
    schedule_id,
    session
):

    url = (
        f"{BASE_URL}/match/data-{schedule_id}"
    )

    try:

        response = session.get(
            url,
            timeout=30
        )

        _append_log(
            f"[페이지] ID={schedule_id} "
            f"HTTP={response.status_code} "
            f"크기={len(response.text):,}"
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
# HTML / JSON 값 찾기
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


def recursive_find(
    obj,
    wanted_keys
):

    if isinstance(
        obj,
        dict
    ):

        for key, value in obj.items():

            key_lower = str(
                key
            ).lower()

            if key_lower in wanted_keys:

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
                wanted_keys
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
                wanted_keys
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
        "hname"
    }

    away_keys = {
        "awayteamname",
        "away_team_name",
        "awayteam",
        "away_team",
        "awayname",
        "aname"
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
# 스코어
# =========================================================

def find_scores(html):

    patterns = [

        (
            r'"homeScore"\s*:\s*["\']?(\d+)'
            r'.{0,1500}?'
            r'"awayScore"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"home_score"\s*:\s*["\']?(\d+)'
            r'.{0,1500}?'
            r'"away_score"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"hscore"\s*:\s*["\']?(\d+)'
            r'.{0,1500}?'
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
# 경기 날짜
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
            f"[경기 파싱 실패] "
            f"ID={schedule_id} "
            f"홈='{home}' "
            f"원정='{away}'"
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
            result
    }


# =========================================================
# 배당 API
# =========================================================

def get_odds(
    schedule_id,
    session,
    selected_companies
):

    url = (
        f"{BASE_URL}/ajax/soccerajax"
        f"?type=14&t=1"
        f"&id={schedule_id}"
        f"&h=0"
    )

    try:

        response = session.get(
            url,
            timeout=30
        )

        _append_log(
            f"[배당 API] "
            f"ID={schedule_id} "
            f"HTTP={response.status_code}"
        )

        if response.status_code != 200:

            return []

        try:

            data = response.json()

        except Exception:

            _append_log(
                f"[배당 JSON 오류] "
                f"ID={schedule_id}"
            )

            return []

    except Exception as e:

        _append_log(
            f"[배당 요청 오류] "
            f"ID={schedule_id}: {e}"
        )

        return []

    if not isinstance(
        data,
        dict
    ):

        return []

    if data.get(
        "ErrCode"
    ) != 0:

        _append_log(
            f"[배당 오류코드] "
            f"ID={schedule_id} "
            f"ErrCode={data.get('ErrCode')}"
        )

        return []

    block = data.get(
        "Data",
        {}
    )

    if not isinstance(
        block,
        dict
    ):

        return []

    mixodds = block.get(
        "mixodds",
        []
    )

    if not isinstance(
        mixodds,
        list
    ):

        return []

    # -----------------------------------------------------
    # 실제 API에서 발견된 모든 업체
    # -----------------------------------------------------

    found_names = []

    for item in mixodds:

        if not isinstance(
            item,
            dict
        ):
            continue

        company_name = clean_text(
            item.get(
                "cn",
                ""
            )
        )

        if company_name:
            found_names.append(
                company_name
            )

    _add_found_companies(
        found_names
    )

    # -----------------------------------------------------
    # 선택 업체
    # -----------------------------------------------------

    selected_companies = [
        str(x).strip()
        for x in selected_companies
        if str(x).strip()
    ]

    result = []

    for item in mixodds:

        if not isinstance(
            item,
            dict
        ):
            continue

        company_id = item.get(
            "cid"
        )

        company_name = clean_text(
            item.get(
                "cn",
                ""
            )
        )

        if not company_name:
            continue

        # -------------------------------------------------
        # 선택 업체와 정규화 비교
        # -------------------------------------------------

        matched_company = None

        for selected in selected_companies:

            if company_matches(
                company_name,
                selected
            ):

                matched_company = selected
                break

        if (
            selected_companies
            and matched_company is None
        ):
            continue

        euro = item.get(
            "euro",
            {}
        )

        if not isinstance(
            euro,
            dict
        ):
            continue

        final = euro.get(
            "l",
            {}
        )

        if not isinstance(
            final,
            dict
        ):
            continue

        home = to_float(
            final.get("u")
        )

        draw = to_float(
            final.get("g")
        )

        away = to_float(
            final.get("d")
        )

        if (
            home is None
            or draw is None
            or away is None
        ):
            continue

        result.append({

            "company_id":
                (
                    str(company_id)
                    if company_id is not None
                    else ""
                ),

            # 실제 스코어맨 업체명을 저장
            "company_name":
                company_name,

            "final_home":
                home,

            "final_draw":
                draw,

            "final_away":
                away
        })

    if found_names:

        unique_names = list(
            dict.fromkeys(
                found_names
            )
        )

        _append_log(
            "[업체 발견] "
            + " / ".join(
                unique_names
            )
        )

    if selected_companies and not result:

        _append_log(
            "[선택업체 배당 없음] "
            f"ID={schedule_id} / "
            "선택="
            + " / ".join(
                selected_companies
            )
        )

    return result


# =========================================================
# 경기 저장
# =========================================================

def save_match_data(
    match,
    odds_list
):

    database.save_match(

        match["schedule_id"],

        match["match_date"],

        match["home_team"],

        match["away_team"],

        match["home_score"],

        match["away_score"],

        match["result"],

        "Scoreman"

    )

    count = 0

    for odds in odds_list:

        database.save_odds(

            match["schedule_id"],

            odds["company_id"],

            odds["company_name"],

            odds["final_home"],

            odds["final_draw"],

            odds["final_away"]

        )

        count += 1

    return count


# =========================================================
# 경기 1개 수집
# =========================================================

def collect_one(
    schedule_id,
    selected_companies,
    session
):

    html = get_match_page(
        schedule_id,
        session
    )

    if not html:

        return {
            "status": "skip",
            "odds": 0
        }

    # -----------------------------------------------------
    # 기존 경기 확인
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

        # 기존 경기라도 페이지를 다시 파싱해서
        # 최신 결과가 있으면 갱신
        parsed = parse_match_info(
            html,
            schedule_id
        )

        if parsed:

            match.update(
                parsed
            )

    else:

        match = parse_match_info(
            html,
            schedule_id
        )

        if not match:

            return {
                "status": "skip",
                "odds": 0
            }

    # -----------------------------------------------------
    # 배당
    # -----------------------------------------------------

    odds_list = get_odds(
        schedule_id,
        session,
        selected_companies
    )

    # 경기 정보는 배당이 없어도 저장
    if match:

        database.save_match(

            match["schedule_id"],

            match["match_date"],

            match["home_team"],

            match["away_team"],

            match["home_score"],

            match["away_score"],

            match["result"],

            "Scoreman"

        )

    # 배당이 없으면 경기만 저장
    if not odds_list:

        _append_log(
            f"[경기 저장 / 배당 없음] "
            f"ID={schedule_id} "
            f"{match['home_team']} vs "
            f"{match['away_team']}"
        )

        return {
            "status": (
                "exists"
                if existing
                else "success"
            ),
            "odds": 0
        }

    # -----------------------------------------------------
    # 배당 저장
    # -----------------------------------------------------

    saved = 0

    for odds in odds_list:

        try:

            database.save_odds(

                match["schedule_id"],

                odds["company_id"],

                odds["company_name"],

                odds["final_home"],

                odds["final_draw"],

                odds["final_away"]

            )

            saved += 1

        except Exception as e:

            _append_log(
                f"[배당 저장 오류] "
                f"ID={schedule_id} "
                f"업체={odds.get('company_name')} "
                f"{e}"
            )

    _append_log(
        f"[저장 완료] "
        f"ID={schedule_id} "
        f"{match['home_team']} vs "
        f"{match['away_team']} "
        f"{match['result']} "
        f"/ 배당 {saved}개"
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
# 실제 백그라운드 작업
# =========================================================

def _run_background(
    start_id,
    end_id,
    selected_companies,
    delay
):

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    total = (
        end_id
        - start_id
        + 1
    )

    _set_job(

        running=True,

        finished=False,

        current=0,

        total=total,

        success=0,

        exists=0,

        failed=0,

        odds=0,

        selected_companies=list(
            selected_companies
        ),

        found_companies=[],

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
        f"범위: {start_id:,} ~ {end_id:,}"
    )

    _append_log(
        "선택 업체: "
        + " / ".join(
            selected_companies
        )
    )

    _append_log(
        "경기정보: 저장"
    )

    _append_log(
        "최종배당: 선택 업체만 저장"
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

            try:

                result = collect_one(

                    schedule_id,

                    selected_companies,

                    session

                )

                status = result[
                    "status"
                ]

                odds = int(
                    result["odds"]
                )

                if status == "success":

                    success += 1

                    odds_total += odds

                elif status == "exists":

                    exists += 1

                    odds_total += odds

                else:

                    failed += 1

            except Exception as e:

                failed += 1

                _append_log(
                    f"[오류] "
                    f"ID={schedule_id}: "
                    f"{e}"
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

            if delay > 0:

                time.sleep(
                    delay
                )

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
            f"실패: {failed:,}"
        )

        _append_log(
            f"저장 최종배당: "
            f"{odds_total:,}"
        )

        found = get_job_status().get(
            "found_companies",
            []
        )

        if found:

            _append_log(
                "실제 발견 업체: "
                + " / ".join(found)
            )

        else:

            _append_log(
                "실제 발견 업체: 없음"
            )

        _append_log(
            "========================================"
        )

        _set_job(

            running=False,

            finished=True,

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

            error=str(e)

        )

    finally:

        session.close()


# =========================================================
# 백그라운드 시작
# =========================================================

def start_background_collection(
    start_id,
    end_id,
    selected_companies,
    delay=0.5
):

    with _JOB_LOCK:

        if _JOB["running"]:
            return False

    database.init_database()

    selected_companies = [

        str(x).strip()

        for x in selected_companies

        if str(x).strip()

    ]

    if not selected_companies:

        return False

    if int(end_id) < int(start_id):

        return False

    thread = threading.Thread(

        target=_run_background,

        args=(

            int(start_id),

            int(end_id),

            list(
                selected_companies
            ),

            float(delay)

        ),

        daemon=False

    )

    thread.start()

    return True


# =========================================================
# 상태
# =========================================================

def is_running():

    with _JOB_LOCK:

        return bool(
            _JOB["running"]
        )


def reset_job():

    with _JOB_LOCK:

        if _JOB["running"]:

            return False

        _JOB.update({

            "running":
                False,

            "finished":
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

            "selected_companies":
                [],

            "found_companies":
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
# 단독 테스트
# =========================================================

if __name__ == "__main__":

    database.init_database()

    print(
        "========================================"
    )

    print(
        "Scoreman Collector"
    )

    print(
        "========================================"
    )

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

    companies = input(
        "업체명(쉼표로 여러 개): "
    ).split(",")

    companies = [

        x.strip()

        for x in companies

        if x.strip()

    ]

    if not companies:

        print(
            "업체를 1개 이상 입력하세요."
        )

        raise SystemExit

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

        raise SystemExit

    while is_running():

        time.sleep(1)

        status = get_job_status()

        print(

            f"\r진행 "
            f"{status['current']}/"
            f"{status['total']} "
            f"신규={status['success']} "
            f"기존={status['exists']} "
            f"실패={status['failed']} "
            f"배당={status['odds']}",

            end=""

        )

    print()
    print(
        get_job_status()
    )
