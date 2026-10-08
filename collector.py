# ============================================================
# collector.py
# Scoreman 백그라운드 수집기
# ============================================================

import re
import time
import json
import html as html_lib
import threading
from datetime import datetime

import requests

import database


BASE_URL = "https://www.scoreman123.com"

MATCH_URL = BASE_URL + "/match/data-{schedule_id}"

ODDS_URL = (
    BASE_URL
    + "/ajax/soccerajax?type=14&t=1&id={schedule_id}&h=0"
)

REQUEST_TIMEOUT = 20
DEFAULT_DELAY = 0.5


session = requests.Session()

session.headers.update({
    "User-Agent":
        "Mozilla/5.0 (Linux; Android 10; K) "
        "AppleWebKit/537.36 "
        "Chrome/130.0 Mobile Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    "Referer": BASE_URL + "/",
})


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

    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {message}"

    with lock:
        job["log"].append(line)

        if len(job["log"]) > 1500:
            job["log"] = job["log"][-1500:]

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

    add_log("🛑 수집 중지 요청")
    return True


# ============================================================
# 숫자
# ============================================================

def to_float(value):

    try:

        if value is None:
            return None

        value = str(value).strip()
        value = value.replace(",", "")

        if not value:
            return None

        value = float(value)

        if value <= 0:
            return None

        return value

    except Exception:
        return None


def score_int(value):

    try:

        value = html_lib.unescape(str(value))
        value = value.replace("\\", "")
        value = re.sub(r"<[^>]+>", "", value)
        value = value.strip()

        m = re.search(r"-?\d{1,3}", value)

        if not m:
            return None

        n = int(m.group())

        if 0 <= n <= 99:
            return n

    except Exception:
        pass

    return None


# ============================================================
# 결과
# ============================================================

def calculate_result(home_score, away_score):

    h = score_int(home_score)
    a = score_int(away_score)

    if h is None or a is None:
        return None

    if h > a:
        return "승"

    if h == a:
        return "무"

    return "패"


# ============================================================
# 텍스트
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    value = html_lib.unescape(str(value))

    value = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    value = value.replace("\\/", "/")

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


# ============================================================
# 페이지
# ============================================================

def fetch_match_page(schedule_id):

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
            f"경기 페이지 HTTP={response.status_code}"
        )

    return response.text


# ============================================================
# 팀명
# ============================================================

def extract_team_names(html):

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

        hm = re.findall(hp, html, re.I)
        am = re.findall(ap, html, re.I)

        if hm and am:

            home = clean_text(hm[-1])
            away = clean_text(am[-1])

            if home and away:
                return home, away

    return "", ""


# ============================================================
# JSON 재귀
# ============================================================

def recursive_score_search(obj):

    if isinstance(obj, dict):

        pairs = [
            ("homeScore", "awayScore"),
            ("home_score", "away_score"),
            ("homescore", "awayscore"),
            ("HomeScore", "AwayScore"),
            ("home_score1", "away_score1"),
            ("hs", "as"),
            ("HScore", "AScore"),
            ("hscore", "ascore"),
            ("score_home", "score_away"),
        ]

        for hk, ak in pairs:

            if hk in obj and ak in obj:

                h = score_int(obj.get(hk))
                a = score_int(obj.get(ak))

                if h is not None and a is not None:
                    return h, a

        for key, value in obj.items():

            key_l = str(key).lower()

            if (
                "score" in key_l
                and isinstance(value, str)
            ):

                m = re.search(
                    r"(\d+)\s*[-:]\s*(\d+)",
                    value,
                )

                if m:
                    h = score_int(m.group(1))
                    a = score_int(m.group(2))

                    if h is not None and a is not None:
                        return h, a

        for value in obj.values():

            found = recursive_score_search(value)

            if found:
                return found

    elif isinstance(obj, list):

        for value in obj:

            found = recursive_score_search(value)

            if found:
                return found

    return None


# ============================================================
# 결과 추출
# ============================================================

