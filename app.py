import streamlit as st
import requests
import sqlite3
import pandas as pd
from bs4 import BeautifulSoup
import re


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="스코어맨 배당 분석",
    page_icon="⚽",
    layout="wide"
)

DB_FILE = "historical_odds.db"


# =========================================================
# DB 연결
# =========================================================

def get_db():

    return sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )


# =========================================================
# DB 생성
# =========================================================

def create_database():

    conn = get_db()
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

            cid TEXT,

            initial_home REAL,

            initial_draw REAL,

            initial_away REAL,

            final_home REAL,

            final_draw REAL,

            final_away REAL,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(
                scoreman_id,
                company
            )

        )
    """)


    conn.commit()
    conn.close()


create_database()


# =========================================================
# 경기 저장
# =========================================================

def save_match(

    scoreman_id,

    home_team,

    away_team,

    home_score,

    away_score,

    result

):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""

        INSERT OR REPLACE INTO matches (

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


# =========================================================
# 배당 저장
# =========================================================

def save_odds(

    scoreman_id,

    company,

    cid,

    initial_home,

    initial_draw,

    initial_away,

    final_home,

    final_draw,

    final_away

):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""

        INSERT OR REPLACE INTO odds (

            scoreman_id,

            company,

            cid,

            initial_home,

            initial_draw,

            initial_away,

            final_home,

            final_draw,

            final_away

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

    """, (

        scoreman_id,

        company,

        str(cid),

        initial_home,

        initial_draw,

        initial_away,

        final_home,

        final_draw,

        final_away

    ))

    conn.commit()
    conn.close()


# =========================================================
# DB 개수
# =========================================================

def get_match_count():

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM matches"
    )

    value = cur.fetchone()[0]

    conn.close()

    return value


def get_odds_count():

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM odds"
    )

    value = cur.fetchone()[0]

    conn.close()

    return value


# =========================================================
# DB 전체 조회
# =========================================================

def get_database():

    conn = get_db()

    query = """

        SELECT

            m.scoreman_id AS 경기ID,

            m.home_team AS 홈팀,

            m.away_team AS 원정팀,

            m.home_score AS 홈점수,

            m.away_score AS 원정점수,

            m.result AS 결과,

            o.company AS 업체,

            o.cid AS CID,

            o.initial_home AS 초기승,

            o.initial_draw AS 초기무,

            o.initial_away AS 초기패,

            o.final_home AS 최종승,

            o.final_draw AS 최종무,

            o.final_away AS 최종패

        FROM matches m

        LEFT JOIN odds o

        ON m.scoreman_id = o.scoreman_id

        ORDER BY m.id DESC

    """

    df = pd.read_sql_query(
        query,
        conn
    )

    conn.close()

    return df


# =========================================================
# 스코어맨 요청
# =========================================================

def get_headers(match_url):

    return {

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
            "*/*"

    }


# =========================================================
# 업체명 자동 추출
# =========================================================

def get_company_names(html):

    company_map = {}

    soup = BeautifulSoup(
        html,
        "html.parser"
    )


    # -----------------------------------------------------
    # name=oddsTr
    # -----------------------------------------------------

    rows = soup.select(
        'tr[name="oddsTr"]'
    )


    for row in rows:

        cid = row.get(
            "cid"
        )


        if not cid:
            continue


        company = ""


        tag = row.select_one(
            ".companyBg b"
        )


        if tag:

            company = tag.get_text(
                strip=True
            )


        if not company:

            tag = row.find("b")

            if tag:

                company = tag.get_text(
                    strip=True
                )


        if company:

            company_map[
                str(cid)
            ] = company


    return company_map


# =========================================================
# 경기 정보
# =========================================================

def parse_match(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )


    title = ""

    if soup.title:

        title = soup.title.get_text(
            " ",
            strip=True
        )


    home_team = ""
    away_team = ""


    # 강원 vs 부천
    match = re.search(
        r'(.+?)\s+vs\s+(.+?)\s+실시간',
        title
    )


    if match:

        home_team = match.group(
            1
        ).strip()

        away_team = match.group(
            2
        ).strip()


    text = soup.get_text(
        " ",
        strip=True
    )


    home_score = None
    away_score = None


    scores = re.findall(
        r'(\d+)\s*-\s*(\d+)',
        text
    )


    # -----------------------------------------------------
    # 실제 점수 후보
    # -----------------------------------------------------

    for a, b in scores:

        a = int(a)
        b = int(b)


        if a <= 20 and b <= 20:

            home_score = a
            away_score = b


            # 0-1 같은 실제 경기 결과 우선
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


    return {

        "home_team":
            home_team,

        "away_team":
            away_team,

        "home_score":
            home_score,

        "away_score":
            away_score,

        "result":
            result

    }


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
# 배당 JSON 추출
# =========================================================

def parse_odds(data):

    rows = []


    if not isinstance(
        data,
        dict
    ):

        return rows


    data_obj = data.get(
        "Data",
        {}
    )


    if not isinstance(
        data_obj,
        dict
    ):

        return rows


    mixodds = data_obj.get(
        "mixodds",
        []
    )


    if not isinstance(
        mixodds,
        list
    ):

        return rows


    for item in mixodds:

        if not isinstance(
            item,
            dict
        ):

            continue


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


        rows.append({

            "cid":
                str(cid),

            "initial_home":
                to_float(
                    first.get("u")
                ),

            "initial_draw":
                to_float(
                    first.get("g")
                ),

            "initial_away":
                to_float(
                    first.get("d")
                ),

            "final_home":
                to_float(
                    last.get("u")
                ),

            "final_draw":
                to_float(
                    last.get("g")
                ),

            "final_away":
                to_float(
                    last.get("d")
                )

        })


    return rows


