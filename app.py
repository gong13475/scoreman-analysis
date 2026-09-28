import streamlit as st
import requests

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


st.write(
    "스코어맨 경기 데이터를 수집하여 "
    "초기배당·최종배당·실제결과를 분석합니다."
)


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
# 스코어맨 접속 테스트
# ==========================================

st.subheader("스코어맨 연결 테스트")


if st.button("스코어맨 접속 확인"):

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


        if response.ok:

            st.success(
                "스코어맨 서버 접속 성공"
            )

        else:

            st.error(
                "스코어맨 접속 실패"
            )


    except Exception as e:

        st.error(
            f"접속 오류: {e}"
        )


st.divider()


# ==========================================
# 데이터 수집 준비
# ==========================================

st.subheader(
    "데이터 수집"
)


st.info(
    "현재는 연결 테스트 단계입니다. "
    "실제 경기 데이터 구조를 확인한 후 "
    "자동 저장 기능을 연결합니다."
)


st.write(
    """
    다음 단계에서 수집합니다.

    • 경기일시
    • 국가
    • 리그
    • 홈팀
    • 원정팀
    • 초기 승/무/패 배당
    • 최종 승/무/패 배당
    • 배당 변동
    • 홈/원정 득점
    • 실제 승/무/패 결과
    """
)
