import streamlit as st
import requests
import json
import re
import pandas as pd

from database import (
    init_db,
    save_match,
    save_odds,
    get_match_count,
    get_odds_count,
    get_all_matches,
    get_all_odds,
    clear_database
)


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="스코어맨 배당 분석",
    page_icon="⚽",
    layout="wide"
)

init_db()


# =========================================================
# 스코어맨 기본 설정
# =========================================================

BASE_URL = "https://www.scoreman123.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Linux; Android 10) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 "
        "Mobile Safari/537.36"
    ),
    "Referer": BASE_URL + "/",
    "Accept": "*/*"
}


# =========================================================
# 제목
# =========================================================

st.title("⚽ 스코어맨 배당 분석")

st.caption(
    "스코어맨 경기 → 초기배당 → 최종배당 → 경기결과 → SQLite DB"
)


# =========================================================
# DB 현황
# =========================================================

match_count = get_match_count()
odds_count = get_odds_count()

c1, c2 = st.columns(2)

with c1:
    st.metric(
        "경기 데이터",
        match_count
    )

with c2:
    st.metric(
        "배당 데이터",
        odds_count
    )


st.divider()


# =========================================================
# 경기 ID 입력
# =========================================================

st.subheader("① 스코어맨 경기")

schedule_id = st.text_input(
    "스코어맨 경기 ID",
    value="2929675"
).strip()


if schedule_id:

    match_url = (
        f"{BASE_URL}/match/data-{schedule_id}"
    )

    st.write(
        "경기 페이지:",
        match_url
    )


# =========================================================
# 스코어맨 경기 페이지 가져오기
# =========================================================