def extract_score(html):

    # --------------------------------------------------------
    # 1. JSON 블록 탐색
    # --------------------------------------------------------

    json_candidates = []

    for pattern in [
        r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
        r'<script[^>]*>(.*?)</script>',
    ]:

        try:
            json_candidates.extend(
                re.findall(
                    pattern,
                    html,
                    re.I | re.S,
                )
            )
        except Exception:
            pass

    for text in json_candidates:

        text = html_lib.unescape(text).strip()

        if not text:
            continue

        try:

            data = json.loads(text)

            found = recursive_score_search(data)

            if found:
                h, a = found
                return h, a, calculate_result(h, a)

        except Exception:
            pass

    # --------------------------------------------------------
    # 2. 전체 HTML에서 명시적인 score 키
    # --------------------------------------------------------

    patterns = [

        (
            r'"homeScore"\s*:\s*["\']?(\d{1,2})',
            r'"awayScore"\s*:\s*["\']?(\d{1,2})',
        ),

        (
            r'"home_score"\s*:\s*["\']?(\d{1,2})',
            r'"away_score"\s*:\s*["\']?(\d{1,2})',
        ),

        (
            r'"homescore"\s*:\s*["\']?(\d{1,2})',
            r'"awayscore"\s*:\s*["\']?(\d{1,2})',
        ),

        (
            r'"HomeScore"\s*:\s*["\']?(\d{1,2})',
            r'"AwayScore"\s*:\s*["\']?(\d{1,2})',
        ),

        (
            r'"hscore"\s*:\s*["\']?(\d{1,2})',
            r'"ascore"\s*:\s*["\']?(\d{1,2})',
        ),

        (
            r'"hs"\s*:\s*["\']?(\d{1,2})',
            r'"as"\s*:\s*["\']?(\d{1,2})',
        ),
    ]

    for hp, ap in patterns:

        hm = re.findall(hp, html, re.I)
        am = re.findall(ap, html, re.I)

        if hm and am:

            h = score_int(hm[-1])
            a = score_int(am[-1])

            if h is not None and a is not None:

                return (
                    h,
                    a,
                    calculate_result(h, a),
                )

    # --------------------------------------------------------
    # 3. score 문자열
    # --------------------------------------------------------

    score_patterns = [
        r'"score"\s*:\s*"(\d{1,2})\s*[-:]\s*(\d{1,2})"',
        r'"score"\s*:\s*\'(\d{1,2})\s*[-:]\s*(\d{1,2})\'',
        r'data-score\s*=\s*["\'](\d{1,2})\s*[-:]\s*(\d{1,2})',
        r'(\d{1,2})\s*[-:]\s*(\d{1,2})',
    ]

    for pattern in score_patterns:

        found = re.findall(
            pattern,
            html,
            re.I,
        )

        if found:

            # 마지막 후보부터 검사
            for pair in reversed(found):

                try:
                    h = score_int(pair[0])
                    a = score_int(pair[1])

                    if h is not None and a is not None:

                        return (
                            h,
                            a,
                            calculate_result(h, a),
                        )

                except Exception:
                    pass

    # --------------------------------------------------------
    # 4. 화면 텍스트 기반 점수
    # --------------------------------------------------------

    visible = re.sub(
        r"<script.*?</script>",
        " ",
        html,
        flags=re.I | re.S,
    )

    visible = re.sub(
        r"<style.*?</style>",
        " ",
        visible,
        flags=re.I | re.S,
    )

    visible = html_lib.unescape(visible)

    visible = re.sub(
        r"<[^>]+>",
        " ",
        visible,
    )

    visible = re.sub(
        r"\s+",
        " ",
        visible,
    )

    patterns = [
        r'(\d{1,2})\s*-\s*(\d{1,2})',
        r'(\d{1,2})\s*:\s*(\d{1,2})',
    ]

    for pattern in patterns:

        found = re.findall(
            pattern,
            visible,
        )

        for pair in reversed(found):

            h = score_int(pair[0])
            a = score_int(pair[1])

            if h is not None and a is not None:

                # 시간처럼 보이는 값은 제외
                if h <= 9 and a <= 9:

                    return (
                        h,
                        a,
                        calculate_result(h, a),
                    )

    return None, None, None


