import streamlit as st
import requests
import sqlite3
import pandas as pd
from bs4 import BeautifulSoup


# =========================================================
# 설정
# =========================================================

st.set_page_config(
    page_title="스코어맨 배당 분석",
    page_icon="⚽",
    layout="wide"
)

DB_FILE = "historical_odds.db"


# =========================================================
# DB
# =========================================================

def db():

    return sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )


def create_database():

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scoreman_id TEXT UNIQUE,
            match_date TEXT,
            home_team TEXT,
            away_team TEXT,
            home_score INTEGER,
            away_score INTEGER,
            result TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS odds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scoreman_id TEXT,
            company TEXT,
            initial_home REAL,
            initial_draw REAL,
            initial_away REAL,
            final_home REAL,
            final_draw REAL,
            final_away REAL,
            UNIQUE(scoreman_id, company)
        )
    """)

    conn.commit()
    conn.close()


def save_match(
    scoreman_id,
    home_team,
    away_team,
    home_score,
    away_score,
    result
):

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO matches
        (
            scoreman_id,
            home_team,
            away_team,
            home_score,
            away_score,
            result
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        scoreman_id,
        home_team,
        away_team,
        home_score,
        away_score,
        result
    ))

    conn.commit()
    conn.close()


def save_odds(
    scoreman_id,
    company,
    initial_home,
    initial_draw,
    initial_away,
    final_home,
    final_draw,
    final_away
):

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO odds
        (
            scoreman_id,
            company,
            initial_home,
            initial_draw,
            initial_away,
            final_home,
            final_draw,
            final_away
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        scoreman_id,
        company,
        initial_home,
        initial_draw,
        initial_away,
        final_home,
        final_draw,
        final_away
    ))

    conn.commit()
    conn.close()


def match_count():

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM matches"
    )

    n = cur.fetchone()[0]

    conn.close()

    return n


def odds_count():

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM odds"
    )

    n = cur.fetchone()[0]

    conn.close()

    return n


# =========================================================
# DB 생성
# =========================================================

create_database()


# =========================================================
# 화면
# =========================================================

st.title("⚽ 스코어맨 배당 분석")

st.caption(
    "스코어맨 경기 → 초기배당 → 최종배당 → 경기결과 → SQLite DB"
)


c1, c2 = st.columns(2)

with c1:
    st.metric(
        "경기 데이터",
        match_count()
    )

with c2:
    st.metric(
        "배당 데이터",
        odds_count()
    )


st.divider()


# =========================================================
# 경기 ID
# =========================================================

st.subheader("① 스코어맨 경기")

scoreman_id = st.text_input(
    "스코어맨 경기 ID",
    "2929675"
).strip()


st.write(
    f"https://www.scoreman123.com/match/data-{scoreman_id}"
)


# =========================================================
# 헤더
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
        f"https://www.scoreman123.com/"
        f"match/data-{scoreman_id}",

    "Accept":
        "*/*"
}


# =========================================================
# 실행
# =========================================================

if st.button(
    "🔎 스코어맨 데이터 가져오기",
    type="primary"
):

    # -----------------------------------------------------
    # 경기 페이지
    # -----------------------------------------------------

    match_url = (
        "https://www.scoreman123.com/"
        f"match/data-{scoreman_id}"
    )

    try:

        response = requests.get(
            match_url,
            headers=headers,
            timeout=30
        )

    except Exception as e:

        st.error(
            f"경기 페이지 접속 오류: {e}"
        )

        st.stop()


    st.subheader("② 경기 페이지")

    st.write(
        "HTTP 상태:",
        response.status_code
    )

    st.write(
        "HTML 크기:",
        len(response.text)
    )


    # -----------------------------------------------------
    # 제목
    # -----------------------------------------------------

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    title = ""

    if soup.title:

        title = soup.title.get_text(
            " ",
            strip=True
        )


    st.write(
        "페이지 제목:",
        title
    )


    # -----------------------------------------------------
    # 팀명
    # -----------------------------------------------------

    home_team = ""
    away_team = ""


    import re


    m = re.search(
        r'(.+?)\s+vs\s+(.+?)\s+실시간',
        title
    )


    if m:

        home_team = m.group(1).strip()
        away_team = m.group(2).strip()


    # -----------------------------------------------------
    # 점수
    # -----------------------------------------------------

    text_content = soup.get_text(
        " ",
        strip=True
    )


    home_score = None
    away_score = None


    # 실제 페이지에서 발견된 대표적인 점수
    score_matches = re.findall(
        r'(\d+)\s*-\s*(\d+)',
        text_content
    )


    for a, b in score_matches:

        a = int(a)
        b = int(b)

        if a <= 20 and b <= 20:

            home_score = a
            away_score = b

            # 0-1 같은 실제 경기 결과를 우선
            if a != b:
                break


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


    # -----------------------------------------------------
    # 경기 정보
    # -----------------------------------------------------

    st.subheader("③ 경기 정보")

    col1, col2 = st.columns(2)

    with col1:

        st.write(
            "홈팀:",
            home_team
        )

        st.write(
            "원정팀:",
            away_team
        )

    with col2:

        st.write(
            "최종 스코어:",
            f"{home_score} - {away_score}"
        )

        st.write(
            "결과:",
            result
        )


    # =====================================================
    # 실제 스코어맨 JSON API
    # =====================================================

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

        "id": scoreman_id,

        "h": "0"

    }


    try:

        api_response = requests.get(

            api_url,

            params=params,

            headers=headers,

            timeout=30

        )

    except Exception as e:

        st.error(
            f"배당 API 오류: {e}"
        )

        st.stop()


    st.write(
        "API HTTP:",
        api_response.status_code
    )

    st.write(
        "API 응답 크기:",
        len(api_response.text)
    )


    # -----------------------------------------------------
    # JSON
    # -----------------------------------------------------

    try:

        data = api_response.json()

    except Exception:

        st.error(
            "배당 응답이 JSON 형식이 아닙니다."
        )

        st.code(
            api_response.text[:5000]
        )

        st.stop()


    # =====================================================
    # 실제 JSON 원본
    # =====================================================

    with st.expander(
        "🔍 실제 배당 JSON 원본"
    ):

        st.json(data)


    # =====================================================
    # 배당 추출
    # =====================================================

    odds_rows = []


    data_obj = data.get(
        "Data",
        {}
    )


    mixodds = data_obj.get(
        "mixodds",
        []
    )


    if isinstance(
        mixodds,
        list
    ):

        for item in mixodds:

            cid = item.get(
                "cid"
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


            def number(v):

                try:
                    return float(v)
                except:
                    return None


            ih = number(
                initial.get("u")
            )

            idraw = number(
                initial.get("g")
            )

            ia = number(
                initial.get("d")
            )


            fh = number(
                final.get("u")
            )

            fdraw = number(
                final.get("g")
            )

            fa = number(
                final.get("d")
            )


            if any([
                ih,
                idraw,
                ia,
                fh,
                fdraw,
                fa
            ]):

                odds_rows.append({

                    "CID": cid,

                    "초기승": ih,

                    "초기무": idraw,

                    "초기패": ia,

                    "최종승": fh,

                    "최종무": fdraw,

                    "최종패": fa

                })


    # =====================================================
    # 배당 결과
    # =====================================================

    st.subheader(
        "⑤ 초기 / 최종 배당"
    )


    if odds_rows:

        odds_df = pd.DataFrame(
            odds_rows
        )


        st.write(
            "배당 업체:",
            len(odds_rows)
        )


        st.dataframe(
            odds_df,
            use_container_width=True,
            hide_index=True
        )


        # =================================================
        # DB 저장
        # =================================================

        save_match(

            scoreman_id,

            home_team,

            away_team,

            home_score,

            away_score,

            result

        )


        for row in odds_rows:

            save_odds(

                scoreman_id,

                str(row["CID"]),

                row["초기승"],

                row["초기무"],

                row["초기패"],

                row["최종승"],

                row["최종무"],

                row["최종패"]

            )


        st.success(
            f"✅ 경기 + 배당 DB 저장 완료 "
            f"({len(odds_rows)}개 업체)"
        )


    else:

        st.warning(
            "실제 JSON에서 승무패 배당을 찾지 못했습니다."
        )


# =========================================================
# DB 확인
# =========================================================

st.divider()

st.subheader(
    "⑥ DB 상태"
)

st.write(
    "경기 데이터:",
    match_count()
)

st.write(
    "배당 데이터:",
    odds_count()
    )
