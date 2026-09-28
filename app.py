import streamlit as st
import requests
import sqlite3
import json
import re
from datetime import datetime

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

try:
    database.init_database()
except Exception as e:
    st.error("DATABASE 오류")
    st.code(str(e))
    st.stop()

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
# 경기 결과
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
# 스코어맨 경기 페이지
# =========================================================

def get_match_page(schedule_id):

    url = f"{BASE_URL}/match/data-{schedule_id}"

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        return response

    except Exception as e:

        st.error(f"경기 페이지 요청 오류: {e}")

        return None


# =========================================================
# 경기 정보 파싱
# =========================================================

def parse_match_info(html, schedule_id):

    home_team = ""
    away_team = ""

    home_score = None
    away_score = None

    match_date = ""

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
    # 팀 이름
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
            home_team = m.group(1).strip()
            break

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
            away_team = m.group(1).strip()
            break

    # -----------------------------------------------------
    # 경기 제목에서 팀 이름 보완
    # -----------------------------------------------------

    if not home_team or not away_team:

        m = re.search(
            r"<title>\s*(.*?)\s+vs\s+(.*?)\s+(?:실시간|[-|])",
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

            home_score = to_int(m.group(1))
            away_score = to_int(m.group(2))

            break

    # -----------------------------------------------------
    # HTML에서 일반적인 0-3 형태 검색
    # -----------------------------------------------------

    if home_score is None:

        score_matches = re.findall(
            r">\s*(\d{1,2})\s*-\s*(\d{1,2})\s*<",
            html
        )

        if score_matches:

            # 마지막에 등장하는 스코어를 우선 사용
            hs, aws = score_matches[-1]

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

            match_date = m.group(1).strip()

            break

    result = calculate_result(
        home_score,
        away_score
    )

    return {
        "schedule_id": str(schedule_id),
        "title": title,
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
        "result": result,
        "match_date": match_date
    }


# =========================================================
# 실제 스코어맨 배당 API
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
            timeout=20
        )

        return url, response

    except Exception as e:

        st.error(f"배당 API 요청 오류: {e}")

        return url, None


# =========================================================
# 배당 JSON 파싱
# =========================================================

def parse_odds_json(data):

    companies = []

    if not isinstance(data, dict):
        return companies

    if data.get("ErrCode") != 0:
        return companies

    data_block = data.get("Data", {})

    mixodds = data_block.get(
        "mixodds",
        []
    )

    for item in mixodds:

        try:

            company_id = item.get("cid")

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

            row = {

                "company_id": company_id,

                "company_name": company_name,

                "initial_home": to_float(
                    initial.get("u")
                ),

                "initial_draw": to_float(
                    initial.get("g")
                ),

                "initial_away": to_float(
                    initial.get("d")
                ),

                "final_home": to_float(
                    final.get("u")
                ),

                "final_draw": to_float(
                    final.get("g")
                ),

                "final_away": to_float(
                    final.get("d")
                )

            }

            companies.append(row)

        except Exception:
            continue

    return companies


# =========================================================
# DB 저장
# =========================================================

def save_to_database(match, odds_list):

    database.save_match(

        schedule_id=match["schedule_id"],

        match_date=match["match_date"],

        home_team=match["home_team"],

        away_team=match["away_team"],

        home_score=match["home_score"],

        away_score=match["away_score"],

        result=match["result"]

    )

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


# =========================================================
# 확률 계산
# =========================================================

def calculate_probability(home, draw, away):

    values = [
        home,
        draw,
        away
    ]

    if any(
        v is None or v <= 0
        for v in values
    ):
        return None

    inverse = [
        1 / home,
        1 / draw,
        1 / away
    ]

    total = sum(inverse)

    if total <= 0:
        return None

    return [

        round(inverse[0] / total * 100, 2),

        round(inverse[1] / total * 100, 2),

        round(inverse[2] / total * 100, 2)

    ]


# =========================================================
# 화면
# =========================================================

