import time
import re
import json
import html as html_lib
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

        value = value.replace(",", "")

        return float(value)

    except Exception:
        return None


def to_int(value):

    try:
        if value is None:
            return None

        return int(float(value))

    except Exception:
        return None


def clean_text(value):

    if value is None:
        return ""

    value = str(value)

    value = html_lib.unescape(value)

    value = value.replace("\\/", "/")
    value = value.replace('\\"', '"')
    value = value.replace("\\'", "'")

    value = re.sub(r"<[^>]+>", " ", value)

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# =========================================================
# 결과
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

    url = (
        f"{BASE_URL}/match/data-{schedule_id}"
    )

    try:

        response = session.get(
            url,
            timeout=20
        )

        print(
            f"[페이지] ID={schedule_id} "
            f"HTTP={response.status_code} "
            f"길이={len(response.text):,}"
        )

        if response.status_code != 200:
            return None

        if len(response.text) < 300:
            return None

        return response.text

    except Exception as e:

        print(
            f"[페이지 오류] ID={schedule_id}: {e}"
        )

        return None


# =========================================================
# JSON 문자열 안에서 값 찾기
# =========================================================

def find_value(html, keys):

    for key in keys:

        patterns = [

            rf'"{re.escape(key)}"\s*:\s*"([^"]*)"',
            rf'"{re.escape(key)}"\s*:\s*([^,}}\s]+)',
            rf"'{re.escape(key)}'\s*:\s*'([^']*)'",
            rf"{re.escape(key)}\s*=\s*[\"']([^\"']+)[\"']"

        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                html,
                re.I | re.S
            )

            if match:

                value = clean_text(
                    match.group(1)
                )

                if value:
                    return value

    return ""


# =========================================================
# 팀명 추출
# =========================================================

def find_team_names(html):

    home_keys = [

        "homeTeamName",
        "home_team_name",
        "homeTeam",
        "home_team",
        "HomeTeam",
        "HomeName",
        "homeName",
        "hname",
        "home"

    ]

    away_keys = [

        "awayTeamName",
        "away_team_name",
        "awayTeam",
        "away_team",
        "AwayTeam",
        "AwayName",
        "awayName",
        "aname",
        "away"

    ]

    home = find_value(
        html,
        home_keys
    )

    away = find_value(
        html,
        away_keys
    )

    if home and away:
        return home, away

    # -----------------------------------------------------
    # 일반적인 팀명 HTML 패턴
    # -----------------------------------------------------

    patterns = [

        (
            r'class=["\'][^"\']*(?:home|team)[^"\']*["\'][^>]*>'
            r'\s*([^<]{2,100})'
        ),

        (
            r'class=["\'][^"\']*(?:away|team)[^"\']*["\'][^>]*>'
            r'\s*([^<]{2,100})'
        )

    ]

    found = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            html,
            re.I | re.S
        )

        for item in matches:

            value = clean_text(item)

            if (
                value
                and len(value) >= 2
                and value not in found
            ):
                found.append(value)

    if len(found) >= 2:

        if not home:
            home = found[0]

        if not away:
            away = found[1]

    # -----------------------------------------------------
    # 화면에 표시되는 "팀명 - 팀명" 형태
    # -----------------------------------------------------

    if not home or not away:

        text = clean_text(html)

        score_match = re.search(
            r"(.{2,100}?)\s+(\d{1,2})\s*[-:]\s*(\d{1,2})\s+(.{2,100}?)",
            text
        )

        if score_match:

            before = clean_text(
                score_match.group(1)
            )

            after = clean_text(
                score_match.group(4)
            )

            if not home:
                home = before[-80:]

            if not away:
                away = after[:80]

    return (
        clean_text(home),
        clean_text(away)
    )


# =========================================================
# 스코어 추출
# =========================================================

def find_scores(html):

    patterns = [

        (
            r'"homeScore"\s*:\s*["\']?(\d+)'
            r'.{0,500}?'
            r'"awayScore"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"home_score"\s*:\s*["\']?(\d+)'
            r'.{0,500}?'
            r'"away_score"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"hscore"\s*:\s*["\']?(\d+)'
            r'.{0,500}?'
            r'"ascore"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"HomeScore"\s*:\s*["\']?(\d+)'
            r'.{0,500}?'
            r'"AwayScore"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"hs"\s*:\s*["\']?(\d+)'
            r'.{0,500}?'
            r'"as"\s*:\s*["\']?(\d+)'
        )

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.I | re.S
        )

        if match:

            return (
                to_int(match.group(1)),
                to_int(match.group(2))
            )

    # -----------------------------------------------------
    # HTML score
    # -----------------------------------------------------

    patterns = [

        r">\s*(\d{1,2})\s*-\s*(\d{1,2})\s*<",

        r">\s*(\d{1,2})\s*:\s*(\d{1,2})\s*<",

        r"(\d{1,2})\s*-\s*(\d{1,2})"

    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            html,
            re.I | re.S
        )

        if matches:

            hs, aws = matches[-1]

            return (
                to_int(hs),
                to_int(aws)
            )

    return None, None


