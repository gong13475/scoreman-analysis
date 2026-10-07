# ============================================================
# collector.py
# ⚽ Scoreman 전종목 해외배당 자동수집기
# ============================================================

import json
import threading
import time
import re
from datetime import datetime

import requests

import database


BASE_URL = "https://www.scoreman123.com"

MATCH_URL = (
    BASE_URL +
    "/match/data-{schedule_id}"
)

ODDS_URL = (
    BASE_URL +
    "/ajax/soccerajax"
)

HEADERS = {
    "User-Agent":
        "Mozilla/5.0 (Linux; Android 10) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/130.0 Mobile Safari/537.36",

    "Referer":
        BASE_URL + "/",

    "Accept":
        "application/json,text/plain,*/*"
}


_JOB_LOCK = threading.RLock()

JOB = {
    "running": False,
    "finished": False,
    "stopped": False,
    "start_id": 0,
    "end_id": 0,
    "current": 0,
    "total": 0,
    "success": 0,
    "exists": 0,
    "failed": 0,
    "no_odds": 0,
    "odds": 0,
    "last_completed_id": 0,
    "selected_companies": None,
    "log": "",
    "result": None,
    "error": ""
}


_STOP_EVENT = threading.Event()
_WORKER = None


def _log(message):

    timestamp = datetime.now().strftime(
        "%H:%M:%S"
    )

    line = (
        f"[{timestamp}] {message}"
    )

    with _JOB_LOCK:

        JOB["log"] = (
            JOB.get("log", "")
            + line
            + "\n"
        )

        if len(JOB["log"]) > 30000:

            JOB["log"] = JOB["log"][-30000:]


def _request(
    url,
    params=None,
    timeout=15
):

    return requests.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=timeout
    )


def _to_float(value):

    try:

        if value is None:
            return None

        value = str(value).replace(
            ",",
            ""
        ).strip()

        number = float(value)

        if number <= 0:
            return None

        return number

    except Exception:

        return None


def _safe_int(value):

    try:

        found = re.search(
            r"-?\d+",
            str(value)
        )

        if not found:
            return None

        return int(
            found.group(0)
        )

    except Exception:

        return None


def _get_match_data(
    schedule_id
):

    response = _request(
        MATCH_URL.format(
            schedule_id=schedule_id
        ),
        timeout=15
    )

    if response.status_code != 200:

        raise RuntimeError(
            f"HTTP={response.status_code}"
        )

    if not response.text:

        raise RuntimeError(
            "빈 경기 페이지"
        )

    return response.text


def _parse_match_html(
    html,
    schedule_id
):

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    text = soup.get_text(
        " ",
        strip=True
    )

    scripts = soup.find_all(
        "script"
    )

    script_text = "\n".join(
        s.get_text(
            " ",
            strip=False
        )
        for s in scripts
    )

    combined = (
        text
        + "\n"
        + script_text
    )

    home_team = ""
    away_team = ""

    match_date = ""

    home_score = None
    away_score = None

    date_patterns = [

        r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}\s+\d{1,2}:\d{2}",

        r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}"

    ]

    for pattern in date_patterns:

        found = re.search(
            pattern,
            combined
        )

        if found:

            match_date = found.group(0)

            break

    home_patterns = [
        r'"home_team"\s*:\s*"([^"]+)"',
        r'"hometeam"\s*:\s*"([^"]+)"',
        r'"homeName"\s*:\s*"([^"]+)"'
    ]

    away_patterns = [
        r'"away_team"\s*:\s*"([^"]+)"',
        r'"awayteam"\s*:\s*"([^"]+)"',
        r'"awayName"\s*:\s*"([^"]+)"'
    ]

    for pattern in home_patterns:

        found = re.search(
            pattern,
            combined,
            re.I
        )

        if found:

            home_team = found.group(1).strip()

            break

    for pattern in away_patterns:

        found = re.search(
            pattern,
            combined,
            re.I
        )

        if found:

            away_team = found.group(1).strip()

            break

    home_score_patterns = [
        r'"home_score"\s*:\s*"?(.*?)"?[,}]',
        r'"homescore"\s*:\s*"?(.*?)"?[,}]',
        r'"hscore"\s*:\s*"?(.*?)"?[,}]'
    ]

    away_score_patterns = [
        r'"away_score"\s*:\s*"?(.*?)"?[,}]',
        r'"awayscore"\s*:\s*"?(.*?)"?[,}]',
        r'"ascore"\s*:\s*"?(.*?)"?[,}]'
    ]

    for pattern in home_score_patterns:

        found = re.search(
            pattern,
            combined,
            re.I
        )

        if found:

            home_score = _safe_int(
                found.group(1)
            )

            if home_score is not None:
                break

    for pattern in away_score_patterns:

        found = re.search(
            pattern,
            combined,
            re.I
        )

        if found:

            away_score = _safe_int(
                found.group(1)
            )

            if away_score is not None:
                break

    result = ""

    if (
        home_score is not None
        and away_score is not None
    ):

        if home_score > away_score:

            result = "승"

        elif home_score < away_score:

            result = "패"

        else:

            result = "무"

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
            "scoreman"
    }


