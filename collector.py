import time
import re
import json
import html as html_lib
import requests
import threading
import traceback

import database


BASE_URL = "https://www.scoreman123.com"

HEADERS = {
    "User-Agent":
        "Mozilla/5.0 (Linux; Android 10; K) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/130.0 Mobile Safari/537.36",

    "Accept":
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8",

    "Accept-Language":
        "ko-KR,ko;q=0.9,en-US;q=0.8",

    "Referer": BASE_URL + "/"
}


_LOCK = threading.RLock()
_STOP = threading.Event()

_JOB = {
    "running": False,
    "finished": False,
    "stopped": False,
    "current": 0,
    "total": 0,
    "success": 0,
    "exists": 0,
    "failed": 0,
    "odds": 0,
    "start_id": None,
    "end_id": None,
    "last_completed_id": None,
    "selected_companies": [],
    "log": "",
    "result": None,
    "error": ""
}


def get_job_status():

    with _LOCK:
        return dict(_JOB)


def _set(**kwargs):

    with _LOCK:
        _JOB.update(kwargs)


def _log(message):

    with _LOCK:
        _JOB["log"] += (
            str(message) + "\n"
        )


def clean(value):

    if value is None:
        return ""

    value = html_lib.unescape(
        str(value)
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


def to_float(value):

    try:
        return float(
            str(value)
            .replace(",", "")
            .strip()
        )
    except Exception:
        return None


def to_int(value):

    try:
        return int(
            float(value)
        )
    except Exception:
        return None


def calculate_result(
    home,
    away
):

    if home is None or away is None:
        return ""

    if home > away:
        return "승"

    if home < away:
        return "패"

    return "무"


def create_session():

    s = requests.Session()
    s.headers.update(HEADERS)

    return s


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
            timeout=20
        )

        _log(
            f"[페이지] ID={schedule_id} "
            f"HTTP={response.status_code}"
        )

        if response.status_code != 200:
            return None

        if len(response.text) < 300:
            return None

        return response.text

    except Exception as e:

        _log(
            f"[페이지 오류] {schedule_id}: {e}"
        )

        return None


# =========================================================
# JSON 객체
# =========================================================

def json_objects(html):

    result = []

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
            result.append(
                json.loads(script)
            )
        except Exception:
            pass

    return result


def recursive_value(
    obj,
    keys
):

    wanted = {
        str(x).lower()
        for x in keys
    }

    if isinstance(obj, dict):

        for key, value in obj.items():

            if str(key).lower() in wanted:

                if isinstance(
                    value,
                    (str, int, float)
                ):

                    value = clean(value)

                    if value:
                        return value

            found = recursive_value(
                value,
                wanted
            )

            if found:
                return found

    elif isinstance(obj, list):

        for item in obj:

            found = recursive_value(
                item,
                wanted
            )

            if found:
                return found

    return ""


def find_value(
    html,
    keys
):

    for key in keys:

        patterns = [
            rf'"{re.escape(key)}"\s*:\s*"([^"]*)"',
            rf"'{re.escape(key)}'\s*:\s*'([^']*)'"
        ]

        for pattern in patterns:

            m = re.search(
                pattern,
                html,
                re.I | re.S
            )

            if m:
                value = clean(
                    m.group(1)
                )

                if value:
                    return value

    for obj in json_objects(html):

        value = recursive_value(
            obj,
            keys
        )

        if value:
            return value

    return ""


# =========================================================
# 경기 정보
# =========================================================

