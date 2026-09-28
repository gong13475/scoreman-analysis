import streamlit as st
import requests
import json
import re
import pandas as pd

from bs4 import BeautifulSoup

from database import (
    create_database,
    save_match,
    save_odds,
    get_match_count,
    get_odds_count,
    get_all_data
)


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="스코어맨 배당 분석",
    page_icon="⚽",
    layout="wide"
)

create_database()


# =========================================================
# 제목
# =========================================================

st.title("⚽ 스코어맨 배당 분석")

st.caption(
    "스코어맨 경기 → 초기배당 → 최종배당 → 경기결과 → SQLite DB"
)


# =========================================================
# 현재 DB 상태
# =========================================================

col1, col2 = st.columns(2)

with col1:
    st.metric(
        "경기 데이터",
        get_match_count()
    )

with col2:
    st.metric(
        "배당 데이터",
        get_odds_count()
    )


st.divider()


# =========================================================
# 경기 ID 입력
# =========================================================

st.subheader("① 스코어맨 경기")

scoreman_id = st.text_input(
    "스코어맨 경기 ID",
    value="2929675"
).strip()


if not scoreman_id.isdigit():

    st.warning(
        "스코어맨 경기 ID를 입력하세요."
    )

    st.stop()


match_url = (
    "https://www.scoreman123.com/"
    f"match/data-{scoreman_id}"
)


st.write(
    "경기 페이지:",
    match_url
)


# =========================================================
# 공통 요청 헤더
# =========================================================

headers = {

    "User-Agent":
        "Mozilla/5.0 "
        "(Linux; Android 10) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 "
        "Mobile Safari/537.36",

    "Referer":
        match_url,

    "Accept":
        "*/*"

}


# =========================================================
# 경기 페이지 가져오기
# =========================================================

def get_match_page():

    response = requests.get(
        match_url,
        headers=headers,
        timeout=30
    )

    return response


# =========================================================
# 경기 정보 추출
# =========================================================

