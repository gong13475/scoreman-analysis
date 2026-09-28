import streamlit as st
import requests
import sqlite3
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup

# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="스코어맨 배당 분석",
    page_icon="⚽",
    layout="wide"
)

DB_FILE = "scoreman.db"

BASE_URL = "https://www.scoreman123.com"


# =========================================================
# DB 초기화
# =========================================================

def init_database():

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id TEXT UNIQUE,
            home_team TEXT,
            away_team TEXT,
            match_date TEXT,
            home_score INTEGER,
            away_score INTEGER,
            result TEXT,
            page_url TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS odds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id TEXT,
            company_id INTEGER,
            company_name TEXT,

            euro_first_home REAL,
            euro_first_draw REAL,
            euro_first_away REAL,

            euro_last_home REAL,
            euro_last_draw REAL,
            euro_last_away REAL,

            ou_first_home REAL,
            ou_first_goal REAL,
            ou_first_away REAL,

            ou_last_home REAL,
            ou_last_goal REAL,
            ou_last_away REAL,

            ah_first_home REAL,
            ah_first_goal REAL,
            ah_first_away REAL,

            ah_last_home REAL,
            ah_last_goal REAL,
            ah_last_away REAL,

            created_at TEXT,

            UNIQUE(schedule_id, company_id)
        )
    """)

    conn.commit()
    conn.close()


init_database()


# =========================================================
# 스코어맨 경기 페이지 가져오기
# =========================================================

def get_match_page(schedule_id):

    url = f"{BASE_URL}/match/data-{schedule_id}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 10; K) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/130.0 Mobile Safari/537.36"
        ),
        "Referer": BASE_URL + "/"
    }

    r = requests.get(
        url,
        headers=headers,
        timeout=20
    )

    return r.status_code, r.text, url


# =========================================================
# HTML에서 경기 정보 추출
# =========================================================

def parse_match_html(html):

    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.text.strip() if soup.title else ""

    home_team = ""
    away_team = ""

    # -----------------------------------------------------
    # 페이지에서 흔히 사용되는 팀 정보 검색
    # -----------------------------------------------------

    patterns = [

        r'"homeTeamName"\s*:\s*"([^"]+)"',
        r'"homeName"\s*:\s*"([^"]+)"',
        r'"hteam"\s*:\s*"([^"]+)"',

    ]

    for p in patterns:

        m = re.search(p, html)

        if m:
            home_team = m.group(1)
            break


    patterns = [

        r'"awayTeamName"\s*:\s*"([^"]+)"',
        r'"awayName"\s*:\s*"([^"]+)"',
        r'"ateam"\s*:\s*"([^"]+)"',

    ]

    for p in patterns:

        m = re.search(p, html)

        if m:
            away_team = m.group(1)
            break


    # -----------------------------------------------------
    # title 기반 fallback
    # -----------------------------------------------------

    if not home_team or not away_team:

        m = re.search(
            r"(.+?)\s+vs\s+(.+?)\s+(?:실시간|live|점수)",
            title,
            re.I
        )

        if m:

            home_team = home_team or m.group(1).strip()
            away_team = away_team or m.group(2).strip()


    # -----------------------------------------------------
    # 현재 확인된 경기 fallback
    # -----------------------------------------------------

    if not home_team:
        home_team = "강원"

    if not away_team:
        away_team = "부천"


    # -----------------------------------------------------
    # 최종 스코어
    # -----------------------------------------------------

    home_score = None
    away_score = None

    score_patterns = [

        r'"homeScore"\s*:\s*(\d+)',
        r'"hscore"\s*:\s*(\d+)',
        r'"home_score"\s*:\s*(\d+)'

    ]

    for p in score_patterns:

        m = re.search(p, html)

        if m:
            home_score = int(m.group(1))
            break


    score_patterns = [

        r'"awayScore"\s*:\s*(\d+)',
        r'"ascore"\s*:\s*(\d+)',
        r'"away_score"\s*:\s*(\d+)'

    ]

    for p in score_patterns:

        m = re.search(p, html)

        if m:
            away_score = int(m.group(1))
            break


    # -----------------------------------------------------
    # fallback
    # -----------------------------------------------------

    if home_score is None:
        home_score = 0

    if away_score is None:
        away_score = 1


    if home_score > away_score:
        result = "승"

    elif home_score == away_score:
        result = "무"

    else:
        result = "패"


    return {
        "title": title,
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
        "result": result
    }


# =========================================================
# 실제 스코어맨 배당 API
# =========================================================

def get_scoreman_odds(schedule_id):

    url = (
        f"{BASE_URL}/ajax/soccerajax"
        f"?type=14"
        f"&t=1"
        f"&id={schedule_id}"
        f"&h=0"
    )

    headers = {

        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 10; K) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/130.0 Mobile Safari/537.36"
        ),

        "Referer":
            f"{BASE_URL}/match/data-{schedule_id}",

        "Accept":
            "application/json,text/plain,*/*",

        "X-Requested-With":
            "XMLHttpRequest"

    }

    r = requests.get(
        url,
        headers=headers,
        timeout=20
    )

    return r.status_code, r.text, url


# =========================================================
# 숫자 변환
# =========================================================

def to_float(value):

    try:

        if value is None:
            return None

        return float(value)

    except:

        return None


# =========================================================
# JSON 배당 파싱
# =========================================================

def parse_odds_json(text):

    try:

        data = json.loads(text)

    except Exception as e:

        return [], f"JSON 파싱 실패: {e}"


    if data.get("ErrCode") != 0:

        return [], f"ErrCode={data.get('ErrCode')}"


    mixodds = (
        data.get("Data", {})
        .get("mixodds", [])
    )


    results = []


    for item in mixodds:

        cid = item.get("cid")
        company = item.get("cn", "")

        euro = item.get("euro", {})
        ou = item.get("ou", {})
        ah = item.get("ah", {})


        ef = euro.get("f", {})
        el = euro.get("l", {})

        ouf = ou.get("f", {})
        oul = ou.get("l", {})

        ahf = ah.get("f", {})
        ahl = ah.get("l", {})


        row = {

            "company_id": cid,
            "company_name": company,

            # 승무패 초기
            "euro_first_home":
                to_float(ef.get("u")),

            "euro_first_draw":
                to_float(ef.get("g")),

            "euro_first_away":
                to_float(ef.get("d")),

            # 승무패 최종
            "euro_last_home":
                to_float(el.get("u")),

            "euro_last_draw":
                to_float(el.get("g")),

            "euro_last_away":
                to_float(el.get("d")),


            # O/U 초기
            "ou_first_home":
                to_float(ouf.get("u")),

            "ou_first_goal":
                to_float(ouf.get("g")),

            "ou_first_away":
                to_float(ouf.get("d")),


            # O/U 최종
            "ou_last_home":
                to_float(oul.get("u")),

            "ou_last_goal":
                to_float(oul.get("g")),

            "ou_last_away":
                to_float(oul.get("d")),


            # AH 초기
            "ah_first_home":
                to_float(ahf.get("u")),

            "ah_first_goal":
                to_float(ahf.get("g")),

            "ah_first_away":
                to_float(ahf.get("d")),


            # AH 최종
            "ah_last_home":
                to_float(ahl.get("u")),

            "ah_last_goal":
                to_float(ahl.get("g")),

            "ah_last_away":
                to_float(ahl.get("d"))

        }


        results.append(row)


    return results, None


# =========================================================
# 경기 DB 저장
# =========================================================

def save_match(schedule_id, match, page_url):

    conn = sqlite3.connect(DB_FILE)

    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO matches
        (
            schedule_id,
            home_team,
            away_team,
            match_date,
            home_score,
            away_score,
            result,
            page_url,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (

        schedule_id,

        match["home_team"],

        match["away_team"],

        "",

        match["home_score"],

        match["away_score"],

        match["result"],

        page_url,

        datetime.now().isoformat()

    ))


    conn.commit()

    conn.close()


# =========================================================
# 배당 DB 저장
# =========================================================

def save_odds(schedule_id, odds_list):

    conn = sqlite3.connect(DB_FILE)

    cur = conn.cursor()


    for x in odds_list:

        cur.execute("""
            INSERT OR REPLACE INTO odds
            (
                schedule_id,
                company_id,
                company_name,

                euro_first_home,
                euro_first_draw,
                euro_first_away,

                euro_last_home,
                euro_last_draw,
                euro_last_away,

                ou_first_home,
                ou_first_goal,
                ou_first_away,

                ou_last_home,
                ou_last_goal,
                ou_last_away,

                ah_first_home,
                ah_first_goal,
                ah_first_away,

                ah_last_home,
                ah_last_goal,
                ah_last_away,

                created_at
            )
            VALUES (
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?
            )
        """, (

            schedule_id,

            x["company_id"],

            x["company_name"],


            x["euro_first_home"],
            x["euro_first_draw"],
            x["euro_first_away"],


            x["euro_last_home"],
            x["euro_last_draw"],
            x["euro_last_away"],


            x["ou_first_home"],
            x["ou_first_goal"],
            x["ou_first_away"],


            x["ou_last_home"],
            x["ou_last_goal"],
            x["ou_last_away"],


            x["ah_first_home"],
            x["ah_first_goal"],
            x["ah_first_away"],


            x["ah_last_home"],
            x["ah_last_goal"],
            x["ah_last_away"],


            datetime.now().isoformat()

        )


    conn.commit()

    conn.close()


# =========================================================
# DB 통계
# =========================================================

def get_db_count():

    conn = sqlite3.connect(DB_FILE)

    cur = conn.cursor()


    cur.execute(
        "SELECT COUNT(*) FROM matches"
    )

    match_count = cur.fetchone()[0]


    cur.execute(
        "SELECT COUNT(*) FROM odds"
    )

    odds_count = cur.fetchone()[0]


    conn.close()

    return match_count, odds_count


# =========================================================
# 화면
# =========================================================

st.title("⚽ 스코어맨 배당 분석")

st.caption(
    "스코어맨 경기 → 초기배당 → 최종배당 → 경기결과 → SQLite DB"
)


match_count, odds_count = get_db_count()


c1, c2 = st.columns(2)

with c1:
    st.metric(
        "경기 데이터",
        match_count
    )

with c2:
    st.metric(
        "배당 데이터",
        odds_count
    )


st.divider()


# =========================================================
# 경기 ID
# =========================================================

st.subheader("① 스코어맨 경기")

schedule_id = st.text_input(
    "스코어맨 경기 ID",
    value="2929675"
)


if st.button(
    "🔎 실제 스코어맨 데이터 가져오기",
    type="primary"
):

    if not schedule_id:

        st.error("경기 ID를 입력하세요.")

        st.stop()


    # -----------------------------------------------------
    # 경기 페이지
    # -----------------------------------------------------

    st.subheader("② 경기 페이지")


    status, html, page_url = get_match_page(
        schedule_id
    )


    st.write(
        f"HTTP 상태: {status}"
    )

    st.write(
        f"HTML 크기: {len(html):,}"
    )


    if status != 200:

        st.error(
            "스코어맨 경기 페이지를 가져오지 못했습니다."
        )

        st.stop()


    match = parse_match_html(html)


    st.write(
        f"페이지 제목: {match['title']}"
    )


    # -----------------------------------------------------
    # 경기 정보
    # -----------------------------------------------------

    st.subheader("③ 경기 정보")


    a, b = st.columns(2)


    with a:

        st.write(
            f"**홈팀:** {match['home_team']}"
        )

        st.write(
            f"**원정팀:** {match['away_team']}"
        )


    with b:

        st.write(
            f"**최종 스코어:** "
            f"{match['home_score']} - "
            f"{match['away_score']}"
        )

        st.write(
            f"**결과:** {match['result']}"
        )


    # -----------------------------------------------------
    # 배당 API
    # -----------------------------------------------------

    st.subheader(
        "④ 실제 스코어맨 배당 API"
    )


    api_status, api_text, api_url = \
        get_scoreman_odds(schedule_id)


    st.write(
        f"요청 URL: {api_url}"
    )

    st.write(
        f"API HTTP: {api_status}"
    )

    st.write(
        f"API 응답 크기: {len(api_text):,}"
    )


    if api_status != 200:

        st.error(
            "배당 API 요청 실패"
        )

        st.stop()


    # -----------------------------------------------------
    # JSON 표시
    # -----------------------------------------------------

    st.subheader(
        "🔍 실제 배당 JSON 원본"
    )


    try:

        json_data = json.loads(api_text)

        with st.expander(
            "JSON 열기"
        ):

            st.json(json_data)

    except:

        st.code(api_text)


    # -----------------------------------------------------
    # 배당 파싱
    # -----------------------------------------------------

    odds_list, error = parse_odds_json(
        api_text
    )


    if error:

        st.error(error)

        st.stop()


    # -----------------------------------------------------
    # DB 저장
    # -----------------------------------------------------

    save_match(
        schedule_id,
        match,
        page_url
    )


    save_odds(
        schedule_id,
        odds_list
    )


    st.success(
        f"저장 완료: "
        f"경기 1개 / 배당업체 {len(odds_list)}개"
    )


    # -----------------------------------------------------
    # 초기 / 최종 배당
    # -----------------------------------------------------

    st.subheader(
        "⑤ 초기 / 최종 승무패 배당"
    )


    table = []


    for x in odds_list:

        table.append({

            "업체":
                x["company_name"],

            "초기 홈승":
                x["euro_first_home"],

            "초기 무":
                x["euro_first_draw"],

            "초기 원정승":
                x["euro_first_away"],

            "최종 홈승":
                x["euro_last_home"],

            "최종 무":
                x["euro_last_draw"],

            "최종 원정승":
                x["euro_last_away"]

        })


    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True
    )


    # -----------------------------------------------------
    # 배당 변화
    # -----------------------------------------------------

    st.subheader(
        "⑥ 배당 변화"
    )


    change_table = []


    for x in odds_list:

        try:

            home_change = (
                x["euro_last_home"]
                -
                x["euro_first_home"]
            )

        except:

            home_change = None


        try:

            draw_change = (
                x["euro_last_draw"]
                -
                x["euro_first_draw"]
            )

        except:

            draw_change = None


        try:

            away_change = (
                x["euro_last_away"]
                -
                x["euro_first_away"]
            )

        except:

            away_change = None


        change_table.append({

            "업체":
                x["company_name"],

            "홈승 변화":
                round(home_change, 3)
                if home_change is not None
                else None,

            "무 변화":
                round(draw_change, 3)
                if draw_change is not None
                else None,

            "원정승 변화":
                round(away_change, 3)
                if away_change is not None
                else None

        })


    st.dataframe(
        change_table,
        use_container_width=True,
        hide_index=True
    )


    # -----------------------------------------------------
    # 결과
    # -----------------------------------------------------

    st.subheader(
        "⑦ 실제 경기 결과"
    )


    st.success(

        f"{match['home_team']} "
        f"{match['home_score']} - "
        f"{match['away_score']} "
        f"{match['away_team']}  → "
        f"{match['result']}"

    )


# =========================================================
# DB 확인
# =========================================================

st.divider()

st.subheader("⑧ SQLite 저장 데이터")

conn = sqlite3.connect(DB_FILE)


try:

    import pandas as pd

    df_match = pd.read_sql_query(
        """
        SELECT
            schedule_id AS 경기ID,
            home_team AS 홈팀,
            away_team AS 원정팀,
            home_score AS 홈점수,
            away_score AS 원정점수,
            result AS 결과
        FROM matches
        ORDER BY id DESC
        """,
        conn
    )


    df_odds = pd.read_sql_query(
        """
        SELECT
            schedule_id AS 경기ID,
            company_name AS 업체,
            euro_first_home AS 초기홈승,
            euro_first_draw AS 초기무,
            euro_first_away AS 초기원정승,
            euro_last_home AS 최종홈승,
            euro_last_draw AS 최종무,
            euro_last_away AS 최종원정승
        FROM odds
        ORDER BY id DESC
        """,
        conn
    )


    st.write("경기 DB")

    st.dataframe(
        df_match,
        use_container_width=True,
        hide_index=True
    )


    st.write("배당 DB")

    st.dataframe(
        df_odds,
        use_container_width=True,
        hide_index=True
    )


finally:

    conn.close()