st.title("⚽ 스코어맨 배당 분석")

st.caption(
    "스코어맨 경기 → 초기배당 → 최종배당 → 경기결과 → SQLite DB"
)


# =========================================================
# 상단 DB 현황
# =========================================================

col1, col2 = st.columns(2)

with col1:

    st.metric(
        "경기 데이터",
        database.get_match_count()
    )

with col2:

    st.metric(
        "배당 데이터",
        database.get_odds_count()
    )


st.divider()


# =========================================================
# 경기 ID 입력
# =========================================================

st.subheader("① 스코어맨 경기")

schedule_id = st.text_input(
    "스코어맨 경기 ID",
    value="2716490"
)

if schedule_id:

    schedule_id = schedule_id.strip()


st.code(
    f"{BASE_URL}/match/data-{schedule_id}",
    language="text"
)


# =========================================================
# 분석 버튼
# =========================================================

if st.button(
    "🔎 스코어맨 경기 불러오기",
    type="primary",
    use_container_width=True
):

    if not schedule_id:

        st.error("경기 ID를 입력하세요.")

        st.stop()

    # -----------------------------------------------------
    # 경기 페이지
    # -----------------------------------------------------

    st.subheader("② 경기 페이지")

    response = get_match_page(
        schedule_id
    )

    if response is None:

        st.stop()

    st.write(
        "HTTP 상태:",
        response.status_code
    )

    st.write(
        "HTML 크기:",
        len(response.text)
    )

    if response.status_code != 200:

        st.error(
            "스코어맨 경기 페이지를 가져오지 못했습니다."
        )

        st.stop()

    # -----------------------------------------------------
    # 경기정보
    # -----------------------------------------------------

    match = parse_match_info(
        response.text,
        schedule_id
    )

    st.subheader("③ 경기 정보")

    c1, c2 = st.columns(2)

    with c1:

        st.write(
            "**홈팀:**",
            match["home_team"] or "확인 안됨"
        )

        st.write(
            "**원정팀:**",
            match["away_team"] or "확인 안됨"
        )

    with c2:

        score_text = "-"

        if (
            match["home_score"] is not None
            and
            match["away_score"] is not None
        ):

            score_text = (
                f'{match["home_score"]} - '
                f'{match["away_score"]}'
            )

        st.write(
            "**최종 스코어:**",
            score_text
        )

        st.write(
            "**결과:**",
            match["result"] or "확인 안됨"
        )

    # -----------------------------------------------------
    # 배당 API
    # -----------------------------------------------------

    st.subheader(
        "④ 실제 스코어맨 배당 API"
    )

    api_url, api_response = get_scoreman_odds(
        schedule_id
    )

    st.code(
        api_url,
        language="text"
    )

    if api_response is None:

        st.stop()

    st.write(
        "API HTTP:",
        api_response.status_code
    )

    st.write(
        "API 응답 크기:",
        len(api_response.text)
    )

    if api_response.status_code != 200:

        st.error(
            "배당 API 요청 실패"
        )

        st.stop()

    # -----------------------------------------------------
    # JSON
    # -----------------------------------------------------

    try:

        odds_json = api_response.json()

    except Exception:

        st.error(
            "배당 API 응답을 JSON으로 읽을 수 없습니다."
        )

        st.code(
            api_response.text[:5000],
            language="json"
        )

        st.stop()

    # -----------------------------------------------------
    # 원본 JSON
    # -----------------------------------------------------

    with st.expander(
        "🔍 실제 배당 JSON 원본",
        expanded=False
    ):

        st.json(
            odds_json
        )

    # -----------------------------------------------------
    # 배당 파싱
    # -----------------------------------------------------

    odds_list = parse_odds_json(
        odds_json
    )

    st.subheader(
        "⑤ 초기 / 최종 배당"
    )

    if not odds_list:

        st.warning(
            "배당 데이터가 없습니다."
        )

        st.stop()

    st.success(
        f"배당 업체 {len(odds_list)}개 발견"
    )

    # -----------------------------------------------------
    # DB 저장
    # -----------------------------------------------------

    try:

        save_to_database(
            match,
            odds_list
        )

        st.success(
            "✅ 경기 및 배당 데이터를 SQLite DB에 저장했습니다."
        )

    except Exception as e:

        st.error(
            f"DB 저장 오류: {e}"
        )

    # -----------------------------------------------------
    # 테이블
    # -----------------------------------------------------

    rows = []

    for odds in odds_list:

        probability = calculate_probability(

            odds["final_home"],

            odds["final_draw"],

            odds["final_away"]

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

            "승 확률":
                f"{probability[0]:.2f}%"
                if probability else "-",

            "무 확률":
                f"{probability[1]:.2f}%"
                if probability else "-",

            "패 확률":
                f"{probability[2]:.2f}%"
                if probability else "-",

            "실제 결과":
                match["result"]

        })

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# DB 저장 현황
# =========================================================

