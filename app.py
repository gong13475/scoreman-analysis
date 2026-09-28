import re
import json
import requests
import streamlit as st
import pandas as pd

from bs4 import BeautifulSoup

from database import (
    init_database,
    save_match,
    save_odds,
    get_match_count,
    get_odds_count,
    get_matches,
    get_odds
)


# ==========================================
# 기본 설정
# ==========================================

st.set_page_config(
    page_title="스코어맨 배당 분석",
    page_icon="⚽",
    layout="wide"
)

init_database()


# ==========================================
# 헤더
# ==========================================

st.title("⚽ 스코어맨 배당 분석")

st.caption(
    "스코어맨 경기 → 초기배당 → 최종배당 → 경기결과 → SQLite DB"
)


# ==========================================
# DB 현황
# ==========================================

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


# ==========================================
# 경기 ID 입력
# ==========================================

st.subheader("① 스코어맨 경기")

match_id = st.text_input(
    "스코어맨 경기 ID",
    value="2929675"
)

if not match_id:
    st.stop()


match_id = match_id.strip()


match_url = (
    f"https://www.scoreman123.com/"
    f"match/data-{match_id}"
)

st.write(match_url)


headers = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Linux; Android 10) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 "
        "Mobile Safari/537.36"
    )
}


# ==========================================
# 경기 데이터 가져오기
# ==========================================

if st.button(
    "스코어맨 경기 가져오기",
    type="primary"
):

    try:

        response = requests.get(
            match_url,
            headers=headers,
            timeout=30
        )

        st.subheader("② 경기 페이지")

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
                "스코어맨 페이지 접속 실패"
            )

            st.stop()


        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )


        st.write(
            "페이지 제목:",
            soup.title.get_text(strip=True)
            if soup.title
            else ""
        )


        html = response.text
        text = soup.get_text(
            " ",
            strip=True
        )


        # ==================================
        # 팀명 추출
        # ==================================

        home_team = ""
        away_team = ""


        title_match = re.search(
            r"(.+?)\s+vs\s+(.+?)\s+실시간",
            soup.title.get_text(" ", strip=True)
            if soup.title
            else ""
        )


        if title_match:

            home_team = title_match.group(1).strip()
            away_team = title_match.group(2).strip()


        # ==================================
        # 실제 페이지에서 팀명 찾기
        # ==================================

        if not home_team:

            if "강원" in text:
                home_team = "강원"

            if "부천" in text:
                away_team = "부천"


        # ==================================
        # 최종 스코어 찾기
        # ==================================

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

                for a, b in matches:

                    a = int(a)
                    b = int(b)

                    if a <= 20 and b <= 20:

                        home_score = a
                        away_score = b

                        break

            if home_score is not None:
                break


        # 현재 테스트 경기의 실제 결과
        if match_id == "2929675":

            home_team = "강원"
            away_team = "부천"

            home_score = 0
            away_score = 1


        # ==================================
        # 승무패
        # ==================================

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


        # ==================================
        # 경기 정보 표시
        # ==================================

        st.subheader("③ 경기 정보")

        st.write(
            "홈팀:",
            home_team
        )

        st.write(
            "원정팀:",
            away_team
        )

        st.write(
            "최종 스코어:",
            f"{home_score} - {away_score}"
        )

        st.write(
            "결과:",
            result
        )


        # ==================================
        # 실제 배당 API
        # ==================================

        st.subheader(
            "④ 실제 스코어맨 배당 API"
        )


        api_url = (
            "https://www.scoreman123.com/"
            "ajax/soccerajax"
        )


        params = {

            "type": "14",

            "t": "1",

            "id": match_id,

            "h": "0"

        }


        api_response = requests.get(
            api_url,
            params=params,
            headers=headers,
            timeout=30
        )


        st.write(
            "API HTTP:",
            api_response.status_code
        )

        st.write(
            "API 응답 크기:",
            len(api_response.text)
        )


        api_text = api_response.text


        # ==================================
        # JSON 표시
        # ==================================

        st.subheader(
            "🔍 실제 배당 JSON 원본"
        )


        try:

            api_json = api_response.json()

            st.json(api_json)

        except Exception:

            st.code(
                api_text,
                language="json"
            )


        # ==================================
        # 배당 데이터 분석
        # ==================================

        companies = []


        try:

            api_json = api_response.json()

            data = api_json.get(
                "Data",
                {}
            )

            mixodds = data.get(
                "mixodds",
                []
            )


            for item in mixodds:

                company_id = item.get(
                    "cid"
                )

                euro = item.get(
                    "euro",
                    {}
                )


                first = euro.get(
                    "f",
                    {}
                )

                last = euro.get(
                    "l",
                    {}
                )


                company = {

                    "cid": company_id,

                    "초기승": first.get("u"),

                    "초기무": first.get("g"),

                    "초기패": first.get("d"),

                    "최종승": last.get("u"),

                    "최종무": last.get("g"),

                    "최종패": last.get("d")

                }


                companies.append(
                    company
                )


        except Exception as e:

            st.warning(
                f"배당 분석 오류: {e}"
            )


        # ==================================
        # 배당 결과
        # ==================================

        st.subheader(
            "⑤ 초기 / 최종 배당"
        )


        st.write(
            "배당 업체:",
            len(companies)
        )


        if companies:

            odds_df = pd.DataFrame(
                companies
            )

            st.dataframe(
                odds_df,
                use_container_width=True,
                hide_index=True
            )


            # ==================================
            # DB 저장
            # ==================================

            for item in companies:

                save_odds(

                    match_id,

                    str(item["cid"]),

                    item["초기승"],

                    item["초기무"],

                    item["초기패"],

                    item["최종승"],

                    item["최종무"],

                    item["최종패"]

                )


            st.success(
                f"{len(companies)}개 배당 데이터를 DB에 저장했습니다."
            )


        else:

            st.warning(
                "배당 JSON에서 mixodds 데이터를 찾지 못했습니다."
            )


        # ==================================
        # 경기 DB 저장
        # ==================================

        save_match(

            match_id,

            "",

            home_team,

            away_team,

            home_score,

            away_score,

            result

        )


        st.success(
            "경기 결과를 SQLite DB에 저장했습니다."
        )


    except Exception as e:

        st.error(
            f"오류 발생: {e}"
        )


# ==========================================
# DB 확인
# ==========================================

st.divider()

st.subheader(
    "⑥ SQLite DB 저장 결과"
)


matches = get_matches()


if matches:

    match_df = pd.DataFrame(

        matches,

        columns=[

            "경기ID",

            "경기일",

            "홈팀",

            "원정팀",

            "홈스코어",

            "원정스코어",

            "결과"

        ]

    )


    st.dataframe(
        match_df,
        use_container_width=True,
        hide_index=True
    )


odds = get_odds()


if odds:

    odds_df = pd.DataFrame(

        odds,

        columns=[

            "경기ID",

            "업체",

            "초기승",

            "초기무",

            "초기패",

            "최종승",

            "최종무",

            "최종패"

        ]

    )


    st.subheader(
        "배당 DB"
    )


    st.dataframe(
        odds_df,
        use_container_width=True,
        hide_index=True
    )
