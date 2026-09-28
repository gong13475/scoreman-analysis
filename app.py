import streamlit as st
import requests
from bs4 import BeautifulSoup

from database import (
    create_database,
    get_database_status
)


# ==========================================
# 페이지 설정
# ==========================================

st.set_page_config(
    page_title="스코어맨 배당 분석",
    page_icon="⚽",
    layout="wide"
)


# ==========================================
# DB 생성
# ==========================================

create_database()


# ==========================================
# 제목
# ==========================================

st.title("⚽ 스코어맨 배당 분석")


# ==========================================
# DB 현황
# ==========================================

status = get_database_status()


col1, col2 = st.columns(2)


with col1:

    st.metric(
        "경기 데이터",
        f"{status['matches']:,}건"
    )


with col2:

    st.metric(
        "배당 데이터",
        f"{status['odds']:,}건"
    )


st.divider()


# ==========================================
# 스코어맨 HTML 확인
# ==========================================

st.subheader(
    "스코어맨 데이터 확인"
)


if st.button("스코어맨 경기 데이터 확인"):

    url = (
        "https://www.scoreman123.com/"
        "football/results"
    )

    headers = {

        "User-Agent":
        (
            "Mozilla/5.0 "
            "(Linux; Android 10) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0 "
            "Mobile Safari/537.36"
        )
    }


    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=30
        )


        st.write(
            "HTTP 상태:",
            response.status_code
        )


        st.write(
            "페이지 크기:",
            len(response.text)
        )


        # ======================================
        # HTML 분석
        # ======================================

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )


        # 모든 링크 찾기

        links = soup.find_all("a")


        st.write(
            "페이지 링크 수:",
            len(links)
        )


        # ======================================
        # 경기 관련 링크 검색
        # ======================================

        match_links = []


        for link in links:

            href = link.get(
                "href"
            )


            text = link.get_text(
                " ",
                strip=True
            )


            if not href:

                continue


            lower_href = href.lower()


            if (
                "match" in lower_href
                or
                "analysis" in lower_href
                or
                "football" in lower_href
            ):

                match_links.append({

                    "text": text,

                    "url": href

                })


        st.write(
            "경기 관련 링크:",
            len(match_links)
        )


        # ======================================
        # 최대 30개 표시
        # ======================================

        if match_links:

            st.success(
                "경기 관련 링크를 찾았습니다."
            )


            for item in match_links[:30]:

                st.write(
                    item["text"]
                )

                st.code(
                    item["url"]
                )


        else:

            st.warning(
                "HTML에서 경기 링크가 발견되지 않았습니다."
            )


        # ======================================
        # 페이지 텍스트 확인
        # ======================================

        st.subheader(
            "페이지 텍스트 일부"
        )


        page_text = soup.get_text(
            " ",
            strip=True
        )


        st.text(
            page_text[:5000]
        )


    except Exception as e:

        st.error(
            f"오류: {e}"
        )


st.divider()


# ==========================================
# 다음 단계
# ==========================================

st.info(
    "이 단계에서는 데이터를 DB에 저장하지 않습니다. "
    "먼저 실제 경기 링크와 페이지 구조를 확인합니다."
)
