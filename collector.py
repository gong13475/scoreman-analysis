# ============================================================
# collector.py
# Scoreman 백그라운드 수집기
# ============================================================

import re
import time
import json
import html as html_module
import threading
from datetime import datetime

import requests

import database


BASE_URL = "https://www.scoreman123.com"

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
# Session
# ============================================================

session = requests.Session()

session.headers.update({

    "User-Agent":
        "Mozilla/5.0 "
        "(Linux; Android 10; K) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/130.0 Mobile Safari/537.36",

    "Accept":
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8",

    "Accept-Language":
        "ko-KR,ko;q=0.9,en-US;q=0.8",

    "Referer":
        BASE_URL + "/",

    "Connection":
        "keep-alive",
})


# ============================================================
# 상태
# ============================================================

job = {

    "running": False,
    "finished": False,

    "current": 0,
    "total": 0,

    "success": 0,
    "exists": 0,
    "failed": 0,
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

    line = f"[{timestamp}] {message}"

    with lock:

        job["log"].append(line)

        if len(job["log"]) > 1500:

            job["log"] = (
                job["log"][-1500:]
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
        return bool(job["running"])


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

        value = str(value).strip()

        value = value.replace(
            ",",
            ""
        )

        value = value.replace(
            "\\",
            ""
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
# 텍스트 정리
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    value = html_module.unescape(
        str(value)
    )

    value = value.replace(
        "\\/",
        "/"
    )

    value = value.replace(
        "\\u002F",
        "/"
    )

    value = value.replace(
        "\\u003A",
        ":"
    )

    value = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


# ============================================================
# HTML 정규화
# ============================================================

def normalize_html(text):

    if not text:
        return ""

    value = text

    value = html_module.unescape(
        value
    )

    replacements = {

        "\\/": "/",

        '\\"': '"',

        "\\'": "'",

        "\\u002F": "/",

        "\\u003A": ":",

        "\\u003C": "<",

        "\\u003E": ">",

        "&quot;": '"',

        "&amp;": "&",
    }

    for old, new in replacements.items():

        value = value.replace(
            old,
            new
        )

    return value


# ============================================================
# 경기 페이지
# ============================================================

def fetch_match_page(
    schedule_id
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
            f"경기 페이지 HTTP="
            f"{response.status_code}"
        )

    return response.text


# ============================================================
# 팀명
# ============================================================

def extract_team_names(html):

    text = normalize_html(html)

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
            r'"home_name"\s*:\s*"([^"]+)"',
            r'"away_name"\s*:\s*"([^"]+)"',
        ),

        (
            r'"HomeName"\s*:\s*"([^"]+)"',
            r'"AwayName"\s*:\s*"([^"]+)"',
        ),
    ]

    for hp, ap in patterns:

        hm = re.findall(
            hp,
            text,
            re.I
        )

        am = re.findall(
            ap,
            text,
            re.I
        )

        if hm and am:

            home = clean_text(
                hm[-1]
            )

            away = clean_text(
                am[-1]
            )

            if home and away:

                return (
                    home,
                    away
                )

    return "", ""


# ============================================================
# JSON 파싱
# ============================================================

def parse_json(
    text
):

    if not text:
        return None

    try:

        return json.loads(
            text
        )

    except Exception:
        pass

    normalized = normalize_html(
        text
    )

    try:

        return json.loads(
            normalized
        )

    except Exception:
        pass

    start = normalized.find("{")
    end = normalized.rfind("}")

    if (
        start >= 0
        and end > start
    ):

        try:

            return json.loads(
                normalized[
                    start:end + 1
                ]
            )

        except Exception:
            pass

    return None


# ============================================================
# JSON 재귀
# ============================================================

def recursive_find_pairs(
    obj,
    key_pairs
):

    if isinstance(obj, dict):

        lower_map = {}

        for key, value in obj.items():

            lower_map[
                str(key).lower()
            ] = value

        for hp, ap in key_pairs:

            hk = hp.lower()
            ak = ap.lower()

            if (
                hk in lower_map
                and ak in lower_map
            ):

                h = parse_score_value(
                    lower_map[hk]
                )

                a = parse_score_value(
                    lower_map[ak]
                )

                if valid_score(
                    h,
                    a
                ):

                    return (
                        h,
                        a
                    )

        for value in obj.values():

            found = recursive_find_pairs(
                value,
                key_pairs
            )

            if found:
                return found

    elif isinstance(obj, list):

        for value in obj:

            found = recursive_find_pairs(
                value,
                key_pairs
            )

            if found:
                return found

    return None


# ============================================================
# 점수 숫자
# ============================================================

def parse_score_value(
    value
):

    if value is None:
        return None

    text = str(value)

    text = text.replace(
        "\\",
        ""
    )

    text = text.strip()

    # 단일 정수
    m = re.fullmatch(
        r"(\d{1,2})",
        text
    )

    if m:

        try:
            return int(m.group(1))
        except Exception:
            return None

    return None


def valid_score(
    home,
    away
):

    if home is None:
        return False

    if away is None:
        return False

    if not (
        0 <= home <= 99
        and 0 <= away <= 99
    ):
        return False

    return True


# ============================================================
# 점수 문자열 탐색
# ============================================================

def score_from_text_patterns(
    text
):

    if not text:
        return None

    text = normalize_html(
        text
    )

    # --------------------------------------------------------
    # 명시적인 home / away
    # --------------------------------------------------------

    patterns = [

        (
            r'"homeScore"\s*:\s*"?(?:\\)?(\d{1,2})',
            r'"awayScore"\s*:\s*"?(?:\\)?(\d{1,2})',
        ),

        (
            r'"home_score"\s*:\s*"?(?:\\)?(\d{1,2})',
            r'"away_score"\s*:\s*"?(?:\\)?(\d{1,2})',
        ),

        (
            r'"homescore"\s*:\s*"?(?:\\)?(\d{1,2})',
            r'"awayscore"\s*:\s*"?(?:\\)?(\d{1,2})',
        ),

        (
            r'"HomeScore"\s*:\s*"?(?:\\)?(\d{1,2})',
            r'"AwayScore"\s*:\s*"?(?:\\)?(\d{1,2})',
        ),

        (
            r'"hs"\s*:\s*"?(?:\\)?(\d{1,2})',
            r'"as"\s*:\s*"?(?:\\)?(\d{1,2})',
        ),

        (
            r'"hscore"\s*:\s*"?(?:\\)?(\d{1,2})',
            r'"ascore"\s*:\s*"?(?:\\)?(\d{1,2})',
        ),

        (
            r'"home_score_value"\s*:\s*"?(?:\\)?(\d{1,2})',
            r'"away_score_value"\s*:\s*"?(?:\\)?(\d{1,2})',
        ),
    ]

    for hp, ap in patterns:

        hm = re.findall(
            hp,
            text,
            re.I
        )

        am = re.findall(
            ap,
            text,
            re.I
        )

        if hm and am:

            try:

                h = int(
                    hm[-1]
                )

                a = int(
                    am[-1]
                )

                if valid_score(
                    h,
                    a
                ):

                    return h, a

            except Exception:
                pass

    # --------------------------------------------------------
    # score: "2-1"
    # --------------------------------------------------------

    score_patterns = [

        r'"score"\s*:\s*"(\d{1,2})\s*[-:]\s*(\d{1,2})"',

        r'"result"\s*:\s*"(\d{1,2})\s*[-:]\s*(\d{1,2})"',

        r'"finalScore"\s*:\s*"(\d{1,2})\s*[-:]\s*(\d{1,2})"',

        r'"final_score"\s*:\s*"(\d{1,2})\s*[-:]\s*(\d{1,2})"',

        r'data-score\s*=\s*["\']'
        r'(\d{1,2})\s*[-:]\s*(\d{1,2})',

        r'class\s*=\s*["\'][^"\']*score[^"\']*["\'][^>]*>'
        r'\s*(\d{1,2})\s*[-:]\s*(\d{1,2})',
    ]

    for pattern in score_patterns:

        matches = re.findall(
            pattern,
            text,
            re.I
        )

        if matches:

            try:

                h = int(
                    matches[-1][0]
                )

                a = int(
                    matches[-1][1]
                )

                if valid_score(
                    h,
                    a
                ):

                    return h, a

            except Exception:
                pass

    return None


# ============================================================
# JSON 문자열 안의 점수 탐색
# ============================================================

def find_score_in_json(
    html
):

    normalized = normalize_html(
        html
    )

    key_pairs = [

        (
            "homeScore",
            "awayScore"
        ),

        (
            "home_score",
            "away_score"
        ),

        (
            "homescore",
            "awayscore"
        ),

        (
            "HomeScore",
            "AwayScore"
        ),

        (
            "hs",
            "as"
        ),

        (
            "hscore",
            "ascore"
        ),

        (
            "home_score_value",
            "away_score_value"
        ),
    ]

    # --------------------------------------------------------
    # 전체 JSON object
    # --------------------------------------------------------

    data = parse_json(
        normalized
    )

    if data is not None:

        found = recursive_find_pairs(
            data,
            key_pairs
        )

        if found:
            return found

    # --------------------------------------------------------
    # script 내부 JSON
    # --------------------------------------------------------

    scripts = re.findall(
        r"<script[^>]*>(.*?)</script>",
        normalized,
        re.I | re.S
    )

    for script in scripts:

        found = score_from_text_patterns(
            script
        )

        if found:
            return found

        data = parse_json(
            script.strip()
        )

        if data is not None:

            found = recursive_find_pairs(
                data,
                key_pairs
            )

            if found:
                return found

    return None


# ============================================================
# 점수 추출
# ============================================================

def extract_score(
    html
):

    # --------------------------------------------------------
    # 1. JSON
    # --------------------------------------------------------

    found = find_score_in_json(
        html
    )

    if found:

        h, a = found

        return (
            h,
            a,
            calculate_result(h, a)
        )

    # --------------------------------------------------------
    # 2. HTML 전체 패턴
    # --------------------------------------------------------

    found = score_from_text_patterns(
        html
    )

    if found:

        h, a = found

        return (
            h,
            a,
            calculate_result(h, a)
        )

    # --------------------------------------------------------
    # 3. 태그 안 숫자
    # --------------------------------------------------------

    normalized = normalize_html(
        html
    )

    tag_patterns = [

        r'<[^>]*data-home-score\s*=\s*["\'](\d{1,2})["\']'
        r'[^>]*data-away-score\s*=\s*["\'](\d{1,2})["\']',

        r'<[^>]*data-homescore\s*=\s*["\'](\d{1,2})["\']'
        r'[^>]*data-awayscore\s*=\s*["\'](\d{1,2})["\']',
    ]

    for pattern in tag_patterns:

        matches = re.findall(
            pattern,
            normalized,
            re.I
        )

        if matches:

            try:

                h = int(
                    matches[-1][0]
                )

                a = int(
                    matches[-1][1]
                )

                if valid_score(
                    h,
                    a
                ):

                    return (
                        h,
                        a,
                        calculate_result(h, a)
                    )

            except Exception:
                pass

    return None, None, None


# ============================================================
# 날짜
# ============================================================

def extract_match_date(
    html
):

    text = normalize_html(
        html
    )

    patterns = [

        r'"matchDate"\s*:\s*"([^"]+)"',

        r'"match_date"\s*:\s*"([^"]+)"',

        r'"MatchDate"\s*:\s*"([^"]+)"',

        r'"date"\s*:\s*"'
        r'(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})"',

        r'"match_time"\s*:\s*"([^"]+)"',
    ]

    for pattern in patterns:

        found = re.findall(
            pattern,
            text,
            re.I
        )

        if found:

            return clean_text(
                found[-1]
            )

    return None


# ============================================================
# 배당 API
# ============================================================

def fetch_odds(
    schedule_id
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
            f"배당 API HTTP="
            f"{response.status_code}"
        )

    return response.text


# ============================================================
# 업체 추출
# ============================================================

def extract_bookmakers(
    data
):

    if not isinstance(
        data,
        dict
    ):

        return []

    mixodds = None

    data_block = data.get(
        "Data"
    )

    if isinstance(
        data_block,
        dict
    ):

        mixodds = data_block.get(
            "mixodds"
        )

    if mixodds is None:

        mixodds = data.get(
            "mixodds"
        )

    if not isinstance(
        mixodds,
        list
    ):

        return []

    result = []

    for item in mixodds:

        if not isinstance(
            item,
            dict
        ):
            continue

        cid = (
            item.get("cid")
            or item.get("company_id")
            or item.get("companyId")
            or item.get("id")
        )

        name = (
            item.get("cn")
            or item.get("company_name")
            or item.get("companyName")
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
            dict
        ):
            continue

        # ----------------------------------------------------
        # 최종배당 l
        # ----------------------------------------------------

        final_odds = euro.get(
            "l"
        )

        if not isinstance(
            final_odds,
            dict
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

        result.append({

            "cid": str(cid),

            "name": str(
                name
            ).strip(),

            "home": home,

            "draw": draw,

            "away": away,
        })

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

            result.append(
                item
            )

    return result


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

        add_log(
            f"[중복] ID={schedule_id}"
        )

        return "exists"

    # --------------------------------------------------------
    # 경기 페이지
    # --------------------------------------------------------

    html = fetch_match_page(
        schedule_id
    )

    # --------------------------------------------------------
    # 팀
    # --------------------------------------------------------

    home_team, away_team = (
        extract_team_names(
            html
        )
    )

    if not home_team:

        home_team = (
            f"ID {schedule_id}"
        )

    if not away_team:

        away_team = "상대팀"

    # --------------------------------------------------------
    # 점수
    # --------------------------------------------------------

    (
        home_score,
        away_score,
        result
    ) = extract_score(
        html
    )

    match_date = (
        extract_match_date(
            html
        )
    )

    # --------------------------------------------------------
    # 결과 없음
    # --------------------------------------------------------

    if (
        home_score is None
        or away_score is None
        or result not in (
            "승",
            "무",
            "패",
        )
    ):

        add_log(
            f"[결과 미확인] "
            f"ID={schedule_id} "
            f"홈={home_team} "
            f"원정={away_team} "
            f"홈점수={home_score} "
            f"원정점수={away_score}"
        )

        # ----------------------------------------------------
        # 미완료 경기만 저장
        # ----------------------------------------------------

        database.save_match(
            schedule_id,
            match_date,
            home_team,
            away_team,
            None,
            None,
            None,
            "scoreman",
        )

        # 완료 상태는 절대 저장하지 않음
        raise RuntimeError(
            "실제 경기결과/스코어 확인 실패"
        )

    add_log(
        f"[경기결과] "
        f"ID={schedule_id} "
        f"{home_team} "
        f"{home_score}-{away_score} "
        f"{away_team} "
        f"결과={result}"
    )

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

    bookmakers = (
        extract_bookmakers(
            odds_data
        )
    )

    bookmakers = (
        filter_bookmakers(
            bookmakers,
            selected_companies,
        )
    )

    add_log(
        f"[배당 추출] "
        f"ID={schedule_id} "
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
                + item["name"]
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
    # 완료 상태
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
        f"결과={result}"
    )

    return {

        "status": "success",

        "odds": saved,

        "result": result,
    }


# ============================================================
# 백그라운드 Worker
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

        job["start_time"] = (
            datetime.now().isoformat(
                timespec="seconds"
            )
        )

    add_log("=" * 60)

    add_log(
        "⚽ Scoreman 백그라운드 수집 시작"
    )

    add_log(
        f"범위: {start_id:,} ~ {end_id:,}"
    )

    add_log(
        "실패/결과미확인/배당없음은 "
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
                map(
                    str,
                    selected
                )
            )
        )

    else:

        add_log(
            "수집 업체: 전체 업체 자동수집"
        )

    add_log("=" * 60)

    for index, schedule_id in enumerate(
        range(
            start_id,
            end_id + 1
        ),
        1,
    ):

        if not is_running():
            break

        with lock:

            job["current"] = index

        try:

            result = collect_one_match(
                schedule_id,
                selected,
            )

            if isinstance(
                result,
                dict
            ):

                with lock:

                    job["success"] += 1

                    job["odds"] += int(
                        result.get(
                            "odds",
                            0
                        )
                    )

                    job[
                        "last_completed_id"
                    ] = int(
                        schedule_id
                    )

            elif result == "exists":

                with lock:

                    job["exists"] += 1

                    job[
                        "last_completed_id"
                    ] = int(
                        schedule_id
                    )

            elif result == "stopped":

                break

        except Exception as e:

            with lock:

                job["failed"] += 1

            add_log(
                f"[수집 실패] "
                f"ID={schedule_id} "
                f"오류="
                f"{type(e).__name__}: {e}"
            )

        if (
            delay > 0
            and is_running()
            and schedule_id < end_id
        ):

            # 중지 시 바로 빠져나오도록
            # 짧게 나눠서 대기
            remaining = delay

            while (
                remaining > 0
                and is_running()
            ):

                step = min(
                    0.1,
                    remaining
                )

                time.sleep(
                    step
                )

                remaining -= step

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
            f"중복 {job['exists']} / "
            f"실패 {job['failed']} / "
            f"배당 {job['odds']}"
        )

    add_log("=" * 60)

    add_log(
        "🏁 Scoreman 수집 종료"
    )

    add_log(
        f"성공={job['success']} "
        f"중복={job['exists']} "
        f"실패={job['failed']} "
        f"배당={job['odds']}"
    )

    add_log("=" * 60)


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
                "이미 수집 중입니다."
            )

    try:

        start_id = int(
            start_id
        )

        end_id = int(
            end_id
        )

    except Exception:

        return (
            False,
            "ID는 숫자로 입력하세요."
        )

    if start_id <= 0:

        return (
            False,
            "시작 ID 오류"
        )

    if end_id < start_id:

        return (
            False,
            "종료 ID 오류"
        )

    try:

        delay = float(
            delay
        )

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

        job["total"] = (
            end_id
            - start_id
            + 1
        )

        job["success"] = 0

        job["exists"] = 0

        job["failed"] = 0

        job["odds"] = 0

        job["start_id"] = start_id

        job["end_id"] = end_id

        job["last_completed_id"] = None

        job["selected_companies"] = list(
            selected_companies
        )

        job["delay"] = delay

        job["start_time"] = None

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
        "수집을 시작했습니다."
    )