def _extract_json(response):

    try:

        return response.json()

    except Exception:

        try:

            return json.loads(
                response.text
            )

        except Exception:

            return None


def _find_mixodds(obj):

    if isinstance(obj, dict):

        if "mixodds" in obj:

            return obj["mixodds"]

        for value in obj.values():

            found = _find_mixodds(
                value
            )

            if found is not None:

                return found

    elif isinstance(obj, list):

        for item in obj:

            found = _find_mixodds(
                item
            )

            if found is not None:

                return found

    return None


def _parse_final_odds(data):

    mixodds = _find_mixodds(
        data
    )

    if not mixodds:
        return []

    if isinstance(
        mixodds,
        dict
    ):

        mixodds = [mixodds]

    results = []

    for company in mixodds:

        if not isinstance(
            company,
            dict
        ):
            continue

        company_id = (
            company.get("cid")
            or company.get("id")
            or ""
        )

        company_name = (
            company.get("cn")
            or company.get("name")
            or company.get("company_name")
            or ""
        )

        euro = (
            company.get("euro")
            or {}
        )

        final = (
            euro.get("l")
            or {}
        )

        home = _to_float(
            final.get("u")
        )

        draw = _to_float(
            final.get("g")
        )

        away = _to_float(
            final.get("d")
        )

        if (
            home is None
            or draw is None
            or away is None
        ):
            continue

        if not str(company_name).strip():
            continue

        results.append({
            "company_id":
                str(company_id),

            "company_name":
                str(company_name).strip(),

            "final_home":
                round(home, 2),

            "final_draw":
                round(draw, 2),

            "final_away":
                round(away, 2)
        })

    return results


def _get_final_odds(
    schedule_id
):

    response = _request(
        ODDS_URL,
        params={
            "type": 14,
            "t": 1,
            "id": schedule_id,
            "h": 0
        },
        timeout=15
    )

    if response.status_code != 200:

        raise RuntimeError(
            f"배당 HTTP={response.status_code}"
        )

    data = _extract_json(
        response
    )

    if data is None:

        raise RuntimeError(
            "배당 JSON 파싱 실패"
        )

    return _parse_final_odds(
        data
    )


def _filter_companies(
    odds_list,
    selected_companies
):

    if not selected_companies:

        return odds_list

    selected = {
        str(x).strip().lower()
        for x in selected_companies
        if str(x).strip()
    }

    return [
        row
        for row in odds_list
        if str(
            row.get(
                "company_name",
                ""
            )
        ).strip().lower()
        in selected
    ]


def collect_one(
    schedule_id,
    selected_companies=None
):

    schedule_id = int(
        schedule_id
    )

    _log(
        f"[수집 시작] ID={schedule_id}"
    )

    html = _get_match_data(
        schedule_id
    )

    _log(
        f"[페이지] ID={schedule_id} "
        f"HTTP=200 SIZE={len(html):,}"
    )

    match = _parse_match_html(
        html,
        schedule_id
    )

    odds_list = _get_final_odds(
        schedule_id
    )

    if not odds_list:

        _log(
            f"[배당 없음] ID={schedule_id}"
        )

        return {
            "status": "no_odds",
            "match": match,
            "odds": []
        }

    filtered = _filter_companies(
        odds_list,
        selected_companies
    )

    if not filtered:

        _log(
            f"[선택 업체 배당 없음] "
            f"ID={schedule_id}"
        )

        return {
            "status": "no_odds",
            "match": match,
            "odds": []
        }

    existed = (
        database.get_match(
            schedule_id
        )
        is not None
    )

    saved = database.save_match_with_odds(
        match,
        filtered
    )

    if existed:

        _log(
            f"[기존 갱신] ID={schedule_id} "
            f"배당={saved}"
        )

        status = "exists"

    else:

        _log(
            f"[신규 저장] ID={schedule_id} "
            f"배당={saved}"
        )

        status = "success"

    return {
        "status": status,
        "match": match,
        "odds": filtered,
        "saved_odds": saved
    }