st.divider()

st.subheader(
    "📊 SQLite DB 저장 데이터"
)

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
# 저장된 경기
# =========================================================

matches = database.get_all_matches()

if matches:

    st.subheader(
        "📋 저장된 경기"
    )

    match_rows = []

    for match in matches:

        match_rows.append({

            "경기ID":
                match["schedule_id"],

            "날짜":
                match["match_date"],

            "홈팀":
                match["home_team"],

            "원정팀":
                match["away_team"],

            "스코어":
                (
                    f'{match["home_score"]} - '
                    f'{match["away_score"]}'
                    if
                    match["home_score"] is not None
                    and
                    match["away_score"] is not None
                    else "-"
                ),

            "결과":
                match["result"],

           "출처":
    match["source"] if "source" in match.keys() else "Scoreman"

        })

    st.dataframe(
        match_rows,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# 저장된 배당
# =========================================================

odds_rows = database.get_all_odds()

if odds_rows:

    st.subheader(
        "💰 저장된 배당"
    )

    display_odds = []

    for row in odds_rows:

        display_odds.append({

            "경기ID":
                row["schedule_id"],

            "업체":
                row["company_name"],

            "초기 승":
                row["initial_home"],

            "초기 무":
                row["initial_draw"],

            "초기 패":
                row["initial_away"],

            "최종 승":
                row["final_home"],

            "최종 무":
                row["final_draw"],

            "최종 패":
                row["final_away"]

        })

    st.dataframe(
        display_odds,
        use_container_width=True,
        hide_index=True
            )
st.divider()

st.header("📊 과거 배당 승무패 분석")

try:

    analysis_df = analysis.get_all_analysis_data()

    if analysis_df.empty:

        st.info(
            "아직 분석할 경기 데이터가 없습니다."
        )

    else:

        st.subheader("📌 전체 결과")

        stats = analysis.calculate_result_stats(
            analysis_df
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "승",
                f'{stats["승"]["percent"]}% '
                f'({stats["승"]["count"]}경기)'
            )

        with col2:

            st.metric(
                "무",
                f'{stats["무"]["percent"]}% '
                f'({stats["무"]["count"]}경기)'
            )

        with col3:

            st.metric(
                "패",
                f'{stats["패"]["percent"]}% '
                f'({stats["패"]["count"]}경기)'
            )


        st.subheader(
            "📈 초기 승배당 구간별 통계"
        )

        table = analysis.make_odds_range_table(
            analysis_df,
            side="home"
        )

        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True
        )


        st.subheader(
            "🏢 배당업체별 통계"
        )

        company_table = analysis.get_company_stats(
            analysis_df
        )

        st.dataframe(
            company_table,
            use_container_width=True,
            hide_index=True
        )


except Exception as e:

    st.error(
        "분석 오류"
    )

    st.code(
        str(e)
    )
# =========================================================
# 과거 경기 DB 구축
# =========================================================

st.divider()

st.header("🗄️ 과거 스코어맨 DB 구축")

