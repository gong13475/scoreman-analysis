import time
import re
import requests

import database


# =========================================================
# 기본 설정
# =========================================================

BASE_URL = "https://www.scoreman123.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; K) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36"
    ),
    "Referer": BASE_URL + "/"
}

session = requests.Session()
session.headers.update(HEADERS)


# =========================================================
# 변환
# =========================================================

def to_float(value):

    try:

        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        return float(value)

    except Exception:

        return None


def to_int(value):

    try:

        if value is None:
            return None

        return int(value)

    except Exception:

        return None


# =========================================================
# 경기 결과
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
# 경기 페이지
# =========================================================

def get_match_page(schedule_id):

    url = (
        f"{BASE_URL}/match/data-{schedule_id}"
    )

    try:

        response = session.get(
            url,
            timeout=15
        )

        if response.status_code != 200:
            return None

        if len(response.text) < 300:
            return None

        return response.text

    except Exception:

        return None


# =========================================================
# 문자열 정리
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

    return value.strip()


# =========================================================
# 정규식 첫 번째 값
# =========================================================

def find_first(
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
# 경기 정보 파싱
# =========================================================

def parse_match_info(
    html,
    schedule_id
):

    # -----------------------------------------------------
    # 홈팀
    # -----------------------------------------------------

    home_team = find_first(
        html,
        [
            r'"homeTeamName"\s*:\s*"([^"]+)"',
            r'"home_team"\s*:\s*"([^"]+)"',
            r'"homeTeam"\s*:\s*"([^"]+)"',
            r'"HomeTeam"\s*:\s*"([^"]+)"',
            r'"hname"\s*:\s*"([^"]+)"',
            r'"HomeName"\s*:\s*"([^"]+)"'
        ]
    )

    # -----------------------------------------------------
    # 원정팀
    # -----------------------------------------------------

    away_team = find_first(
        html,
        [
            r'"awayTeamName"\s*:\s*"([^"]+)"',
            r'"away_team"\s*:\s*"([^"]+)"',
            r'"awayTeam"\s*:\s*"([^"]+)"',
            r'"AwayTeam"\s*:\s*"([^"]+)"',
            r'"aname"\s*:\s*"([^"]+)"',
            r'"AwayName"\s*:\s*"([^"]+)"'
        ]
    )

    # -----------------------------------------------------
    # 스코어
    # -----------------------------------------------------

    home_score = None
    away_score = None

    score_patterns = [

        (
            r'"homeScore"\s*:\s*(\d+)'
            r'.*?'
            r'"awayScore"\s*:\s*(\d+)'
        ),

        (
            r'"home_score"\s*:\s*(\d+)'
            r'.*?'
            r'"away_score"\s*:\s*(\d+)'
        ),

        (
            r'"hscore"\s*:\s*(\d+)'
            r'.*?'
            r'"ascore"\s*:\s*(\d+)'
        ),

        (
            r'"HomeScore"\s*:\s*(\d+)'
            r'.*?'
            r'"AwayScore"\s*:\s*(\d+)'
        )
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

    if home_score is None:

        scores = re.findall(
            r">\s*(\d{1,2})\s*-\s*(\d{1,2})\s*<",
            html
        )

        if scores:

            hs, aws = scores[-1]

            home_score = to_int(hs)
            away_score = to_int(aws)

    # -----------------------------------------------------
    # 경기 날짜
    # -----------------------------------------------------

    match_date = find_first(
        html,
        [
            r'"matchTime"\s*:\s*"([^"]+)"',
            r'"matchDate"\s*:\s*"([^"]+)"',
            r'"startTime"\s*:\s*"([^"]+)"',
            r'"date"\s*:\s*"([^"]+)"',
            r'"MatchTime"\s*:\s*"([^"]+)"'
        ]
    )

    # -----------------------------------------------------
    # 결과
    # -----------------------------------------------------

    result = calculate_result(
        home_score,
        away_score
    )

    # -----------------------------------------------------
    # 팀 정보가 전혀 없으면 실패
    # -----------------------------------------------------

    if (
        not home_team
        and
        not away_team
    ):

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
# Scoreman 배당 데이터
# =========================================================

def get_odds(schedule_id):

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
            timeout=15
        )

        if response.status_code != 200:
            return []

        data = response.json()

    except Exception:

        return []

    if not isinstance(
        data,
        dict
    ):

        return []

    if data.get(
        "ErrCode"
    ) != 0:

        return []

    data_block = data.get(
        "Data",
        {}
    )

    if not isinstance(
        data_block,
        dict
    ):

        return []

    mixodds = data_block.get(
        "mixodds",
        []
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

        # =================================================
        # 최초 배당
        # =================================================

        initial = euro.get(
            "f",
            {}
        )

        # =================================================
        # 최종 배당
        # =================================================

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

        # -------------------------------------------------
        # 최초배당 3개가 없으면 해당 업체 제외
        # -------------------------------------------------

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
                str(company_id)
                if company_id is not None
                else "",

            "company_name":
                str(company_name)
                if company_name
                else "알 수 없음",

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

    return result


# =========================================================
# 경기 + 배당 저장
# =========================================================

def save_match_data(
    match,
    odds_list
):

    # -----------------------------------------------------
    # 경기 저장
    # -----------------------------------------------------

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
            "Scoreman"
    )

    # -----------------------------------------------------
    # 모든 회사 배당 저장
    # -----------------------------------------------------

    for odds in odds_list:

        database.save_odds(

            schedule_id=
                match["schedule_id"],

            company_id=
                odds["company_id"],

            company_name=
                odds["company_name"],

            initial_home=
                odds["initial_home"],

            initial_draw=
                odds["initial_draw"],

            initial_away=
                odds["initial_away"],

            final_home=
                odds["final_home"],

            final_draw=
                odds["final_draw"],

            final_away=
                odds["final_away"]
        )


# =========================================================
# 경기 존재 여부
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
# ID 하나 수집
# =========================================================

def collect_one(
    schedule_id,
    force_update=False
):

    # =====================================================
    # 기존 경기 처리
    #
    # force_update=False
    # → 기존 경기면 건너뜀
    #
    # force_update=True
    # → 다시 Scoreman에서 읽어 최신 배당으로 갱신
    # =====================================================

    if (
        match_exists(schedule_id)
        and
        not force_update
    ):

        return {

            "status":
                "exists",

            "odds":
                0
        }

    # =====================================================
    # 경기 페이지
    # =====================================================

    html = get_match_page(
        schedule_id
    )

    if not html:

        return {

            "status":
                "skip",

            "odds":
                0
        }

    # =====================================================
    # 경기 정보
    # =====================================================

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

    # =====================================================
    # 완료 경기만 저장
    # =====================================================

    if match["result"] not in [
        "승",
        "무",
        "패"
    ]:

        return {

            "status":
                "skip",

            "odds":
                0
        }

    # =====================================================
    # 배당
    # =====================================================

    odds_list = get_odds(
        schedule_id
    )

    if not odds_list:

        return {

            "status":
                "skip",

            "odds":
                0
        }

    # =====================================================
    # 저장
    # =====================================================

    save_match_data(
        match,
        odds_list
    )

    return {

        "status":
            "updated"
            if force_update
            else "success",

        "odds":
            len(odds_list),

        "home":
            match["home_team"],

        "away":
            match["away_team"],

        "result":
            match["result"]
    }


# =========================================================
# 범위 자동 수집
# =========================================================

def build_database_progress(
    start_id,
    end_id,
    progress_callback=None,
    log_callback=None,
    delay=0.5,
    force_update=False
):

    database.init_database()

    start_id = int(start_id)
    end_id = int(end_id)

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
    updated = 0
    failed = 0
    exists = 0
    odds_total = 0

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
                force_update=
                    force_update
            )

            status = result.get(
                "status",
                "skip"
            )

            # ---------------------------------------------
            # 신규 저장
            # ---------------------------------------------

            if status == "success":

                success += 1

                odds_count = int(
                    result.get(
                        "odds",
                        0
                    )
                )

                odds_total += odds_count

                if log_callback:

                    log_callback(

                        f"[저장] "
                        f"{schedule_id} | "
                        f"{result.get('home', '')} "
                        f"vs "
                        f"{result.get('away', '')} | "
                        f"{result.get('result', '')} | "
                        f"업체 {odds_count}"
                    )

            # ---------------------------------------------
            # 기존 경기 갱신
            # ---------------------------------------------

            elif status == "updated":

                updated += 1

                odds_count = int(
                    result.get(
                        "odds",
                        0
                    )
                )

                odds_total += odds_count

                if log_callback:

                    log_callback(

                        f"[갱신] "
                        f"{schedule_id} | "
                        f"{result.get('home', '')} "
                        f"vs "
                        f"{result.get('away', '')} | "
                        f"{result.get('result', '')} | "
                        f"업체 {odds_count}"
                    )

            # ---------------------------------------------
            # 이미 저장
            # ---------------------------------------------

            elif status == "exists":

                exists += 1

            # ---------------------------------------------
            # 건너뜀
            # ---------------------------------------------

            else:

                failed += 1

        except Exception as e:

            failed += 1

            if log_callback:

                log_callback(
                    f"[오류] "
                    f"{schedule_id}: "
                    f"{e}"
                )

        # =================================================
        # 진행률
        # =================================================

        if progress_callback:

            progress_callback(
                index / total
            )

        # =================================================
        # 요청 간격
        # =================================================

        if delay:

            time.sleep(
                float(delay)
            )

    return {

        "total":
            total,

        "success":
            success,

        "updated":
            updated,

        "failed":
            failed,

        "exists":
            exists,

        "odds":
            odds_total
    }


