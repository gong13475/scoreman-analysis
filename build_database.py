import requests
import re
import time
from datetime import datetime

import database


BASE_URL = "https://www.scoreman123.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; K) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36"
    ),
    "Referer": BASE_URL + "/"
}


# =========================================================
# 숫자 변환
# =========================================================

def to_float(value):

    try:

        if value is None:
            return None

        value = str(value).strip()

        if value == "":
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

def calculate_result(home_score, away_score):

    if home_score is None or away_score is None:
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

    url = f"{BASE_URL}/match/data-{schedule_id}"

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        if response.status_code != 200:
            return None

        return response.text

    except Exception:

        return None


# =========================================================
# 경기 정보 파싱
# =========================================================

def parse_match_info(html, schedule_id):

    if not html:
        return None

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

        r'"HomeTeam"\s*:\s*"([^"]+)"'

    ]

    for pattern in home_patterns:

        m = re.search(
            pattern,
            html,
            re.I
        )

        if m:

            home_team = m.group(1).strip()

            break


    # -----------------------------------------------------
    # 원정팀
    # -----------------------------------------------------

    away_patterns = [

        r'"awayTeamName"\s*:\s*"([^"]+)"',

        r'"away_team"\s*:\s*"([^"]+)"',

        r'"awayTeam"\s*:\s*"([^"]+)"',

        r'"AwayTeam"\s*:\s*"([^"]+)"'

    ]

    for pattern in away_patterns:

        m = re.search(
            pattern,
            html,
            re.I
        )

        if m:

            away_team = m.group(1).strip()

            break


    # -----------------------------------------------------
    # 스코어
    # -----------------------------------------------------

    score_patterns = [

        r'"homeScore"\s*:\s*(\d+).*?"awayScore"\s*:\s*(\d+)',

        r'"home_score"\s*:\s*(\d+).*?"away_score"\s*:\s*(\d+)',

        r'"hscore"\s*:\s*(\d+).*?"ascore"\s*:\s*(\d+)'

    ]

    for pattern in score_patterns:

        m = re.search(
            pattern,
            html,
            re.I | re.S
        )

        if m:

            home_score = to_int(
                m.group(1)
            )

            away_score = to_int(
                m.group(2)
            )

            break


    # -----------------------------------------------------
    # HTML 스코어 보완
    # -----------------------------------------------------

    if home_score is None:

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

    date_patterns = [

        r'"matchTime"\s*:\s*"([^"]+)"',

        r'"matchDate"\s*:\s*"([^"]+)"',

        r'"startTime"\s*:\s*"([^"]+)"',

        r'"date"\s*:\s*"([^"]+)"'

    ]

    for pattern in date_patterns:

        m = re.search(
            pattern,
            html,
            re.I
        )

        if m:

            match_date = m.group(1).strip()

            break


    # -----------------------------------------------------
    # 제목
    # -----------------------------------------------------

    title_match = re.search(
        r"<title>(.*?)</title>",
        html,
        re.I | re.S
    )

    title = ""

    if title_match:

        title = re.sub(
            r"\s+",
            " ",
            title_match.group(1)
        ).strip()


    # -----------------------------------------------------
    # 팀명 보완
    # -----------------------------------------------------

    if not home_team or not away_team:

        m = re.search(
            r"<title>\s*(.*?)\s+vs\s+(.*?)\s*(?:[-|]|$)",
            html,
            re.I | re.S
        )

        if m:

            if not home_team:

                home_team = re.sub(
                    r"\s+",
                    " ",
                    m.group(1)
                ).strip()

            if not away_team:

                away_team = re.sub(
                    r"\s+",
                    " ",
                    m.group(2)
                ).strip()


    # -----------------------------------------------------
    # 유효성
    # -----------------------------------------------------

    if not home_team or not away_team:

        return None


    result = calculate_result(
        home_score,
        away_score
    )


    # 완료 경기만 사용
    if result not in ["승", "무", "패"]:

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

        "title":
            title

    }


# =========================================================
# 배당 API
# =========================================================

def get_scoreman_odds(schedule_id):

    url = (
        f"{BASE_URL}/ajax/soccerajax"
        f"?type=14"
        f"&t=1"
        f"&id={schedule_id}"
        f"&h=0"
    )

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        if response.status_code != 200:

            return []

        try:

            data = response.json()

        except Exception:

            return []

        return parse_odds_json(
            data
        )

    except Exception:

        return []


# =========================================================
# 배당 JSON
# =========================================================

