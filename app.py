import streamlit as st
import requests
import re

from bs4 import BeautifulSoup
from urllib.parse import urljoin

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

st.title(
    "⚽ 스코어맨 배당 분석"
)


# ==========================================
# DB 현황
# ==========================================

try:

    status = get_database_status()

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "경기 데이터",
            status.get("matches", 0)
        )

    with col2:

        st.metric(
            "배당 데이터",
            status.get("odds", 0)
        )

except Exception as e:

    st.warning(
        f"DB 상태 확인 실패: {e}"
    )


# ==========================================
# 안내
# ==========================================

st.info(
    "이 단계에서는 데이터를 DB에 저장하지 않습니다. "
    "먼저 실제 경기 링크와 페이지 구조를 확인합니다."
)


# ==========================================
# 공통 설정
# ==========================================

SCOREMAN_URL = (
    "https://www.scoreman123.com/"
    "match/data-2929675"
)


HEADERS = {

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
# 실제 스코어맨 경기 테스트
# ==========================================

st.divider()

st.subheader(
    "실제 스코어맨 경기 테스트"
)


if st.button(
    "강원 vs 부천 데이터 가져오기"
):

    try:

        response = requests.get(
            SCOREMAN_URL,
            headers=HEADERS,
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


        page_text = soup.get_text(
            " ",
            strip=True
        )


        st.subheader(
            "가져온 경기 데이터"
        )


        st.text(
            page_text[:8000]
        )


        if response.status_code == 200:

            st.success(
                "실제 스코어맨 경기 페이지 접속 성공"
            )

        else:

            st.error(
                "경기 페이지 접속 실패"
            )


    except Exception as e:

        st.error(
            f"오류 발생: {e}"
        )


# ==========================================
# 실제 스코어맨 경기 구조 분석
# ==========================================

st.divider()

st.subheader(
    "실제 스코어맨 경기 구조 분석"
)


if st.button(
    "스코어맨 경기 구조 분석"
):

    try:

        response = requests.get(
            SCOREMAN_URL,
            headers=HEADERS,
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
        # 페이지 제목
        # ==================================

        if soup.title:

            st.subheader(
                "페이지 제목"
            )

            st.write(
                soup.title.get_text(
                    " ",
                    strip=True
                )
            )


        # ==================================
        # 스크립트
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
        # 배당 관련 키워드
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
            "firstOdds",
            "initial",
            "Initial",
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
        # 경기 정보
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
        # 경기 텍스트
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

st.divider()

st.subheader(
    "실제 스코어맨 배당 원본 분석"
)


if st.button(
    "초기/최종 배당 원본 확인"
):

    try:

        response = requests.get(
            SCOREMAN_URL,
            headers=HEADERS,
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
        # 배당 키워드
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
        # 키워드 주변 HTML
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

st.divider()

st.subheader(
    "스코어맨 배당 JavaScript 분석"
)


if st.button(
    "배당 함수 상세 분석"
):

    try:

        # ==================================
        # 경기 페이지 요청
        # ==================================

        response = requests.get(
            SCOREMAN_URL,
            headers=HEADERS,
            timeout=30
        )


        html = response.text


        st.write(
            "HTTP 상태:",
            response.status_code
        )


        st.write(
            "HTML 크기:",
            len(html)
        )


        # ==================================
        # callOddsDetailWin 찾기
        # ==================================

        positions = [

            m.start()

            for m in re.finditer(
                "callOddsDetailWin",
                html
            )

        ]


        st.write(
            "callOddsDetailWin 발견:",
            len(positions)
        )


        # ==================================
        # 호출부 표시
        # ==================================

        for index, position in enumerate(
            positions[:3]
        ):

            st.write(
                f"### 호출부 {index + 1}"
            )


            start = max(
                0,
                position - 500
            )


            end = min(
                len(html),
                position + 1500
            )


            st.code(
                html[start:end],
                language="html"
            )


        # ==================================
        # JavaScript 파일 찾기
        # ==================================

        scripts = re.findall(

            r'<script[^>]+src=["\']'
            r'([^"\']+)["\']',

            html,

            re.I

        )


        st.subheader(
            "JavaScript 파일"
        )


        st.write(
            "총",
            len(scripts),
            "개"
        )


        # ==================================
        # JS 파일 분석
        # ==================================

        for script in scripts:

            js_url = urljoin(
                SCOREMAN_URL,
                script
            )


            try:

                js_response = requests.get(
                    js_url,
                    headers=HEADERS,
                    timeout=20
                )


                js = js_response.text


                # callOddsDetailWin 없는 파일 제외

                if (
                    "callOddsDetailWin"
                    not in js
                ):

                    continue


                st.subheader(
                    "배당 함수가 발견된 JS"
                )


                st.code(
                    js_url
                )


                positions_js = [

                    m.start()

                    for m in re.finditer(
                        "callOddsDetailWin",
                        js
                    )

                ]


                st.write(
                    "JS 내부 발견:",
                    len(positions_js)
                )


                # ==================================
                # 함수 주변 코드
                # ==================================

                for position in positions_js[:5]:

                    start = max(
                        0,
                        position - 2000
                    )


                    end = min(
                        len(js),
                        position + 6000
                    )


                    st.code(
                        js[start:end],
                        language="javascript"
                    )


            except Exception as js_error:

                st.write(
                    "JS 분석 실패:",
                    js_error
                )


    except Exception as e:

        st.error(
            f"오류: {e}"
        )


# ==========================================
# 끝
# ==========================================

st.divider()

st.caption(
    "현재 단계: 스코어맨 경기 페이지 및 "
    "배당 요청 구조 확인"
            )
