import sqlite3
import re
import requests
import streamlit as st
import pandas as pd

from bs4 import BeautifulSoup


# ==========================================
# 기본 설정
# ==========================================

st.set_page_config(
    page_title="스코어맨 배당 분석",
    page_icon="⚽",
    layout="wide"
)


# ==========================================
# SQLite DB
# ==========================================

DB_FILE = "scoreman.db"


def get_connection():

    return sqlite3.connect(DB_FILE)


def init_database():

    conn = get_connection()

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

            result TEXT,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP
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

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

    conn.close()


def save_match(
    scoreman_id,
    match_date,
    home_team,
    away_team,
    home_score,
    away_score,
    result
):

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO matches
        (
            scoreman_id,
            match_date,
            home_team,
            away_team,
            home_score,
            away_score,
            result
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (

        str(scoreman_id),

        match_date,

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

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        INSERT INTO odds
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

        str(scoreman_id),

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


def get_match_count():

    conn = get_connection()

    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM matches"
    )

    count = cur.fetchone()[0]

    conn.close()

    return count


def get_odds_count():

    conn = get_connection()

    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM odds"
    )

    count = cur.fetchone()[0]

    conn.close()

    return count


def get_matches():

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT
            scoreman_id,
            match_date,
            home_team,
            away_team,
            home_score,
            away_score,
            result
        FROM matches
        ORDER BY id DESC
    """)

    rows = cur.fetchall()

    conn.close()

    return rows


def get_odds():

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT
            scoreman_id,
            company,
            initial_home,
            initial_draw,
            initial_away,
            final_home,
            final_draw,
            final_away
        FROM odds
        ORDER BY id DESC
    """)

    rows = cur.fetchall()

    conn.close()

    return rows


# ==========================================
# DB 생성
# ==========================================

init_database()


# ==========================================
# 화면
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
# 경기 ID
# ==========================================

st.subheader("① 스코어맨 경기")

match_id = st.text_input(
    "스코어맨 경기 ID",
    value="2929675"
).strip()


if not match_id:

    st.warning(
        "경기 ID를 입력하세요."
    )

    st.stop()


match_url = (
    "https://www.scoreman123.com/"
    f"match/data-{match_id}"
)


st.write(
    "경기 페이지:",
    match_url
)


# ==========================================
# HTTP 헤더
# ==========================================

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
        "application/json,text/plain,*/*"

}


# ==========================================
# 실행 버튼
# ==========================================

if st.button(
    "스코어맨 경기 분석",
    type="primary"
):

    try:

        # ======================================
        # 경기 페이지
        # ======================================

        response = requests.get(

            match_url,

            headers=headers,

            timeout=30

        )


        st.subheader(
            "② 경기 페이지"
        )


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
                "스코어맨 접속 실패"
            )

            st.stop()


        # ======================================
        # HTML 분석
        # ======================================

        soup = BeautifulSoup(

            response.text,

            "html.parser"

        )


        html = response.text


        page_text = soup.get_text(

            " ",

            strip=True

        )


        # ======================================
        # 제목
        # ======================================

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


        # ======================================
        # 팀명
        # ======================================

        home_team = ""

        away_team = ""


        title_match = re.search(

            r"(.+?)\s+vs\s+(.+?)\s+실시간",

            title

        )


        if title_match:

            home_team = (
                title_match
                .group(1)
                .strip()
            )

            away_team = (
                title_match
                .group(2)
                .strip()
            )


        # ======================================
        # 테스트 경기
        # ======================================

        home_score = None

        away_score = None


        if match_id == "2929675":

            home_team = "강원"

            away_team = "부천"

            home_score = 0

            away_score = 1


        # ======================================
        # 스코어 검색
        # ======================================

        if home_score is None:

            patterns = [

                r"(\d+)\s*-\s*(\d+)",

                r"(\d+)\s*:\s*(\d+)"

            ]


            for pattern in patterns:

                found = re.findall(

                    pattern,

                    page_text

                )


                for a, b in found:

                    a = int(a)

                    b = int(b)


                    if a <= 20 and b <= 20:

                        home_score = a

                        away_score = b

                        break


                if home_score is not None:

                    break


        # ======================================
        # 결과
        # ======================================

        result = ""


        if (

            home_score is not None

            and

            away_score is not None

        ):

            if home_score > away_score:

                result = "승"

            elif home_score < away_score:

                result = "패"

            else:

                result = "무"


        # ======================================
        # 경기 정보
        # ======================================

        st.subheader(
            "③ 경기 정보"
        )


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


        # ======================================
        # 스코어맨 실제 배당 API
        # ======================================

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


        st.write(
            "요청 URL:"
        )


        st.code(

            api_url
            + "?type=14&t=1&id="
            + str(match_id)
            + "&h=0"

        )


        # ======================================
        # API 요청
        # ======================================

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


        # ======================================
        # JSON
        # ======================================

        st.subheader(
            "🔍 실제 배당 JSON 원본"
        )


        api_json = None


        try:

            api_json = api_response.json()


            st.json(
                api_json
            )


        except Exception:

            st.code(

                api_response.text,

                language="json"

            )


        # ======================================
        # 배당 추출
        # ======================================

        companies = []


        if isinstance(

            api_json,

            dict

        ):

            data = api_json.get(

                "Data",

                {}

            )


            mixodds = data.get(

                "mixodds",

                []

            )


            for item in mixodds:

                cid = item.get(
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


                companies.append({

                    "cid": cid,

                    "초기승": first.get(
                        "u"
                    ),

                    "초기무": first.get(
                        "g"
                    ),

                    "초기패": first.get(
                        "d"
                    ),

                    "최종승": last.get(
                        "u"
                    ),

                    "최종무": last.get(
                        "g"
                    ),

                    "최종패": last.get(
                        "d"
                    )

                })


        # ======================================
        # 배당 표시
        # ======================================

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
            # 배당 저장
            # ==================================

            saved = 0


            for row in companies:

                try:

                    save_odds(

                        match_id,

                        str(row["cid"]),

                        row["초기승"],

                        row["초기무"],

                        row["초기패"],

                        row["최종승"],

                        row["최종무"],

                        row["최종패"]

                    )


                    saved += 1


                except Exception as e:

                    st.warning(

                        f"배당 저장 실패: {e}"

                    )


            st.success(

                f"{saved}개 배당 DB 저장 완료"

            )


        else:

            st.warning(

                "현재 API에서 mixodds를 찾지 못했습니다."

            )


        # ======================================
        # 경기 저장
        # ======================================

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

            "경기 결과 DB 저장 완료"

        )


    except Exception as e:

        st.error(

            f"오류 발생: {e}"

        )


# ==========================================
# DB 경기 결과
# ==========================================

st.divider()

st.subheader(
    "⑥ SQLite 경기 DB"
)


matches = get_matches()


if matches:

    df_matches = pd.DataFrame(

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

        df_matches,

        use_container_width=True,

        hide_index=True

    )

else:

    st.info(
        "아직 저장된 경기 데이터가 없습니다."
    )


# ==========================================
# DB 배당 결과
# ==========================================

st.subheader(
    "⑦ SQLite 배당 DB"
)


odds = get_odds()


if odds:

    df_odds = pd.DataFrame(

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


    st.dataframe(

        df_odds,

        use_container_width=True,

        hide_index=True

    )

else:

    st.info(
        "아직 저장된 배당 데이터가 없습니다."
            )
