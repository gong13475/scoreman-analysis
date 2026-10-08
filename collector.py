# ============================================================
# collector.py
# ⚽ Scoreman 전종목 해외배당 자동수집기
#
# 기존 기능 유지 + 안정화 확장
#
# 기능
# - Scoreman 경기 ID 수집
# - 경기 결과 수집
# - 전체 해외업체 최종배당 수집
# - 업체 수동 선택
# - 백그라운드 수집
# - 수집 시작 / 중지
# - 진행률
# - 신규 / 기존 / 실패 / 배당없음
# - 마지막 성공 ID 저장
# - 중지 후 이어받기
# - Turso / SQLite database.py 연동
# - 실패 자동 재시도
# - DB 저장 재시도
# - Streamlit 화면을 닫아도 서버에서 실행
# ============================================================

import json
import re
import threading
import time
from datetime import datetime

import requests

import database


# ============================================================
# 기본 설정
# ============================================================

BASE_URL = "https://www.scoreman123.com"

MATCH_URL = (
    BASE_URL + "/match/data-{schedule_id}"
)

ODDS_URL = (
    BASE_URL + "/ajax/soccerajax"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/130.0 Mobile Safari/537.36"
    ),
    "Referer": BASE_URL + "/",
    "Accept": "application/json,text/plain,*/*",
}

REQUEST_TIMEOUT = 15

# 기존: 실패 1회 자동 재시도
# 총 2회 시도
MAX_RETRY = 2

# DB 저장 재시도
DB_RETRY = 4


# ============================================================
# 작업 상태
# ============================================================

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

    "error": "",
}


_STOP_EVENT = threading.Event()

_WORKER = None


# ============================================================
# 로그
# ============================================================

def _log(message):

    timestamp = datetime.now().strftime(
        "%H:%M:%S"
    )

    line = f"[{timestamp}] {message}"

    with _JOB_LOCK:

        old = JOB.get(
            "log",
            ""
        )

        JOB["log"] = (
            old
            + line
            + "\n"
        )

        if len(JOB["log"]) > 30000:

            JOB["log"] = JOB["log"][-30000:]


# ============================================================
# HTTP 요청
# ============================================================

def _request(
    url,
    params=None,
    timeout=REQUEST_TIMEOUT,
):

    return requests.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=timeout,
    )


# ============================================================
# 숫자 변환
# ============================================================

def _to_float(value):

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

        number = float(
            value
        )

        if number <= 0:
            return None

        return number

    except Exception:

        return None


# ============================================================
# 정수 변환
# ============================================================

def _safe_int(value):

    try:

        if value is None:
            return None

        found = re.search(
            r"-?\d+",
            str(value),
        )

        if not found:
            return None

        return int(
            found.group(0)
        )

    except Exception:

        return None


# ============================================================
# 경기 페이지
# ============================================================