def parse_odds_json(data):

    companies = []

    if not isinstance(data, dict):

        return companies


    if data.get("ErrCode") != 0:

        return companies


    data_block = data.get(
        "Data",
        {}
    )


    mixodds = data_block.get(
        "mixodds",
        []
    )


    if not isinstance(
        mixodds,
        list
    ):

        return companies


    for item in mixodds:

        try:

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


            initial = euro.get(
                "f",
                {}
            )


            final = euro.get(
                "l",
                {}
            )


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


            # 1X2가 모두 있어야 저장
            if not all([

                initial_home,
                initial_draw,
                initial_away

            ]):

                continue


            row = {

                "company_id":
                    company_id,

                "company_name":
                    company_name,

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

            }


            companies.append(
                row
            )


        except Exception:

            continue


    return companies


# =========================================================
# DB 저장
# =========================================================

def save_match_to_db(
    match,
    odds_list
):

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
# 날짜 문자열
# =========================================================

def extract_year(match_date):

    if not match_date:

        return None

    m = re.search(
        r"(20\d{2})",
        str(match_date)
    )

    if not m:

        return None

    return int(
        m.group(1)
    )


# =========================================================
# 자동 ID 범위 수집
# =========================================================

def build_database_progress(
    start_id,
    end_id,
    progress_callback=None,
    log_callback=None,
    delay=0.5,
    start_year=2020,
    end_year=2026
):

    start_id = int(
        start_id
    )

    end_id = int(
        end_id
    )


    if end_id < start_id:

        raise ValueError(
            "end_id가 start_id보다 작습니다."
        )


    total = (
        end_id -
        start_id +
        1
    )


    success = 0

    failed = 0

    odds_count = 0

    skipped_year = 0


    for index, schedule_id in enumerate(
        range(
            start_id,
            end_id + 1
        ),
        start=1
    ):

        # -------------------------------------------------
        # 진행률
        # -------------------------------------------------

        if progress_callback:

            progress_callback(
                index / total
            )


        # -------------------------------------------------
        # 경기 페이지
        # -------------------------------------------------

        html = get_match_page(
            schedule_id
        )


        if not html:

            failed += 1

            if log_callback:

                log_callback(
                    f"[{index}/{total}] "
                    f"{schedule_id} - 경기 없음"
                )

            time.sleep(
                delay
            )

            continue


        # -------------------------------------------------
        # 경기 정보
        # -------------------------------------------------

        match = parse_match_info(
            html,
            schedule_id
        )


        if not match:

            failed += 1

            if log_callback:

                log_callback(
                    f"[{index}/{total}] "
                    f"{schedule_id} - 완료 경기 아님"
                )

            time.sleep(
                delay
            )

            continue


        # -------------------------------------------------
        # 날짜 필터
        # -------------------------------------------------

        year = extract_year(
            match["match_date"]
        )


        if year is not None:

            if year < start_year or year > end_year:

                skipped_year += 1

                if log_callback:

                    log_callback(
                        f"[{index}/{total}] "
                        f"{schedule_id} - "
                        f"{year}년 범위 제외"
                    )

                time.sleep(
                    delay
                )

                continue


        # -------------------------------------------------
        # 배당
        # -------------------------------------------------

        odds_list = get_scoreman_odds(
            schedule_id
        )


        if not odds_list:

            failed += 1

            if log_callback:

                log_callback(
                    f"[{index}/{total}] "
                    f"{schedule_id} - 배당 없음"
                )

            time.sleep(
                delay
            )

            continue


        # -------------------------------------------------
        # 저장
        # -------------------------------------------------

        try:

            save_match_to_db(
                match,
                odds_list
            )

            success += 1

            odds_count += len(
                odds_list
            )


            if log_callback:

                log_callback(
                    f"[{index}/{total}] "
                    f"저장 완료 | "
                    f"{match['home_team']} "
                    f"vs "
                    f"{match['away_team']} | "
                    f"{match['result']} | "
                    f"업체 {len(odds_list)}"
                )


        except Exception as e:

            failed += 1

            if log_callback:

                log_callback(
                    f"[{index}/{total}] "
                    f"{schedule_id} - "
                    f"DB 오류: {e}"
                )


        time.sleep(
            delay
        )


    if progress_callback:

        progress_callback(
            1.0
        )


    return {

        "success":
            success,

        "failed":
            failed,

        "odds":
            odds_count,

        "skipped_year":
            skipped_year,

        "start_id":
            start_id,

        "end_id":
            end_id

    }


# =========================================================
# 직접 실행
# =========================================================

if __name__ == "__main__":

    database.init_database()

    print(
        "Scoreman DB 수집 테스트"
    )

    print(
        "DB:",
        database.DB_FILE
    )

    result = build_database_progress(

        2716480,

        2716580,

        delay=0.5

    )

    print(
        result
    )
