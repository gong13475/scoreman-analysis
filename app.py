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
# ==========================================
# 실제 스코어맨 경기 테스트
# ==========================================

import requests
from bs4 import BeautifulSoup

st.divider()

st.subheader("실제 스코어맨 경기 테스트")

# ==========================================
# 실제 스코어맨 경기 구조 분석
# ==========================================

import requests
from bs4 import BeautifulSoup

st.divider()

st.subheader("실제 스코어맨 경기 구조 분석")


if st.button("스코어맨 경기 구조 분석"):

    url = (
        "https://www.scoreman123.com/"
        "match/data-2929675"
    )

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


        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )


        # ==================================
        # 1. 제목
        # ==================================

        if soup.title:

            st.subheader("페이지 제목")

            st.write(
                soup.title.get_text(
                    " ",
                    strip=True
                )
            )


        # ==================================
        # 2. 스크립트 개수
        # ==================================

        scripts = soup.find_all(
            "script"
        )


        st.subheader(
            "스크립트 분석"
        )


        st.write(
            "스크립트 개수:",
            len(scripts)
        )


        # ==================================
        # 3. 배당 관련 HTML 검색
        # ==================================

        keywords = [

            "Bet365",
            "SBOBET",
            "Pinnacle",
            "Macauslot",
            "Crown",
            "12BET",
            "18Bet",
            "First Odds",
            "Odds",
            "odds",
            "배당",
            "初盘",
            "终盘"

        ]


        found = []


        for keyword in keywords:

            count = response.text.count(
                keyword
            )

            if count > 0:

                found.append(
                    (
                        keyword,
                        count
                    )
                )


        st.subheader(
            "배당 관련 데이터 발견"
        )


        if found:

            for keyword, count in found:

                st.write(
                    f"**{keyword}** : "
                    f"{count}회"
                )

        else:

            st.warning(
                "배당 관련 키워드를 찾지 못했습니다."
            )


        # ==================================
        # 4. 경기 관련 키워드
        # ==================================

        match_keywords = [

            "강원",
            "부천",
            "0-3",
            "0 : 3",
            "2026-08-01",
            "19:30"

        ]


        st.subheader(
            "경기 정보 발견 여부"
        )


        for keyword in match_keywords:

            count = response.text.count(
                keyword
            )

            st.write(
                f"{keyword}: {count}회"
            )


        # ==================================
        # 5. 경기 페이지 텍스트
        # ==================================

        page_text = soup.get_text(
            " ",
            strip=True
        )


        st.subheader(
            "경기 페이지 텍스트"
        )


        st.text(
            page_text[:10000]
        )


    except Exception as e:

        st.error(
            f"오류: {e}"
    )
# ==========================================
# 실제 배당 원본 확인
# ==========================================

import requests
from bs4 import BeautifulSoup


st.divider()

st.subheader("실제 스코어맨 배당 원본 분석")


if st.button("초기/최종 배당 원본 확인"):

    url = (
        "https://www.scoreman123.com/"
        "match/data-2929675"
    )

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

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        html = response.text


        # ==================================
        # 배당 관련 키워드
        # ==================================

        keywords = [
            "Bet365",
            "Pinnacle",
            "Macauslot",
            "Crown",
            "18Bet",
            "First Odds",
            "firstOdds",
            "initial",
            "Initial",
            "初盘",
            "终盘",
            "初始",
            "即时",
            "Final",
            "final"
        ]


        st.subheader(
            "배당 관련 원본 위치"
        )


        # ==================================
        # 키워드 주변 HTML 표시
        # ==================================

        for keyword in keywords:

            position = html.find(
                keyword
            )

            if position == -1:

                continue


            st.write(
                f"### {keyword}"
            )


            start = max(
                0,
                position - 1500
            )


            end = min(
                len(html),
                position + 3000
            )


            context = html[
                start:end
            ]


            st.code(
                context,
                language="html"
            )


        # ==================================
        # 페이지 텍스트
        # ==================================

        text = soup.get_text(
            " ",
            strip=True
        )


        st.subheader(
            "배당 페이지 텍스트"
        )


        # 배당이라는 단어 주변 표시

        position = text.find(
            "배당"
        )


        if position >= 0:

            start = max(
                0,
                position - 2000
            )

            end = min(
                len(text),
                position + 5000
            )

            st.text(
                text[start:end]
            )

        else:

            st.warning(
                "배당 텍스트 위치를 찾지 못했습니다."
            )


    except Exception as e:

        st.error(
            f"오류: {e}"
        )
# ==========================================
# 스코어맨 배당 JavaScript 분석
# ==========================================

import re


st.divider()

st.subheader(
    "스코어맨 배당 요청 분석"
)


if st.button(
    "배당 요청 주소 찾기"
):

    url = (
        "https://www.scoreman123.com/"
        "match/data-2929675"
    )

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


    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=30
        )


        html = response.text


        # ==================================
        # callOddsDetailWin 위치
        # ==================================

        keyword = (
            "callOddsDetailWin"
        )


        positions = [
            m.start()
            for m in re.finditer(
                keyword,
                html
            )
        ]


        st.write(
            "callOddsDetailWin 발견:",
            len(positions)
        )


        # ==================================
        # 함수 주변 HTML
        # ==================================

        for index, position in enumerate(
            positions[:5]
        ):

            st.write(
                f"### 발견 {index + 1}"
            )


            start = max(
                0,
                position - 1000
            )


            end = min(
                len(html),
                position + 5000
            )


            st.code(
                html[start:end],
                language="html"
            )


        # ==================================
        # JavaScript 파일
        # ==================================

        scripts = re.findall(

            r'<script[^>]+src=["\']'
            r'([^"\']+)',

            html,

            re.I

        )


        st.write(
            "JavaScript 파일:",
            len(scripts)
        )


        for script in scripts:

            lower = script.lower()


            if (
                "odds" in lower
                or
                "match" in lower
                or
                "data" in lower
            ):

                st.code(
                    script
                )


    except Exception as e:

        st.error(
            f"오류: {e}"
        )