# ============================================================
# 날짜
# ============================================================

def extract_match_date(html):

    patterns = [

        r'"matchDate"\s*:\s*"([^"]+)"',

        r'"match_date"\s*:\s*"([^"]+)"',

        r'"matchTime"\s*:\s*"([^"]+)"',

        r'"date"\s*:\s*"'
        r'(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})"',

        r'(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
    ]

    for pattern in patterns:

        found = re.findall(
            pattern,
            html,
            re.I,
        )

        if found:
            return clean_text(found[-1])

    return None


# ============================================================
# 배당 API
# ============================================================

def fetch_odds(schedule_id):

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
            f"배당 API HTTP={response.status_code}"
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

        if start >= 0 and end > start:

            try:
                return json.loads(
                    text[start:end + 1]
                )
            except Exception:
                pass

    return None


# ============================================================
# 업체
# ============================================================

def extract_bookmakers(data):

    if not isinstance(data, dict):
        return []

    mixodds = None

    if isinstance(data.get("Data"), dict):
        mixodds = data["Data"].get("mixodds")

    if mixodds is None:
        mixodds = data.get("mixodds")

    if not isinstance(mixodds, list):
        return []

    result = []

    for item in mixodds:

        if not isinstance(item, dict):
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

        euro = item.get("euro")

        if not isinstance(euro, dict):
            continue

        final_odds = euro.get("l")

        if not isinstance(final_odds, dict):
            continue

        home = to_float(final_odds.get("u"))
        draw = to_float(final_odds.get("g"))
        away = to_float(final_odds.get("d"))

        if (
            home is None
            or draw is None
            or away is None
        ):
            continue

        result.append({
            "cid": str(cid),
            "name": str(name).strip(),
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
        str(x).strip().lower()
        for x in selected_companies
        if str(x).strip()
    }

    result = []

    for item in bookmakers:

        cid = str(item["cid"]).lower()
        name = str(item["name"]).lower()

        if cid in selected or name in selected:
            result.append(item)

    return result


# ============================================================
# 한 경기
# ============================================================

def collect_one_match(
    schedule_id,
    selected_companies=None,
):

    schedule_id = str(schedule_id)

    # 완료 경기만 중복 처리
    if database.is_collection_completed(schedule_id):

        add_log(
            f"[중복] ID={schedule_id}"
        )

        return "exists"

    html = fetch_match_page(schedule_id)

    home_team, away_team = extract_team_names(html)

    home_score, away_score, result = extract_score(html)

    match_date = extract_match_date(html)

    if not home_team:
        home_team = f"ID {schedule_id}"

    if not away_team:
        away_team = "상대팀"

    # --------------------------------------------------------
    # 결과 확인
    # --------------------------------------------------------

    if (
        home_score is None
        or away_score is None
        or result not in ("승", "무", "패")
    ):

        add_log(
            f"[결과 미확인] ID={schedule_id} "
            f"홈점수={home_score} "
            f"원정점수={away_score}"
        )

        # 임시 저장
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
        f"[경기결과] ID={schedule_id} "
        f"{home_team} "
        f"{home_score}-{away_score} "
        f"{away_team} "
        f"결과={result}"
    )

    # --------------------------------------------------------
    # 배당
    # --------------------------------------------------------

    odds_text = fetch_odds(schedule_id)

    odds_data = parse_json(odds_text)

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
                f"배당 저장 실패: {item['name']}"
            )

        saved += 1

        add_log(
            f"[배당 저장] "
            f"ID={schedule_id} "
            f"업체={item['name']} "
            f"승={item['home']} "
            f"무={item['draw']} "
            f"패={item['away']}"
        )

    if saved <= 0:
        raise RuntimeError(
            "저장된 배당 없음"
        )

    # --------------------------------------------------------
    # 모든 저장 성공 후 완료
    # --------------------------------------------------------

    if not database.save_collection_state(
        schedule_id,
        "completed",
    ):
        raise RuntimeError(
            "완료 상태 저장 실패"
        )

    add_log(
        f"[수집 성공] ID={schedule_id} "
        f"업체={saved} 결과={result}"
    )

    return {
        "status": "success",
        "odds": saved,
        "result": result,
    }