def _get_match_data(schedule_id):

    url = MATCH_URL.format(
        schedule_id=schedule_id
    )

    response = _request(
        url,
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code != 200:

        raise RuntimeError(
            f"HTTP={response.status_code}"
        )

    html = response.text

    if not html:

        raise RuntimeError(
            "빈 경기 페이지"
        )

    return html


# ============================================================
# JSON 추출
# ============================================================

def _extract_json(response):

    try:

        return response.json()

    except Exception:

        text = response.text.strip()

        if not text:
            return None

        try:

            return json.loads(
                text
            )

        except Exception:

            return None


# ============================================================
# 경기 HTML 파싱
# ============================================================

def _parse_match_html(
    html,
    schedule_id,
):

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    text = soup.get_text(
        " ",
        strip=True,
    )

    scripts = soup.find_all(
        "script"
    )

    script_text = "\n".join(
        s.get_text(
            " ",
            strip=False,
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

    # ========================================================
    # 날짜
    # ========================================================

    date_patterns = [

        r"(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}\s+\d{1,2}:\d{2})",

        r"(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})",

    ]

    for pattern in date_patterns:

        found = re.search(
            pattern,
            combined,
            re.I,
        )

        if found:

            match_date = found.group(1)

            break

    # ========================================================
    # 홈 스코어
    # ========================================================

    home_score_patterns = [

        r'"home_score"\s*:\s*"?(.*?)"?[,}]',

        r'"homescore"\s*:\s*"?(.*?)"?[,}]',

        r'"hscore"\s*:\s*"?(.*?)"?[,}]',

        r'"homeScore"\s*:\s*"?(.*?)"?[,}]',

    ]

    for pattern in home_score_patterns:

        found = re.search(
            pattern,
            combined,
            re.I,
        )

        if found:

            value = _safe_int(
                found.group(1)
            )

            if value is not None:

                home_score = value

                break

    # ========================================================
    # 원정 스코어
    # ========================================================

    away_score_patterns = [

        r'"away_score"\s*:\s*"?(.*?)"?[,}]',

        r'"awayscore"\s*:\s*"?(.*?)"?[,}]',

        r'"ascore"\s*:\s*"?(.*?)"?[,}]',

        r'"awayScore"\s*:\s*"?(.*?)"?[,}]',

    ]

    for pattern in away_score_patterns:

        found = re.search(
            pattern,
            combined,
            re.I,
        )

        if found:

            value = _safe_int(
                found.group(1)
            )

            if value is not None:

                away_score = value

                break

    # ========================================================
    # 홈팀
    # ========================================================

    home_patterns = [

        r'"home_team"\s*:\s*"([^"]+)"',

        r'"hometeam"\s*:\s*"([^"]+)"',

        r'"homeName"\s*:\s*"([^"]+)"',

        r'"home_name"\s*:\s*"([^"]+)"',

    ]

    for pattern in home_patterns:

        found = re.search(
            pattern,
            combined,
            re.I,
        )

        if found:

            home_team = (
                found.group(1)
                .strip()
            )

            break

    # ========================================================
    # 원정팀
    # ========================================================

    away_patterns = [

        r'"away_team"\s*:\s*"([^"]+)"',

        r'"awayteam"\s*:\s*"([^"]+)"',

        r'"awayName"\s*:\s*"([^"]+)"',

        r'"away_name"\s*:\s*"([^"]+)"',

    ]

    for pattern in away_patterns:

        found = re.search(
            pattern,
            combined,
            re.I,
        )

        if found:

            away_team = (
                found.group(1)
                .strip()
            )

            break

    # ========================================================
    # 결과
    # ========================================================

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
            "scoreman",

    }


# ============================================================
# mixodds 탐색
# ============================================================

def _find_mixodds(obj):

    if isinstance(
        obj,
        dict
    ):

        if "mixodds" in obj:

            return obj["mixodds"]

        if "Data" in obj:

            found = _find_mixodds(
                obj["Data"]
            )

            if found is not None:

                return found

        for value in obj.values():

            found = _find_mixodds(
                value
            )

            if found is not None:

                return found

    elif isinstance(
        obj,
        list
    ):

        for item in obj:

            found = _find_mixodds(
                item
            )

            if found is not None:

                return found

    return None


# ============================================================
# 최종배당 파싱
# ============================================================

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

        mixodds = [
            mixodds
        ]

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

        # 최종배당
        final = (
            euro.get("l")
            or {}
        )

        if not final:

            continue

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

        name = str(
            company_name
        ).strip()

        if not name:

            continue

        results.append({

            "company_id":
                str(company_id),

            "company_name":
                name,

            "final_home":
                home,

            "final_draw":
                draw,

            "final_away":
                away,

        })

    return results


# ============================================================
# 최종배당 요청
# ============================================================

def _get_final_odds(schedule_id):

    params = {

        "type": 14,

        "t": 1,

        "id": schedule_id,

        "h": 0,

    }

    response = _request(
        ODDS_URL,
        params=params,
        timeout=REQUEST_TIMEOUT,
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


# ============================================================
# 업체 필터
# ============================================================

def _filter_companies(
    odds_list,
    selected_companies,
):

    if not selected_companies:

        return odds_list

    selected = {

        str(x)
        .strip()
        .lower()

        for x in selected_companies

        if str(x).strip()

    }

    result = []

    for row in odds_list:

        name = str(
            row.get(
                "company_name",
                "",
            )
        ).strip().lower()

        if name in selected:

            result.append(
                row
            )

    return result


# ============================================================
# DB 저장
# ============================================================

def _save_match_odds(
    match,
    odds_list,
):

    last_error = None

    for attempt in range(
        DB_RETRY
    ):

        try:

            saved = (
                database.save_match_with_odds(
                    match,
                    odds_list,
                )
            )

            if saved > 0:

                return saved

            last_error = (
                "최종배당 저장 결과 0건"
            )

        except Exception as e:

            last_error = e

            if attempt < DB_RETRY - 1:

                _log(
                    "[DB 재시도] "
                    f"{attempt + 1}/{DB_RETRY} "
                    f"오류={e}"
                )

                time.sleep(
                    0.7
                    * (attempt + 1)
                )

    raise RuntimeError(
        f"최종배당 저장 실패: {last_error}"
    )


# ============================================================
# 수집 상태 저장
#
# Turso 오류가 발생해도 수집 자체가 죽지 않도록 한다.
# ============================================================

def _save_state(
    start_id,
    end_id,
    last_completed_id,
    current,
    total,
    running,
    stopped,
    selected_companies,
):

    for attempt in range(
        DB_RETRY
    ):

        try:

            database.save_collection_state(

                start_id,

                end_id,

                last_completed_id,

                current,

                total,

                running,

                stopped,

                selected_companies,

            )

            return True

        except Exception as e:

            if attempt < DB_RETRY - 1:

                time.sleep(
                    0.4
                    * (attempt + 1)
                )

            else:

                _log(
                    f"[상태 저장 실패] {e}"
                )

    return False


# ============================================================
# 한 경기 수집
# ============================================================

def collect_one(
    schedule_id,
    selected_companies=None,
):

    schedule_id = int(
        schedule_id
    )

    _log(
        f"[수집 시작] ID={schedule_id}"
    )

    # ========================================================
    # 경기 페이지
    # ========================================================

    html = _get_match_data(
        schedule_id
    )

    _log(
        f"[페이지] ID={schedule_id} "
        f"HTTP=200 "
        f"SIZE={len(html):,}"
    )

    # ========================================================
    # 경기 정보
    # ========================================================

    match = _parse_match_html(
        html,
        schedule_id,
    )

    if not match:

        raise RuntimeError(
            "경기 데이터 파싱 실패"
        )

    # ========================================================
    # 최종배당
    # ========================================================

    odds_list = _get_final_odds(
        schedule_id
    )

    if not odds_list:

        _log(
            f"[배당 없음] ID={schedule_id}"
        )

        return {

            "status":
                "no_odds",

            "match":
                match,

            "odds":
                [],

            "saved_odds":
                0,

        }

    # ========================================================
    # 업체 선택
    # ========================================================

    filtered = _filter_companies(
        odds_list,
        selected_companies,
    )

    if selected_companies:

        _log(
            f"[업체 필터] "
            f"{len(odds_list)} → "
            f"{len(filtered)}"
        )

    if not filtered:

        _log(
            f"[선택 업체 배당 없음] "
            f"ID={schedule_id}"
        )

        return {

            "status":
                "no_odds",

            "match":
                match,

            "odds":
                [],

            "saved_odds":
                0,

        }

    # ========================================================
    # 기존 경기 확인
    # ========================================================

    existed = (
        database.get_match(
            schedule_id
        ) is not None
    )

    # ========================================================
    # DB 저장
    # ========================================================

    saved = _save_match_odds(
        match,
        filtered,
    )

    if saved <= 0:

        raise RuntimeError(
            "최종배당 저장 실패"
        )

    if existed:

        _log(
            f"[기존 갱신] "
            f"ID={schedule_id} "
            f"배당={saved}"
        )

        status = "exists"

    else:

        _log(
            f"[신규 저장] "
            f"ID={schedule_id} "
            f"배당={saved}"
        )

        status = "success"

    return {

        "status":
            status,

        "match":
            match,

        "odds":
            filtered,

        "saved_odds":
            saved,

    }


# ============================================================
# 백그라운드 작업
# ============================================================

def _worker(
    start_id,
    end_id,
    selected_companies,
    delay,
    resume,
):

    total = (
        end_id
        - start_id
        + 1
    )

    result = {

        "start_id":
            start_id,

        "end_id":
            end_id,

        "total":
            total,

        "success":
            0,

        "exists":
            0,

        "failed":
            0,

        "no_odds":
            0,

        "odds":
            0,

        "last_completed_id":
            0,

        "stopped":
            False,

    }

    try:

        for index, schedule_id in enumerate(

            range(
                start_id,
                end_id + 1,
            ),

            start=1,

        ):

            # =================================================
            # 중지 확인
            # =================================================

            if _STOP_EVENT.is_set():

                result[
                    "stopped"
                ] = True

                _log(
                    "🛑 수집 중지 요청 확인"
                )

                break

            with _JOB_LOCK:

                JOB[
                    "current"
                ] = index

            # =================================================
            # 경기 수집
            # 실패하면 1회 재시도
            # =================================================

            completed_successfully = False

            for attempt in range(
                MAX_RETRY
            ):

                try:

                    data = collect_one(

                        schedule_id,

                        selected_companies,

                    )

                    status = data.get(
                        "status"
                    )

                    # -----------------------------------------
                    # 신규
                    # -----------------------------------------

                    if status == "success":

                        result[
                            "success"
                        ] += 1

                        result[
                            "odds"
                        ] += int(
                            data.get(
                                "saved_odds",
                                0,
                            )
                            or 0
                        )

                        completed_successfully = True

                        break

                    # -----------------------------------------
                    # 기존
                    # -----------------------------------------

                    if status == "exists":

                        result[
                            "exists"
                        ] += 1

                        result[
                            "odds"
                        ] += int(
                            data.get(
                                "saved_odds",
                                0,
                            )
                            or 0
                        )

                        completed_successfully = True

                        break

                    # -----------------------------------------
                    # 배당 없음
                    # -----------------------------------------

                    if status == "no_odds":

                        result[
                            "no_odds"
                        ] += 1

                        # 중요:
                        # 배당없음은 완료 ID로 저장하지 않음
                        break

                except Exception as e:

                    if attempt < MAX_RETRY - 1:

                        _log(
                            f"[재시도] "
                            f"ID={schedule_id} "
                            f"오류={e}"
                        )

                        time.sleep(
                            0.7
                        )

                    else:

                        result[
                            "failed"
                        ] += 1

                        _log(
                            f"[실패] "
                            f"ID={schedule_id} "
                            f"오류={e}"
                        )

            # =================================================
            # 마지막 완료 ID
            #
            # 성공 또는 기존 갱신만 완료 처리
            # 실패 / 배당없음은 완료 처리하지 않음
            # =================================================

            if completed_successfully:

                result[
                    "last_completed_id"
                ] = schedule_id

                with _JOB_LOCK:

                    JOB[
                        "last_completed_id"
                    ] = schedule_id

            # =================================================
            # 현재 JOB 수치
            # =================================================

            with _JOB_LOCK:

                JOB[
                    "success"
                ] = result[
                    "success"
                ]

                JOB[
                    "exists"
                ] = result[
                    "exists"
                ]

                JOB[
                    "failed"
                ] = result[
                    "failed"
                ]

                JOB[
                    "no_odds"
                ] = result[
                    "no_odds"
                ]

                JOB[
                    "odds"
                ] = result[
                    "odds"
                ]

            # =================================================
            # 진행상태 DB 저장
            # =================================================

            _save_state(

                start_id,

                end_id,

                result[
                    "last_completed_id"
                ],

                index,

                total,

                True,

                False,

                selected_companies,

            )

            # =================================================
            # 중지 요청이 들어왔는지 다시 확인
            # =================================================

            if _STOP_EVENT.is_set():

                result[
                    "stopped"
                ] = True

                _log(
                    "🛑 현재 경기 처리 후 "
                    "수집을 중지합니다."
                )

                break

            # =================================================
            # 요청 간격
            # =================================================

            if delay > 0:

                # 긴 sleep 대신 작은 단위로 확인
                # 중지 버튼 반응속도 향상
                remaining = float(
                    delay
                )

                while remaining > 0:

                    if _STOP_EVENT.is_set():

                        result[
                            "stopped"
                        ] = True

                        break

                    step = min(
                        0.1,
                        remaining
                    )

                    time.sleep(
                        step
                    )

                    remaining -= step

                if result[
                    "stopped"
                ]:

                    break

        result[
            "stopped"
        ] = (
            _STOP_EVENT.is_set()
            or result[
                "stopped"
            ]
        )

    except Exception as e:

        with _JOB_LOCK:

            JOB[
                "error"
            ] = str(e)

        _log(
            f"[치명적 오류] {e}"
        )

    finally:

        # =====================================================
        # 마지막 상태
        # =====================================================

        with _JOB_LOCK:

            JOB[
                "running"
            ] = False

            JOB[
                "finished"
            ] = True

            JOB[
                "stopped"
            ] = result[
                "stopped"
            ]

            JOB[
                "result"
            ] = result

            JOB[
                "success"
            ] = result[
                "success"
            ]

            JOB[
                "exists"
            ] = result[
                "exists"
            ]

            JOB[
                "failed"
            ] = result[
                "failed"
            ]

            JOB[
                "no_odds"
            ] = result[
                "no_odds"
            ]

            JOB[
                "odds"
            ] = result[
                "odds"
            ]

            JOB[
                "last_completed_id"
            ] = result[
                "last_completed_id"
            ]

        # =====================================================
        # 최종 DB 상태
        # =====================================================

        _save_state(

            start_id,

            end_id,

            result[
                "last_completed_id"
            ],

            JOB.get(
                "current",
                0
            ),

            total,

            False,

            result[
                "stopped"
            ],

            selected_companies,

        )

        # =====================================================
        # 이벤트 초기화
        # =====================================================

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


# ============================================================
# 백그라운드 수집 시작
# ============================================================

def start_background_collection(
    start_id,
    end_id,
    selected_companies=None,
    delay=0.5,
    resume=False,
):

    global _WORKER

    try:

        start_id = int(
            start_id
        )

        end_id = int(
            end_id
        )

        delay = float(
            delay
        )

    except Exception:

        return False

    if end_id < start_id:

        return False

    with _JOB_LOCK:

        # ====================================================
        # 이미 실행 중
        # ====================================================

        if JOB.get(
            "running"
        ):

            return False

        # ====================================================
        # 이어받기
        #
        # resume=True일 때만 DB의 마지막 완료 ID 사용
        # ====================================================

        if resume:

            try:

                state = (
                    database.get_collection_state()
                    or {}
                )

            except Exception:

                state = {}

            last_id = state.get(
                "last_completed_id",
                0,
            )

            try:

                last_id = int(
                    last_id or 0
                )

            except Exception:

                last_id = 0

            saved_end = state.get(
                "end_id",
                0,
            )

            try:

                saved_end = int(
                    saved_end or 0
                )

            except Exception:

                saved_end = 0

            # ------------------------------------------------
            # 기존 범위 안에서 이어받기
            # ------------------------------------------------

            if (
                last_id >= start_id
                and last_id < end_id
            ):

                start_id = (
                    last_id + 1
                )

            # ------------------------------------------------
            # 이전 작업의 범위를 이용
            # ------------------------------------------------

            elif (
                last_id > 0
                and saved_end > 0
                and last_id < saved_end
            ):

                start_id = (
                    last_id + 1
                )

                if end_id < saved_end:

                    end_id = saved_end

            # ------------------------------------------------
            # 이미 끝까지 완료
            # ------------------------------------------------

            elif (
                last_id >= end_id
            ):

                return False

        # ====================================================
        # JOB 초기화
        # ====================================================

        JOB.clear()

        JOB.update({

            "running":
                True,

            "finished":
                False,

            "stopped":
                False,

            "start_id":
                start_id,

            "end_id":
                end_id,

            "current":
                0,

            "total":
                (
                    end_id
                    - start_id
                    + 1
                ),

            "success":
                0,

            "exists":
                0,

            "failed":
                0,

            "no_odds":
                0,

            "odds":
                0,

            "last_completed_id":
                0,

            "selected_companies":
                selected_companies,

            "log":
                "",

            "result":
                None,

            "error":
                "",

        })

        _STOP_EVENT.clear()

        # ====================================================
        # 로그
        # ====================================================

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

        if selected_companies:

            _log(
                "수집 업체: "
                + ", ".join(
                    str(x)
                    for x in selected_companies
                )
            )

        else:

            _log(
                "수집 업체: 전체 업체 자동수집"
            )

        _log(
            f"요청 간격: {delay:.2f}초"
        )

        if resume:

            _log(
                "▶ 이전 중단 지점부터 "
                "이어받기 모드"
            )

        # ====================================================
        # DB 상태
        #
        # 새 작업이면 0부터
        # 이어받기라도 마지막 ID 자체는 worker가
        # 성공할 때마다 갱신한다.
        # ====================================================

        initial_last_id = 0

        if resume:

            try:

                state = (
                    database.get_collection_state()
                    or {}
                )

                initial_last_id = int(
                    state.get(
                        "last_completed_id",
                        0
                    )
                    or 0
                )

            except Exception:

                initial_last_id = 0

        _save_state(

            start_id,

            end_id,

            initial_last_id,

            0,

            end_id - start_id + 1,

            True,

            False,

            selected_companies,

        )

        # ====================================================
        # 백그라운드 스레드
        # ====================================================

        _WORKER = threading.Thread(

            target=_worker,

            args=(

                start_id,

                end_id,

                selected_companies,

                delay,

                resume,

            ),

            daemon=True,

            name="ScoremanCollector",

        )

        _WORKER.start()

        return True


# ============================================================
# 수집 중지
# ============================================================

def stop_background_collection():

    with _JOB_LOCK:

        if not JOB.get(
            "running"
        ):

            return False

        JOB[
            "stopped"
        ] = True

        _STOP_EVENT.set()

        # 현재 마지막 완료 ID 확보
        current_last_id = JOB.get(
            "last_completed_id",
            0
        )

        current_start = JOB.get(
            "start_id",
            0
        )

        current_end = JOB.get(
            "end_id",
            0
        )

        current_index = JOB.get(
            "current",
            0
        )

        total = JOB.get(
            "total",
            0
        )

        selected = JOB.get(
            "selected_companies"
        )

    # ========================================================
    # 중지 요청 즉시 상태 저장
    # ========================================================

    try:

        _save_state(

            current_start,

            current_end,

            current_last_id,

            current_index,

            total,

            True,

            True,

            selected,

        )

    except Exception:

        pass

    _log(
        "🛑 사용자에 의해 "
        "수집 중지 요청"
    )

    _log(
        f"▶ 마지막 완료 ID="
        f"{current_last_id}"
    )

    _log(
        "▶ 다시 시작하면 "
        "마지막 완료 ID 다음부터 진행"
    )

    return True


# ============================================================
# 작업 상태
# ============================================================

def get_job_status():

    with _JOB_LOCK:

        return dict(
            JOB
        )


# ============================================================
# 실행 여부
# ============================================================

def is_running():

    with _JOB_LOCK:

        return bool(
            JOB.get(
                "running"
            )
        )


# ============================================================
# 진행률
# ============================================================

def get_progress():

    with _JOB_LOCK:

        current = int(
            JOB.get(
                "current",
                0
            )
            or 0
        )

        total = int(
            JOB.get(
                "total",
                0
            )
            or 0
        )

    if total <= 0:

        return 0.0

    return min(
        1.0,
        current / total
    )


# ============================================================
# 현재 작업 초기화
# ============================================================

def clear_finished_job():

    with _JOB_LOCK:

        if JOB.get(
            "running"
        ):

            return False

        JOB[
            "finished"
        ] = False

        JOB[
            "result"
        ] = None

        JOB[
            "error"
        ] = ""

        JOB[
            "log"
        ] = ""

        return True


# ============================================================
# 마지막 완료 ID
# ============================================================

def get_last_completed_id():

    with _JOB_LOCK:

        value = JOB.get(
            "last_completed_id",
            0
        )

    try:

        value = int(
            value or 0
        )

    except Exception:

        value = 0

    # 메모리 값이 없으면 DB에서 확인
    if value <= 0:

        try:

            value = int(
                database.get_last_completed_id()
                or 0
            )

        except Exception:

            value = 0

    return value


# ============================================================
# 다음 시작 ID
# ============================================================

def get_next_start_id():

    last_id = get_last_completed_id()

    if last_id > 0:

        return (
            last_id + 1
        )

    try:

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

        if last_id > 0:

            return (
                last_id + 1
            )

    except Exception:

        pass

    return 0


# ============================================================
# 이어받기 가능 여부
# ============================================================

def can_resume():

    if is_running():

        return False

    try:

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

        end_id = int(
            state.get(
                "end_id",
                0
            )
            or 0
        )

        stopped = bool(
            state.get(
                "stopped",
                False
            )
        )

        if (
            stopped
            and last_id > 0
            and end_id > last_id
        ):

            return True

    except Exception:

        pass

    return False


# ============================================================
# 이어받기 정보
# ============================================================

def get_resume_info():

    try:

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

        end_id = int(
            state.get(
                "end_id",
                0
            )
            or 0
        )

        if last_id > 0:

            next_id = (
                last_id + 1
            )

        else:

            next_id = int(
                state.get(
                    "start_id",
                    0
                )
                or 0
            )

        return {

            "available":
                (
                    bool(
                        state.get(
                            "stopped",
                            False
                        )
                    )
                    and
                    next_id > 0
                    and
                    end_id >= next_id
                ),

            "start_id":
                next_id,

            "end_id":
                end_id,

            "last_completed_id":
                last_id,

            "selected_companies":
                state.get(
                    "selected_companies"
                ),

        }

    except Exception:

        return {

            "available":
                False,

            "start_id":
                0,

            "end_id":
                0,

            "last_completed_id":
                0,

            "selected_companies":
                None,

    }