# ============================================================
# 이어받기
# ============================================================

def resume_collection(
    end_id,
    selected_companies=None,
    delay=DEFAULT_DELAY,
):

    last_id = (
        database.get_last_completed_id()
    )

    if last_id is None:

        return (
            False,
            "저장된 완료 ID가 없습니다."
        )

    next_id = (
        last_id + 1
    )

    try:

        end_id = int(
            end_id
        )

    except Exception:

        return (
            False,
            "종료 ID 오류"
        )

    if next_id > end_id:

        return (
            False,
            f"이어받을 ID가 없습니다. "
            f"마지막 완료 ID={last_id:,}"
        )

    return start_background_collection(
        next_id,
        end_id,
        selected_companies or [],
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
            current
            / total
            * 100
            if total
            else 0
        )

        return {

            "current": current,

            "total": total,

            "percent": percent,

            "success":
                job["success"],

            "exists":
                job["exists"],

            "failed":
                job["failed"],

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
# 단일 경기
# ============================================================

def collect_single(
    schedule_id,
    selected_companies=None,
):

    try:

        with lock:

            if job["running"]:

                return {
                    "status": "failed",
                    "error":
                        "현재 백그라운드 "
                        "수집 중입니다.",
                }

            job["running"] = True

        result = collect_one_match(
            int(schedule_id),
            selected_companies,
        )

        return result

    except Exception as e:

        return {
            "status": "failed",
            "error": str(e),
        }

    finally:

        with lock:

            job["running"] = False
