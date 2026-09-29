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
    "Referer": BASE_URL + "/",
    "Accept": "text/html,application/xhtml+xml,application/json,"
              "application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
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

        return float(value.replace(",", ""))

    except Exception:
        return None


def to_int(value):
    try:
        if value is None:
            return None

        value = str(value).strip()

        if not value:
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
    value = value.replace("&nbsp;", " ")

    value = re.sub(
        r"<br\s*/?>",
        " ",
        value,
        flags=re.I
    )

    value = re.sub(
        r"<[^>]+>",
        " ",
        value
    )

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
# 페이지 요청
# =========================================================

def get_match_page(schedule_id):

    url = f"{BASE_URL}/match/data-{schedule_id}"

    try:

        response = session.get(
            url,
            timeout=20
        )

        print(
            f"[페이지] ID={schedule_id} "
            f"HTTP={response.status_code} "
            f"길이={len(response.text):,}",
            flush=True
        )

        if response.status_code != 200:
            return None

        if len(response.text) < 300:
            return None

        return response.text

    except Exception as e:

        print(
            f"[페이지 오류] ID={schedule_id}: {e}",
            flush=True
        )

        return None


# =========================================================
# 일반 키 검색
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
# HTML 속성 검색
# =========================================================

def find_attribute_value(html, names):

    for name in names:

        pattern = (
            rf'\b{re.escape(name)}\s*=\s*'
            rf'["\']([^"\']+)["\']'
        )

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
# JSON 객체 추출
# =========================================================

def search_json_objects(html):

    objects = []

    scripts = re.findall(
        r"<script[^>]*>(.*?)</script>",
        html,
        re.I | re.S
    )

    for script in scripts:

        script = script.strip()

        if not script:
            continue

        try:

            obj = json.loads(script)

            objects.append(obj)

        except Exception:
            pass

        # script 안의 JSON 조각
        for match in re.finditer(
            r"\{[^{}]{20,10000}\}",
            script,
            re.S
        ):

            value = match.group(0)

            try:

                obj = json.loads(value)

                objects.append(obj)

            except Exception:
                continue

    return objects


# =========================================================
# JSON 재귀 검색
# =========================================================

def recursive_find(obj, wanted_keys):

    if isinstance(obj, dict):

        for key, value in obj.items():

            key_lower = str(key).lower()

            if key_lower in wanted_keys:

                if isinstance(
                    value,
                    (str, int, float)
                ):

                    value = clean_text(value)

                    if value:
                        return value

            result = recursive_find(
                value,
                wanted_keys
            )

            if result:
                return result

    elif isinstance(obj, list):

        for item in obj:

            result = recursive_find(
                item,
                wanted_keys
            )

            if result:
                return result

    return ""


# =========================================================
# 팀명 추출
# =========================================================