def parse_match(
    html,
    schedule_id
):

    home = find_value(
        html,
        [
            "homeTeamName",
            "home_team_name",
            "homeTeam",
            "home_team",
            "homeName"
        ]
    )

    away = find_value(
        html,
        [
            "awayTeamName",
            "away_team_name",
            "awayTeam",
            "away_team",
            "awayName"
        ]
    )

    hs = None
    aws = None

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
        )
    ]

    for pattern in patterns:

        m = re.search(
            pattern,
            html,
            re.I | re.S
        )

        if m:

            hs = to_int(m.group(1))
            aws = to_int(m.group(2))
            break

    if hs is None:

        scores = re.findall(
            r">\s*(\d{1,2})\s*-\s*(\d{1,2})\s*<",
            html
        )

        if scores:

            hs = to_int(scores[-1][0])
            aws = to_int(scores[-1][1])

    date = find_value(
        html,
        [
            "matchTime",
            "matchDate",
            "startTime"
        ]
    )

    if not date:

        m = re.search(
            r"(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}"
            r"(?:\s+\d{1,2}:\d{2})?)",
            html
        )

        if m:
            date = m.group(1)

    if not home or not away:

        return None

    return {
        "schedule_id": str(schedule_id),
        "match_date": date,
        "home_team": home,
        "away_team": away,
        "home_score": hs,
        "away_score": aws,
        "result": calculate_result(hs, aws),
        "source": "scoreman"
    }


# =========================================================
# 최종배당
# =========================================================

def find_mixodds(obj):

    if isinstance(obj, dict):

        if isinstance(
            obj.get("mixodds"),
            list
        ):
            return obj["mixodds"]

        for value in obj.values():

            found = find_mixodds(value)

            if found:
                return found

    elif isinstance(obj, list):

        for item in obj:

            if isinstance(item, dict):

                if (
                    item.get("cn")
                    or item.get("companyName")
                    or item.get("bookmaker")
                ):
                    return obj

        for item in obj:

            found = find_mixodds(item)

            if found:
                return found

    return []


