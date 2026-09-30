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
        "(KHTML, like Gecko) "
        "Chrome/130.0 Mobile Safari/537.36"
    ),
    "Referer": BASE_URL + "/"
}

session = requests.Session()
session.headers.update(HEADERS)


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

        return float(
            value.replace(",", "")
        )

    except Exception:

        return None


def to_int(value):

    try:

        if value is None:
            return None

        return int(
            float(value)
        )

    except Exception:

        return None


# =========================================================
# 문자열 정리
# =========================================================

def clean_text(value):

    if value is None:
        return ""

    value = str(value)

    value = html_lib.unescape(value)

    value = value.replace(
        "\\/",
        "/"
    )

    value = value.replace(
        '\\"',
        '"'
    )

    value = value.replace(
        "\\'",
        "'"
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
# 경기 결과 계산
# =========================================================

def calculate_result(
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

    if home_score < away_score:
        return "패"

    return "무"


# =========================================================
# 이미 저장된 경기인지 먼저 확인
#
# 중요:
# 여기서 존재하면 경기 페이지 자체를 요청하지 않음
# =========================================================

def match_exists(
    schedule_id
):

    try:

        return database.match_exists(
            schedule_id
        )

    except Exception:

        return False


# =========================================================
# 경기 페이지 가져오기
# =========================================================

def get_match_page(
    schedule_id
):

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
            f"[페이지 오류] "
            f"ID={schedule_id}: {e}",
            flush=True
        )

        return None


# =========================================================
# HTML에서 값 찾기
# =========================================================

def find_value(
    html,
    keys
):

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
# JSON 객체 탐색
# =========================================================

def search_json_objects(
    html
):

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

            obj = json.loads(
                script
            )

            objects.append(obj)

        except Exception:

            pass

        for match in re.finditer(
            r"\{[^{}]{20,5000}\}",
            script,
            re.S
        ):

            value = match.group(0)

            try:

                obj = json.loads(
                    value
                )

                objects.append(obj)

            except Exception:

                continue

    return objects


# =========================================================
# JSON 재귀 검색
# =========================================================

def recursive_find(
    obj,
    wanted_keys
):

    if isinstance(
        obj,
        dict
    ):

        for key, value in obj.items():

            key_lower = str(
                key
            ).lower()

            if key_lower in wanted_keys:

                if isinstance(
                    value,
                    (
                        str,
                        int,
                        float
                    )
                ):

                    value = clean_text(
                        value
                    )

                    if value:
                        return value

            result = recursive_find(
                value,
                wanted_keys
            )

            if result:
                return result

    elif isinstance(
        obj,
        list
    ):

        for item in obj:

            result = recursive_find(
                item,
                wanted_keys
            )

            if result:
                return result

    return ""


# =========================================================
# 팀명 찾기
# =========================================================

def find_team_names(
    html
):

    home_keys = {

        "hometeamname",
        "home_team_name",
        "hometeam",
        "home_team",
        "homename",
        "hname",
        "hometeamnamecn"

    }

    away_keys = {

        "awayteamname",
        "away_team_name",
        "awayteam",
        "away_team",
        "awayname",
        "aname",
        "awayteamnamecn"

    }

    home = find_value(
        html,
        list(home_keys)
    )

    away = find_value(
        html,
        list(away_keys)
    )

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

    if not home:

        patterns = [

            r'data-home(?:team|name)?=["\']([^"\']+)',

            r'data-hname=["\']([^"\']+)',

            r'data-home-team=["\']([^"\']+)'

        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                html,
                re.I
            )

            if match:

                home = clean_text(
                    match.group(1)
                )

                break

    if not away:

        patterns = [

            r'data-away(?:team|name)?=["\']([^"\']+)',

            r'data-aname=["\']([^"\']+)',

            r'data-away-team=["\']([^"\']+)'

        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                html,
                re.I
            )

            if match:

                away = clean_text(
                    match.group(1)
                )

                break

    return (
        clean_text(home),
        clean_text(away)
    )


# =========================================================
# 스코어 찾기
# =========================================================

def find_scores(
    html
):

    patterns = [

        (
            r'"homeScore"\s*:\s*["\']?(\d+)'
            r'.{0,1000}?'
            r'"awayScore"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"home_score"\s*:\s*["\']?(\d+)'
            r'.{0,1000}?'
            r'"away_score"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"hscore"\s*:\s*["\']?(\d+)'
            r'.{0,1000}?'
            r'"ascore"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"HomeScore"\s*:\s*["\']?(\d+)'
            r'.{0,1000}?'
            r'"AwayScore"\s*:\s*["\']?(\d+)'
        ),

        (
            r'"hs"\s*:\s*["\']?(\d+)'
            r'.{0,1000}?'
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

    return (
        None,
        None
    )


# =========================================================
# 경기 날짜
# =========================================================

def find_match_date(
    html
):

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
# 경기 정보 파싱
# =========================================================

def parse_match_info(
    html,
    schedule_id
):

    home_team, away_team = (
        find_team_names(
            html
        )
    )

    home_score, away_score = (
        find_scores(
            html
        )
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
# 업체명 비교용
# =========================================================

def normalize_company_name(
    name
):

    return str(
        name or ""
    ).strip().lower()


# =========================================================
# 선택 업체 필터
# =========================================================

def filter_selected_companies(
    odds_list,
    selected_companies=None
):

    # 아무 업체도 선택하지 않으면 전체 저장
    if not selected_companies:

        return odds_list

    selected = {

        normalize_company_name(
            company
        )

        for company in selected_companies

        if str(company).strip()

    }

    result = []

    for odds in odds_list:

        company_name = normalize_company_name(

            odds.get(
                "company_name",
                ""
            )

        )

        if company_name in selected:

            result.append(
                odds
            )

    return result


# =========================================================
# 최종배당 수집
#
# f = 초기배당
# l = 최종배당
#
# 반드시 l만 사용
# =========================================================

def get_odds(
    schedule_id,
    selected_companies=None
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
            f"[배당 오류] "
            f"ID={schedule_id}: {e}",
            flush=True
        )

        return []

    if not isinstance(
        data,
        dict
    ):
        return []

    if data.get(
        "ErrCode"
    ) != 0:

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

        company_name = clean_text(
            item.get(
                "cn",
                ""
            )
        )

        if not company_name:
            continue

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
        # 초기배당 f는 사용하지 않음
        # 최종배당 l만 저장
        # -------------------------------------------------

        final = euro.get(
            "l",
            {}
        )

        if not isinstance(
            final,
            dict
        ):
            continue

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
            final_home is None
            or final_draw is None
            or final_away is None
        ):
            continue

        result.append({

            "company_id":
                str(company_id)
                if company_id is not None
                else "",

            "company_name":
                company_name,

            "final_home":
                final_home,

            "final_draw":
                final_draw,

            "final_away":
                final_away

        })

    # =====================================================
    # 선택 업체만 필터
    # =====================================================

    before_count = len(
        result
    )

    result = filter_selected_companies(
        result,
        selected_companies
    )

    after_count = len(
        result
    )

    if selected_companies:

        print(
            f"[업체 선택] "
            f"전체={before_count} "
            f"선택={after_count}",
            flush=True
        )

    print(
        f"[최종배당 완료] "
        f"ID={schedule_id} "
        f"업체={len(result)}",
        flush=True
    )

    return result


# =========================================================
# DB 저장
# =========================================================

def save_match_data(
    match,
    odds_list
):

    # -----------------------------------------------------
    # 신규 경기인지 다시 한 번 확인
    #
    # 중복 실행 방지용 이중 안전장치
    # -----------------------------------------------------

    if database.match_exists(
        match["schedule_id"]
    ):

        print(
            f"[저장 차단] "
            f"이미 저장된 경기 "
            f"ID={match['schedule_id']}",
            flush=True
        )

        return 0

    # -----------------------------------------------------
    # 경기 저장
    # -----------------------------------------------------

    saved_match = database.save_match_if_new(

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

    if not saved_match:

        print(
            f"[저장 차단] "
            f"이미 존재하는 경기 "
            f"ID={match['schedule_id']}",
            flush=True
        )

        return 0

    # -----------------------------------------------------
    # 최종배당 저장
    # -----------------------------------------------------

    count = 0

    for odds in odds_list:

        saved = database.save_odds_if_new_match(

            schedule_id=
                match["schedule_id"],

            company_id=
                odds.get(
                    "company_id",
                    ""
                ),

            company_name=
                odds.get(
                    "company_name",
                    ""
                ),

            final_home=
                odds.get(
                    "final_home"
                ),

            final_draw=
                odds.get(
                    "final_draw"
                ),

            final_away=
                odds.get(
                    "final_away"
                )

        )

        if saved:

            count += 1

    # -----------------------------------------------------
    # 마지막 저장 경기 기록
    # -----------------------------------------------------

    database.save_last_crawler_state(

        schedule_id=
            match["schedule_id"],

        match_date=
            match.get(
                "match_date",
                ""
            ),

        home_team=
            match.get(
                "home_team",
                ""
            ),

        away_team=
            match.get(
                "away_team",
                ""
            ),

        result=
            match.get(
                "result",
                ""
            ),

        odds_count=
            count

    )

    return count


# =========================================================
# 경기 하나 수집
# =========================================================

def collect_one(
    schedule_id,
    selected_companies=None
):

    print(
        "",
        flush=True
    )

    print(
        f"========== ID {schedule_id} ==========",
        flush=True
    )

    # =====================================================
    # 가장 먼저 DB 존재 여부 확인
    #
    # 중요:
    # 기존 경기면 페이지 자체를 요청하지 않음
    # =====================================================

    if match_exists(
        schedule_id
    ):

        print(
            f"[이미 저장됨] ID={schedule_id} "
            f"→ 경기/배당 재수집 안 함",
            flush=True
        )

        return {

            "status":
                "exists",

            "odds":
                0,

            "schedule_id":
                str(schedule_id)

        }

    # =====================================================
    # 신규 경기만 페이지 요청
    # =====================================================

    html = get_match_page(
        schedule_id
    )

    if not html:

        return {

            "status":
                "skip",

            "odds":
                0,

            "schedule_id":
                str(schedule_id)

        }

    # =====================================================
    # 경기 정보 파싱
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
                0,

            "schedule_id":
                str(schedule_id)

        }

    # =====================================================
    # 완료된 경기만 저장
    # =====================================================

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

            "status":
                "skip",

            "odds":
                0,

            "schedule_id":
                str(schedule_id)

        }

    # =====================================================
    # 신규 경기의 최종배당 수집
    # =====================================================

    odds_list = get_odds(

        schedule_id,

        selected_companies=
            selected_companies

    )

    if not odds_list:

        print(
            f"[최종배당 없음] ID={schedule_id}",
            flush=True
        )

        return {

            "status":
                "skip",

            "odds":
                0,

            "schedule_id":
                str(schedule_id)

        }

    # =====================================================
    # 신규 경기 + 최종배당 저장
    # =====================================================

    saved = save_match_data(
        match,
        odds_list
    )

    if saved <= 0:

        return {

            "status":
                "exists",

            "odds":
                0,

            "schedule_id":
                str(schedule_id)

        }

    print(
        f"[저장 완료] "
        f"{schedule_id} "
        f"{match.get('home_team', '')} "
        f"vs "
        f"{match.get('away_team', '')} "
        f"→ {match.get('result', '')} "
        f"/ 최종배당 {saved}개",
        flush=True
    )

    return {

        "status":
            "success",

        "odds":
            saved,

        "schedule_id":
            str(schedule_id),

        "home":
            match.get(
                "home_team",
                ""
            ),

        "away":
            match.get(
                "away_team",
                ""
            ),

        "result":
            match.get(
                "result",
                ""
            ),

        "match_date":
            match.get(
                "match_date",
                ""
            )

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
    selected_companies=None
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

    last_saved_id = (
        database.get_last_saved_schedule_id()
    )

    def log(message):

        message = str(
            message
        )

        print(
            message,
            flush=True
        )

        if log_callback:

            log_callback(
                message
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
        "초기배당: 저장하지 않음"
    )

    log(
        "최종배당: 저장"
    )

    if selected_companies:

        log(
            "선택 업체: "
            +
            ", ".join(
                str(x)
                for x in selected_companies
            )
        )

    else:

        log(
            "선택 업체: 전체 업체"
        )

    if last_saved_id:

        log(
            f"현재 DB 마지막 저장 ID: "
            f"{last_saved_id}"
        )

    log(
        "기존 경기: 재수집하지 않음"
    )

    log(
        "========================================"
    )

    # =====================================================
    # ID 순서대로 수집
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

                schedule_id,

                selected_companies=
                    selected_companies

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

                odds_total += (
                    odds_count
                )

                last_saved_id = str(
                    schedule_id
                )

            elif status == "exists":

                exists += 1

            else:

                failed += 1

        except Exception as e:

            failed += 1

            log(
                f"[오류] "
                f"ID={schedule_id}: {e}"
            )

        percent = (
            index
            /
            total
        )

        log(
            f"[진행] "
            f"{index}/{total} "
            f"({percent * 100:.1f}%) "
            f"신규={success} "
            f"기존={exists} "
            f"실패={failed} "
            f"최종배당={odds_total}"
        )

        if progress_callback:

            progress_callback(
                percent
            )

        if delay:

            time.sleep(
                float(delay)
            )

    # =====================================================
    # 실제 DB 마지막 저장 경기
    # =====================================================

    last_match = (
        database.get_last_saved_match()
    )

    if last_match:

        last_saved_id = (
            last_match.get(
                "schedule_id"
            )
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
        f"저장 최종배당: {odds_total}"
    )

    if last_match:

        log(
            "----------------------------------------"
        )

        log(
            "마지막 저장 경기"
        )

        log(
            f"경기 ID: "
            f"{last_match.get('schedule_id', '-')}"
        )

        log(
            f"경기일: "
            f"{last_match.get('match_date', '-')}"
        )

        log(
            f"경기: "
            f"{last_match.get('home_team', '')} "
            f"vs "
            f"{last_match.get('away_team', '')}"
        )

        log(
            f"결과: "
            f"{last_match.get('result', '-')}"
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
            odds_total,

        "last_saved_id":
            last_saved_id,

        "last_match":
            last_match

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
    selected_companies=None
):

    return build_database_progress(

        start_id=start_id,

        end_id=end_id,

        progress_callback=
            progress_callback,

        log_callback=
            log_callback,

        delay=delay,

        selected_companies=
            selected_companies

    )


# =========================================================
# 마지막 저장 경기 정보
# =========================================================

def get_last_saved_info():

    state = (
        database.get_last_crawler_state()
    )

    if state:

        return state

    match = (
        database.get_last_saved_match()
    )

    if match is None:

        return None

    return {

        "last_saved_schedule_id":
            match.get(
                "schedule_id"
            ),

        "last_saved_match_date":
            match.get(
                "match_date"
            ),

        "last_saved_home_team":
            match.get(
                "home_team"
            ),

        "last_saved_away_team":
            match.get(
                "away_team"
            ),

        "last_saved_result":
            match.get(
                "result"
            ),

        "last_saved_odds_count":
            0

    }


# =========================================================
# 다음 수집 시작 ID
# =========================================================

def get_next_collect_id():

    return (
        database.get_next_schedule_id()
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
        "Scoreman 최종배당 DB 수집"
    )

    print(
        "초기배당 저장 안 함"
    )

    print(
        "최종배당만 저장"
    )

    print(
        "기존 경기 재수집 안 함"
    )

    print(
        "========================================"
    )

    last_id = (
        database.get_last_saved_schedule_id()
    )

    if last_id:

        print(
            f"현재 마지막 저장 경기 ID: "
            f"{last_id}"
        )

        next_id = (
            database.get_next_schedule_id()
        )

        print(
            f"다음 권장 시작 ID: "
            f"{next_id}"
        )

    print()

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

    print()

    print(
        "업체 선택"
    )

    print(
        "예: Bet365,William Hill,10Bet"
    )

    print(
        "전체 업체는 그냥 Enter"
    )

    company_input = input(
        "업체: "
    ).strip()

    if company_input:

        selected_companies = [

            x.strip()

            for x in
            company_input.split(",")

            if x.strip()

        ]

    else:

        selected_companies = None

    result = build_database_progress(

        start_id=start_id,

        end_id=end_id,

        log_callback=print,

        delay=0.5,

        selected_companies=
            selected_companies

    )

    print()

    print(
        "========================================"
    )

    print(
        "수집 결과"
    )

    print(
        "========================================"
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
        "최종배당:",
        result["odds"]
    )

    print(
        "마지막 저장 ID:",
        result.get(
            "last_saved_id",
            "-"
        )
    )

    print(
        "========================================"
                )
