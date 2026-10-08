# ============================================================
# collector.py
# Scoreman 백그라운드 수집기
#
# 기능
# - 자동 재시도 없음
# - 최종배당 저장
# - 경기결과 저장
# - 결과 누락 경기 자동 보정
# - 중지
# - 이어받기
# - 진행상태 DB 저장
# ============================================================

import re
import time
import json
import threading
from datetime import datetime

import requests

import database


# ============================================================
# URL
# ============================================================

BASE_URL = (
    "https://www.scoreman123.com"
)

MATCH_URL = (
    BASE_URL
    + "/match/data-{schedule_id}"
)

ODDS_URL = (
    BASE_URL
    + "/ajax/soccerajax?type=14&t=1&id={schedule_id}&h=0"
)

REQUEST_TIMEOUT = 20
DEFAULT_DELAY = 0.5


# ============================================================
# HTTP
# ============================================================

session = requests.Session()

session.headers.update(
    {
        "User-Agent":
            "Mozilla/5.0 "
            "(Linux; Android 10; K) "
            "AppleWebKit/537.36 "
            "Chrome/130.0 Mobile Safari/537.36",

        "Accept": "*/*",

        "Accept-Language":
            "ko-KR,ko;q=0.9,en-US;q=0.8",

        "Referer":
            BASE_URL + "/",
    }
)


# ============================================================
# 작업 상태
# ============================================================

job = {

    "running": False,
    "finished": False,

    "current": 0,
    "total": 0,

    "current_id": 0,

    "success": 0,
    "exists": 0,
    "failed": 0,
    "fixed": 0,
    "odds": 0,

    "start_id": 0,
    "end_id": 0,

    "last_completed_id": None,

    "selected_companies": [],

    "delay": DEFAULT_DELAY,

    "start_time": None,
    "end_time": None,

    "log": [],

    "result": "",
    "error": "",
}


lock = threading.Lock()


# ============================================================
# 로그
# ============================================================

def add_log(message):

    timestamp = datetime.now().strftime(
        "%H:%M:%S"
    )

    line = (
        f"[{timestamp}] {message}"
    )

    with lock:

        job["log"].append(line)

        if len(job["log"]) > 1000:

            job["log"] = (
                job["log"][-1000:]
            )

    print(line)


def get_job_status():

    with lock:
        return dict(job)


def get_logs():

    with lock:
        return list(job["log"])


def clear_logs():

    with lock:
        job["log"] = []


def is_running():

    with lock:
        return bool(
            job["running"]
        )


# ============================================================
# 중지
# ============================================================

def stop_collection():

    with lock:

        if not job["running"]:
            return False

        job["running"] = False

    add_log(
        "🛑 수집 중지 요청"
    )

    return True


# ============================================================
# 숫자
# ============================================================

def to_float(value):

    try:

        if value is None:
            return None

        value = str(
            value
        ).strip()

        value = value.replace(
            ",",
            "",
        )

        if not value:
            return None

        value = float(value)

        if value <= 0:
            return None

        return value

    except Exception:

        return None


# ============================================================
# 결과
# ============================================================

def calculate_result(
    home_score,
    away_score,
):

    try:

        h = int(home_score)
        a = int(away_score)

    except Exception:

        return None

    if h > a:
        return "승"

    if h == a:
        return "무"

    return "패"


# ============================================================
# 경기 페이지
# ============================================================

def fetch_match_page(
    schedule_id,
):

    url = MATCH_URL.format(
        schedule_id=schedule_id
    )

    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT,
    )

    add_log(
        f"[페이지] ID={schedule_id} "
        f"HTTP={response.status_code} "
        f"SIZE={len(response.text):,}"
    )

    if response.status_code != 200:

        raise RuntimeError(
            "경기 페이지 "
            f"HTTP={response.status_code}"
        )

    return response.text


