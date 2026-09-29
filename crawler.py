# crawler.py

import time
import re
import requests
from typing import Optional, Dict, List, Callable

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
        "Chrome/130.0.0.0 "
        "Mobile Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": BASE_URL + "/",
    "Connection": "keep-alive",
}


session = requests.Session()
session.headers.update(HEADERS)


# =========================================================
# 로그
# =========================================================

def _log(
    message: str,
    log_callback: Optional[Callable] = None
):

    message = str(message)

    print(
        message,
        flush=True
    )

    if log_callback:

        try:
            log_callback(message)

        except Exception:
            pass


# =========================================================
# 숫자 변환
# =========================================================

def to_float(value):

    try:

        if value is None:
            return None

        value = str(value).strip()

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

        if value is None:
            return None

        return int(
            str(value).strip()
        )

    except Exception:

        return None


# =========================================================
# 결과 계산
# =========================================================

def calculate_result(
    home_score,
    away_score
):

    if (
        home_score is None
        or
        away_score is None
    ):
        return ""

    if home_score > away_score:
        return "승"

    if home_score < away_score:
        return "패"

    return "무"


# =========================================================
# 경기 페이지 요청
# =========================================================

def get_match_page(
    schedule_id,
    log_callback=None
):

    url = (
        f"{BASE_URL}/match/"
        f"data-{schedule_id}"
    )

    try:

        response = session.get(
            url,
            timeout=20
        )

        _log(
            f"[페이지] ID={schedule_id} "
            f"HTTP={response.status_code} "
            f"길이={len(response.text):,}",
            log_callback
        )

        if response.status_code != 200:

            return None

        if not response.text:

            return None

        return response.text

    except Exception as e:

        _log(
            f"[페이지 오류] ID={schedule_id} "
            f"{e}",
            log_callback
        )

        return None


# =========================================================
# 텍스트 정리
# =========================================================

def clean_text(value):

    if value is None:
        return ""

    value = str(value)

    value = value.replace(
        "\\/",
        "/"
    )

    value = value.replace(
        '\\"',
        '"'
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# =========================================================
# JSON 형태 값 검색
# =========================================================

def search_first(
    html,
    patterns
):

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.I | re.S
        )

        if match:

            return clean_text(
                match.group(1)
            )

    return ""


# =========================================================
# 경기정보 파싱
# =========================================================

def parse_match_info(
    html,
    schedule_id,
    log_callback=None
):

    if not html:

        return None

    # -----------------------------------------------------
    # 홈팀
    # -----------------------------------------------------

    home_team = search_first(
        html,
        [
            r'"homeTeamName"\s*:\s*"([^"]+)"',
            r'"home_team"\s*:\s*"([^"]+)"',
            r'"homeTeam"\s*:\s*"([^"]+)"',
            r'"HomeTeam"\s*:\s*"([^"]+)"',
            r'"hname"\s*:\s*"([^"]+)"',
            r'"HomeName"\s*:\s*"([^"]+)"',
            r'"HomeTeamName"\s*:\s*"([^"]+)"',
        ]
    )

    # -----------------------------------------------------
    # 원정팀
    # -----------------------------------------------------

    away_team = search_first(
        html,
        [
            r'"awayTeamName"\s*:\s*"([^"]+)"',
            r'"away_team"\s*:\s*"([^"]+)"',
            r'"awayTeam"\s*:\s*"([^"]+)"',
            r'"AwayTeam"\s*:\s*"([^"]+)"',
            r'"aname"\s*:\s*"([^"]+)"',
            r'"AwayName"\s*:\s*"([^"]+)"',
            r'"AwayTeamName"\s*:\s*"([^"]+)"',
        ]
    )

    # -----------------------------------------------------
    # 스코어
    # -----------------------------------------------------

    home_score = None
    away_score = None

    score_patterns = [

        (
            r'"homeScore"\s*:\s*"?(\d+)"?'
            r'.{0,500}'
            r'"awayScore"\s*:\s*"?(\d+)"?'
        ),

        (
            r'"home_score"\s*:\s*"?(\d+)"?'
            r'.{0,500}'
            r'"away_score"\s*:\s*"?(\d+)"?'
        ),

        (
            r'"hscore"\s*:\s*"?(\d+)"?'
            r'.{0,500}'
            r'"ascore"\s*:\s*"?(\d+)"?'
        ),

        (
            r'"HomeScore"\s*:\s*"?(\d+)"?'
            r'.{0,500}'
            r'"AwayScore"\s*:\s*"?(\d+)"?'
        ),

    ]

    for pattern in score_patterns:

        match = re.search(
            pattern,
            html,
            re.I | re.S
        )

        if match:

            home_score = to_int(
                match.group(1)
            )

            away_score = to_int(
                match.group(2)
            )

            break

    # -----------------------------------------------------
    # HTML 스코어 보완
    # -----------------------------------------------------

    if (
        home_score is None
        or
        away_score is None
    ):

        score_matches = re.findall(
            r">\s*(\d{1,2})\s*-\s*(\d{1,2})\s*<",
            html
        )

        if score_matches:

            hs, aws = score_matches[-1]

            home_score = to_int(hs)

            away_score = to_int(aws)

    # -----------------------------------------------------
    # 날짜
    # -----------------------------------------------------

    match_date = search_first(
        html,
        [
            r'"matchTime"\s*:\s*"([^"]+)"',
            r'"matchDate"\s*:\s*"([^"]+)"',
            r'"startTime"\s*:\s*"([^"]+)"',
            r'"date"\s*:\s*"([^"]+)"',
            r'"MatchTime"\s*:\s*"([^"]+)"',
        ]
    )

    # -----------------------------------------------------
    # 결과
    # -----------------------------------------------------

    result = calculate_result(
        home_score,
        away_score
    )

    _log(
        f"[파싱] ID={schedule_id} "
        f"홈={home_team or '-'} "
        f"원정={away_team or '-'} "
        f"스코어="
        f"{home_score if home_score is not None else '-'}"
        f"-"
        f"{away_score if away_score is not None else '-'} "
        f"결과={result or '-'}",
        log_callback
    )

    # -----------------------------------------------------
    # 팀명이 하나도 없으면 실패
    # -----------------------------------------------------

    if (
        not home_team
        and
        not away_team
    ):

        _log(
            f"[파싱 실패] ID={schedule_id} "
            f"팀 정보를 찾지 못했습니다.",
            log_callback
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
            result

    }


