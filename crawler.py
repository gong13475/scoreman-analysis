# crawler.py

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
# 경기 정보 파싱
# =========================================================

def parse_match_info(
    html,
    schedule_id
):

    home_team = ""
    away_team = ""

    home_score = None
    away_score = None

    match_date = ""


    # -----------------------------------------------------
    # 홈팀
    # -----------------------------------------------------

    home_patterns = [

        r'"homeTeamName"\s*:\s*"([^"]+)"',
        r'"home_team"\s*:\s*"([^"]+)"',
        r'"homeTeam"\s*:\s*"([^"]+)"',
        r'"HomeTeam"\s*:\s*"([^"]+)"',
        r'"hname"\s*:\s*"([^"]+)"',
        r'"HomeName"\s*:\s*"([^"]+)"'

    ]

    for pattern in home_patterns:

        match = re.search(
            pattern,
            html,
            re.I
        )

        if match:

            home_team = clean_text(
                match.group(1)
            )

            break


    # -----------------------------------------------------
    # 원정팀
    # -----------------------------------------------------

    away_patterns = [

        r'"awayTeamName"\s*:\s*"([^"]+)"',
        r'"away_team"\s*:\s*"([^"]+)"',
        r'"awayTeam"\s*:\s*"([^"]+)"',
        r'"AwayTeam"\s*:\s*"([^"]+)"',
        r'"aname"\s*:\s*"([^"]+)"',
        r'"AwayName"\s*:\s*"([^"]+)"'

    ]

    for pattern in away_patterns:

        match = re.search(
            pattern,
            html,
            re.I
        )

        if match:

            away_team = clean_text(
                match.group(1)
            )

            break


    # -----------------------------------------------------
    # 스코어
    # -----------------------------------------------------

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
    # 날짜
    # -----------------------------------------------------

    date_patterns = [

        r'"matchTime"\s*:\s*"([^"]+)"',
        r'"matchDate"\s*:\s*"([^"]+)"',
        r'"startTime"\s*:\s*"([^"]+)"',
        r'"date"\s*:\s*"([^"]+)"',
        r'"MatchTime"\s*:\s*"([^"]+)"'

    ]

    for pattern in date_patterns:

        match = re.search(
            pattern,
            html,
            re.I
        )

        if match:

            match_date = clean_text(
                match.group(1)
            )

            break


    # -----------------------------------------------------
    # 결과
    # -----------------------------------------------------

    result = calculate_result(
        home_score,
        away_score
    )


    # -----------------------------------------------------
    # 팀명이 전혀 없으면 실패
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
# 배당 API
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


    if data.get("ErrCode") != 0:

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


    # =====================================================
    # 모든 업체
    # =====================================================

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


        # -------------------------------------------------
        # 최초 배당
        # -------------------------------------------------

        initial = euro.get(
            "f",
            {}
        )

        if not isinstance(
            initial,
            dict
        ):

            initial = {}


        # -------------------------------------------------
        # 최종 배당
        # -------------------------------------------------

        final = euro.get(
            "l",
            {}
        )

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
        # 최초배당이 없는 업체는 제외
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


    return result


# =========================================================
# 경기 저장
# =========================================================

def save_match_data(
    match,
    odds_list
):

    # -----------------------------------------------------
    # 경기
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

        source="Scoreman"

    )


    # -----------------------------------------------------
    # 업체별 배당
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
# 경기 1개 수집
# =========================================================
#
# 중요:
# 이미 DB에 경기 데이터가 있어도
# 배당은 다시 확인한다.
#
# =========================================================

