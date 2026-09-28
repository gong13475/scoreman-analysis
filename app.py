# ============================================================
# app.py
# 스코어맨 경기 / 초기배당 / 최종배당 / 경기결과 DB
# ============================================================

import streamlit as st
import requests
from bs4 import BeautifulSoup
import sqlite3
import re
import json
import os
from datetime import datetime


# ============================================================
# 기본 설정
# ============================================================

st.set_page_config(
    page_title="스코어맨 배당 분석",
    page_icon="⚽",
    layout="wide"
)


# ============================================================
# HTTP 설정
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Linux; Android 10) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0.0.0 "
        "Mobile Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": (
        "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    )
}


# ============================================================
# DB
# ============================================================

DB_FILE = "historical_odds.db"


def init_db():

    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            match_id TEXT UNIQUE,

            home_team TEXT,

            away_team TEXT,

            match_date TEXT,

            final_score TEXT,

            result TEXT,

            source TEXT,

            created_at TEXT

        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS odds (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            match_id TEXT,

            company TEXT,

            initial_home REAL,

            initial_draw REAL,

            initial_away REAL,

            final_home REAL,

            final_draw REAL,

            final_away REAL,

            created_at TEXT,

            UNIQUE(
                match_id,
                company
            )

        )
    """)

    conn.commit()

    conn.close()


init_db()


# ============================================================
# 경기 결과 판정
# ============================================================

def calculate_result(
    home_score,
    away_score
):

    try:

        home_score = int(
            home_score
        )

        away_score = int(
            away_score
        )

    except:

        return ""

    if home_score > away_score:

        return "승"

    elif home_score < away_score:

        return "패"

    else:

        return "무"


# ============================================================
# 경기 정보 추출
# ============================================================

def parse_match_info(
    html,
    match_id
):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    text = soup.get_text(
        " ",
        strip=True
    )

    home = ""
    away = ""

    # ------------------------------------------
    # 알려진 테스트 경기
    # ------------------------------------------

    if "강원" in text:

        home = "강원"

    if "부천" in text:

        away = "부천"

    # ------------------------------------------
    # score 패턴
    # ------------------------------------------

    score = ""

    patterns = [

        r'(\d+)\s*[-:]\s*(\d+)',

        r'(\d+)\s*:\s*(\d+)'

    ]

    for pattern in patterns:

        m = re.search(
            pattern,
            text
        )

        if m:

            score = (
                f"{m.group(1)}-{m.group(2)}"
            )

            break

    # ------------------------------------------
    # 날짜
    # ------------------------------------------

    match_date = ""

    date_patterns = [

        r'20\d{2}-\d{2}-\d{2}',

        r'20\d{2}/\d{2}/\d{2}'

    ]

    for pattern in date_patterns:

        m = re.search(
            pattern,
            text
        )

        if m:

            match_date = m.group(0)

            break

    # ------------------------------------------
    # 결과
    # ------------------------------------------

    result = ""

    if score:

        parts = re.split(
            r'[-:]',
            score
        )

        if len(parts) == 2:

            result = calculate_result(
                parts[0],
                parts[1]
            )

    return {
        "match_id": str(match_id),
        "home_team": home,
        "away_team": away,
        "match_date": match_date,
        "final_score": score,
        "result": result
    }


# ============================================================
# 스코어맨 변수 추출
# ============================================================

def find_variable(
    html,
    variable
):

    patterns = [

        rf'{re.escape(variable)}\s*=\s*[\'"]?(\d+)',

        rf'{re.escape(variable)}\s*:\s*[\'"]?(\d+)'

    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            html,
            re.IGNORECASE
        )

        if matches:

            return matches[0]

    return None


# ============================================================
# 스코어맨 배당 JSON 요청
# ============================================================

def get_scoreman_odds(
    match_id
):

    match_url = (
        "https://www.scoreman123.com/"
        f"match/data-{match_id}"
    )

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    session.headers.update({
        "Referer": match_url,
        "X-Requested-With":
            "XMLHttpRequest"
    })

    # ------------------------------------------
    # 경기 페이지 먼저 접속
    # ------------------------------------------

    page = session.get(
        match_url,
        timeout=30
    )

    html = page.text

    # ------------------------------------------
    # 실제 페이지 변수
    # ------------------------------------------

    schedule_id = (
        find_variable(
            html,
            "_scheduleID"
        )
        or str(match_id)
    )

    live_type = (
        find_variable(
            html,
            "_oLiveType"
        )
        or "14"
    )

    sub_type = (
        find_variable(
            html,
            "_subType"
        )
        or "1"
    )

    half_time = (
        find_variable(
            html,
            "_halfTime"
        )
        or "0"
    )

    # ------------------------------------------
    # 실제 API
    # ------------------------------------------

    api_url = (
        "https://www.scoreman123.com/"
        "ajax/soccerajax"
    )

    params = {

        "type": live_type,

        "t": sub_type,

        "id": schedule_id,

        "h": half_time

    }

    response = session.get(
        api_url,
        params=params,
        timeout=30
    )

    try:

        data = response.json()

    except:

        data = {
            "raw": response.text
        }

    return {
        "page": page,
        "html": html,
        "response": response,
        "data": data,
        "schedule_id": schedule_id,
        "live_type": live_type,
        "sub_type": sub_type,
        "half_time": half_time
    }


# ============================================================
# mixodds 분석
# ============================================================

def parse_mixodds(
    data
):

    results = []

    if not isinstance(
        data,
        dict
    ):

        return results

    # ------------------------------------------
    # Data
    # ------------------------------------------

    data_block = data.get(
        "Data",
        {}
    )

    if not isinstance(
        data_block,
        dict
    ):

        return results

    mixodds = data_block.get(
        "mixodds",
        []
    )

    if not isinstance(
        mixodds,
        list
    ):

        return results

    # ------------------------------------------
    # 업체별
    # ------------------------------------------

    for item in mixodds:

        if not isinstance(
            item,
            dict
        ):

            continue

        company_id = item.get(
            "cid",
            ""
        )

        euro = item.get(
            "euro",
            {}
        )

        if not isinstance(
            euro,
            dict
        ):

            continue

        first = euro.get(
            "f",
            {}
        )

        last = euro.get(
            "l",
            {}

        )

        if not isinstance(
            first,
            dict
        ):

            first = {}

        if not isinstance(
            last,
            dict
        ):

            last = {}

        row = {

            "회사ID":
                company_id,

            "초기승":
                first.get(
                    "u"
                ),

            "초기무":
                first.get(
                    "g"
                ),

            "초기패":
                first.get(
                    "d"
                ),

            "최종승":
                last.get(
                    "u"
                ),

            "최종무":
                last.get(
                    "g"
                ),

            "최종패":
                last.get(
                    "d"
                )

        }

        results.append(
            row
        )

    return results


# ============================================================
# 회사 ID → 회사명
# ============================================================

COMPANY_MAP = {

    "8": "Bet365",

    "31": "Sbobet",

    "47": "Pinnacle",

    "23": "Crown",

    "12": "Macauslot",

    "14": "M88",

    "17": "12Bet",

    "24": "18Bet",

    "42": "Easybet",

    "19": "Vcbet"

}


def company_name(
    company_id
):

    return COMPANY_MAP.get(
        str(company_id),
        f"회사ID {company_id}"
    )


# ============================================================
# DB 저장
# ============================================================

def save_match(
    match
):

    conn = sqlite3.connect(
        DB_FILE
    )

    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO matches
        (
            match_id,
            home_team,
            away_team,
            match_date,
            final_score,
            result,
            source,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (

        match["match_id"],

        match["home_team"],

        match["away_team"],

        match["match_date"],

        match["final_score"],

        match["result"],

        "Scoreman",

        datetime.now().isoformat()

    ))

    conn.commit()

    conn.close()


def save_odds(
    match_id,
    odds_rows
):

    conn = sqlite3.connect(
        DB_FILE
    )

    cursor = conn.cursor()

    for row in odds_rows:

        company = company_name(
            row["회사ID"]
        )

        cursor.execute("""
            INSERT OR REPLACE INTO odds
            (
                match_id,
                company,
                initial_home,
                initial_draw,
                initial_away,
                final_home,
                final_draw,
                final_away,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (

            str(match_id),

            company,

            row["초기승"],

            row["초기무"],

            row["초기패"],

            row["최종승"],

            row["최종무"],

            row["최종패"],

            datetime.now().isoformat()

        ))

    conn.commit()

    conn.close()


