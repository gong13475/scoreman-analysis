# ============================================================
# collector.py
# ⚽ Scoreman 자동 수집기 - 최종 보강본
#
# 기존 기능 유지
# - Scoreman 경기 페이지 수집
# - 실제 경기 결과 수집
# - 최종 해외배당 수집
# - 전체 업체 자동수집
# - 특정 업체 수집
# - 백그라운드 실행
# - 중지
# - 중지 지점 이어받기
# - 실패 1회 재시도
#
# 추가 보강
# - HTTP/배당 API 상세 로그
# - 업체별 배당 저장 오류 표시
# - 일부 업체 저장 실패 시 나머지 업체 계속 저장
# - 최종배당 저장 실패 원인 상세 표시
# - 저장된 업체 수 기준 성공 판정
# ============================================================

import json
import re
import threading
import time

import requests
from bs4 import BeautifulSoup

import database


# ============================================================
# 기본 설정
# ============================================================

BASE_URL = "https://www.scoreman123.com"

MATCH_URL = (
    BASE_URL +
    "/match/data-{schedule_id}"
)

ODDS_URL = (
    BASE_URL +
    "/ajax/soccerajax"
    "?type=14&t=1&id={schedule_id}&h=0"
)


# ============================================================
# HTTP
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Linux; Android 10) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/130.0 Mobile Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/json,text/plain,*/*"
    ),
    "Referer": BASE_URL + "/",
}


# ============================================================
# 작업 상태
# ============================================================

JOB_LOCK = threading.RLock()

JOB = {
    "running": False,
    "finished": False,
    "current": 0,
    "total": 0,

    "success": 0,
    "exists": 0,
    "failed": 0,
    "no_odds": 0,
    "odds": 0,

    "start_id": 0,
    "end_id": 0,
    "last_completed_id": 0,

    "selected_companies": None,

    "result": {},
    "error": "",
    "stopped": False,

    "log": "",
}

STOP_EVENT = threading.Event()
WORKER = None


# ============================================================
# 숫자 변환
# ============================================================

def to_float(value):

    try:

        if value is None:
            return None

        text = str(value).strip()

        if not text:
            return None

        return float(
            text.replace(",", "")
        )

    except Exception:

        return None


# ============================================================
# 로그
# ============================================================

def _log(message):

    text = str(message)

    try:
        database.save_collection_log(text)
    except Exception:
        pass

    with JOB_LOCK:

        old = str(
            JOB.get("log", "")
            or ""
        )

        JOB["log"] = (
            old
            + text
            + "\n"
        )

        lines = JOB["log"].splitlines()

        if len(lines) > 500:

            JOB["log"] = "\n".join(
                lines[-500:]
            )


# ============================================================
# JSON 후보
# ============================================================

def _find_json_objects(text):

    objects = []

    if not text:
        return objects

    try:

        obj = json.loads(text)

        objects.append(obj)

        return objects

    except Exception:
        pass

    patterns = [
        r'\{.*?"mixodds".*?\}',
        r'\{.*?"Data".*?\}',
        r'\[.*?"mixodds".*?\]',
    ]

    for pattern in patterns:

        try:

            matches = re.findall(
                pattern,
                text,
                re.S
            )

            for item in matches:

                try:

                    objects.append(
                        json.loads(item)
                    )

                except Exception:
                    continue

        except Exception:
            continue

    return objects


# ============================================================
# 스코어
# ============================================================

def _score_from_text(text):

    if not text:
        return None, None

    patterns = [
        r'(\d+)\s*[-:]\s*(\d+)',
        r'(\d+)\s*:\s*(\d+)',
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text
        )

        if match:

            try:

                return (
                    int(match.group(1)),
                    int(match.group(2))
                )

            except Exception:
                pass

    return None, None


# ============================================================
# 결과
# ============================================================

def _result_from_score(
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

    if home_score == away_score:
        return "무"

    return "패"


# ============================================================
# 팀명
# ============================================================

def _extract_teams(
    soup,
    text
):

    home = ""
    away = ""

    selectors = [
        ".team_name",
        ".teamname",
        ".team",
        ".home",
        ".away",
        ".homeTeam",
        ".awayTeam",
        "[class*='home']",
        "[class*='away']",
    ]

    candidates = []

    for selector in selectors:

        try:

            for node in soup.select(selector):

                value = node.get_text(
                    " ",
                    strip=True
                )

                if (
                    value
                    and len(value) < 100
                    and value not in candidates
                ):

                    candidates.append(value)

        except Exception:
            continue

    if len(candidates) >= 2:

        home = candidates[0]
        away = candidates[1]

    if not home or not away:

        title = ""

        try:

            if soup.title:

                title = soup.title.get_text(
                    " ",
                    strip=True
                )

        except Exception:
            pass

        match = re.search(
            r'(.{2,50}?)\s+(?:vs|VS|v\.|:)\s+(.{2,50})',
            title
        )

        if match:

            home = (
                home
                or match.group(1).strip()
            )

            away = (
                away
                or match.group(2).strip()
            )

    if not home or not away:

        lines = [
            x.strip()
            for x in text.splitlines()
            if x.strip()
        ]

        for line in lines:

            match = re.search(
                r'^(.{2,50})\s+(?:vs|VS)\s+(.{2,50})$',
                line
            )

            if match:

                home = (
                    home
                    or match.group(1).strip()
                )

                away = (
                    away
                    or match.group(2).strip()
                )

                break

    return home, away


# ============================================================
# 날짜
# ============================================================

def _extract_date(
    soup,
    text
):

    patterns = [

        r'(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}'
        r'(?:\s+\d{1,2}:\d{2})?)',

        r'(20\d{2}\d{2}\d{2})',

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text
        )

        if match:

            value = match.group(1)

            if len(value) == 8:

                return (
                    value[0:4]
                    + "-"
                    + value[4:6]
                    + "-"
                    + value[6:8]
                )

            return value

    try:

        meta = soup.find(
            "meta",
            attrs={
                "property":
                    "article:published_time"
            }
        )

        if meta:

            return meta.get(
                "content",
                ""
            )

    except Exception:
        pass

    return ""


# ============================================================
# 경기 페이지
# ============================================================

def fetch_match(
    schedule_id
):

    url = MATCH_URL.format(
        schedule_id=schedule_id
    )

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        _log(
            f"[페이지] ID={schedule_id} "
            f"HTTP={response.status_code} "
            f"SIZE={len(response.text or ''):,}"
        )

        if response.status_code != 200:

            _log(
                f"[페이지 실패] ID={schedule_id} "
                f"HTTP={response.status_code}"
            )

            return None

        html_text = response.text

        if not html_text:

            return None

        soup = BeautifulSoup(
            html_text,
            "html.parser"
        )

        text = soup.get_text(
            "\n",
            strip=True
        )

        home_team, away_team = (
            _extract_teams(
                soup,
                text
            )
        )

        home_score = None
        away_score = None

        score_candidates = []

        for selector in [
            ".score",
            ".scores",
            ".result",
            ".final_score",
            "[class*='score']",
        ]:

            try:

                for node in soup.select(selector):

                    value = node.get_text(
                        " ",
                        strip=True
                    )

                    if value:

                        score_candidates.append(
                            value
                        )

            except Exception:
                continue

        for candidate in score_candidates:

            h, a = _score_from_text(
                candidate
            )

            if h is not None:

                home_score = h
                away_score = a

                break

        if home_score is None:

            home_score, away_score = (
                _score_from_text(text)
            )

        result = _result_from_score(
            home_score,
            away_score
        )

        match_date = _extract_date(
            soup,
            text
        )

        if not home_team and not away_team:

            _log(
                f"[경기정보 없음] ID={schedule_id}"
            )

            return None

        return {

            "schedule_id":
                str(schedule_id),

            "match_date":
                match_date,

            "home_team":
                home_team,

            "away_team":
                away_team,

            "home_score":
                home_score,

            "away_score":
                away_score,

            "result":
                result,

            "source":
                "Scoreman",

        }

    except Exception as e:

        _log(
            f"[경기 오류] ID={schedule_id} "
            f"{type(e).__name__}: {e}"
        )

        return None


# ============================================================
# 최종배당
# ============================================================

def fetch_odds(
    schedule_id
):

    url = ODDS_URL.format(
        schedule_id=schedule_id
    )

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        _log(
            f"[배당 API] ID={schedule_id} "
            f"HTTP={response.status_code} "
            f"SIZE={len(response.text or ''):,}"
        )

        if response.status_code != 200:

            _log(
                f"[배당 API 실패] "
                f"ID={schedule_id}"
            )

            return []

        text = response.text

        payload = None

        try:

            payload = response.json()

        except Exception:

            objects = _find_json_objects(
                text
            )

            if objects:

                payload = objects[0]

        if payload is None:

            _log(
                f"[배당 JSON 없음] "
                f"ID={schedule_id}"
            )

            return []

        mixodds = None

        if isinstance(payload, dict):

            data = payload.get(
                "Data"
            )

            if isinstance(data, dict):

                mixodds = data.get(
                    "mixodds"
                )

            if mixodds is None:

                mixodds = payload.get(
                    "mixodds"
                )

        if not isinstance(
            mixodds,
            list
        ):

            _log(
                f"[mixodds 없음] "
                f"ID={schedule_id}"
            )

            return []

        result = []

        for item in mixodds:

            if not isinstance(
                item,
                dict
            ):

                continue

            company_id = (
                item.get("cid")
                or item.get("company_id")
                or ""
            )

            company_name = (
                item.get("cn")
                or item.get("company_name")
                or item.get("name")
                or ""
            )

            euro = item.get(
                "euro"
            )

            if not isinstance(
                euro,
                dict
            ):

                continue

            final_data = euro.get(
                "l"
            )

            if not isinstance(
                final_data,
                dict
            ):

                continue

            home = to_float(
                final_data.get("u")
            )

            draw = to_float(
                final_data.get("g")
            )

            away = to_float(
                final_data.get("d")
            )

            if (
                home is None
                or draw is None
                or away is None
            ):

                continue

            if (
                home <= 0
                or draw <= 0
                or away <= 0
            ):

                continue

            if not company_name:

                company_name = (
                    f"업체_{company_id}"
                )

            result.append({

                "company_id":
                    str(company_id),

                "company_name":
                    str(company_name).strip(),

                "final_home":
                    home,

                "final_draw":
                    draw,

                "final_away":
                    away,

            })

        _log(
            f"[배당 추출] ID={schedule_id} "
            f"업체={len(result)}"
        )

        return result

    except Exception as e:

        _log(
            f"[배당 오류] ID={schedule_id} "
            f"{type(e).__name__}: {e}"
        )

        return []


# ============================================================
# 한 경기
# ============================================================

def collect_one(
    schedule_id,
    selected_companies=None
):

    match = fetch_match(
        schedule_id
    )

    if not match:

        return {
            "status": "failed",
            "odds": 0,
            "error": "경기 페이지 수집 실패",
        }

    odds = fetch_odds(
        schedule_id
    )

    if not odds:

        return {
            "status": "no_odds",
            "odds": 0,
            "error": "최종배당 없음",
        }

    # --------------------------------------------------------
    # 업체 필터
    # --------------------------------------------------------

    if selected_companies:

        wanted = {
            str(x).strip().lower()
            for x in selected_companies
        }

        filtered = []

        for item in odds:

            name = str(
                item.get(
                    "company_name",
                    ""
                )
            ).strip().lower()

            if name in wanted:

                filtered.append(
                    item
                )

        odds = filtered

    if not odds:

        return {
            "status": "no_odds",
            "odds": 0,
            "error": "선택 업체의 최종배당 없음",
        }

    # --------------------------------------------------------
    # 경기 저장
    # --------------------------------------------------------

    try:

        database.save_match(

            schedule_id=
                match["schedule_id"],

            match_date=
                match["match_date"],

            home_team=
                match["home_team"],

            away_team=
                match["away_team"],

            home_score=
                match["home_score"],

            away_score=
                match["away_score"],

            result=
                match["result"],

            source=
                match["source"],

        )

    except Exception as e:

        error_text = (
            f"경기 저장 실패: "
            f"{type(e).__name__}: {e}"
        )

        _log(
            f"[{error_text}] ID={schedule_id}"
        )

        return {
            "status": "failed",
            "odds": 0,
            "error": error_text,
        }

    # --------------------------------------------------------
    # 배당 저장
    # --------------------------------------------------------

    saved_odds = 0
    failed_odds = 0

    for item in odds:

        company_name = str(
            item.get(
                "company_name",
                ""
            )
        ).strip()

        try:

            database.save_odds(

                schedule_id=
                    match["schedule_id"],

                company_id=
                    item.get(
                        "company_id",
                        ""
                    ),

                company_name=
                    company_name,

                final_home=
                    item.get(
                        "final_home"
                    ),

                final_draw=
                    item.get(
                        "final_draw"
                    ),

                final_away=
                    item.get(
                        "final_away"
                    ),

            )

            saved_odds += 1

            _log(
                f"[배당 저장 성공] "
                f"ID={schedule_id} "
                f"업체={company_name}"
            )

        except Exception as e:

            failed_odds += 1

            _log(
                f"[배당 저장 실패] "
                f"ID={schedule_id} "
                f"업체={company_name} "
                f"CID={item.get('company_id', '')} "
                f"승={item.get('final_home')} "
                f"무={item.get('final_draw')} "
                f"패={item.get('final_away')} "
                f"오류={type(e).__name__}: {e}"
            )

    # --------------------------------------------------------
    # 하나라도 저장되면 성공
    # --------------------------------------------------------

    if saved_odds > 0:

        if failed_odds > 0:

            _log(
                f"[부분 저장] ID={schedule_id} "
                f"성공={saved_odds} "
                f"실패={failed_odds}"
            )

        return {
            "status": "success",
            "odds": saved_odds,
            "failed_odds": failed_odds,
        }

    # --------------------------------------------------------
    # 하나도 저장되지 않은 경우
    # --------------------------------------------------------

    return {
        "status": "failed",
        "odds": 0,
        "failed_odds": failed_odds,
        "error": "최종배당 저장 실패",
    }


# ============================================================
# 백그라운드
# ============================================================

def _worker(
    start_id,
    end_id,
    selected_companies,
    delay,
    resume
):

    global JOB

    total = (
        int(end_id)
        - int(start_id)
        + 1
    )

    with JOB_LOCK:

        JOB["running"] = True
        JOB["finished"] = False

        JOB["current"] = 0
        JOB["total"] = max(
            total,
            0
        )

        JOB["success"] = 0
        JOB["exists"] = 0
        JOB["failed"] = 0
        JOB["no_odds"] = 0
        JOB["odds"] = 0

        JOB["start_id"] = int(start_id)
        JOB["end_id"] = int(end_id)

        JOB["last_completed_id"] = 0

        JOB["selected_companies"] = (
            selected_companies
        )

        JOB["error"] = ""
        JOB["stopped"] = False
        JOB["result"] = {}
        JOB["log"] = ""

    STOP_EVENT.clear()

    try:

        database.save_collection_state(
            start_id,
            end_id,
            start_id,
            0,
            True,
            False
        )

    except Exception as e:

        _log(
            f"[상태 저장 오류] {e}"
        )

    _log(
        "========================================"
    )

    _log(
        "⚽ Scoreman 백그라운드 수집 시작"
    )

    _log(
        f"범위: {start_id:,} ~ {end_id:,}"
    )

    _log(
        "실패 경기 / 배당 없음은 "
        "완료 ID로 저장하지 않음"
    )

    _log(
        "실패는 1회 자동 재시도"
    )

    _log(
        f"요청 간격: {float(delay):.2f}초"
    )

    if selected_companies:

        _log(
            "수집 업체: "
            + ", ".join(
                selected_companies
            )
        )

    else:

        _log(
            "수집 업체: 전체 업체 자동수집"
        )

    _log(
        "========================================"
    )

    last_completed = 0

    try:

        for index, schedule_id in enumerate(
            range(
                int(start_id),
                int(end_id) + 1
            ),
            start=1
        ):

            if STOP_EVENT.is_set():

                _log(
                    "🛑 중지 요청 감지"
                )

                break

            with JOB_LOCK:

                JOB["current"] = index

            try:

                database.save_collection_state(
                    start_id,
                    end_id,
                    schedule_id,
                    last_completed,
                    True,
                    False
                )

            except Exception:
                pass

            _log(
                f"[수집 시작] ID={schedule_id}"
            )

            # ------------------------------------------------
            # 기존 경기 확인
            # ------------------------------------------------

            already_exists = False

            try:

                if database.match_exists(
                    schedule_id
                ):

                    old_odds = (
                        database.get_odds_by_match(
                            schedule_id
                        )
                    )

                    if old_odds:

                        already_exists = True

            except Exception as e:

                _log(
                    f"[중복 확인 오류] "
                    f"ID={schedule_id} "
                    f"{e}"
                )

            if already_exists:

                with JOB_LOCK:

                    JOB["exists"] += 1

                last_completed = schedule_id

                with JOB_LOCK:

                    JOB[
                        "last_completed_id"
                    ] = last_completed

                try:

                    database.save_collection_state(
                        start_id,
                        end_id,
                        schedule_id,
                        last_completed,
                        True,
                        False
                    )

                except Exception:
                    pass

                _log(
                    f"[중복] ID={schedule_id}"
                )

                if delay > 0:

                    time.sleep(
                        float(delay)
                    )

                continue

            # ------------------------------------------------
            # 1차
            # ------------------------------------------------

            result = collect_one(
                schedule_id,
                selected_companies
            )

            # ------------------------------------------------
            # 실패 재시도
            # ------------------------------------------------

            if result.get(
                "status"
            ) == "failed":

                _log(
                    f"[재시도] ID={schedule_id} "
                    f"오류={result.get('error', '')}"
                )

                time.sleep(
                    max(
                        0.5,
                        float(delay)
                    )
                )

                result = collect_one(
                    schedule_id,
                    selected_companies
                )

            status = result.get(
                "status"
            )

            odds_count = int(
                result.get(
                    "odds",
                    0
                )
                or 0
            )

            if status == "success":

                with JOB_LOCK:

                    JOB["success"] += 1
                    JOB["odds"] += odds_count

                last_completed = schedule_id

                with JOB_LOCK:

                    JOB[
                        "last_completed_id"
                    ] = last_completed

                try:

                    database.save_collection_state(
                        start_id,
                        end_id,
                        schedule_id,
                        last_completed,
                        True,
                        False
                    )

                except Exception:
                    pass

                _log(
                    f"[완료] ID={schedule_id} "
                    f"배당={odds_count}"
                )

            elif status == "no_odds":

                with JOB_LOCK:

                    JOB["no_odds"] += 1

                _log(
                    f"[배당 없음] ID={schedule_id}"
                )

            else:

                with JOB_LOCK:

                    JOB["failed"] += 1

                _log(
                    f"[실패] ID={schedule_id} "
                    f"오류={result.get('error', '')}"
                )

            if delay > 0:

                time.sleep(
                    float(delay)
                )

    except Exception as e:

        with JOB_LOCK:

            JOB["error"] = str(e)
            JOB["failed"] += 1

        _log(
            f"[치명적 오류] "
            f"{type(e).__name__}: {e}"
        )

    finally:

        stopped = STOP_EVENT.is_set()

        with JOB_LOCK:

            JOB["running"] = False
            JOB["finished"] = True
            JOB["stopped"] = stopped

            JOB[
                "last_completed_id"
            ] = last_completed

            JOB["result"] = {

                "success":
                    JOB["success"],

                "exists":
                    JOB["exists"],

                "failed":
                    JOB["failed"],

                "no_odds":
                    JOB["no_odds"],

                "odds":
                    JOB["odds"],

                "stopped":
                    stopped,

            }

        try:

            database.save_collection_state(
                start_id,
                end_id,
                (
                    last_completed
                    if last_completed > 0
                    else start_id
                ),
                last_completed,
                False,
                stopped
            )

        except Exception as e:

            _log(
                f"[종료 상태 저장 오류] {e}"
            )

        _log(
            "========================================"
        )

        if stopped:

            _log(
                "🛑 수집 작업 중지"
            )

        else:

            _log(
                "✅ 수집 작업 종료"
            )

        _log(
            f"신규={JOB['success']} "
            f"기존={JOB['exists']} "
            f"실패={JOB['failed']} "
            f"배당없음={JOB['no_odds']} "
            f"최종배당={JOB['odds']}"
        )

        _log(
            "========================================"
        )


# ============================================================
# 시작
# ============================================================

def start_background_collection(
    start_id,
    end_id,
    selected_companies=None,
    delay=0.5,
    resume=True
):

    global WORKER

    with JOB_LOCK:

        if JOB.get("running"):

            return False

    if int(end_id) < int(start_id):

        return False

    STOP_EVENT.clear()

    WORKER = threading.Thread(

        target=_worker,

        args=(
            int(start_id),
            int(end_id),
            selected_companies,
            float(delay),
            bool(resume),
        ),

        daemon=True
    )

    WORKER.start()

    return True


# ============================================================
# 중지
# ============================================================

def stop_background_collection():

    with JOB_LOCK:

        if not JOB.get("running"):

            return False

    STOP_EVENT.set()

    _log(
        "🛑 수집중지 요청"
    )

    return True


# ============================================================
# 실행 여부
# ============================================================

def is_running():

    with JOB_LOCK:

        return bool(
            JOB.get("running")
        )


# ============================================================
# 상태
# ============================================================

def get_job_status():

    with JOB_LOCK:

        return dict(
            JOB
        )


# ============================================================
# 단일 테스트
# ============================================================

if __name__ == "__main__":

    database.init_database()

    print(
        collect_one(
            2716488
        )
                )