def find_team_names(html):

    home_keys = {
        "hometeamname",
        "home_team_name",
        "hometeam",
        "home_team",
        "homename",
        "hname",
        "hometeamnamecn",
        "home_name",
        "hometeamcn",
        "teamhome"
    }

    away_keys = {
        "awayteamname",
        "away_team_name",
        "awayteam",
        "away_team",
        "awayname",
        "aname",
        "awayteamnamecn",
        "away_name",
        "awayteamcn",
        "teamaway"
    }

    home = find_value(
        html,
        list(home_keys)
    )

    away = find_value(
        html,
        list(away_keys)
    )

    # -----------------------------------------------------
    # JSON
    # -----------------------------------------------------

    if not home or not away:

        objects = search_json_objects(
            html
        )

        for obj in objects:

            if not home:

                home = recursive_find(
                    obj,
                    home_keys
                )

            if not away:

                away = recursive_find(
                    obj,
                    away_keys
                )

            if home and away:
                break

    # -----------------------------------------------------
    # data-* 속성
    # -----------------------------------------------------

    if not home:

        home = find_attribute_value(
            html,
            [
                "data-home",
                "data-home-team",
                "data-home-name",
                "data-hname",
                "data-hometeam"
            ]
        )

    if not away:

        away = find_attribute_value(
            html,
            [
                "data-away",
                "data-away-team",
                "data-away-name",
                "data-aname",
                "data-awayteam"
            ]
        )

    # -----------------------------------------------------
    # HTML class
    # -----------------------------------------------------

    if not home:

        patterns = [

            r'class=["\'][^"\']*(?:home|Home)[^"\']*["\']'
            r'[^>]*>\s*([^<]{2,200})',

            r'<span[^>]*class=["\'][^"\']*'
            r'(?:home|Home)[^"\']*["\'][^>]*>'
            r'\s*([^<]{2,200})',

            r'<div[^>]*class=["\'][^"\']*'
            r'(?:home|Home)[^"\']*["\'][^>]*>'
            r'\s*([^<]{2,200})'

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
                    home = value
                    break

    if not away:

        patterns = [

            r'class=["\'][^"\']*(?:away|Away)[^"\']*["\']'
            r'[^>]*>\s*([^<]{2,200})',

            r'<span[^>]*class=["\'][^"\']*'
            r'(?:away|Away)[^"\']*["\'][^>]*>'
            r'\s*([^<]{2,200})',

            r'<div[^>]*class=["\'][^"\']*'
            r'(?:away|Away)[^"\']*["\'][^>]*>'
            r'\s*([^<]{2,200})'

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
                    away = value
                    break

    return (
        clean_text(home),
        clean_text(away)
    )


# =========================================================
# 스코어
# =========================================================

def find_scores(html):

    patterns = [

        (
            r'"homeScore"\s*:\s*["\']?(\d+)'
            r'.{0,2000}?'
            r'"awayScore"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"home_score"\s*:\s*["\']?(\d+)'
            r'.{0,2000}?'
            r'"away_score"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"hscore"\s*:\s*["\']?(\d+)'
            r'.{0,2000}?'
            r'"ascore"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"HomeScore"\s*:\s*["\']?(\d+)'
            r'.{0,2000}?'
            r'"AwayScore"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"hs"\s*:\s*["\']?(\d+)'
            r'.{0,2000}?'
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
    # HTML
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
        "date",
        "gameTime",
        "eventTime"

    ]

    value = find_value(
        html,
        keys
    )

    if value:
        return value

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
# 경기 파싱
# =========================================================

def parse_match_info(
    html,
    schedule_id
):

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
        f"결과={result or '-'}",
        flush=True
    )

    if not home_team or not away_team:

        print(
            f"[파싱 실패] ID={schedule_id} "
            f"팀 정보를 찾지 못했습니다.",
            flush=True
        )

        # =================================================
        # 실제 HTML 확인용
        # =================================================

        print(
            "========== HTML DEBUG START ==========",
            flush=True
        )

        print(
            html[:10000],
            flush=True
        )

        print(
            "========== HTML DEBUG END ==========",
            flush=True
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
            f"HTTP={response.status_code}",
            flush=True
        )

        if response.status_code != 200:
            return []

        data = response.json()

    except Exception as e:

        print(
            f"[배당 오류] ID={schedule_id}: {e}",
            flush=True
        )

        return []

    if not isinstance(data, dict):
        return []

    if data.get("ErrCode") != 0:

        print(
            f"[배당 오류] "
            f"ErrCode={data.get('ErrCode')}",
            flush=True
        )

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

        company_id = item.get("cid")

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

        # 초기배당 3개가 없는 업체는 제외
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
        f"업체={len(result)}",
        flush=True
    )

    for odds in result:

        print(
            f"  - {odds['company_name']} "
            f"초기 "
            f"{odds['initial_home']}/"
            f"{odds['initial_draw']}/"
            f"{odds['initial_away']} "
            f"→ 최종 "
            f"{odds['final_home']}/"
            f"{odds['final_draw']}/"
            f"{odds['final_away']}",
            flush=True
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

    count = 0

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

        count += 1

    return count


# =========================================================
# 경기 존재 여부
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

    print(
        "",
        flush=True
    )

    print(
        f"========== ID {schedule_id} ==========",
        flush=True
    )

    # -----------------------------------------------------
    # 페이지 먼저 가져오기
    # -----------------------------------------------------

    html = get_match_page(
        schedule_id
    )

    if not html:

        return {
            "status": "skip",
            "odds": 0
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
            "status": "skip",
            "odds": 0
        }

    # -----------------------------------------------------
    # 배당 가져오기
    # -----------------------------------------------------

    odds_list = get_odds(
        schedule_id
    )

    # -----------------------------------------------------
    # 기존 경기
    #
    # 경기정보가 이미 DB에 있어도
    # 배당은 다시 받아서 최종배당까지 갱신
    # -----------------------------------------------------

    existed = match_exists(
        schedule_id
    )

    # -----------------------------------------------------
    # 결과가 완료된 경기인지 확인
    # -----------------------------------------------------

    if match["result"] not in [
        "승",
        "무",
        "패"
    ]:

        print(
            f"[미완료] ID={schedule_id}",
            flush=True
        )

        return {
            "status": "skip",
            "odds": 0
        }

    # -----------------------------------------------------
    # 배당이 없으면 저장하지 않음
    # -----------------------------------------------------

    if not odds_list:

        print(
            f"[배당 없음] ID={schedule_id}",
            flush=True
        )

        return {
            "status": "skip",
            "odds": 0
        }

    # -----------------------------------------------------
    # 경기 + 업체별 배당 저장
    # -----------------------------------------------------

    saved = save_match_data(
        match,
        odds_list
    )

    if existed:

        print(
            f"[기존 갱신 완료] "
            f"{schedule_id} "
            f"{match['home_team']} "
            f"vs "
            f"{match['away_team']} "
            f"→ {match['result']} "
            f"/ 배당 {saved}개",
            flush=True
        )

        return {
            "status": "exists",
            "odds": saved,
            "home": match["home_team"],
            "away": match["away_team"],
            "result": match["result"]
        }

    print(
        f"[신규 저장 완료] "
        f"{schedule_id} "
        f"{match['home_team']} "
        f"vs "
        f"{match['away_team']} "
        f"→ {match['result']} "
        f"/ 배당 {saved}개",
        flush=True
    )

    return {
        "status": "success",
        "odds": saved,
        "home": match["home_team"],
        "away": match["away_team"],
        "result": match["result"]
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

        message = str(message)

        print(
            message,
            flush=True
        )

        if log_callback:

            log_callback(
                message
            )

    # -----------------------------------------------------
    # 시작
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # ID 순서대로
    # -----------------------------------------------------

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
            f"[진행] "
            f"{index}/{total} "
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
                max(
                    0,
                    float(delay)
                )
            )

    # -----------------------------------------------------
    # 완료
    # -----------------------------------------------------

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

    print(
        "========================================"
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