# =========================================================
# 화면
# =========================================================

st.title(
    "⚽ 스코어맨 배당 분석"
)

st.caption(
    "스코어맨 경기 → 초기배당 → 최종배당 → 경기결과 → SQLite DB"
)


# =========================================================
# DB 상태
# =========================================================

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


# =========================================================
# 경기 ID
# =========================================================

st.subheader(
    "① 스코어맨 경기"
)


scoreman_id = st.text_input(
    "스코어맨 경기 ID",
    value="2929675"
).strip()


match_url = (
    "https://www.scoreman123.com/"
    f"match/data-{scoreman_id}"
)


st.write(
    match_url
)


# =========================================================
# 실행
# =========================================================

if st.button(
    "🔎 스코어맨 데이터 가져오기",
    type="primary"
):

    headers = get_headers(
        match_url
    )


    # =====================================================
    # 경기 페이지
    # =====================================================

    st.subheader(
        "② 경기 페이지"
    )


    try:

        response = requests.get(

            match_url,

            headers=headers,

            timeout=30

        )

    except Exception as e:

        st.error(
            f"접속 오류: {e}"
        )

        st.stop()


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
            "스코어맨 페이지 접속 실패"
        )

        st.stop()


    html = response.text


    # =====================================================
    # 경기 정보
    # =====================================================

    match_info = parse_match(
        html
    )


    st.subheader(
        "③ 경기 정보"
    )


    col1, col2 = st.columns(2)


    with col1:

        st.write(
            "홈팀:",
            match_info[
                "home_team"
            ]
        )

        st.write(
            "원정팀:",
            match_info[
                "away_team"
            ]
        )


    with col2:

        st.write(
            "최종 스코어:",
            f'{match_info["home_score"]}'
            f' - '
            f'{match_info["away_score"]}'
        )

        st.write(
            "결과:",
            match_info[
                "result"
            ]
        )


    # =====================================================
    # 업체명
    # =====================================================

    company_map = get_company_names(
        html
    )


    st.write(
        "스코어맨 업체:",
        len(company_map),
        "개"
    )


    # =====================================================
    # API
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

        api = requests.get(

            api_url,

            params=params,

            headers=headers,

            timeout=30

        )

    except Exception as e:

        st.error(
            f"API 오류: {e}"
        )

        st.stop()


    st.write(
        "API HTTP:",
        api.status_code
    )


    st.write(
        "API 응답 크기:",
        len(api.text)
    )


    try:

        json_data = api.json()

    except:

        st.error(
            "JSON 변환 실패"
        )

        st.code(
            api.text[:5000]
        )

        st.stop()


    # =====================================================
    # 배당 추출
    # =====================================================

    odds = parse_odds(
        json_data
    )


    st.subheader(
        "⑤ 초기 / 최종 배당"
    )


    display_rows = []


    for item in odds:

        cid = item["cid"]


        company = company_map.get(

            cid,

            f"CID {cid}"

        )


        display_rows.append({

            "업체":
                company,

            "CID":
                cid,

            "초기 승":
                item[
                    "initial_home"
                ],

            "초기 무":
                item[
                    "initial_draw"
                ],

            "초기 패":
                item[
                    "initial_away"
                ],

            "최종 승":
                item[
                    "final_home"
                ],

            "최종 무":
                item[
                    "final_draw"
                ],

            "최종 패":
                item[
                    "final_away"
                ]

        })


    if display_rows:

        df = pd.DataFrame(
            display_rows
        )


        st.write(
            "배당 업체:",
            len(df)
        )


        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )


        # =================================================
        # 경기 DB
        # =================================================

        save_match(

            scoreman_id,

            match_info[
                "home_team"
            ],

            match_info[
                "away_team"
            ],

            match_info[
                "home_score"
            ],

            match_info[
                "away_score"
            ],

            match_info[
                "result"
            ]

        )


        # =================================================
        # 배당 DB
        # =================================================

        for item in odds:

            cid = item[
                "cid"
            ]


            company = company_map.get(

                cid,

                f"CID {cid}"

            )


            save_odds(

                scoreman_id,

                company,

                cid,

                item[
                    "initial_home"
                ],

                item[
                    "initial_draw"
                ],

                item[
                    "initial_away"
                ],

                item[
                    "final_home"
                ],

                item[
                    "final_draw"
                ],

                item[
                    "final_away"
                ]

            )


        st.success(
            f"✅ 저장 완료: "
            f"{len(odds)}개 업체"
        )


        # =================================================
        # 저장 직후 다시 읽기
        # =================================================

        st.subheader(
            "⑥ 저장된 DB"
        )


        saved_df = get_database()


        st.write(
            "경기 데이터:",
            get_match_count()
        )


        st.write(
            "배당 데이터:",
            get_odds_count()
        )


        if not saved_df.empty:

            st.dataframe(

                saved_df,

                use_container_width=True,

                hide_index=True

            )


    else:

        st.warning(
            "배당 데이터를 찾지 못했습니다."
    )