# =========================================================
# 자동 수집
# =========================================================

def auto_collect(
    start_id,
    end_id,
    progress_callback=None,
    log_callback=None,
    delay=0.5,
    force_update=False
):

    return build_database_progress(

        start_id=
            start_id,

        end_id=
            end_id,

        progress_callback=
            progress_callback,

        log_callback=
            log_callback,

        delay=
            delay,

        force_update=
            force_update
    )


# =========================================================
# 직접 실행 테스트
# =========================================================

if __name__ == "__main__":

    database.init_database()

    print(
        "================================"
    )

    print(
        "Scoreman 자동 DB 수집"
    )

    print(
        "================================"
    )

    start_id = int(
        input(
            "시작 경기 ID: "
        )
    )

    end_id = int(
        input(
            "마지막 경기 ID: "
        )
    )

    result = build_database_progress(

        start_id=
            start_id,

        end_id=
            end_id,

        log_callback=
            print,

        delay=
            0.5,

        force_update=
            False
    )

    print()
    print(
        "================================"
    )

    print(
        "수집 완료"
    )

    print(
        "전체:",
        result["total"]
    )

    print(
        "신규 저장:",
        result["success"]
    )

    print(
        "갱신:",
        result["updated"]
    )

    print(
        "기존:",
        result["exists"]
    )

    print(
        "실패/건너뜀:",
        result["failed"]
    )

    print(
        "배당 업체:",
        result["odds"]
    )

    print(
        "================================"
  )