# =========================================================
# 날짜
# =========================================================

def find_match_date(html):

    keys = [

        "matchTime",
        "matchDate",
        "startTime",
        "MatchTime",
        "MatchDate",
        "date"

    ]

    value = find_value(
        html,
        keys
    )

    if value:
        return value

    # 일반 날짜
    match = re.search(
        r"(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}"
        r"(?:\s+\d{1,2}:\d{2})?)",
        html
    )

    if match:
        return clean_text(
            match.group(1)
        )

    return ""


# =========================================================
# 경기정보 파싱
# =========================================================

def parse_match_info(html, schedule_id):

    home_team, away_team = find_team_names(
        html
    )

    home_score, away_score = find_scores(
        html
    )

    match_date = find_match_date(
        html
    )

    result = calculate_result(
        home_score,
        away_score
    )

    print(
        f"[파싱] ID={schedule_id} "
        f"홈={home_team or '-'} "
        f"원정={away_team or '-'} "
        f"스코어="
        f"{home_score if home_score is not None else '-'}-"
        f"{away_score if away_score is not None else '-'} "
        f"결과={result or '-'}"
    )

    if not home_team or not away_team:

        print(
            f"[파싱 실패] ID={schedule_id} "
            f"팀 정보를 찾지 못했습니다."
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
            timeout=20
        )

        print(
            f"[배당] ID={schedule_id} "
            f"HTTP={response.status_code}"
        )

        if response.status_code != 200:
            return []

        data = response.json()

    except Exception as e:

        print(
            f"[배당 오류] ID={schedule_id}: {e}"
        )

        return []

    if not isinstance(data, dict):
        return []

    if data.get("ErrCode") != 0:
        return []

    data_block = data.get(
        "Data",
        {}
    )

    if not isinstance(data_block, dict):
        return []

    mixodds = data_block.get(
        "mixodds",
        []
    )

    if not isinstance(mixodds, list):
        return []

    result = []

    for item in mixodds:

        if not isinstance(item, dict):
            continue

        company_id = item.get(
            "cid"
        )

        company_name = clean_text(
            item.get(
                "cn",
                ""
            )
        )

        euro = item.get(
            "euro",
            {}
        )

        if not isinstance(euro, dict):
            continue

        initial = euro.get(
            "f",
            {}
        )

        final = euro.get(
            "l",
            {}
        )

        if not isinstance(initial, dict):
            initial = {}

        if not isinstance(final, dict):
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

        # 초기배당이 없는 업체는 분석 대상에서 제외
        if (
            initial_home is None
            or initial_draw is None
            or initial_away is None
        ):
            continue

        result.append({

            "company_id":
                str(company_id)
                if company_id is not None
                else "",

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

        })

    print(
        f"[배당 완료] ID={schedule_id} "
        f"업체={len(result)}"
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

        schedule_id=match["schedule_id"],

        match_date=match["match_date"],

        home_team=match["home_team"],

        away_team=match["away_team"],

        home_score=match["home_score"],

        away_score=match["away_score"],

        result=match["result"],

        source="Scoreman"

    )

    saved_odds = 0

    for odds in odds_list:

        database.save_odds(

            schedule_id=match["schedule_id"],

            company_id=odds["company_id"],

            company_name=odds["company_name"],

            initial_home=odds["initial_home"],

            initial_draw=odds["initial_draw"],

            initial_away=odds["initial_away"],

            final_home=odds["final_home"],

            final_draw=odds["final_draw"],

            final_away=odds["final_away"]

        )

        saved_odds += 1

    return saved_odds


# =========================================================
# 존재 여부
# =========================================================

def match_exists(schedule_id):

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

