import streamlit as st
import requests
import pandas as pd
import numpy as np
import re

import database
import analysis


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(

    page_title="스코어맨 배당 분석",

    page_icon="⚽",

    layout="wide"

)


BASE_URL = "https://www.scoreman123.com"


HEADERS = {

    "User-Agent":
        (
            "Mozilla/5.0 "
            "(Linux; Android 10; K) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/130.0 Mobile Safari/537.36"
        ),

    "Referer":
        BASE_URL + "/"

}


# =========================================================
# DB 초기화
# =========================================================

try:

    database.init_database()

except Exception as e:

    st.error(
        "DATABASE 오류"
    )

    st.code(
        str(e)
    )

    st.stop()


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

def get_match_page(
    schedule_id
):

    try:

        return requests.get(

            f"{BASE_URL}/match/data-{schedule_id}",

            headers=HEADERS,

            timeout=20

        )

    except Exception as e:

        st.error(
            f"경기 페이지 오류: {e}"
        )

        return None


# =========================================================
# 경기 파싱
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
    # title
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
    # 홈팀
    # -----------------------------------------------------

    patterns = [

        r'"homeTeamName"\s*:\s*"([^"]+)"',

        r'"home_team"\s*:\s*"([^"]+)"',

        r'"homeTeam"\s*:\s*"([^"]+)"'

    ]


    for pattern in patterns:

        m = re.search(
            pattern,
            html,
            re.I
        )

        if m:

            home_team = (
                m.group(1).strip()
            )

            break


    # -----------------------------------------------------
    # 원정팀
    # -----------------------------------------------------

    patterns = [

        r'"awayTeamName"\s*:\s*"([^"]+)"',

        r'"away_team"\s*:\s*"([^"]+)"',

        r'"awayTeam"\s*:\s*"([^"]+)"'

    ]


    for pattern in patterns:

        m = re.search(
            pattern,
            html,
            re.I
        )

        if m:

            away_team = (
                m.group(1).strip()
            )

            break


    # -----------------------------------------------------
    # title 보완
    # -----------------------------------------------------

    if (
        not home_team
        or
        not away_team
    ):

        m = re.search(

            r"<title>\s*(.*?)\s+vs\s+(.*?)\s*</title>",

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
    # score
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
    # HTML score
    # -----------------------------------------------------

    if home_score is None:

        matches = re.findall(

            r">\s*(\d{1,2})\s*-\s*(\d{1,2})\s*<",

            html

        )


        if matches:

            hs, aws = matches[-1]

            home_score = to_int(hs)

            away_score = to_int(aws)


    # -----------------------------------------------------
    # 날짜
    # -----------------------------------------------------

    date_patterns = [

        r'"matchTime"\s*:\s*"([^"]+)"',

        r'"matchDate"\s*:\s*"([^"]+)"',

        r'"startTime"\s*:\s*"([^"]+)"'

    ]


    for pattern in date_patterns:

        m = re.search(

            pattern,

            html,

            re.I

        )


        if m:

            match_date = (
                m.group(1).strip()
            )

            break


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
            calculate_result(
                home_score,
                away_score
            ),

        "title":
            title

    }


# =========================================================
# 배당 API
# =========================================================

def get_scoreman_odds(
    schedule_id
):

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

            timeout=20

        )

        return url, response

    except Exception:

        return url, None


# =========================================================
# 배당 JSON
# =========================================================

def parse_odds_json(
    data
):

    companies = []


    if not isinstance(
        data,
        dict
    ):

        return companies


    if data.get(
        "ErrCode"
    ) != 0:

        return companies


    block = data.get(
        "Data",
        {}
    )


    mixodds = block.get(
        "mixodds",
        []
    )


    for item in mixodds:

        try:

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


            row = {

                "company_id":
                    item.get("cid"),

                "company_name":
                    item.get("cn", ""),

                "initial_home":
                    to_float(
                        initial.get("u")
                    ),

                "initial_draw":
                    to_float(
                        initial.get("g")
                    ),

                "initial_away":
                    to_float(
                        initial.get("d")
                    ),

                "final_home":
                    to_float(
                        final.get("u")
                    ),

                "final_draw":
                    to_float(
                        final.get("g")
                    ),

                "final_away":
                    to_float(
                        final.get("d")
                    )

            }


            if (

                row["initial_home"] is None
                or
                row["initial_draw"] is None
                or
                row["initial_away"] is None

            ):

                continue


            if (

                row["initial_home"] <= 1
                or
                row["initial_draw"] <= 1
                or
                row["initial_away"] <= 1

            ):

                continue


            companies.append(
                row
            )


        except Exception:

            continue


    return companies