# ============================================================
# 텍스트
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    value = re.sub(
        r"<[^>]+>",
        " ",
        str(value),
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


# ============================================================
# 팀명
# ============================================================

def extract_team_names(html):

    home = ""
    away = ""

    patterns = [

        (
            r'"homeTeam"\s*:\s*"([^"]+)"',
            r'"awayTeam"\s*:\s*"([^"]+)"',
        ),

        (
            r'"home_team"\s*:\s*"([^"]+)"',
            r'"away_team"\s*:\s*"([^"]+)"',
        ),

        (
            r'"hteam"\s*:\s*"([^"]+)"',
            r'"ateam"\s*:\s*"([^"]+)"',
        ),

        (
            r'"HomeTeam"\s*:\s*"([^"]+)"',
            r'"AwayTeam"\s*:\s*"([^"]+)"',
        ),

        (
            r'"home"\s*:\s*"([^"]+)"',
            r'"away"\s*:\s*"([^"]+)"',
        ),
    ]

    for hp, ap in patterns:

        hm = re.findall(
            hp,
            html,
            re.I,
        )

        am = re.findall(
            ap,
            html,
            re.I,
        )

        if hm and am:

            home = clean_text(
                hm[-1]
            )

            away = clean_text(
                am[-1]
            )

            if home and away:
                break

    return home, away


# ============================================================
# 스코어 / 결과
# ============================================================

def extract_score(html):

    if not html:
        return (
            None,
            None,
            None,
        )

    text = str(html)

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    patterns = [

        (
            r'"homeScore"\s*:\s*"?(?:\\")?(\d+)',
            r'"awayScore"\s*:\s*"?(?:\\")?(\d+)',
        ),

        (
            r'"home_score"\s*:\s*"?(?:\\")?(\d+)',
            r'"away_score"\s*:\s*"?(?:\\")?(\d+)',
        ),

        (
            r'"hs"\s*:\s*"?(?:\\")?(\d+)',
            r'"as"\s*:\s*"?(?:\\")?(\d+)',
        ),

        (
            r'"homeGoals"\s*:\s*"?(?:\\")?(\d+)',
            r'"awayGoals"\s*:\s*"?(?:\\")?(\d+)',
        ),

        (
            r'"homeScoreValue"\s*:\s*"?(?:\\")?(\d+)',
            r'"awayScoreValue"\s*:\s*"?(?:\\")?(\d+)',
        ),

        (
            r'"HomeScore"\s*:\s*"?(?:\\")?(\d+)',
            r'"AwayScore"\s*:\s*"?(?:\\")?(\d+)',
        ),
    ]

    for hp, ap in patterns:

        hm = re.findall(
            hp,
            text,
            re.I,
        )

        am = re.findall(
            ap,
            text,
            re.I,
        )

        if hm and am:

            try:

                home = int(
                    str(
                        hm[-1]
                    ).replace(
                        "\\",
                        "",
                    )
                )

                away = int(
                    str(
                        am[-1]
                    ).replace(
                        "\\",
                        "",
                    )
                )

                return (
                    home,
                    away,
                    calculate_result(
                        home,
                        away,
                    ),
                )

            except Exception:
                pass

    # --------------------------------------------------------
    # score = "3-1"
    # --------------------------------------------------------

    score_patterns = [

        r'"score"\s*:\s*"(\d+)\s*[-:]\s*(\d+)"',

        r'"ft"\s*:\s*"(\d+)\s*[-:]\s*(\d+)"',

        r'"fullScore"\s*:\s*"(\d+)\s*[-:]\s*(\d+)"',

        r'"resultScore"\s*:\s*"(\d+)\s*[-:]\s*(\d+)"',

        r'"finalScore"\s*:\s*"(\d+)\s*[-:]\s*(\d+)"',

        r'"result"\s*:\s*"(\d+)\s*[-:]\s*(\d+)"',
    ]

    for pattern in score_patterns:

        found = re.findall(
            pattern,
            text,
            re.I,
        )

        if found:

            try:

                home = int(
                    found[-1][0]
                )

                away = int(
                    found[-1][1]
                )

                if (
                    home <= 30
                    and away <= 30
                ):

                    return (
                        home,
                        away,
                        calculate_result(
                            home,
                            away,
                        ),
                    )

            except Exception:
                pass

    # --------------------------------------------------------
    # HTML 숫자-숫자
    # --------------------------------------------------------

    html_patterns = [

        r">(\d+)\s*[-:]\s*(\d+)<",

        r">(\d+)\s*:\s*(\d+)<",
    ]

    for pattern in html_patterns:

        found = re.findall(
            pattern,
            text,
            re.I,
        )

        if not found:
            continue

        for pair in reversed(found):

            try:

                home = int(pair[0])
                away = int(pair[1])

                if home > 30:
                    continue

                if away > 30:
                    continue

                return (
                    home,
                    away,
                    calculate_result(
                        home,
                        away,
                    ),
                )

            except Exception:
                continue

    return (
        None,
        None,
        None,
    )


# ============================================================
# 날짜
# ============================================================

def extract_match_date(html):

    patterns = [

        r'"matchDate"\s*:\s*"([^"]+)"',

        r'"match_date"\s*:\s*"([^"]+)"',

        r'"date"\s*:\s*"'
        r'(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})"',
    ]

    for pattern in patterns:

        found = re.findall(
            pattern,
            html,
            re.I,
        )

        if found:
            return found[-1]

    return None


# ============================================================
# 배당 API
# ============================================================

def fetch_odds(
    schedule_id,
):

    url = ODDS_URL.format(
        schedule_id=schedule_id
    )

    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT,
    )

    add_log(
        f"[배당 API] ID={schedule_id} "
        f"HTTP={response.status_code} "
        f"SIZE={len(response.text):,}"
    )

    if response.status_code != 200:

        raise RuntimeError(
            "배당 API "
            f"HTTP={response.status_code}"
        )

    return response.text