def get_match_page(schedule_id):

    url = (
        f"{BASE_URL}/match/data-{schedule_id}"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    return response


# =========================================================
# 경기 정보 추출
# =========================================================

def parse_match_info(html):

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
    # 홈팀 / 원정팀
    # -----------------------------------------------------

    home_team = ""
    away_team = ""

    # 일반적인 Scoreman title 구조
    title_team = re.search(
        r"([^|<>]+?)\s+vs\s+([^|<>]+?)\s+(?:실시간|live|Live)",
        title,
        re.I
    )

    if title_team:

        home_team = title_team.group(1).strip()
        away_team = title_team.group(2).strip()


    # -----------------------------------------------------
    # 제목에서 못 찾았을 경우 HTML 검색
    # -----------------------------------------------------

    if not home_team or not away_team:

        patterns = [
            r'homeName["\']?\s*[:=]\s*["\']([^"\']+)',
            r'home["\']?\s*[:=]\s*["\']([^"\']+)',
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


    if not away_team:

        patterns = [
            r'guestName["\']?\s*[:=]\s*["\']([^"\']+)',
            r'away["\']?\s*[:=]\s*["\']([^"\']+)',
            r'guest["\']?\s*[:=]\s*["\']([^"\']+)'
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
    # 스코어
    # -----------------------------------------------------

    home_score = None
    away_score = None

    score_patterns = [
        r'["\']?homeScore["\']?\s*[:=]\s*["\']?(\d+)',
        r'["\']?home_score["\']?\s*[:=]\s*["\']?(\d+)'
    ]

    for pattern in score_patterns:

        m = re.search(
            pattern,
            html,
            re.I
        )

        if m:
            home_score = int(m.group(1))
            break


    score_patterns = [
        r'["\']?awayScore["\']?\s*[:=]\s*["\']?(\d+)',
        r'["\']?away_score["\']?\s*[:=]\s*["\']?(\d+)'
    ]

    for pattern in score_patterns:

        m = re.search(
            pattern,
            html,
            re.I
        )

        if m:
            away_score = int(m.group(1))
            break


    # -----------------------------------------------------
    # 실제 페이지에서 0-1 / 0-3 형태의 점수 찾기
    # -----------------------------------------------------

    if home_score is None or away_score is None:

        score_candidates = re.findall(
            r'(?<!\d)(\d{1,2})\s*[-:]\s*(\d{1,2})(?!\d)',
            html
        )

        for a, b in score_candidates:

            a = int(a)
            b = int(b)

            if a <= 20 and b <= 20:

                home_score = a
                away_score = b

                break


    # -----------------------------------------------------
    # 결과
    # -----------------------------------------------------

    result = ""

    if home_score is not None and away_score is not None:

        if home_score > away_score:
            result = "승"

        elif home_score == away_score:
            result = "무"

        else:
            result = "패"


    return {
        "title": title,
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
        "result": result
    }


# =========================================================
# 실제 스코어맨 배당 API
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

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    return url, response


# =========================================================
# 업체 이름
# =========================================================

COMPANY_NAMES = {
    1: "Macauslot",
    3: "Crown",
    8: "Bet365",
    12: "12Bet",
    14: "M88",
    17: "Easybet",
    19: "Interwetten",
    23: "18Bet",
    24: "Vcbet",
    31: "Sbobet",
    42: "1xBet",
    47: "Pinnacle"
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

    except:

        return None


# =========================================================
# JSON에서 승무패 배당 추출
# =========================================================

def parse_odds_json(data):

    result = []

    if not isinstance(data, dict):
        return result


    data_section = data.get(
        "Data",
        {}
    )

    mixodds = data_section.get(
        "mixodds",
        []
    )


    if not isinstance(mixodds, list):
        return result


    for item in mixodds:

        if not isinstance(item, dict):
            continue


        cid = item.get("cid")

        try:
            cid = int(cid)
        except:
            continue


        company_name = COMPANY_NAMES.get(
            cid,
            f"회사 {cid}"
        )


        euro = item.get(
            "euro",
            {}
        )


        if not isinstance(euro, dict):
            euro = {}


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


        result.append({
            "company_id": cid,
            "company_name": company_name,

            "initial_home": initial_home,
            "initial_draw": initial_draw,
            "initial_away": initial_away,

            "final_home": final_home,
            "final_draw": final_draw,
            "final_away": final_away
        })


    return result


# =========================================================
# 경기 데이터 불러오기
# =========================================================

if st.button(
    "🔎 스코어맨 경기 불러오기",
    type="primary"
):

    if not schedule_id:

        st.error(
            "스코어맨 경기 ID를 입력하세요."
        )

        st.stop()


    # -----------------------------------------------------
    # 경기 페이지
    # -----------------------------------------------------

    st.subheader(
        "② 경기 페이지"
    )

    try:

        response = get_match_page(
            schedule_id
        )

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
                "스코어맨 경기 페이지 접속 실패"
            )

            st.stop()


        html = response.text


        st.success(
            "스코어맨 경기 페이지 접속 성공"
        )


    except Exception as e:

        st.error(
            f"경기 페이지 오류: {e}"
        )

        st.stop()


    # -----------------------------------------------------
    # 경기 정보
    # -----------------------------------------------------

    info = parse_match_info(
        html
    )


    st.subheader(
        "③ 경기 정보"
    )


    st.write(
        "홈팀:",
        info["home_team"]
    )

    st.write(
        "원정팀:",
        info["away_team"]
    )


    if (
        info["home_score"] is not None
        and
        info["away_score"] is not None
    ):

        st.write(
            "최종 스코어:",
            f"{info['home_score']} - "
            f"{info['away_score']}"
        )

        st.write(
            "결과:",
            info["result"]
        )

    else:

        st.warning(
            "최종 스코어를 자동으로 찾지 못했습니다."
        )


    # -----------------------------------------------------
    # 실제 배당 API
    # -----------------------------------------------------

    st.subheader(
        "④ 실제 스코어맨 배당 API"
    )


    odds_url, odds_response = get_scoreman_odds(
        schedule_id
    )


    st.write(
        "요청 URL:",
        odds_url
    )

    st.write(
        "API HTTP:",
        odds_response.status_code
    )

    st.write(
        "API 응답 크기:",
        len(odds_response.text)
    )


    # -----------------------------------------------------
    # JSON 분석
    # -----------------------------------------------------

    odds_data = None

    try:

        odds_data = odds_response.json()

    except Exception:

        try:

            odds_data = json.loads(
                odds_response.text
            )

        except:

            odds_data = None


    if odds_data is None:

        st.error(
            "배당 API가 JSON으로 반환되지 않았습니다."
        )

        st.code(
            odds_response.text[:5000]
        )

        st.stop()


    # -----------------------------------------------------
    # JSON 원본
    # -----------------------------------------------------

    with st.expander(
        "🔍 실제 배당 JSON 원본"
    ):

        st.json(
            odds_data
        )


    # -----------------------------------------------------
    # 배당 추출
    # -----------------------------------------------------

    odds_list = parse_odds_json(
        odds_data
    )


    st.subheader(
        "⑤ 초기 / 최종 배당"
    )


    st.write(
        "배당 업체:",
        len(odds_list)
    )


    if len(odds_list) == 0:

        st.warning(
            "JSON에서 승무패 배당을 찾지 못했습니다."
        )

        st.write(
            "JSON 최상위 구조:"
        )

        st.write(
            odds_data
        )

    else:

        df = pd.DataFrame(
            odds_list
        )


        display_df = df.rename(
            columns={
                "company_id": "업체ID",
                "company_name": "업체",

                "initial_home": "초기승",
                "initial_draw": "초기무",
                "initial_away": "초기패",

                "final_home": "최종승",
                "final_draw": "최종무",
                "final_away": "최종패"
            }
        )


        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )


    # -----------------------------------------------------
    # DB 저장
    # -----------------------------------------------------

    st.subheader(
        "⑥ SQLite DB 저장"
    )


    try:

        save_match(
            schedule_id=schedule_id,
            sport="축구",
            league="",
            match_date="",
            home_team=info["home_team"],
            away_team=info["away_team"],
            home_score=info["home_score"],
            away_score=info["away_score"],
            result=info["result"],
            source="Scoreman"
        )


        saved = 0


        for item in odds_list:

            save_odds(
                schedule_id=schedule_id,

                company_id=item[
                    "company_id"
                ],

                company_name=item[
                    "company_name"
                ],

                initial_home=item[
                    "initial_home"
                ],

                initial_draw=item[
                    "initial_draw"
                ],

                initial_away=item[
                    "initial_away"
                ],

                final_home=item[
                    "final_home"
                ],

                final_draw=item[
                    "final_draw"
                ],

                final_away=item[
                    "final_away"
                ],

                result=info["result"]
            )

            saved += 1


        st.success(
            f"DB 저장 완료: 경기 1건 / "
            f"배당 {saved}건"
        )


    except Exception as e:

        st.error(
            f"DB 저장 오류: {e}"
        )


# =========================================================
# 저장된 데이터 확인
# =========================================================

st.divider()

st.subheader(
    "⑦ 저장된 DB 데이터"
)


tab1, tab2 = st.tabs(
    [
        "경기 데이터",
        "배당 데이터"
    ]
)


with tab1:

    matches = get_all_matches()

    if matches:

        df_matches = pd.DataFrame(
            matches,
            columns=[
                "경기ID",
                "종목",
                "리그",
                "경기일",
                "홈팀",
                "원정팀",
                "홈점수",
                "원정점수",
                "결과",
                "출처"
            ]
        )

        st.dataframe(
            df_matches,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "저장된 경기 데이터가 없습니다."
        )


with tab2:

    odds = get_all_odds()

    if odds:

        df_odds = pd.DataFrame(
            odds,
            columns=[
                "경기ID",
                "업체ID",
                "업체",

                "초기승",
                "초기무",
                "초기패",

                "최종승",
                "최종무",
                "최종패",

                "결과"
            ]
        )

        st.dataframe(
            df_odds,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "저장된 배당 데이터가 없습니다."
        )


# =========================================================
# DB 초기화
# =========================================================

st.divider()

with st.expander(
    "⚠️ DB 관리"
):

    st.warning(
        "DB 초기화 시 지금까지 저장된 "
        "경기 및 배당 데이터가 모두 삭제됩니다."
    )


    if st.button(
        "DB 전체 삭제"
    ):

        clear_database()

        st.success(
            "DB를 초기화했습니다."
        )

        st.rerun()
