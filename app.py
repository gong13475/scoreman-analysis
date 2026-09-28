import streamlit as st
import requests
import sqlite3
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup
import pandas as pd


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="스코어맨 배당 분석",
    page_icon="⚽",
    layout="wide"
)

BASE_URL = "https://www.scoreman123.com"
DB_FILE = "scoreman.db"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; K) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36"
    ),
    "Referer": BASE_URL + "/"
}


# =========================================================
# DB
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
            market TEXT,
            first_home TEXT,
            first_draw TEXT,
            first_away TEXT,
            last_home TEXT,
            last_draw TEXT,
            last_away TEXT,
            created_at TEXT,
            UNIQUE(
                schedule_id,
                company_id,
                market
            )
        )
    """)

    conn.commit()
    conn.close()


def save_match(match):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO matches (
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
        match["schedule_id"],
        match["home_team"],
        match["away_team"],
        match["match_date"],
        match["home_score"],
        match["away_score"],
        match["result"],
        match["page_url"],
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


def save_odds(schedule_id, odds_list):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    for row in odds_list:
        cur.execute("""
            INSERT OR REPLACE INTO odds (
                schedule_id,
                company_id,
                company_name,
                market,
                first_home,
                first_draw,
                first_away,
                last_home,
                last_draw,
                last_away,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            schedule_id,
            row["company_id"],
            row["company_name"],
            row["market"],
            row["first_home"],
            row["first_draw"],
            row["first_away"],
            row["last_home"],
            row["last_draw"],
            row["last_away"],
            datetime.now().isoformat()
        ))

    conn.commit()
    conn.close()


# =========================================================
# 스코어맨 경기 페이지
# =========================================================

def get_match_page(schedule_id):

    url = f"{BASE_URL}/match/data-{schedule_id}"

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        return response, url

    except Exception as e:
        st.error(f"경기 페이지 요청 오류: {e}")
        return None, url


# =========================================================
# 경기 정보 추출
# =========================================================