def parse_bookmaker(item):

    if not isinstance(item, dict):
        return None

    company = recursive_value(
        item,
        [
            "cn",
            "companyName",
            "company_name",
            "bookmaker",
            "bookmakerName",
            "name"
        ]
    )

    if not company:
        return None

    company_id = recursive_value(
        item,
        [
            "cid",
            "companyId",
            "company_id"
        ]
    )

    final = None

    euro = item.get("euro")

    if isinstance(euro, dict):
        final = euro.get("l")

    if not isinstance(final, dict):
        final = item.get("l")

    if not isinstance(final, dict):
        final = item.get("final")

    home = None
    draw = None
    away = None

    if isinstance(final, dict):

        home = final.get("u")
        draw = final.get("g")
        away = final.get("d")

    if home is None:
        home = recursive_value(
            item,
            [
                "final_home",
                "homeOdds",
                "home_odds"
            ]
        )

    if draw is None:
        draw = recursive_value(
            item,
            [
                "final_draw",
                "drawOdds",
                "draw_odds"
            ]
        )

    if away is None:
        away = recursive_value(
            item,
            [
                "final_away",
                "awayOdds",
                "away_odds"
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
            str(company_id or ""),

        "company_name":
            clean(company),

        "final_home":
            home,

        "final_draw":
            draw,

        "final_away":
            away
    }


def get_odds(
    schedule_id,
    session,
    selected_companies=None
):

    url = (
        f"{BASE_URL}/ajax/soccerajax"
        f"?type=14&t=1&id={schedule_id}&h=0"
    )

    headers = {
        "Accept":
            "application/json, text/plain, */*",

        "X-Requested-With":
            "XMLHttpRequest",

        "Referer":
            f"{BASE_URL}/match/data-{schedule_id}"
    }

    try:

        response = session.get(
            url,
            headers=headers,
            timeout=20
        )

        _log(
            f"[배당] ID={schedule_id} "
            f"HTTP={response.status_code}"
        )

        if response.status_code != 200:
            return []

        try:
            data = response.json()
        except Exception:
            data = json.loads(
                response.text
            )

        mixodds = find_mixodds(data)

        result = []

        for item in mixodds:

            parsed = parse_bookmaker(
                item
            )

            if parsed:
                result.append(parsed)

        if selected_companies:

            wanted = {
                str(x).strip().lower()
                for x in selected_companies
            }

            result = [
                x for x in result
                if x["company_name"]
                .strip()
                .lower()
                in wanted
            ]

        unique = {}

        for row in result:

            key = row[
                "company_name"
            ].strip().lower()

            unique[key] = row

        result = list(
            unique.values()
        )

        _log(
            f"[배당 결과] "
            f"ID={schedule_id} "
            f"{len(result)}개"
        )

        return result

    except Exception as e:

        _log(
            f"[배당 오류] "
            f"ID={schedule_id}: {e}"
        )

        return []


# =========================================================
# 한 경기
# =========================================================

def collect_one(
    schedule_id,
    selected_companies,
    session
):

    if _STOP.is_set():
        return "stopped", 0

    html = get_match_page(
        schedule_id,
        session
    )

    if not html:
        return "skip", 0

    existing = database.get_match(
        schedule_id
    )

    if existing:

        match = dict(existing)

        if match.get("result") not in [
            "승",
            "무",
            "패"
        ]:

            match = parse_match(
                html,
                schedule_id
            )

    else:

        match = parse_match(
            html,
            schedule_id
        )

    if not match:
        return "skip", 0

    if match.get("result") not in [
        "승",
        "무",
        "패"
    ]:
        return "skip", 0

    odds = get_odds(
        schedule_id,
        session,
        selected_companies
    )

    if not odds:
        return "skip", 0

    saved = database.save_match_with_odds(
        match,
        odds
    )

    _log(
        f"[저장] {schedule_id} "
        f"{match['home_team']} "
        f"vs "
        f"{match['away_team']} "
        f"/ {match['result']} "
        f"/ 최종배당 {saved}개"
    )

    return (
        "exists" if existing else "success",
        saved
    )


# =========================================================
# 백그라운드
# =========================================================

def _worker(
    start_id,
    end_id,
    companies,
    delay
):

    session = create_session()

    total = end_id - start_id + 1

    _STOP.clear()

    _set(
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
        selected_companies=(
            companies or ["전체 업체 자동수집"]
        ),
        log="",
        result=None,
        error=""
    )

    success = 0
    exists = 0
    failed = 0
    odds_total = 0

    try:

        for index, schedule_id in enumerate(
            range(start_id, end_id + 1),
            1
        ):

            if _STOP.is_set():
                break

            try:

                status, odds = collect_one(
                    schedule_id,
                    companies,
                    session
                )

                if status == "success":
                    success += 1
                    odds_total += odds

                elif status == "exists":
                    exists += 1
                    odds_total += odds

                elif status == "stopped":
                    break

                else:
                    failed += 1

            except Exception as e:

                failed += 1

                _log(
                    f"[오류] {schedule_id}: {e}"
                )

            _set(
                current=index,
                success=success,
                exists=exists,
                failed=failed,
                odds=odds_total,
                last_completed_id=schedule_id
            )

            if _STOP.wait(
                timeout=max(
                    0,
                    float(delay)
                )
            ):
                break

        stopped = _STOP.is_set()

        result = {
            "total": total,
            "success": success,
            "exists": exists,
            "failed": failed,
            "odds": odds_total
        }

        _set(
            running=False,
            finished=True,
            stopped=stopped,
            result=result
        )

    except Exception as e:

        _set(
            running=False,
            finished=True,
            error=str(e)
        )

        _log(
            traceback.format_exc()
        )

    finally:
        session.close()


def start_background_collection(
    start_id,
    end_id,
    selected_companies=None,
    delay=0.5
):

    with _LOCK:

        if _JOB["running"]:
            return False

    start_id = int(start_id)
    end_id = int(end_id)

    if end_id < start_id:
        return False

    database.init_database()

    thread = threading.Thread(
        target=_worker,
        args=(
            start_id,
            end_id,
            list(selected_companies)
            if selected_companies
            else None,
            float(delay)
        ),
        daemon=True
    )

    thread.start()

    return True


def stop_background_collection():

    with _LOCK:

        if not _JOB["running"]:
            return False

    _STOP.set()

    _log(
        "🛑 수집 중지 요청"
    )

    return True


def is_running():

    with _LOCK:
        return bool(
            _JOB["running"]
        )


def reset_job():

    with _LOCK:

        if _JOB["running"]:
            return False

        _STOP.clear()

        _JOB.update({
            "running": False,
            "finished": False,
            "stopped": False,
            "current": 0,
            "total": 0,
            "success": 0,
            "exists": 0,
            "failed": 0,
            "odds": 0,
            "start_id": None,
            "end_id": None,
            "last_completed_id": None,
            "selected_companies": [],
            "log": "",
            "result": None,
            "error": ""
        })

    return True