# =========================================================
# 배당 API
# =========================================================

def get_odds(
    schedule_id,
    log_callback=None
):

    url = (
        f"{BASE_URL}/ajax/soccerajax"
        f"?type=14"
        f"&t=1"
        f"&id={schedule_id}"
        f"&h=0"
    )

    try:

        response = session.get(
            url,
            timeout=20
        )

        _log(
            f"[배당API] ID={schedule_id} "
            f"HTTP={response.status_code} "
            f"길이={len(response.text):,}",
            log_callback
        )

        if response.status_code != 200:

            return []

        try:

            data = response.json()

        except Exception as e:

            _log(
                f"[배당 JSON 오류] "
                f"ID={schedule_id} "
                f"{e}",
                log_callback
            )

            return []

    except Exception as e:

        _log(
            f"[배당 요청 오류] "
            f"ID={schedule_id} "
            f"{e}",
            log_callback
        )

        return []

    if not isinstance(data, dict):

        _log(
            f"[배당 오류] "
            f"ID={schedule_id} "
            f"응답이 dict가 아닙니다.",
            log_callback
        )

        return []

    err_code = data.get(
        "ErrCode"
    )

    if err_code != 0:

        _log(
            f"[배당 오류] "
            f"ID={schedule_id} "
            f"ErrCode={err_code}",
            log_callback
        )

        return []

    data_block = data.get(
        "Data",
        {}
    )

    if not isinstance(
        data_block,
        dict
    ):

        _log(
            f"[배당 오류] "
            f"ID={schedule_id} "
            f"Data 없음",
            log_callback
        )

        return []

    mixodds = data_block.get(
        "mixodds",
        []
    )

    if not isinstance(
        mixodds,
        list
    ):

        _log(
            f"[배당 오류] "
            f"ID={schedule_id} "
            f"mixodds 없음",
            log_callback
        )

        return []

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

        company_name = item.get(
            "cn",
            ""
        )

        euro = item.get(
            "euro",
            {}
        )

        if not isinstance(
            euro,
            dict
        ):
            continue

        initial = euro.get(
            "f",
            {}
        )

        final = euro.get(
            "l",
            {}
        )

        if not isinstance(
            initial,
            dict
        ):
            initial = {}

        if not isinstance(
            final,
            dict
        ):
            final = {}

        initial_home = to_float(
            initial.get("u")
        )

        initial_draw = to_float(
            initial.get("g")
        )

        initial_away = to_float(
            initial.get("d")
        )

        final_home = to_float(
            final.get("u")
        )

        final_draw = to_float(
            final.get("g")
        )

        final_away = to_float(
            final.get("d")
        )

        if (
            initial_home is None
            or
            initial_draw is None
            or
            initial_away is None
        ):

            continue

        result.append({

            "company_id":
                company_id,

            "company_name":
                clean_text(
                    company_name
                ),

            "initial_home":
                initial_home,

            "initial_draw":
                initial_draw,

            "initial_away":
                initial_away,

            "final_home":
                final_home,

            "final_draw":
                final_draw,

            "final_away":
                final_away

        })

    _log(
        f"[배당 파싱] ID={schedule_id} "
        f"업체={len(result)}개",
        log_callback
    )

    for odds in result:

        _log(
            f"  └ {odds['company_name'] or '-'} "
            f"초기 "
            f"{odds['initial_home']}/"
            f"{odds['initial_draw']}/"
            f"{odds['initial_away']} "
            f"→ 최종 "
            f"{odds['final_home']}/"
            f"{odds['final_draw']}/"
            f"{odds['final_away']}",
            log_callback
        )

    return result