def parse_match_html(html, schedule_id):

    soup = BeautifulSoup(html, "html.parser")

    text = soup.get_text(" ", strip=True)

    home_team = ""
    away_team = ""

    # 제목에서 팀명 추출
    title = soup.title.text.strip() if soup.title else ""

    if "vs" in title:
        part = title.split("vs", 1)

        if len(part) == 2:
            home_team = part[0].strip()
            away_team = part[1].split("실시간")[0].strip()

    # HTML에서 score 패턴 검색
    home_score = None
    away_score = None

    patterns = [
        r'(\d+)\s*-\s*(\d+)',
        r'(\d+)\s*:\s*(\d+)'
    ]

    for pattern in patterns:

        matches = re.findall(pattern, text)

        if matches:
            for a, b in matches:

                try:
                    aa = int(a)
                    bb = int(b)

                    if aa <= 20 and bb <= 20:
                        home_score = aa
                        away_score = bb
                        break

                except:
                    pass

        if home_score is not None:
            break

    # 사용자 테스트 경기의 경우
    # HTML에 팀명/스코어가 정상적으로 존재하면 사용
    if not home_team:
        home_team = "알 수 없음"

    if not away_team:
        away_team = "알 수 없음"

    result = ""

    if home_score is not None and away_score is not None:

        if home_score > away_score:
            result = "승"

        elif home_score < away_score:
            result = "패"

        else:
            result = "무"

    return {
        "schedule_id": str(schedule_id),
        "home_team": home_team,
        "away_team": away_team,
        "match_date": "",
        "home_score": home_score,
        "away_score": away_score,
        "result": result,
        "page_url": f"{BASE_URL}/match/data-{schedule_id}"
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

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        return response, url

    except Exception as e:

        st.error(f"배당 API 요청 오류: {e}")

        return None, url


# =========================================================
# JSON 분석
# =========================================================

def parse_odds_json(data, schedule_id):

    result = []

    if not isinstance(data, dict):
        return result

    if data.get("ErrCode") != 0:
        return result

    data_obj = data.get("Data", {})

    mixodds = data_obj.get("mixodds", [])

    for company in mixodds:

        company_id = company.get("cid")
        company_name = company.get("cn", "")

        # 승무패
        euro = company.get("euro", {})

        first = euro.get("f", {})
        last = euro.get("l", {})

        result.append({
            "schedule_id": str(schedule_id),
            "company_id": company_id,
            "company_name": company_name,
            "market": "승무패",
            "first_home": first.get("u", ""),
            "first_draw": first.get("g", ""),
            "first_away": first.get("d", ""),
            "last_home": last.get("u", ""),
            "last_draw": last.get("g", ""),
            "last_away": last.get("d", "")
        })

    return result


# =========================================================
# 확률 계산
# =========================================================

def calc_probability(home, draw, away):

    try:

        h = 1 / float(home)
        d = 1 / float(draw)
        a = 1 / float(away)

        total = h + d + a

        return (
            round(h / total * 100, 2),
            round(d / total * 100, 2),
            round(a / total * 100, 2)
        )

    except:

        return None, None, None


# =========================================================
# DB 조회
# =========================================================

def load_matches():

    conn = sqlite3.connect(DB_FILE)

    df = pd.read_sql_query(
        "SELECT * FROM matches ORDER BY id DESC",
        conn
    )

    conn.close()

    return df


def load_odds():

    conn = sqlite3.connect(DB_FILE)

    df = pd.read_sql_query(
        "SELECT * FROM odds ORDER BY id DESC",
        conn
    )

    conn.close()

    return df


# =========================================================
# DB 초기화
# =========================================================

init_database()


# =========================================================
# 화면
# =========================================================

st.title("⚽ 스코어맨 배당 분석")

st.caption(
    "스코어맨 경기 → 초기배당 → 최종배당 → 경기결과 → SQLite DB"
)


# =========================================================
# 경기 ID
# =========================================================

schedule_id = st.text_input(
    "스코어맨 경기 ID",
    value="2929675"
).strip()


if st.button("🔎 스코어맨 경기 분석", type="primary"):

    if not schedule_id:

        st.warning("경기 ID를 입력하세요.")
        st.stop()

    # -----------------------------------------------------
    # 경기 페이지
    # -----------------------------------------------------

    st.subheader("① 스코어맨 경기")

    response, page_url = get_match_page(schedule_id)

    if response is None:
        st.stop()

    st.write(f"경기 페이지: {page_url}")

    st.write(
        f"HTTP 상태: {response.status_code}"
    )

    st.write(
        f"HTML 크기: {len(response.text):,}"
    )

    if response.status_code != 200:

        st.error("스코어맨 경기 페이지 요청 실패")
        st.stop()

    # -----------------------------------------------------
    # 경기 정보
    # -----------------------------------------------------

    st.subheader("② 경기 정보")

    match = parse_match_html(
        response.text,
        schedule_id
    )

    st.write(
        f"홈팀: **{match['home_team']}**"
    )

    st.write(
        f"원정팀: **{match['away_team']}**"
    )

    if (
        match["home_score"] is not None
        and
        match["away_score"] is not None
    ):

        st.write(
            f"최종 스코어: "
            f"**{match['home_score']} - "
            f"{match['away_score']}**"
        )

        st.write(
            f"결과: **{match['result']}**"
        )

    else:

        st.info(
            "최종 스코어를 HTML에서 자동으로 찾지 못했습니다."
        )

    # -----------------------------------------------------
    # 실제 API
    # -----------------------------------------------------

    st.subheader("③ 실제 스코어맨 배당 API")

    odds_response, odds_url = get_scoreman_odds(
        schedule_id
    )

    st.write(
        f"요청 URL: `{odds_url}`"
    )

    if odds_response is None:
        st.stop()

    st.write(
        f"API HTTP: {odds_response.status_code}"
    )

    st.write(
        f"API 응답 크기: "
        f"{len(odds_response.text):,}"
    )

    # -----------------------------------------------------
    # JSON 파싱
    # -----------------------------------------------------

    try:

        odds_json = odds_response.json()

    except Exception as e:

        st.error(
            f"JSON 변환 실패: {e}"
        )

        st.code(
            odds_response.text[:5000],
            language="json"
        )

        st.stop()

    # -----------------------------------------------------
    # 원본 JSON
    # -----------------------------------------------------

    with st.expander(
        "🔍 실제 배당 JSON 원본"
    ):

        st.json(odds_json)

    # -----------------------------------------------------
    # 배당 분석
    # -----------------------------------------------------

    odds_list = parse_odds_json(
        odds_json,
        schedule_id
    )

    st.subheader("④ 초기 / 최종 배당")

    if not odds_list:

        st.warning(
            "승무패 배당 데이터를 찾지 못했습니다."
        )

    else:

        rows = []

        for row in odds_list:

            fh = row["first_home"]
            fd = row["first_draw"]
            fa = row["first_away"]

            lh = row["last_home"]
            ld = row["last_draw"]
            la = row["last_away"]

            fp_h, fp_d, fp_a = calc_probability(
                fh,
                fd,
                fa
            )

            lp_h, lp_d, lp_a = calc_probability(
                lh,
                ld,
                la
            )

            rows.append({
                "업체": row["company_name"],

                "초기 승": fh,
                "초기 무": fd,
                "초기 패": fa,

                "최종 승": lh,
                "최종 무": ld,
                "최종 패": la,

                "초기 승확률": (
                    f"{fp_h}%"
                    if fp_h is not None else "-"
                ),

                "초기 무확률": (
                    f"{fp_d}%"
                    if fp_d is not None else "-"
                ),

                "초기 패확률": (
                    f"{fp_a}%"
                    if fp_a is not None else "-"
                ),

                "최종 승확률": (
                    f"{lp_h}%"
                    if lp_h is not None else "-"
                ),

                "최종 무확률": (
                    f"{lp_d}%"
                    if lp_d is not None else "-"
                ),

                "최종 패확률": (
                    f"{lp_a}%"
                    if lp_a is not None else "-"
                )
            })

        df = pd.DataFrame(rows)

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

        # -------------------------------------------------
        # DB 저장
        # -------------------------------------------------

        save_match(match)

        save_odds(
            schedule_id,
            odds_list
        )

        st.success(
            f"✅ 경기 1건 + 배당 "
            f"{len(odds_list)}개 DB 저장 완료"
        )


# =========================================================
# 저장된 DB
# =========================================================

st.divider()

st.subheader("📊 SQLite DB 저장 데이터")

matches_df = load_matches()
odds_df = load_odds()

col1, col2 = st.columns(2)

with col1:

    st.metric(
        "경기 데이터",
        len(matches_df)
    )

with col2:

    st.metric(
        "배당 데이터",
        len(odds_df)
    )


# =========================================================
# 경기 DB
# =========================================================

if not matches_df.empty:

    with st.expander(
        "⚽ 저장된 경기 데이터"
    ):

        st.dataframe(
            matches_df,
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# 배당 DB
# =========================================================

if not odds_df.empty:

    with st.expander(
        "💰 저장된 배당 데이터"
    ):

        st.dataframe(
            odds_df,
            use_container_width=True,
            hide_index=True
        )