# =========================================================
# DB 저장
# =========================================================

def save_to_database(
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
            match["result"]

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
# 확률
# =========================================================

def calculate_probability(
    home,
    draw,
    away
):

    if any(

        x is None
        or
        x <= 0

        for x in [
            home,
            draw,
            away
        ]

    ):

        return None


    values = [

        1 / home,

        1 / draw,

        1 / away

    ]


    total = sum(values)


    return [

        round(
            values[0] / total * 100,
            2
        ),

        round(
            values[1] / total * 100,
            2
        ),

        round(
            values[2] / total * 100,
            2
        )

    ]


# =========================================================
# 제목
# =========================================================

st.title(
    "⚽ 스코어맨 배당 분석"
)

st.caption(
    "스코어맨 경기 · 초기배당 · 최종배당 · 실제결과 · 과거통계"
)


# =========================================================
# DB 현황
# =========================================================

c1, c2 = st.columns(2)


with c1:

    st.metric(
        "경기 데이터",
        database.get_match_count()
    )


with c2:

    st.metric(
        "배당 데이터",
        database.get_odds_count()
    )


# =========================================================
# 개별 경기 조회
# =========================================================

st.divider()

st.header(
    "🔎 스코어맨 경기 조회"
)


schedule_id = st.text_input(

    "경기 ID",

    value="2716490",

    key="single_match_id"

).strip()


if st.button(

    "경기 불러오기 및 DB 저장",

    type="primary",

    use_container_width=True

):

    response = get_match_page(
        schedule_id
    )


    if response is None:

        st.stop()


    if response.status_code != 200:

        st.error(
            f"HTTP 오류: {response.status_code}"
        )

        st.stop()


    match = parse_match_info(

        response.text,

        schedule_id

    )


    if not match["home_team"]:

        st.error(
            "경기 정보를 찾지 못했습니다."
        )

        st.stop()


    st.subheader(
        "경기 정보"
    )


    st.write(
        f"**{match['home_team']}** "
        f"vs "
        f"**{match['away_team']}**"
    )


    st.write(
        "스코어:",
        f"{match['home_score']} - "
        f"{match['away_score']}"
    )


    st.write(
        "결과:",
        match["result"]
    )


    api_url, api_response = (
        get_scoreman_odds(
            schedule_id
        )
    )


    if api_response is None:

        st.error(
            "배당 API 요청 실패"
        )

        st.stop()


    try:

        odds_json = (
            api_response.json()
        )

    except Exception:

        st.error(
            "배당 JSON 오류"
        )

        st.stop()


    odds_list = parse_odds_json(
        odds_json
    )


    if not odds_list:

        st.warning(
            "배당 데이터가 없습니다."
        )

    else:

        save_to_database(
            match,
            odds_list
        )


        st.success(
            f"저장 완료: "
            f"배당업체 {len(odds_list)}개"
        )


        rows = []


        for odds in odds_list:

            probability = (
                calculate_probability(

                    odds["final_home"],

                    odds["final_draw"],

                    odds["final_away"]

                )
            )


            rows.append({

                "업체":
                    odds["company_name"],

                "초기 승":
                    odds["initial_home"],

                "초기 무":
                    odds["initial_draw"],

                "초기 패":
                    odds["initial_away"],

                "최종 승":
                    odds["final_home"],

                "최종 무":
                    odds["final_draw"],

                "최종 패":
                    odds["final_away"],

                "승확률":
                    (
                        f"{probability[0]:.2f}%"
                        if probability
                        else "-"
                    ),

                "무확률":
                    (
                        f"{probability[1]:.2f}%"
                        if probability
                        else "-"
                    ),

                "패확률":
                    (
                        f"{probability[2]:.2f}%"
                        if probability
                        else "-"
                    ),

                "실제결과":
                    match["result"]

            })


        st.dataframe(

            pd.DataFrame(rows),

            use_container_width=True,

            hide_index=True

        )


# =========================================================
# ★ 과거 스코어맨 자동 DB 구축
# =========================================================

st.divider()

st.header(
    "🗄️ 2020~2026 과거 스코어맨 자동수집"
)

st.caption(
    "경기 ID를 순차적으로 탐색하여 완료 경기 + 1X2 배당을 자동으로 DB에 저장합니다."
)


try:

    from build_database import (
        build_database_progress
    )

except Exception as e:

    st.error(
        "build_database.py를 불러올 수 없습니다."
    )

    st.code(
        str(e)
    )

    st.stop()


# =========================================================
# 자동수집 범위
# =========================================================

col1, col2 = st.columns(2)


with col1:

    start_id = st.number_input(

        "시작 경기 ID",

        min_value=1,

        value=2710000,

        step=100,

        key="history_start"

    )


with col2:

    end_id = st.number_input(

        "마지막 경기 ID",

        min_value=1,

        value=2711000,

        step=100,

        key="history_end"

    )


total_ids = (
    int(end_id)
    -
    int(start_id)
    +
    1
)


st.info(
    f"탐색 ID: {total_ids:,}개"
)


# =========================================================
# 요청 간격
# =========================================================

delay = st.number_input(

    "요청 간격",

    min_value=0.3,

    max_value=5.0,

    value=0.7,

    step=0.1,

    key="history_delay"

)


# =========================================================
# 자동수집 버튼
# =========================================================

if st.button(

    "🚀 과거 경기 자동수집 시작",

    type="primary",

    use_container_width=True,

    key="history_auto_button"

):

    if end_id < start_id:

        st.error(
            "마지막 ID가 시작 ID보다 작습니다."
        )

        st.stop()


    progress = st.progress(
        0
    )


    log_box = st.empty()

    logs = []


    def update_progress(
        value
    ):

        progress.progress(
            min(
                max(
                    float(value),
                    0
                ),
                1
            )
        )


    def update_log(
        message
    ):

        logs.append(
            str(message)
        )


        log_box.code(

            "\n".join(
                logs[-100:]
            ),

            language="text"

        )


    with st.spinner(
        "과거 스코어맨 데이터를 수집하는 중..."
    ):

        try:

            result = build_database_progress(

                int(start_id),

                int(end_id),

                progress_callback=
                    update_progress,

                log_callback=
                    update_log,

                delay=
                    float(delay)

            )

        except Exception as e:

            st.error(
                "자동수집 오류"
            )

            st.code(
                str(e)
            )

            st.stop()


    progress.progress(
        1.0
    )


    st.success(
        "✅ 자동수집 완료"
    )


    c1, c2, c3, c4 = st.columns(4)


    with c1:

        st.metric(
            "저장 경기",
            result.get(
                "success",
                0
            )
        )


    with c2:

        st.metric(
            "배당 업체",
            result.get(
                "odds",
                0
            )
        )


    with c3:

        st.metric(
            "건너뜀",
            result.get(
                "skipped",
                0
            )
        )


    with c4:

        st.metric(
            "실패",
            result.get(
                "failed",
                0
            )
        )


# =========================================================
# 현재 DB
# =========================================================

st.divider()

st.header(
    "📊 현재 DB"
)


c1, c2 = st.columns(2)


with c1:

    st.metric(
        "전체 경기",
        database.get_match_count()
    )


with c2:

    st.metric(
        "전체 배당",
        database.get_odds_count()
    )


# =========================================================
# 과거 분석
# =========================================================

st.divider()

st.header(
    "📊 과거 배당 승무패 분석"
)


try:

    df = (
        analysis
        .get_all_analysis_data()
    )

except Exception as e:

    st.error(
        "분석 오류"
    )

    st.code(
        str(e)
    )

    df = pd.DataFrame()


if df.empty:

    st.info(
        "아직 분석할 과거 데이터가 없습니다."
    )

else:

    stats = (
        analysis
        .calculate_result_stats(
            df
        )
    )


    c1, c2, c3 = st.columns(3)


    with c1:

        st.metric(

            "승",

            f'{stats["승"]["percent"]}%',

            f'{stats["승"]["count"]}경기'

        )


    with c2:

        st.metric(

            "무",

            f'{stats["무"]["percent"]}%',

            f'{stats["무"]["count"]}경기'

        )


    with c3:

        st.metric(

            "패",

            f'{stats["패"]["percent"]}%',

            f'{stats["패"]["count"]}경기'

        )


    # -----------------------------------------------------
    # 승 배당
    # -----------------------------------------------------

    st.subheader(
        "승 배당구간별 통계"
    )


    home_table = (
        analysis
        .make_odds_range_table(
            df,
            side="home"
        )
    )


    st.dataframe(

        home_table,

        use_container_width=True,

        hide_index=True

    )


    # -----------------------------------------------------
    # 무 배당
    # -----------------------------------------------------

    st.subheader(
        "무 배당구간별 통계"
    )


    draw_table = (
        analysis
        .make_odds_range_table(
            df,
            side="draw"
        )
    )


    st.dataframe(

        draw_table,

        use_container_width=True,

        hide_index=True

    )


    # -----------------------------------------------------
    # 패 배당
    # -----------------------------------------------------

    st.subheader(
        "패 배당구간별 통계"
    )


    away_table = (
        analysis
        .make_odds_range_table(
            df,
            side="away"
        )
    )


    st.dataframe(

        away_table,

        use_container_width=True,

        hide_index=True

    )


    # -----------------------------------------------------
    # 업체별
    # -----------------------------------------------------

    st.subheader(
        "🏢 배당업체별 통계"
    )


    company_table = (
        analysis
        .get_company_stats(
            df
        )
    )


    st.dataframe(

        company_table,

        use_container_width=True,

        hide_index=True

    )


# =========================================================
# 사용자 배당 입력
# =========================================================

st.divider()

st.header(
    "🎯 배당 입력 → 과거경기 자동분석"
)


c1, c2, c3 = st.columns(3)


with c1:

    input_home = st.number_input(

        "승 배당",

        min_value=1.01,

        max_value=100.0,

        value=1.65,

        step=0.01,

        format="%.2f",

        key="user_home"

    )


with c2:

    input_draw = st.number_input(

        "무 배당",

        min_value=1.01,

        max_value=100.0,

        value=3.70,

        step=0.01,

        format="%.2f",

        key="user_draw"

    )


with c3:

    input_away = st.number_input(

        "패 배당",

        min_value=1.01,

        max_value=100.0,

        value=5.20,

        step=0.01,

        format="%.2f",

        key="user_away"

    )


# =========================================================
# 배당 분석
# =========================================================

if st.button(

    "🔎 과거 배당 분석",

    type="primary",

    use_container_width=True,

    key="user_analysis"

):

    data = (
        analysis
        .get_all_analysis_data()
    )


    if data.empty:

        st.warning(
            "과거 DB 데이터가 없습니다."
        )

        st.stop()


    data = data.drop_duplicates(
        subset=["schedule_id"]
    ).copy()


    data["차이"] = (

        abs(
            data["initial_home"]
            -
            input_home
        )

        +

        abs(
            data["initial_draw"]
            -
            input_draw
        )

        +

        abs(
            data["initial_away"]
            -
            input_away
        )

    )


    similar = (
        data
        .sort_values(
            "차이"
        )
        .head(100)
        .copy()
    )


    total = len(
        similar
    )


    win = int(
        (
            similar["result"]
            ==
            "승"
        ).sum()
    )


    draw = int(
        (
            similar["result"]
            ==
            "무"
        ).sum()
    )


    lose = int(
        (
            similar["result"]
            ==
            "패"
        ).sum()
    )


    st.subheader(
        f"📊 가장 유사한 과거 {total}경기"
    )


    c1, c2, c3 = st.columns(3)


    with c1:

        st.metric(
            "승",
            f"{win / total * 100:.2f}%",
            f"{win}경기"
        )


    with c2:

        st.metric(
            "무",
            f"{draw / total * 100:.2f}%",
            f"{draw}경기"
        )


    with c3:

        st.metric(
            "패",
            f"{lose / total * 100:.2f}%",
            f"{lose}경기"
        )


    results = {

        "승":
            win,

        "무":
            draw,

        "패":
            lose

    }


    recommendation = max(
        results,
        key=results.get
    )


    percent = (
        results[recommendation]
        /
        total
        *
        100
    )


    st.success(

        f"🎯 과거 통계 추천: "
        f"**{recommendation}** "
        f"({percent:.2f}%, "
        f"{results[recommendation]}경기)"

    )


    display = similar[[

        "schedule_id",

        "match_date",

        "home_team",

        "away_team",

        "initial_home",

        "initial_draw",

        "initial_away",

        "result",

        "차이"

    ]].copy()


    display.columns = [

        "경기ID",

        "날짜",

        "홈팀",

        "원정팀",

        "승배당",

        "무배당",

        "패배당",

        "실제결과",

        "배당차이"

    ]


    st.dataframe(

        display,

        use_container_width=True,

        hide_index=True

    )


# =========================================================
# 최종 상태
# =========================================================

st.divider()

st.success(
    "✅ 스코어맨 배당 분석 프로그램 정상 실행"
    )