# ============================================================
# 백그라운드
# ============================================================

def _worker():

    with lock:

        start_id = int(job["start_id"])
        end_id = int(job["end_id"])
        delay = float(job["delay"])
        selected = list(job["selected_companies"])

        job["start_time"] = datetime.now().isoformat(
            timespec="seconds"
        )

    add_log("=" * 50)
    add_log("⚽ Scoreman 백그라운드 수집 시작")
    add_log(f"범위: {start_id:,} ~ {end_id:,}")
    add_log(
        "실패 / 결과미확인 / 배당없음은 "
        "완료 ID로 저장하지 않음"
    )
    add_log("자동 재시도: 없음")
    add_log(f"요청 간격: {delay:.2f}초")

    if selected:
        add_log(
            "수집 업체: "
            + ", ".join(map(str, selected))
        )
    else:
        add_log(
            "수집 업체: 전체 업체 자동수집"
        )

    add_log("=" * 50)

    total = end_id - start_id + 1

    for index, schedule_id in enumerate(
        range(start_id, end_id + 1),
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

            if isinstance(result, dict):

                with lock:
                    job["success"] += 1
                    job["odds"] += int(
                        result.get("odds", 0)
                    )
                    job["last_completed_id"] = int(
                        schedule_id
                    )

            elif result == "exists":

                with lock:
                    job["exists"] += 1
                    job["last_completed_id"] = int(
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

        job["end_time"] = datetime.now().isoformat(
            timespec="seconds"
        )

        job["result"] = (
            f"성공 {job['success']} / "
            f"중복 {job['exists']} / "
            f"실패 {job['failed']} / "
            f"배당 {job['odds']}"
        )

    add_log("=" * 50)
    add_log("🏁 Scoreman 수집 종료")

    add_log(
        f"성공={job['success']} "
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
            return False, "이미 수집 중입니다."

    try:
        start_id = int(start_id)
        end_id = int(end_id)
    except Exception:
        return False, "ID는 숫자로 입력하세요."

    if start_id <= 0:
        return False, "시작 ID 오류"

    if end_id < start_id:
        return False, "종료 ID 오류"

    try:
        delay = float(delay)
    except Exception:
        delay = DEFAULT_DELAY

    delay = max(0, delay)

    selected_companies = (
        selected_companies or []
    )

    with lock:

        job["running"] = True
        job["finished"] = False
        job["current"] = 0
        job["total"] = end_id - start_id + 1

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

    return True, "수집을 시작했습니다."


# ============================================================
# 이어받기
# ============================================================

def resume_collection(
    end_id,
    selected_companies=None,
    delay=DEFAULT_DELAY,
):

    last_id = database.get_last_completed_id()

    if last_id is None:
        return False, "저장된 완료 ID가 없습니다."

    try:
        end_id = int(end_id)
    except Exception:
        return False, "종료 ID 오류"

    next_id = last_id + 1

    if next_id > end_id:
        return False, (
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

        total = int(job["total"] or 0)
        current = int(job["current"] or 0)

        percent = (
            current / total * 100
            if total
            else 0
        )

        return {
            "current": current,
            "total": total,
            "percent": percent,
            "success": job["success"],
            "exists": job["exists"],
            "failed": job["failed"],
            "odds": job["odds"],
            "running": job["running"],
            "finished": job["finished"],
            "last_completed_id":
                job["last_completed_id"],
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