# ============================================================
# 화면
# ============================================================

st.title(
    "⚽ 스코어맨 배당 분석"
)

st.caption(
    "스코어맨 경기 → 초기배당 → 최종배당 → "
    "경기결과 → SQLite DB"
)


# ============================================================
# 경기 ID
# ============================================================

match_id = st.text_input(
    "스코어맨 경기 ID",
    value="2929675"
)


match_url = (
    "https://www.scoreman123.com/"
    f"match/data-{match_id}"
)


st.write(
    "경기 페이지:",
    match_url
)


# ============================================================
# 전체 실행
# ============================================================

if st.button(
    "🚀 스코어맨 데이터 가져오기",
    type="primary"
):

    try:

        # ======================================
        # 1. 스코어맨 접속
        # ======================================

        result_data = get_scoreman_odds(
            match_id
        )

        page = result_data[
            "page"
        ]

        html = result_data[
            "html"
        ]

        response = result_data[
            "response"
        ]

        data = result_data[
            "data"
        ]

        st.subheader(
            "① 경기 페이지"
        )

        st.write(
            "HTTP 상태:",
            page.status_code
        )

        st.write(
            "HTML 크기:",
            len(html)
        )

        # ======================================
        # 2. 실제 파라미터
        # ======================================

        st.subheader(
            "② 실제 스코어맨 요청값"
        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "scheduleID",
            result_data["schedule_id"]
        )

        c2.metric(
            "type",
            result_data["live_type"]
        )

        c3.metric(
            "t",
            result_data["sub_type"]
        )

        c4.metric(
            "h",
            result_data["half_time"]
        )

        # ======================================
        # 3. 경기 정보
        # ======================================

        match = parse_match_info(
            html,
            match_id
        )

        st.subheader(
            "③ 경기 정보"
        )

        st.write(
            "홈팀:",
            match["home_team"]
        )

        st.write(
            "원정팀:",
            match["away_team"]
        )

        st.write(
            "경기일:",
            match["match_date"]
        )

        st.write(
            "최종 스코어:",
            match["final_score"]
        )

        st.write(
            "결과:",
            match["result"]
        )

        # ======================================
        # 4. 실제 API
        # ======================================

        st.subheader(
            "④ 실제 배당 API"
        )

        st.write(
            "API HTTP:",
            response.status_code
        )

        st.write(
            "API 응답 크기:",
            len(response.text)
        )

        st.write(
            "요청 URL:",
            response.url
        )

        # ======================================
        # 5. API 응답
        # ======================================

        if (
            isinstance(data, dict)
            and data.get("code") == 1002
        ):

            st.error(
                "스코어맨에서 배당 API 요청을 "
                "code 1002로 반환했습니다."
            )

            st.info(
                "경기 페이지와 요청 구조는 확인됐지만 "
                "현재 서버에서 해당 요청에 대한 "
                "배당 데이터를 반환하지 않았습니다."
            )

            st.json(
                data
            )

        else:

            st.subheader(
                "⑤ 배당 JSON"
            )

            st.json(
                data
            )

            # ==================================
            # 6. mixodds
            # ==================================

            odds_rows = parse_mixodds(
                data
            )

            st.subheader(
                "⑥ 업체별 초기 / 최종 배당"
            )

            if odds_rows:

                display_rows = []

                for row in odds_rows:

                    display_rows.append({

                        "업체":
                            company_name(
                                row["회사ID"]
                            ),

                        "초기 승":
                            row["초기승"],

                        "초기 무":
                            row["초기무"],

                        "초기 패":
                            row["초기패"],

                        "최종 승":
                            row["최종승"],

                        "최종 무":
                            row["최종무"],

                        "최종 패":
                            row["최종패"]

                    })

                st.dataframe(
                    display_rows,
                    use_container_width=True,
                    hide_index=True
                )

                # ==============================
                # 7. DB 저장
                # ==============================

                save_match(
                    match
                )

                save_odds(
                    match_id,
                    odds_rows
                )

                st.success(
                    f"DB 저장 완료: "
                    f"{len(odds_rows)}개 업체"
                )

            else:

                st.warning(
                    "mixodds 배당 데이터가 없습니다."
                )

    except Exception as e:

        st.error(
            f"오류 발생: {e}"
        )