# ============================================================
# JSON
# ============================================================

def parse_json(text):

    try:

        return json.loads(text)

    except Exception:

        start = text.find("{")
        end = text.rfind("}")

        if (
            start >= 0
            and end > start
        ):

            try:

                return json.loads(
                    text[
                        start:
                        end + 1
                    ]
                )

            except Exception:
                pass

    return None


# ============================================================
# 업체 추출
# ============================================================

def extract_bookmakers(data):

    if not isinstance(
        data,
        dict,
    ):

        return []

    mixodds = None

    if isinstance(
        data.get("Data"),
        dict,
    ):

        mixodds = data[
            "Data"
        ].get(
            "mixodds"
        )

    if mixodds is None:

        mixodds = data.get(
            "mixodds"
        )

    if not isinstance(
        mixodds,
        list,
    ):

        return []

    result = []

    for item in mixodds:

        if not isinstance(
            item,
            dict,
        ):
            continue

        cid = (
            item.get("cid")
            or item.get("company_id")
            or item.get("id")
        )

        name = (
            item.get("cn")
            or item.get("company_name")
            or item.get("name")
            or ""
        )

        if cid is None:
            continue

        euro = item.get(
            "euro"
        )

        if not isinstance(
            euro,
            dict,
        ):
            continue

        final_odds = euro.get(
            "l"
        )

        if not isinstance(
            final_odds,
            dict,
        ):
            continue

        home = to_float(
            final_odds.get("u")
        )

        draw = to_float(
            final_odds.get("g")
        )

        away = to_float(
            final_odds.get("d")
        )

        if (
            home is None
            or draw is None
            or away is None
        ):
            continue

        result.append(
            {
                "cid": str(cid),
                "name":
                    str(name).strip(),
                "home": home,
                "draw": draw,
                "away": away,
            }
        )

    return result


# ============================================================
# 업체 필터
# ============================================================

def filter_bookmakers(
    bookmakers,
    selected_companies=None,
):

    if not selected_companies:
        return bookmakers

    selected = {
        str(x)
        .strip()
        .lower()
        for x in selected_companies
        if str(x).strip()
    }

    result = []

    for item in bookmakers:

        cid = str(
            item["cid"]
        ).lower()

        name = str(
            item["name"]
        ).lower()

        if (
            cid in selected
            or name in selected
        ):

            result.append(item)

    return result


# ============================================================
# 기존 경기 결과 보정
# ============================================================

def repair_existing_result(
    schedule_id,
):

    match = database.get_match(
        schedule_id
    )

    if not match:
        return False

    existing_result = (
        match.get("result")
    )

    if existing_result:
        return False

    add_log(
        f"[결과 보정] ID={schedule_id}"
    )

    html = fetch_match_page(
        schedule_id
    )

    home_score, away_score, result = (
        extract_score(html)
    )

    if (
        home_score is None
        or away_score is None
        or result is None
    ):

        add_log(
            f"[결과 보정 실패] "
            f"ID={schedule_id} "
            f"점수를 찾지 못함"
        )

        return False

    ok = database.update_match_result(
        schedule_id,
        home_score,
        away_score,
        result,
    )

    if ok:

        add_log(
            f"[결과 보정 완료] "
            f"ID={schedule_id} "
            f"{home_score}-{away_score} "
            f"결과={result}"
        )

        return True

    return False


# ============================================================
# 한 경기
# ============================================================