def collect_one(schedule_id):

    print()
    print(
        f"========== ID {schedule_id} =========="
    )

    # -----------------------------------------------------
    # 이미 경기 존재
    # -----------------------------------------------------

    if match_exists(schedule_id):

        print(
            f"[기존 경기] {schedule_id}"
        )

        # 기존 경기라도 배당이 없거나 업데이트할 수 있도록
        # 배당 API는 다시 확인
        odds_list = get_odds(
            schedule_id
        )

        saved = 0

        if odds_list:

            match = database.get_match(
                schedule_id
            )

            if match:

                match_dict = dict(match)

                saved = save_match_data(
                    match_dict,
                    odds_list
                )

        return {

            "status":
                "exists",

            "odds":
                saved

        }

    # -----------------------------------------------------
    # 페이지
    # -----------------------------------------------------

    html = get_match_page(
        schedule_id
    )

    if not html:

        print(
            f"[건너뜀] 페이지 없음"
        )

        return {

            "status":
                "skip",

            "odds":
                0

        }

    # -----------------------------------------------------
    # 경기 파싱
    # -----------------------------------------------------

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
    # 완료 경기
    # -----------------------------------------------------

    if match["result"] not in [
        "승",
        "무",
        "패"
    ]:

        print(
            f"[미완료] ID={schedule_id} "
            f"결과={match['result'] or '-'}"
        )

        return {

            "status":
                "skip",

            "odds":
                0

        }

    # -----------------------------------------------------
    # 배당
    # -----------------------------------------------------

    odds_list = get_odds(
        schedule_id
    )

    if not odds_list:

        print(
            f"[배당 없음] ID={schedule_id}"
        )

        return {

            "status":
                "skip",

            "odds":
                0

        }

    # -----------------------------------------------------
    # 저장
    # -----------------------------------------------------

    saved_odds = save_match_data(
        match,
        odds_list
    )

    print(
        f"[저장 완료] {schedule_id} "
        f"{match['home_team']} vs "
        f"{match['away_team']} "
        f"→ {match['result']} "
        f"/ 배당 {saved_odds}개"
    )

    return {

        "status":
            "success",

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
# ID 범위 수집
# =========================================================

def build_database_progress(
    start_id,
    end_id,
    progress_callback=None,
    log_callback=None,
    delay=0.5
):

    database.init_database()

    start_id = int(start_id)
    end_id = int(end_id)

    if end_id < start_id:

        raise ValueError(
            "마지막 ID가 시작 ID보다 작습니다."
        )

    total = (
        end_id -
        start_id +
        1
    )

    success = 0
    failed = 0
    exists = 0
    odds_total = 0

    def log(message):

        print(
            message,
            flush=True
        )

        if log_callback:

            log_callback(
                str(message)
            )

    log(
        "========================================"
    )

    log(
        "Scoreman DB 수집 시작"
    )

    log(
        f"범위: {start_id:,} ~ {end_id:,}"
    )

    log(
        f"총 검색: {total:,}건"
    )

    log(
        "========================================"
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
                schedule_id
            )

            status = result.get(
                "status",
                "skip"
            )

            odds_count = int(
                result.get(
                    "odds",
                    0
                )
            )

            if status == "success":

                success += 1

                odds_total += odds_count

            elif status == "exists":

                exists += 1

                odds_total += odds_count

            else:

                failed += 1

        except Exception as e:

            failed += 1

            log(
                f"[오류] ID={schedule_id}: {e}"
            )

        percent = (
            index /
            total
        )

        log(
            f"[진행] {index}/{total} "
            f"({percent * 100:.1f}%) "
            f"신규={success} "
            f"기존={exists} "
            f"실패={failed} "
            f"배당={odds_total}"
        )

        if progress_callback:

            progress_callback(
                percent
            )

        if delay:

            time.sleep(
                float(delay)
            )

    log(
        "========================================"
    )

    log(
        "DB 수집 완료"
    )

    log(
        f"전체 검색: {total}"
    )

    log(
        f"신규 저장: {success}"
    )

    log(
        f"기존 경기: {exists}"
    )

    log(
        f"실패/건너뜀: {failed}"
    )

    log(
        f"저장 배당: {odds_total}"
    )

    log(
        "========================================"
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
# 직접 실행
# =========================================================

if __name__ == "__main__":

    database.init_database()

    print(
        "========================================"
    )

    print(
        "Scoreman DB 수집"
    )

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

    result = build_database_progress(

        start_id=start_id,

        end_id=end_id,

        log_callback=print,

        delay=0.5

    )

    print()
    print(
        "수집 완료"
    )

    print(
        "전체:",
        result["total"]
    )

    print(
        "신규:",
        result["success"]
    )

    print(
        "기존:",
        result["exists"]
    )

    print(
        "실패:",
        result["failed"]
    )

    print(
        "배당:",
        result["odds"]
            )