def _worker(
    start_id,
    end_id,
    selected_companies,
    delay
):

    total = (
        end_id - start_id + 1
    )

    result = {
        "start_id": start_id,
        "end_id": end_id,
        "total": total,
        "success": 0,
        "exists": 0,
        "failed": 0,
        "no_odds": 0,
        "odds": 0,
        "last_completed_id": 0,
        "stopped": False
    }

    try:

        for index, schedule_id in enumerate(
            range(
                start_id,
                end_id + 1
            ),
            start=1
        ):

            if _STOP_EVENT.is_set():

                result["stopped"] = True

                _log(
                    "🛑 수집 중지 확인"
                )

                break

            with _JOB_LOCK:

                JOB["current"] = index

            success_this = False

            for attempt in range(2):

                try:

                    data = collect_one(
                        schedule_id,
                        selected_companies
                    )

                    status = data.get(
                        "status"
                    )

                    if status == "success":

                        result["success"] += 1
                        result["odds"] += int(
                            data.get(
                                "saved_odds",
                                0
                            ) or 0
                        )

                        success_this = True
                        break

                    if status == "exists":

                        result["exists"] += 1
                        result["odds"] += int(
                            data.get(
                                "saved_odds",
                                0
                            ) or 0
                        )

                        success_this = True
                        break

                    if status == "no_odds":

                        result["no_odds"] += 1
                        break

                except Exception as e:

                    if attempt == 0:

                        _log(
                            f"[재시도] ID={schedule_id} "
                            f"오류={e}"
                        )

                        time.sleep(0.5)

                    else:

                        result["failed"] += 1

                        _log(
                            f"[실패] ID={schedule_id} "
                            f"오류={e}"
                        )

            if success_this:

                result[
                    "last_completed_id"
                ] = schedule_id

                with _JOB_LOCK:

                    JOB[
                        "last_completed_id"
                    ] = schedule_id

            database.save_collection_state(
                start_id,
                end_id,
                result["last_completed_id"],
                index,
                total,
                True,
                False,
                selected_companies
            )

            with _JOB_LOCK:

                JOB["success"] = result["success"]
                JOB["exists"] = result["exists"]
                JOB["failed"] = result["failed"]
                JOB["no_odds"] = result["no_odds"]
                JOB["odds"] = result["odds"]

            if (
                delay > 0
                and not _STOP_EVENT.is_set()
            ):

                time.sleep(delay)

        result["stopped"] = (
            result["stopped"]
            or _STOP_EVENT.is_set()
        )

    except Exception as e:

        result["error"] = str(e)

        with _JOB_LOCK:

            JOB["error"] = str(e)

        _log(
            f"[치명적 오류] {e}"
        )

    finally:

        with _JOB_LOCK:

            JOB["running"] = False
            JOB["finished"] = True
            JOB["stopped"] = result["stopped"]
            JOB["result"] = result

        database.save_collection_state(
            start_id,
            end_id,
            result["last_completed_id"],
            JOB.get("current", 0),
            total,
            False,
            result["stopped"],
            selected_companies
        )

        _STOP_EVENT.clear()

        _log(
            "========================================"
        )

        _log(
            "수집 작업 종료"
        )

        _log(
            f"신규={result['success']} "
            f"기존={result['exists']} "
            f"실패={result['failed']} "
            f"배당없음={result['no_odds']} "
            f"최종배당={result['odds']}"
        )


def start_background_collection(
    start_id,
    end_id,
    selected_companies=None,
    delay=0.5,
    resume=True
):

    global _WORKER

    try:

        start_id = int(start_id)
        end_id = int(end_id)

    except Exception:

        return False

    if end_id < start_id:
        return False

    with _JOB_LOCK:

        if JOB.get("running"):
            return False

        if resume:

            state = (
                database.get_collection_state()
                or {}
            )

            last_id = int(
                state.get(
                    "last_completed_id",
                    0
                )
                or 0
            )

            # 현재 요청 범위와 무관하게
            # 이미 끝난 ID면 다음 ID부터 시작
            if (
                last_id >= start_id
                and last_id < end_id
            ):

                start_id = last_id + 1

            # 마지막 ID까지 완료된 경우
            elif last_id >= end_id:

                return False

        JOB.clear()

        JOB.update({
            "running": True,
            "finished": False,
            "stopped": False,
            "start_id": start_id,
            "end_id": end_id,
            "current": 0,
            "total": end_id - start_id + 1,
            "success": 0,
            "exists": 0,
            "failed": 0,
            "no_odds": 0,
            "odds": 0,
            "last_completed_id": 0,
            "selected_companies":
                selected_companies,
            "log": "",
            "result": None,
            "error": ""
        })

        _STOP_EVENT.clear()

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
            "실패 / 배당없음은 완료 ID로 "
            "기록하지 않음"
        )

        _log(
            "실패는 1회 자동 재시도"
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
                "수집 업체: 전체 업체"
            )

        _log(
            f"요청 간격: {float(delay):.2f}초"
        )

        database.save_collection_state(
            start_id,
            end_id,
            0,
            0,
            end_id - start_id + 1,
            True,
            False,
            selected_companies
        )

        _WORKER = threading.Thread(
            target=_worker,
            args=(
                start_id,
                end_id,
                selected_companies,
                float(delay)
            ),
            daemon=True
        )

        _WORKER.start()

        return True


def stop_background_collection():

    with _JOB_LOCK:

        if not JOB.get("running"):
            return False

        JOB["stopped"] = True

        _STOP_EVENT.set()

    _log(
        "🛑 사용자에 의해 수집 중지 요청"
    )

    return True


def get_job_status():

    with _JOB_LOCK:

        return dict(JOB)


def is_running():

    with _JOB_LOCK:

        return bool(
            JOB.get("running")
        )


def clear_finished_job():

    with _JOB_LOCK:

        if JOB.get("running"):
            return False

        JOB["finished"] = False
        JOB["result"] = None
        JOB["error"] = ""
        JOB["log"] = ""

        return True