def collect_one_match(
    schedule_id,
    selected_companies=None,
):

    schedule_id = str(
        schedule_id
    )

    # --------------------------------------------------------
    # 이미 완료된 경기
    # --------------------------------------------------------

    if database.is_collection_completed(
        schedule_id
    ):

        # 결과가 빠져 있으면 보정
        match = database.get_match(
            schedule_id
        )

        if (
            match
            and not match.get("result")
        ):

            if repair_existing_result(
                schedule_id
            ):

                return {
                    "status":
                        "result_fixed",
                    "odds": 0,
                }

        add_log(
            f"[중복] ID={schedule_id}"
        )

        return "exists"

    # --------------------------------------------------------
    # 수집 시작 상태 DB 기록
    # --------------------------------------------------------

    database.save_collection_state(
        schedule_id,
        "in_progress",
    )

    # --------------------------------------------------------
    # 경기 페이지
    # --------------------------------------------------------

    html = fetch_match_page(
        schedule_id
    )

    home_team, away_team = (
        extract_team_names(html)
    )

    home_score, away_score, result = (
        extract_score(html)
    )

    match_date = extract_match_date(
        html
    )

    if not home_team:
        home_team = (
            f"ID {schedule_id}"
        )

    if not away_team:
        away_team = "상대팀"

    # --------------------------------------------------------
    # 배당
    # --------------------------------------------------------

    odds_text = fetch_odds(
        schedule_id
    )

    odds_data = parse_json(
        odds_text
    )

    if odds_data is None:

        raise RuntimeError(
            "배당 JSON 파싱 실패"
        )

    bookmakers = extract_bookmakers(
        odds_data
    )

    bookmakers = filter_bookmakers(
        bookmakers,
        selected_companies,
    )

    add_log(
        f"[배당 추출] ID={schedule_id} "
        f"업체={len(bookmakers)}"
    )

    if not bookmakers:

        raise RuntimeError(
            "최종배당 없음"
        )

    # --------------------------------------------------------
    # 경기 저장
    # --------------------------------------------------------

    if not database.save_match(
        schedule_id,
        match_date,
        home_team,
        away_team,
        home_score,
        away_score,
        result,
        "scoreman",
    ):

        raise RuntimeError(
            "경기 저장 실패"
        )

    # --------------------------------------------------------
    # 배당 저장
    # --------------------------------------------------------

    saved = 0

    for item in bookmakers:

        if not is_running():

            return "stopped"

        ok = database.save_odds(
            schedule_id,
            item["cid"],
            item["name"],
            item["home"],
            item["draw"],
            item["away"],
        )

        if not ok:

            raise RuntimeError(
                "배당 저장 실패: "
                f"{item['name']}"
            )

        saved += 1

        add_log(
            f"[배당 저장] "
            f"ID={schedule_id} "
            f"업체={item['name']} "
            f"CID={item['cid']} "
            f"승={item['home']} "
            f"무={item['draw']} "
            f"패={item['away']}"
        )

    if saved <= 0:

        raise RuntimeError(
            "저장된 배당 없음"
        )

    # --------------------------------------------------------
    # 완료
    # --------------------------------------------------------

    if not database.save_collection_state(
        schedule_id,
        "completed",
    ):

        raise RuntimeError(
            "완료 상태 저장 실패"
        )

    add_log(
        f"[수집 성공] "
        f"ID={schedule_id} "
        f"업체={saved} "
        f"결과={result or '미확인'}"
    )

    return {
        "status": "success",
        "odds": saved,
    }


# ============================================================
# 백그라운드
# ============================================================

def _worker():

    with lock:

        start_id = int(
            job["start_id"]
        )

        end_id = int(
            job["end_id"]
        )

        delay = float(
            job["delay"]
        )

        selected = list(
            job["selected_companies"]
        )

    total = (
        end_id
        - start_id
        + 1
    )

    add_log("=" * 50)

    add_log(
        "⚽ Scoreman 백그라운드 수집 시작"
    )

    add_log(
        f"범위: {start_id:,} ~ "
        f"{end_id:,}"
    )

    add_log(
        "실패 경기 / 배당 없음은 "
        "완료 ID로 저장하지 않음"
    )

    add_log(
        "자동 재시도: 없음"
    )

    add_log(
        f"요청 간격: {delay:.2f}초"
    )

    if selected:

        add_log(
            "수집 업체: "
            + ", ".join(
                map(str, selected)
            )
        )

    else:

        add_log(
            "수집 업체: "
            "전체 업체 자동수집"
        )

    add_log("=" * 50)

    for index, schedule_id in enumerate(
        range(
            start_id,
            end_id + 1,
        ),
        1,
    ):

        if not is_running():
            break

        with lock:

            job["current"] = index
            job["current_id"] = (
                schedule_id
            )

        try:

            result = collect_one_match(
                schedule_id,
                selected,
            )

            if isinstance(
                result,
                dict,
            ):

                status = result.get(
                    "status"
                )

                if status == "result_fixed":

                    with lock:
                        job["fixed"] += 1

                else:

                    with lock:
                        job["success"] += 1
                        job["odds"] += int(
                            result.get(
                                "odds",
                                0,
                            )
                        )

                with lock:

                    job[
                        "last_completed_id"
                    ] = schedule_id

            elif result == "exists":

                with lock:

                    job["exists"] += 1

                    job[
                        "last_completed_id"
                    ] = schedule_id

            elif result == "stopped":

                break

        except Exception as e:

            with lock:
                job["failed"] += 1

            database.save_collection_state(
                schedule_id,
                "failed",
            )

            add_log(
                f"[수집 실패] "
                f"ID={schedule_id} "
                f"오류={type(e).__name__}: {e}"
            )

        if (
            delay > 0
            and is_running()
            and schedule_id < end_id
        ):

            time.sleep(delay)

    with lock:

        job["running"] = False
        job["finished"] = True

        job["end_time"] = (
            datetime.now().isoformat(
                timespec="seconds"
            )
        )

        job["result"] = (
            f"성공 {job['success']} / "
            f"결과보정 {job['fixed']} / "
            f"중복 {job['exists']} / "
            f"실패 {job['failed']} / "
            f"배당 {job['odds']}"
        )

    add_log("=" * 50)

    add_log(
        "🏁 Scoreman 수집 종료"
    )

    add_log(
        f"성공={job['success']} "
        f"결과보정={job['fixed']} "
        f"중복={job['exists']} "
        f"실패={job['failed']} "
        f"배당={job['odds']}"
    )

    add_log("=" * 50)