def collect_one(schedule_id):

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


    # -----------------------------------------------------
    # 완료 경기만 저장
    # -----------------------------------------------------

    if match["result"] not in [

        "승",
        "무",
        "패"

    ]:

        return {

            "status":
                "not_finished",

            "odds":
                0

        }


    # -----------------------------------------------------
    # 배당 가져오기
    # -----------------------------------------------------

    odds_list = get_odds(
        schedule_id
    )


    if not odds_list:

        # 경기 정보만 저장
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

            source="Scoreman"

        )

        return {

            "status":
                "no_odds",

            "odds":
                0,

            "home":
                match["home_team"],

            "away":
                match["away_team"],

            "result":
                match["result"]

        }


    # -----------------------------------------------------
    # 경기 + 모든 업체 배당 저장
    # -----------------------------------------------------

    save_match_data(
        match,
        odds_list
    )


    return {

        "status":
            "success",

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
# 연속 ID 전체 수집
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

    no_odds = 0

    not_finished = 0


    # =====================================================
    # 순차 검색
    # =====================================================

    for index, schedule_id in enumerate(

        range(
            start_id,
            end_id + 1
        ),

        start=1

    ):

        try:

            result = collect_one(
                schedule_id
            )


            status = result.get(
                "status",
                "skip"
            )


            # -------------------------------------------------
            # 성공
            # -------------------------------------------------

            if status == "success":

                success += 1

                odds_count = int(
                    result.get(
                        "odds",
                        0
                    )
                )

                odds_total += (
                    odds_count
                )


                if log_callback:

                    log_callback(

                        f"[저장/갱신] "
                        f"{schedule_id} | "

                        f"{result.get('home', '')} "
                        f"vs "
                        f"{result.get('away', '')} | "

                        f"결과 "
                        f"{result.get('result', '')} | "

                        f"업체 "
                        f"{odds_count}"

                    )


            # -------------------------------------------------
            # 배당 없음
            # -------------------------------------------------

            elif status == "no_odds":

                no_odds += 1

                if log_callback:

                    log_callback(

                        f"[경기 저장/배당 없음] "
                        f"{schedule_id} | "

                        f"{result.get('home', '')} "
                        f"vs "
                        f"{result.get('away', '')}"

                    )


            # -------------------------------------------------
            # 미종료
            # -------------------------------------------------

            elif status == "not_finished":

                not_finished += 1


            # -------------------------------------------------
            # 기타 실패
            # -------------------------------------------------

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


        # -----------------------------------------------------
        # 진행률
        # -----------------------------------------------------

        if progress_callback:

            progress_callback(

                index /
                total

            )


        # -----------------------------------------------------
        # 요청 간격
        # -----------------------------------------------------

        if delay:

            time.sleep(
                float(delay)
            )


    return {

        "total":
            total,

        "success":
            success,

        "failed":
            failed,

        "exists":
            exists,

        "odds":
            odds_total,

        "no_odds":
            no_odds,

        "not_finished":
            not_finished

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
# 단일 경기 테스트
# =========================================================

def test_one(schedule_id):

    database.init_database()

    print(
        f"경기 {schedule_id} 수집 테스트"
    )

    result = collect_one(
        schedule_id
    )

    print()
    print(
        "결과:"
    )

    print(
        result
    )

    print()
    print(
        "저장된 경기:"
    )

    match = database.get_match(
        schedule_id
    )

    if match:

        print(
            dict(match)
        )

    print()
    print(
        "저장된 업체별 배당:"
    )

    odds = database.get_match_odds(
        schedule_id
    )

    for row in odds:

        print(
            dict(row)
        )

    return result


# =========================================================
# 직접 실행
# =========================================================

if __name__ == "__main__":

    database.init_database()

    print(
        "======================================"
    )

    print(
        "Scoreman 과거 경기 전체 수집"
    )

    print(
        "======================================"
    )

    print()

    print(
        "1 = 단일 경기 테스트"
    )

    print(
        "2 = ID 범위 전체 수집"
    )

    print()

    mode = input(
        "선택: "
    ).strip()


    # =====================================================
    # 단일 테스트
    # =====================================================

    if mode == "1":

        schedule_id = int(
            input(
                "경기 ID: "
            )
        )

        test_one(
            schedule_id
        )


    # =====================================================
    # 전체 수집
    # =====================================================

    elif mode == "2":

        start_id = int(
            input(
                "시작 ID: "
            )
        )

        end_id = int(
            input(
                "마지막 ID: "
            )
        )

        delay = float(
            input(
                "요청 간격(초, 기본 0.5): "
            )
            or "0.5"
        )


        result = build_database_progress(

            start_id=start_id,

            end_id=end_id,

            log_callback=print,

            delay=delay

        )


        print()

        print(
            "======================================"
        )

        print(
            "수집 완료"
        )

        print(
            "======================================"
        )

        print(
            "전체 검색:",
            result["total"]
        )

        print(
            "저장/갱신:",
            result["success"]
        )

        print(
            "실패:",
            result["failed"]
        )

        print(
            "배당 없음:",
            result["no_odds"]
        )

        print(
            "미종료:",
            result["not_finished"]
        )

        print(
            "배당 업체 레코드:",
            result["odds"]
        )

        print(
            "======================================"
        )


    else:

        print(
            "잘못된 선택입니다."
        )
