import streamlit as st
import requests
import re
import sqlite3

from bs4 import BeautifulSoup
from urllib.parse import urljoin


# ==========================================
# 페이지 설정
# ==========================================

st.set_page_config(
    page_title="스코어맨 배당 분석",
    page_icon="⚽",
    layout="wide"
)


# ==========================================
# 기본 설정
# ==========================================

SCOREMAN_URL = (
    "https://www.scoreman123.com/"
    "match/data-2929675"
)

SUMMARY_JS = (
    "https://www.scoreman123.com/"
    "scripts/soccer/summary"
    "?v=w3EZghaJjq5VC2gU04EO10nrVNDVtsWwUUiY8uZJFxM1"
)

DB_FILE = "historical_odds.db"


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
# DB 생성
# ==========================================

def create_database():

    conn = sqlite3.connect(
        DB_FILE
    )

    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            scoreman_id TEXT UNIQUE,

            home_team TEXT,

            away_team TEXT,

            match_date TEXT,

            final_score TEXT,

            result TEXT,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP

        )
    """)


    cur.execute("""
        CREATE TABLE IF NOT EXISTS odds (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            match_id INTEGER,

            company TEXT,

            market TEXT,

            initial_home REAL,

            initial_draw REAL,

            initial_away REAL,

            final_home REAL,

            final_draw REAL,

            final_away REAL,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP

        )
    """)


    conn.commit()

    conn.close()


create_database()


# ==========================================
# DB 현황
# ==========================================

def get_db_count(table):

    conn = sqlite3.connect(
        DB_FILE
    )

    cur = conn.cursor()

    cur.execute(
        f"SELECT COUNT(*) FROM {table}"
    )

    count = cur.fetchone()[0]

    conn.close()

    return count


col1, col2 = st.columns(2)


with col1:

    st.metric(
        "경기 데이터",
        get_db_count("matches")
    )


with col2:

    st.metric(
        "배당 데이터",
        get_db_count("odds")
    )


# ==========================================
# 제목
# ==========================================

st.title(
    "⚽ 스코어맨 배당 분석"
)


st.info(
    "현재 단계에서는 실제 배당 요청 구조를 확인합니다. "
    "배당 요청 주소가 확인된 뒤 초기/최종 배당을 DB에 저장합니다."
)


# ==========================================
# 실제 경기 페이지 확인
# ==========================================

st.divider()

st.subheader(
    "실제 스코어맨 경기 페이지"
)


if st.button(
    "경기 페이지 확인"
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


        if soup.title:

            st.write(
                "페이지 제목:",
                soup.title.get_text(
                    " ",
                    strip=True
                )
            )


        html = response.text


        for word in [
            "강원",
            "부천",
            "2929675",
            "Bet365",
            "Pinnacle"
        ]:

            st.write(
                word,
                ":",
                html.count(word),
                "회"
            )


    except Exception as e:

        st.error(
            str(e)
        )


# ==========================================
# 핵심 JS 분석
# ==========================================

st.divider()

st.subheader(
    "🔎 실제 배당 JavaScript 분석"
)


if st.button(
    "실제 배당 요청 구조 찾기"
):

    try:

        # ==================================
        # summary JS 다운로드
        # ==================================

        response = requests.get(
            SUMMARY_JS,
            headers=HEADERS,
            timeout=30
        )


        st.write(
            "JS HTTP 상태:",
            response.status_code
        )


        st.write(
            "JS 크기:",
            len(response.text)
        )


        js = response.text


        if not js:

            st.error(
                "JavaScript 내용을 가져오지 못했습니다."
            )

            st.stop()


        st.success(
            "summary JavaScript 다운로드 성공"
        )


        # ==================================
        # 찾을 키워드
        # ==================================

        keywords = [

            "callOddsDetailWin",

            "_oddsDetailWin",

            "_oddsDetailWin.open",

            "loadOddsData",

            "oddsDetail",

            "OddsDetail",

            "ajax",

            "$.ajax",

            "$.get",

            "$.post",

            "fetch(",

            "XMLHttpRequest",

            "odds",

            "Odds"

        ]


        # ==================================
        # 키워드 발견 횟수
        # ==================================

        st.subheader(
            "키워드 발견"
        )


        for keyword in keywords:

            count = js.count(
                keyword
            )

            if count > 0:

                st.write(
                    f"**{keyword}** : "
                    f"{count}회"
                )


        # ==================================
        # callOddsDetailWin
        # ==================================

        if "callOddsDetailWin" in js:

            position = js.find(
                "callOddsDetailWin"
            )


            st.subheader(
                "callOddsDetailWin"
            )


            start = max(
                0,
                position - 3000
            )


            end = min(
                len(js),
                position + 10000
            )


            st.code(
                js[start:end],
                language="javascript"
            )


        # ==================================
        # _oddsDetailWin.open
        # ==================================

        if "_oddsDetailWin.open" in js:

            position = js.find(
                "_oddsDetailWin.open"
            )


            st.subheader(
                "_oddsDetailWin.open"
            )


            start = max(
                0,
                position - 5000
            )


            end = min(
                len(js),
                position + 15000
            )


            st.code(
                js[start:end],
                language="javascript"
            )


        # ==================================
        # loadOddsData
        # ==================================

        if "loadOddsData" in js:

            positions = [

                m.start()

                for m in re.finditer(
                    "loadOddsData",
                    js
                )

            ]


            st.subheader(
                "loadOddsData"
            )


            for position in positions[:5]:

                start = max(
                    0,
                    position - 5000
                )


                end = min(
                    len(js),
                    position + 15000
                )


                st.code(
                    js[start:end],
                    language="javascript"
                )


        # ==================================
        # AJAX / FETCH 주변 검색
        # ==================================

        st.subheader(
            "🌐 실제 요청 후보"
        )


        request_patterns = [

            r'\$\.ajax\s*\(',

            r'\$\.get\s*\(',

            r'\$\.post\s*\(',

            r'fetch\s*\(',

            r'XMLHttpRequest',

            r'url\s*:',

            r'url\s*='

        ]


        found_request = False


        for pattern in request_patterns:

            matches = list(
                re.finditer(
                    pattern,
                    js,
                    re.I
                )
            )


            for match in matches[:10]:

                found_request = True

                position = match.start()


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


        if not found_request:

            st.warning(
                "AJAX/fetch 요청 패턴을 찾지 못했습니다."
            )


        # ==================================
        # URL 문자열 후보
        # ==================================

        st.subheader(
            "URL 후보"
        )


        urls = re.findall(

            r'["\']([^"\']+)["\']',

            js

        )


        unique_urls = []


        for value in urls:

            lower = value.lower()


            if any(
                word in lower
                for word in [
                    "odds",
                    "ajax",
                    "api",
                    "match",
                    "data",
                    "soccer"
                ]
            ):

                if value not in unique_urls:

                    unique_urls.append(
                        value
                    )


        for value in unique_urls[:100]:

            st.code(
                value
            )


    except Exception as e:

        st.error(
            f"분석 오류: {e}"
        )


# ==========================================
# 실제 배당 HTML 구조
# ==========================================

st.divider()

st.subheader(
    "📊 배당 HTML 구조"
)


if st.button(
    "Bet365 배당 구조 확인"
):

    try:

        response = requests.get(
            SCOREMAN_URL,
            headers=HEADERS,
            timeout=30
        )


        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )


        # Bet365 찾기

        company = soup.find(
            string=lambda x:
            x and "Bet365" in x
        )


        if company:

            parent = company.parent


            row = parent.find_parent(
                "tr"
            )


            if row:

                st.code(
                    row.prettify(),
                    language="html"
                )


                st.success(
                    "Bet365 배당 행 발견"
                )


                # span ID 출력

                spans = row.find_all(
                    "span"
                )


                st.subheader(
                    "배당 span ID"
                )


                for span in spans:

                    span_id = span.get(
                        "id"
                    )


                    if span_id:

                        st.write(
                            span_id,
                            "=",
                            span.get_text(
                                strip=True
                            )
                        )


        else:

            st.warning(
                "Bet365를 찾지 못했습니다."
            )


    except Exception as e:

        st.error(
            str(e)
        )


# ==========================================
# 향후 DB 저장 안내
# ==========================================

st.divider()

st.subheader(
    "📁 최종 DB 구조"
)


st.code(
"""
historical_odds.db

matches
--------------------------------
scoreman_id
home_team
away_team
match_date
final_score
result


odds
--------------------------------
match_id
company
market
initial_home
initial_draw
initial_away
final_home
final_draw
final_away
""",
    language="text"
)


st.caption(
    "현재는 구조 분석 단계입니다. "
    "실제 배당 요청 주소 확인 후 자동 저장 기능을 연결합니다."
)
