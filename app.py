# ==========================================
# app.py
# 스코어맨 경기 / 배당 데이터 분석
# ==========================================

import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import json


# ==========================================
# 기본 설정
# ==========================================

st.set_page_config(
    page_title="스코어맨 배당 분석",
    page_icon="⚽",
    layout="wide"
)


# ==========================================
# HTTP 헤더
# ==========================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Linux; Android 10) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 "
        "Mobile Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
}


# ==========================================
# 제목
# ==========================================

st.title("⚽ 스코어맨 배당 분석")

st.info(
    "현재 단계에서는 실제 스코어맨 경기 페이지와 "
    "배당 요청 구조를 확인합니다."
)


# ==========================================
# 경기 ID 입력
# ==========================================

st.subheader("📌 스코어맨 경기")

match_id = st.text_input(
    "스코어맨 경기 ID",
    value="2929675"
)


# ==========================================
# 경기 URL
# ==========================================

match_url = (
    "https://www.scoreman123.com/"
    f"match/data-{match_id}"
)


st.write(
    "경기 페이지:",
    match_url
)


# ==========================================
# 경기 페이지 가져오기
# ==========================================

if st.button("① 실제 스코어맨 경기 확인"):

    try:

        response = requests.get(
            match_url,
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

        if response.status_code == 200:

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            st.success(
                "실제 스코어맨 경기 페이지 접속 성공"
            )

            # ------------------------------
            # 제목
            # ------------------------------

            title = soup.title

            if title:

                st.write(
                    "페이지 제목:",
                    title.get_text(
                        strip=True
                    )
                )

            # ------------------------------
            # 경기 팀 찾기
            # ------------------------------

            html = response.text

            st.subheader(
                "경기 정보 확인"
            )

            for keyword in [
                "강원",
                "부천"
            ]:

                count = html.count(
                    keyword
                )

                st.write(
                    f"{keyword}: {count}회"
                )

            # ------------------------------
            # 경기 결과
            # ------------------------------

            for score in [
                "0-3",
                "0 : 3",
                "3-0",
                "3 : 0"
            ]:

                count = html.count(
                    score
                )

                if count:

                    st.write(
                        f"{score}: {count}회"
                    )

        else:

            st.error(
                "스코어맨 페이지 접속 실패"
            )

    except Exception as e:

        st.error(
            f"오류: {e}"
        )


# ==========================================
# 실제 배당 JavaScript 분석
# ==========================================

st.divider()

st.subheader(
    "🔎 실제 스코어맨 배당 JavaScript 분석"
)


if st.button(
    "② 배당 JavaScript 분석"
):

    try:

        response = requests.get(
            match_url,
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

        # ------------------------------
        # script 태그
        # ------------------------------

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        scripts = soup.find_all(
            "script"
        )

        st.write(
            "스크립트 개수:",
            len(scripts)
        )

        # ------------------------------
        # 키워드
        # ------------------------------

        keywords = [
            "callOddsDetailWin",
            "_oddsDetailWin",
            "_oddsDetailWin.open",
            "loadOddsData",
            "loadThreeMixCompOdds",
            "oddsDetail",
            "OddsDetail",
            "$.ajax",
            "$.get",
            "XMLHttpRequest",
            "soccerajax"
        ]

        for keyword in keywords:

            count = html.count(
                keyword
            )

            if count:

                st.write(
                    f"{keyword}: {count}회"
                )

        # ------------------------------
        # soccerajax 위치
        # ------------------------------

        positions = []

        start = 0

        while True:

            pos = html.find(
                "soccerajax",
                start
            )

            if pos == -1:

                break

            positions.append(
                pos
            )

            start = (
                pos + 1
            )

        st.write(
            "soccerajax 발견:",
            len(positions)
        )

        # ------------------------------
        # 주변 코드
        # ------------------------------

        for i, pos in enumerate(
            positions[:10],
            1
        ):

            st.subheader(
                f"배당 요청 구조 {i}"
            )

            context = html[
                max(
                    0,
                    pos - 1500
                ):
                min(
                    len(html),
                    pos + 2500
                )
            ]

            st.code(
                context,
                language="javascript"
            )

    except Exception as e:

        st.error(
            f"오류: {e}"
        )


# ==========================================
# 실제 배당 요청 파라미터 찾기
# ==========================================

st.divider()

st.subheader(
    "🎯 실제 배당 요청 파라미터 찾기"
)


if st.button(
    "③ 실제 배당 요청값 찾기"
):

    try:

        response = requests.get(
            match_url,
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
        # JavaScript 변수 찾기
        # ==================================

        patterns = {

            "_scheduleID": [
                r'_scheduleID\s*=\s*[\'"]?(\d+)',
                r'_scheduleID\s*:\s*[\'"]?(\d+)',
                r'scheduleID\s*=\s*[\'"]?(\d+)',
                r'scheduleID\s*:\s*[\'"]?(\d+)'
            ],

            "_oLiveType": [
                r'_oLiveType\s*=\s*[\'"]?(\d+)',
                r'_oLiveType\s*:\s*[\'"]?(\d+)'
            ],

            "_subType": [
                r'_subType\s*=\s*[\'"]?(\d+)',
                r'_subType\s*:\s*[\'"]?(\d+)'
            ],

            "_halfTime": [
                r'_halfTime\s*=\s*[\'"]?(\d+)',
                r'_halfTime\s*:\s*[\'"]?(\d+)'
            ]

        }

        for name, pattern_list in patterns.items():

            found = []

            for pattern in pattern_list:

                matches = re.findall(
                    pattern,
                    html,
                    re.IGNORECASE
                )

                if matches:

                    found.extend(
                        matches
                    )

            # 중복 제거

            found = list(
                dict.fromkeys(
                    found
                )
            )

            if found:

                st.success(
                    f"{name} → {found[:20]}"
                )

            else:

                st.warning(
                    f"{name} → 찾지 못함"
                )

        # ==================================
        # soccerajax 요청문 찾기
        # ==================================

        ajax_patterns = [

            r'/ajax/soccerajax\?[^"\']+',

            r'ajax/soccerajax\?[^"\']+',

            r'url\s*:\s*["\']([^"\']*soccerajax[^"\']*)'

        ]

        all_urls = []

        for pattern in ajax_patterns:

            matches = re.findall(
                pattern,
                html,
                re.IGNORECASE
            )

            all_urls.extend(
                matches
            )

        all_urls = list(
            dict.fromkeys(
                all_urls
            )
        )

        st.subheader(
            "🌐 발견된 배당 API 주소"
        )

        if all_urls:

            for url in all_urls:

                st.code(
                    url
                )

        else:

            st.warning(
                "HTML에서 직접적인 API URL을 찾지 못했습니다."
            )

        # ==================================
        # soccerajax 주변 코드
        # ==================================

        positions = []

        start = 0

        while True:

            pos = html.find(
                "/ajax/soccerajax",
                start
            )

            if pos == -1:

                break

            positions.append(
                pos
            )

            start = pos + 1

        for i, pos in enumerate(
            positions[:5],
            1
        ):

            st.subheader(
                f"실제 요청 코드 {i}"
            )

            context = html[
                max(
                    0,
                    pos - 1000
                ):
                min(
                    len(html),
                    pos + 2000
                )
            ]

            st.code(
                context,
                language="javascript"
            )

    except Exception as e:

        st.error(
            f"오류: {e}"
        )


# ==========================================
# 직접 배당 API 테스트
# ==========================================

st.divider()

st.subheader(
    "🧪 스코어맨 배당 API 직접 테스트"
)


st.caption(
    "위 ③번에서 확인된 실제 값을 입력한 뒤 테스트합니다."
)


col1, col2 = st.columns(2)

with col1:

    api_type = st.number_input(
        "type",
        min_value=0,
        max_value=100,
        value=14,
        step=1
    )

    api_t = st.number_input(
        "t",
        min_value=0,
        max_value=100,
        value=1,
        step=1
    )


with col2:

    api_id = st.text_input(
        "id",
        value=str(match_id)
    )

    api_h = st.number_input(
        "h",
        min_value=0,
        max_value=10,
        value=0,
        step=1
    )


if st.button(
    "④ 실제 배당 JSON 가져오기"
):

    api_url = (
        "https://www.scoreman123.com/"
        "ajax/soccerajax"
    )

    params = {

        "type": api_type,

        "t": api_t,

        "id": api_id,

        "h": api_h

    }

    try:

        response = requests.get(
            api_url,
            params=params,
            headers=HEADERS,
            timeout=30
        )

        st.write(
            "HTTP 상태:",
            response.status_code
        )

        st.write(
            "요청 URL:",
            response.url
        )

        st.write(
            "응답 크기:",
            len(response.text)
        )

        # ------------------------------
        # JSON 검사
        # ------------------------------

        try:

            data = response.json()

            st.subheader(
                "JSON 응답"
            )

            st.json(
                data
            )

            # --------------------------
            # code 확인
            # --------------------------

            if (
                isinstance(data, dict)
                and data.get("code") == 1002
            ):

                st.warning(
                    "code 1002가 반환되었습니다. "
                    "type/t/h 조합이 실제 요청값과 "
                    "다를 가능성이 있습니다."
                )

            # --------------------------
            # ErrCode 확인
            # --------------------------

            if (
                isinstance(data, dict)
                and data.get("ErrCode") == 0
            ):

                st.success(
                    "배당 데이터 응답 성공"
                )

                if (
                    "Data" in data
                    and isinstance(
                        data["Data"],
                        dict
                    )
                ):

                    mixodds = data[
                        "Data"
                    ].get(
                        "mixodds",
                        []
                    )

                    st.write(
                        "mixodds 건수:",
                        len(mixodds)
                    )

                    if mixodds:

                        st.dataframe(
                            mixodds,
                            use_container_width=True
                        )

        except Exception:

            st.code(
                response.text,
                language="json"
            )

    except Exception as e:

        st.error(
            f"오류: {e}"
        )


# ==========================================
# 배당 구조 설명
# ==========================================

st.divider()

st.subheader(
    "📊 현재 확인된 스코어맨 배당 구조"
)

st.code(
"""
스코어맨
   │
   ├── 경기 페이지
   │      └── /match/data-경기ID
   │
   └── 배당 API
          └── /ajax/soccerajax
                  │
                  ├── type
                  ├── t
                  ├── id
                  └── h
                        │
                        ▼
                   Data.mixodds
                        │
                        ├── cid
                        │
                        ├── ah
                        │
                        ├── euro
                        │     ├── f = 최초
                        │     ├── l = 현재/최종
                        │     └── r = 진행
                        │
                        └── ou
""",
language="text"
)


st.success(
    "현재는 스코어맨 실제 요청 구조를 확인하는 단계입니다. "
    "API가 정상적으로 확인되면 다음 단계에서 "
    "초기배당 + 최종배당 + 경기결과를 DB에 자동 저장하도록 연결합니다."
        )