# =========================================================
# 저장
# =========================================================

def save_match_data(
    match,
    odds_list
):

    database.save_match(

        schedule_id=match[
            "schedule_id"
        ],

        match_date=match[
            "match_date"
        ],

        home_team=match[
            "home_team"
        ],

        away_team=match[
            "away_team"
        ],

        home_score=match[
            "home_score"
        ],

        away_score=match[
            "away_score"
        ],

        result=match[
            "result"
        ],

        source="Scoreman"

    )

    saved_odds = 0

    for odds in odds_list:

        database.save_odds(

            schedule_id=match[
                "schedule_id"
            ],

            company_id=odds[
                "company_id"
            ],

            company_name=odds[
                "company_name"
            ],

            initial_home=odds[
                "initial_home"
            ],

            initial_draw=odds[
                "initial_draw"
            ],

            initial_away=odds[
                "initial_away"
            ],

            final_home=odds[
                "final_home"
            ],

            final_draw=odds[
                "final_draw"
            ],

            final_away=odds[
                "final_away"
            ]

        )

        saved_odds += 1

    return saved_odds


# =========================================================
# 존재 여부
# =========================================================

def match_exists(
    schedule_id
):

    try:

        return (
            database.get_match(
                schedule_id
            )
            is not None
        )

    except Exception:

        return False


# =========================================================
# 경기 1개 수집
# =========================================================

def collect_one(
    schedule_id,
    log_callback=None
):

    schedule_id = str(
        schedule_id
    )

    _log(
        "",
        log_callback
    )

    _log(
        f"========== ID {schedule_id} ==========",
        log_callback
    )

    # -----------------------------------------------------
    # 기존 경기라도 다시 확인
    #
    # 기존 DB의 경기 때문에
    # 배당이 갱신되지 않는 문제 방지
    # -----------------------------------------------------

    already_exists = match_exists(
        schedule_id
    )

    if already_exists:

        _log(
            f"[기존 경기] {schedule_id} "
            f"→ 페이지/배당을 다시 확인합니다.",
            log_callback
        )

    # -----------------------------------------------------
    # 경기 페이지
    # -----------------------------------------------------

    html = get_match_page(
        schedule_id,
        log_callback
    )

    if not html:

        _log(
            f"[건너뜀] {schedule_id} "
            f"경기 페이지 없음",
            log_callback
        )

        return {
            "status": "skip",
            "odds": 0
        }

    # -----------------------------------------------------
    # 경기 파싱
    # -----------------------------------------------------

    match = parse_match_info(
        html,
        schedule_id,
        log_callback
    )

    if not match:

        return {
            "status": "skip",
            "odds": 0
        }

    # -----------------------------------------------------
    # 완료 경기만 저장
    # -----------------------------------------------------

    if match["result"] not in (
        "승",
        "무",
        "패"
    ):

        _log(
            f"[미완료] {schedule_id} "
            f"결과={match['result'] or '-'}",
            log_callback
        )

        return {
            "status": "skip",
            "odds": 0
        }

    # -----------------------------------------------------
    # 배당
    # -----------------------------------------------------

    odds_list = get_odds(
        schedule_id,
        log_callback
    )

    if not odds_list:

        _log(
            f"[배당 없음] {schedule_id}",
            log_callback
        )

        return {
            "status": "skip",
            "odds": 0
        }

    # -----------------------------------------------------
    # 저장
    # -----------------------------------------------------

    saved_odds = save_match_data(
        match,
        odds_list
    )

    _log(
        f"[저장 완료] {schedule_id} "
        f"{match['home_team']} vs "
        f"{match['away_team']} "
        f"→ {match['result']} "
        f"/ 배당 {saved_odds}개",
        log_callback
    )

    return {

        "status":
            "exists"
            if already_exists
            else "success",

        "odds":
            saved_odds,

        "home":
            match["home_team"],

        "away":
            match["away_team"],

        "result":
            match["result"]

    }