st.caption(
    "경기 ID 범위를 입력하여 완료된 경기의 결과와 1X2 배당을 DB에 저장합니다."
)


# ---------------------------------------------------------
# build_database 불러오기
# ---------------------------------------------------------

try:

    from build_database import build_database_progress

except Exception as e:

    st.error(
        "build_database.py를 불러오지 못했습니다."
    )

    st.code(
        str(e)
    )

    st.stop()


# ---------------------------------------------------------
# 경기 ID 입력
# ---------------------------------------------------------

col1, col2 = st.columns(2)


with col1:

    history_start_id = st.number_input(
        "시작 경기 ID",
        min_value=1,
        value=2716480,
        step=1
    )


with col2:

    history_end_id = st.number_input(
        "마지막 경기 ID",
        min_value=1,
        value=2716500,
        step=1
    )


# ---------------------------------------------------------
# 예상 수집 개수
# ---------------------------------------------------------

total_ids = (
    history_end_id -
    history_start_id +
    1
)


if total_ids > 0:

    st.info(
        f"수집 대상 ID: {total_ids}개"
    )


# ---------------------------------------------------------
# 너무 많은 ID 방지
# ---------------------------------------------------------

if total_ids > 1000:

    st.warning(
        "⚠️ 한 번에 1,000개 이상 수집하지 않는 것을 권장합니다."
    )


# ---------------------------------------------------------
# 수집 버튼
# ---------------------------------------------------------

if st.button(
    "📥 과거 경기 DB 수집",
    type="primary",
    use_container_width=True
):

    # -----------------------------------------------------
    # ID 검사
    # -----------------------------------------------------

    if history_end_id < history_start_id:

        st.error(
            "마지막 경기 ID가 시작 경기 ID보다 작습니다."
        )

        st.stop()


    # -----------------------------------------------------
    # 진행률
    # -----------------------------------------------------

    progress = st.progress(
        0
    )


    # -----------------------------------------------------
    # 로그 표시
    # -----------------------------------------------------

    log_box = st.empty()

    logs = []


    def update_progress(value):

        value = min(
            max(
                float(value),
                0.0
            ),
            1.0
        )

        progress.progress(
            value
        )


    def update_log(message):

        logs.append(
            message
        )

        # 최근 30개만 화면에 표시
        log_box.code(
            "\n".join(
                logs[-30:]
            ),
            language="text"
        )


    # -----------------------------------------------------
    # DB 수집
    # -----------------------------------------------------

    with st.spinner(
        "스코어맨 과거 경기 데이터를 수집하고 있습니다..."
    ):

        try:

            result = build_database_progress(

                history_start_id,

                history_end_id,

                progress_callback=
                    update_progress,

                log_callback=
                    update_log,

                delay=0.5

            )

        except Exception as e:

            st.error(
                "과거 DB 수집 중 오류가 발생했습니다."
            )

            st.code(
                str(e)
            )

            st.stop()


    # -----------------------------------------------------
    # 완료
    # -----------------------------------------------------

    progress.progress(
        1.0
    )


    st.success(
        "✅ 과거 DB 수집이 완료되었습니다."
    )


    # -----------------------------------------------------
    # 결과
    # -----------------------------------------------------

    col1, col2, col3 = st.columns(3)


    with col1:

        st.metric(
            "저장 성공 경기",
            result.get(
                "success",
                0
            )
        )


    with col2:

        st.metric(
            "실패 / 건너뜀",
            result.get(
                "failed",
                0
            )
        )


    with col3:

        st.metric(
            "저장 배당 업체",
            result.get(
                "odds",
                0
            )
        )


    # -----------------------------------------------------
    # 현재 DB
    # -----------------------------------------------------

    st.subheader(
        "📊 현재 DB 현황"
    )


    col1, col2 = st.columns(2)


    with col1:

        st.metric(
            "전체 경기",
            database.get_match_count()
        )


    with col2:

        st.metric(
            "전체 배당",
            database.get_odds_count()
    )