# ============================================================
# 시작
# ============================================================

def start_background_collection(
    start_id,
    end_id,
    selected_companies=None,
    delay=DEFAULT_DELAY,
):

    with lock:

        if job["running"]:

            return (
                False,
                "이미 수집 중입니다.",
            )

    try:

        start_id = int(start_id)
        end_id = int(end_id)

    except Exception:

        return (
            False,
            "ID는 숫자로 입력하세요.",
        )

    if start_id <= 0:

        return (
            False,
            "시작 ID 오류",
        )

    if end_id < start_id:

        return (
            False,
            "종료 ID 오류",
        )

    try:

        delay = float(delay)

    except Exception:

        delay = DEFAULT_DELAY

    if delay < 0:
        delay = 0

    if selected_companies is None:
        selected_companies = []

    with lock:

        job["running"] = True
        job["finished"] = False

        job["current"] = 0
        job["current_id"] = 0

        job["total"] = (
            end_id
            - start_id
            + 1
        )

        job["success"] = 0
        job["exists"] = 0
        job["failed"] = 0
        job["fixed"] = 0
        job["odds"] = 0

        job["start_id"] = start_id
        job["end_id"] = end_id

        job["last_completed_id"] = (
            database.get_last_completed_id(
                start_id,
                end_id,
            )
        )

        job[
            "selected_companies"
        ] = list(
            selected_companies
        )

        job["delay"] = delay

        job["start_time"] = (
            datetime.now().isoformat(
                timespec="seconds"
            )
        )

        job["end_time"] = None

        job["log"] = []

        job["result"] = ""
        job["error"] = ""

    thread = threading.Thread(
        target=_worker,
        daemon=True,
    )

    thread.start()

    return (
        True,
        "수집을 시작했습니다.",
    )


# ============================================================
# 이어받기
# ============================================================

def resume_collection(
    start_id,
    end_id,
    selected_companies=None,
    delay=DEFAULT_DELAY,
):

    try:

        start_id = int(start_id)
        end_id = int(end_id)

    except Exception:

        return (
            False,
            "ID 오류",
        )

    resume_id = (
        database.get_resume_id(
            start_id,
            end_id,
        )
    )

    if resume_id > end_id:

        return (
            False,
            "지정 범위는 이미 완료되었습니다.",
        )

    add_log(
        f"▶️ 이어받기 시작 ID="
        f"{resume_id}"
    )

    return start_background_collection(
        resume_id,
        end_id,
        selected_companies,
        delay,
    )


# ============================================================
# 진행률
# ============================================================

def get_progress():

    with lock:

        total = int(
            job["total"] or 0
        )

        current = int(
            job["current"] or 0
        )

        percent = (
            current / total * 100
            if total
            else 0
        )

        return {

            "current": current,

            "total": total,

            "percent": percent,

            "current_id":
                job["current_id"],

            "success":
                job["success"],

            "exists":
                job["exists"],

            "failed":
                job["failed"],

            "fixed":
                job["fixed"],

            "odds":
                job["odds"],

            "running":
                job["running"],

            "finished":
                job["finished"],

            "last_completed_id":
                job[
                    "last_completed_id"
                ],
        }


# ============================================================
# 단일 테스트
# ============================================================

def collect_single(
    schedule_id,
    selected_companies=None,
):

    try:

        return collect_one_match(
            int(schedule_id),
            selected_companies,
        )

    except Exception as e:

        return {
            "status": "failed",
            "error": str(e),
            }