# ============================================================
# DB 확인
# ============================================================

st.divider()

st.subheader(
    "🗄️ historical_odds.db"
)


if os.path.exists(
    DB_FILE
):

    conn = sqlite3.connect(
        DB_FILE
    )

    matches_df = None
    odds_df = None

    try:

        import pandas as pd

        matches_df = pd.read_sql_query(
            "SELECT * FROM matches ORDER BY id DESC",
            conn
        )

        odds_df = pd.read_sql_query(
            "SELECT * FROM odds ORDER BY id DESC",
            conn
        )

    except Exception as e:

        st.error(
            f"DB 읽기 오류: {e}"
        )

    conn.close()

    if matches_df is not None:

        st.write(
            "경기 데이터:",
            len(matches_df),
            "건"
        )

        if len(matches_df) > 0:

            st.dataframe(
                matches_df,
                use_container_width=True,
                hide_index=True
            )

    if odds_df is not None:

        st.write(
            "배당 데이터:",
            len(odds_df),
            "건"
        )

        if len(odds_df) > 0:

            st.dataframe(
                odds_df,
                use_container_width=True,
                hide_index=True
            )

else:

    st.info(
        "historical_odds.db가 아직 없습니다."
    )


# ============================================================
# 안내
# ============================================================

st.divider()

st.caption(
    "※ 스코어맨 페이지의 실제 응답 구조에 따라 "
    "일부 경기의 팀명/결과/배당 데이터는 추가 파싱이 필요할 수 있습니다."
        )