def parse_match_info(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    text = soup.get_text(
        " ",
        strip=True
    )

    home_team = ""
    away_team = ""

    # -----------------------------------------------------
    # 실제 페이지에서 흔히 발견되는 팀명 패턴
    # -----------------------------------------------------

    patterns = [

        r'홈팀["\']?\s*[:：]\s*([^<\n]+)',

        r'원정팀["\']?\s*[:：]\s*([^<\n]+)'

    ]

    # -----------------------------------------------------
    # 강원 / 부천 같은 실제 경기명을 우선 탐색
    # -----------------------------------------------------

    title = soup.title.get_text(
        " ",
        strip=True
    ) if soup.title else ""

    m = re.search(
        r'(.+?)\s+vs\s+(.+?)\s+실시간',
        title
    )

    if m:

        home_team = m.group(1).strip()
        away_team = m.group(2).strip()


    # -----------------------------------------------------
    # 점수 찾기
    # -----------------------------------------------------

    home_score = None
    away_score = None

    score_patterns = [

        r'(\d+)\s*-\s*(\d+)',

        r'(\d+)\s*:\s*(\d+)'

    ]

    for pattern in score_patterns:

        matches = re.findall(
            pattern,
            text
        )

        if matches:

            # 실제 페이지의 대표 점수
            for a, b in matches:

                try:

                    aa = int(a)
                    bb = int(b)

                    if aa <= 20 and bb <= 20:

                        home_score = aa
                        away_score = bb

                        break

                except:

                    pass

        if home_score is not None:
            break


    # -----------------------------------------------------
    # 결과 계산
    # -----------------------------------------------------

    result = ""

    if (
        home_score is not None
        and away_score is not None
    ):

        if home_score > away_score:

            result = "승"

        elif home_score < away_score:

            result = "패"

        else:

            result = "무"


    return {

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
# 스코어맨 실제 API 호출
# =========================================================

def get_odds_api():

    url = (
        "https://www.scoreman123.com/"
        "ajax/soccerajax"
    )

    params = {

        "type": "14",

        "t": "1",

        "id": scoreman_id,

        "h": "0"

    }

    response = requests.get(

        url,

        params=params,

        headers=headers,

        timeout=30

    )

    return response


# =========================================================
# JSON 분석
# =========================================================

def parse_odds_json(data):

    result = []

    if not isinstance(
        data,
        dict
    ):

        return result


    # -----------------------------------------------------
    # Data
    # -----------------------------------------------------

    data_obj = data.get(
        "Data",
        {}
    )

    if not isinstance(
        data_obj,
        dict
    ):

        return result


    # -----------------------------------------------------
    # mixodds
    # -----------------------------------------------------

    mixodds = data_obj.get(
        "mixodds",
        []
    )

    if not isinstance(
        mixodds,
        list
    ):

        return result


    # -----------------------------------------------------
    # 업체별 데이터
    # -----------------------------------------------------

    for item in mixodds:

        if not isinstance(
            item,
            dict
        ):

            continue


        cid = item.get(
            "cid"
        )


        # -------------------------------------------------
        # 승무패 = euro
        # -------------------------------------------------

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


        # -------------------------------------------------
        # u = 홈승
        # g = 무
        # d = 원정승
        # -------------------------------------------------

        initial_home = initial.get(
            "u"
        )

        initial_draw = initial.get(
            "g"
        )

        initial_away = initial.get(
            "d"
        )


        final_home = final.get(
            "u"
        )

        final_draw = final.get(
            "g"
        )

        final_away = final.get(
            "d"
        )


        # -------------------------------------------------
        # 숫자 변환
        # -------------------------------------------------

        def to_float(value):

            try:

                return float(value)

            except:

                return None


        initial_home = to_float(
            initial_home
        )

        initial_draw = to_float(
            initial_draw
        )

        initial_away = to_float(
            initial_away
        )

        final_home = to_float(
            final_home
        )

        final_draw = to_float(
            final_draw
        )

        final_away = to_float(
            final_away
        )


        # -------------------------------------------------
        # 데이터가 하나라도 있으면 저장 후보
        # -------------------------------------------------

        if any([

            initial_home,
            initial_draw,
            initial_away,
            final_home,
            final_draw,
            final_away

        ]):

            result.append({

                "cid":
                    cid,

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
# 업체 CID 이름
# =========================================================

COMPANY_NAMES = {

    1: "Macauslot",

    3: "Crown",

    8: "Bet365",

    12: "18Bet",

    14: "12Bet",

    17: "Ladbrokes",

    19: "WilliamHill",

    23: "Easybets",

    24: "SBOBET",

    31: "Sbobet",

    42: "Pinnacle",

    47: "Pinnacle"

}


def get_company_name(cid):

    try:

        cid_int = int(cid)

        return COMPANY_NAMES.get(
            cid_int,
            f"회사ID-{cid}"
        )

    except:

        return f"회사ID-{cid}"


# =========================================================
# 실행 버튼
# =========================================================

if st.button(
    "🔎 스코어맨 경기 + 배당 가져오기",
    type="primary"
):

    # =====================================================
    # 경기 페이지
    # =====================================================

    with st.spinner(
        "스코어맨 경기 페이지를 가져오는 중..."
    ):

        try:

            page_response = (
                get_match_page()
            )

        except Exception as e:

            st.error(
                f"경기 페이지 오류: {e}"
            )

            st.stop()


    st.subheader("② 경기 페이지")

    st.write(
        "HTTP 상태:",
        page_response.status_code
    )

    st.write(
        "HTML 크기:",
        len(page_response.text)
    )


    if page_response.status_code != 200:

        st.error(
            "스코어맨 경기 페이지 접속 실패"
        )

        st.stop()


    # =====================================================
    # 경기정보
    # =====================================================

    match_info = parse_match_info(
        page_response.text
    )


    st.subheader(
        "③ 경기 정보"
    )


    c1, c2 = st.columns(2)

    with c1:

        st.write(
            "홈팀:",
            match_info["home_team"]
        )

        st.write(
            "원정팀:",
            match_info["away_team"]
        )


    with c2:

        st.write(
            "최종 스코어:",
            f'{match_info["home_score"]}'
            f' - '
            f'{match_info["away_score"]}'
        )

        st.write(
            "결과:",
            match_info["result"]
        )


    # =====================================================
    # 실제 API
    # =====================================================

    st.subheader(
        "④ 실제 스코어맨 배당 API"
    )


    with st.spinner(
        "실제 배당 JSON을 가져오는 중..."
    ):

        try:

            odds_response = (
                get_odds_api()
            )

        except Exception as e:

            st.error(
                f"배당 API 오류: {e}"
            )

            st.stop()


    st.write(
        "API HTTP:",
        odds_response.status_code
    )

    st.write(
        "API 응답 크기:",
        len(odds_response.text)
    )


    if odds_response.status_code != 200:

        st.error(
            "배당 API 요청 실패"
        )

        st.stop()


    # =====================================================
    # JSON
    # =====================================================

    try:

        odds_json = (
            odds_response.json()
        )

    except Exception:

        st.error(
            "배당 응답을 JSON으로 변환하지 못했습니다."
        )

        st.code(
            odds_response.text[:5000]
        )

        st.stop()


    # =====================================================
    # API 오류 코드
    # =====================================================

    if odds_json.get("code") not in (
        None,
        0
    ):

        st.warning(
            f'스코어맨 API 코드: '
            f'{odds_json.get("code")}'
        )


    # =====================================================
    # 배당 추출
    # =====================================================

    odds_list = parse_odds_json(
        odds_json
    )


    st.write(
        "추출된 배당 업체:",
        len(odds_list)
    )


    # =====================================================
    # JSON 구조 확인
    # =====================================================

    with st.expander(
        "🔍 실제 JSON 원본 확인"
    ):

        st.json(
            odds_json
        )


    # =====================================================
    # 배당표
    # =====================================================

    if odds_list:

        rows = []

        for item in odds_list:

            rows.append({

                "업체":
                    get_company_name(
                        item["cid"]
                    ),

                "CID":
                    item["cid"],

                "초기 승":
                    item["initial_home"],

                "초기 무":
                    item["initial_draw"],

                "초기 패":
                    item["initial_away"],

                "최종 승":
                    item["final_home"],

                "최종 무":
                    item["final_draw"],

                "최종 패":
                    item["final_away"]

            })


        df = pd.DataFrame(
            rows
        )


        st.subheader(
            "⑤ 초기 / 최종 배당"
        )

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )


        # =================================================
        # DB 저장
        # =================================================

        st.subheader(
            "⑥ SQLite DB 저장"
        )


        save_match(

            scoreman_id,

            "",

            match_info["home_team"],

            match_info["away_team"],

            match_info["home_score"],

            match_info["away_score"],

            match_info["result"]

        )


        saved_count = 0


        for item in odds_list:

            save_odds(

                scoreman_id,

                get_company_name(
                    item["cid"]
                ),

                item["initial_home"],

                item["initial_draw"],

                item["initial_away"],

                item["final_home"],

                item["final_draw"],

                item["final_away"]

            )

            saved_count += 1


        st.success(
            f"DB 저장 완료: "
            f"{saved_count}개 업체"
        )


    else:

        st.warning(
            "승무패 배당 데이터를 찾지 못했습니다."
        )


# =========================================================
# DB 전체 조회
# =========================================================

st.divider()

st.subheader(
    "📊 현재 DB 저장 데이터"
)


if st.button(
    "DB 데이터 새로고침"
):

    rows = get_all_data()

    if rows:

        columns = [

            "경기ID",

            "경기일",

            "홈팀",

            "원정팀",

            "홈점수",

            "원정점수",

            "결과",

            "업체",

            "초기승",

            "초기무",

            "초기패",

            "최종승",

            "최종무",

            "최종패"

        ]

        db_df = pd.DataFrame(
            rows,
            columns=columns
        )

        st.dataframe(
            db_df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "아직 DB에 저장된 데이터가 없습니다."
        )