# =========================================================
# 범위 수집
# =========================================================

def build_database_progress(
    start_id,
    end_id,
    progress_callback=None,
    log_callback=None,
    delay=0.5
):

    database.init_database()

    start_id = int(
        start_id
    )

    end_id = int(
        end_id
    )

    if end_id < start_id:

        raise ValueError(
            "마지막 ID가 시작 ID보다 작습니다."
        )

    total = (
        end_id
        -
        start_id
        +
        1
    )

    success = 0
    failed = 0
    exists = 0
    odds_total = 0

    _log(
        "========================================",
        log_callback
    )

    _log(
        "Scoreman DB 수집 시작",
        log_callback
    )

    _log(
        f"범위: {start_id:,} ~ {end_id:,}",
        log_callback
    )

    _log(
        f"총 검색: {total:,}건",
        log_callback
    )

    _log(
        "========================================",
        log_callback
    )

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
                log_callback
            )

            status = result.get(
                "status",
                "skip"
            )

            if status == "success":

                success += 1

                odds_total += int(
                    result.get(
                        "odds",
                        0
                    )
                )

            elif status == "exists":

                exists += 1

                odds_total += int(
                    result.get(
                        "odds",
                        0
                    )
                )

            else:

                failed += 1

        except Exception as e:

            failed += 1

            _log(
                f"[예외] ID={schedule_id} "
                f"{type(e).__name__}: {e}",
                log_callback
            )

        # -------------------------------------------------
        # 진행률
        # -------------------------------------------------

        if progress_callback:

            try:

                progress_callback(
                    index / total
                )

            except Exception:
                pass

        # -------------------------------------------------
        # 진행 상황
        # -------------------------------------------------

        if (
            index % 10 == 0
            or
            index == total
        ):

            _log(
                f"[진행] "
                f"{index:,}/{total:,} "
                f"({index / total * 100:.1f}%) "
                f"신규={success} "
                f"기존={exists} "
                f"실패={failed} "
                f"배당={odds_total}",
                log_callback
            )

        if delay:

            time.sleep(
                float(delay)
            )

    # -----------------------------------------------------
    # 완료
    # -----------------------------------------------------

    _log(
        "========================================",
        log_callback
    )

    _log(
        "DB 수집 완료",
        log_callback
    )

    _log(
        f"전체 검색: {total:,}",
        log_callback
    )

    _log(
        f"신규 저장: {success:,}",
        log_callback
    )

    _log(
        f"기존 경기: {exists:,}",
        log_callback
    )

    _log(
        f"실패/건너뜀: {failed:,}",
        log_callback
    )

    _log(
        f"저장 배당: {odds_total:,}",
        log_callback
    )

    _log(
        "========================================",
        log_callback
    )

    return {

        "success":
            success,

        "failed":
            failed,

        "exists":
            exists,

        "odds":
            odds_total,

        "total":
            total
    }


# =========================================================
# 자동 수집
# =========================================================

def auto_collect(
    start_id,
    end_id,
    progress_callback=None,
    log_callback=None,
    delay=0.5
):

    return build_database_progress(

        start_id=start_id,

        end_id=end_id,

        progress_callback=
            progress_callback,

        log_callback=
            log_callback,

        delay=delay
    )


# =========================================================
# 단일 ID 테스트
# =========================================================

if __name__ == "__main__":

    database.init_database()

    print(
        "========================================"
    )

    print(
        "Scoreman 단일 경기 테스트"
    )

    print(
        "========================================"
    )

    schedule_id = input(
        "경기 ID 입력: "
    ).strip()

    if not schedule_id:

        print(
            "경기 ID가 없습니다."
        )

        raise SystemExit

    result = collect_one(
        schedule_id,
        log_callback=print
    )

    print()
    print(
        "========================================"
    )
    print(
        "테스트 결과"
    )
    print(
        result
    )
    print(
        "========================================"
    )
