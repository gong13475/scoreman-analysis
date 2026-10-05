import time
import streamlit as st

import database
import collector
import analysis


# =========================================================
# 페이지
# =========================================================

st.set_page_config(
    page_title="Scoreman 해외배당 분석",
    page_icon="⚽",
    layout="wide"
)


database.init_database()


# =========================================================
# CSS
# =========================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 30px;
        font-weight: 800;
        margin-bottom: 5px;
    }

    .sub-title {
        color: #666;
        margin-bottom: 20px;
    }

    .match-box {
        padding: 20px;
        border-radius: 15px;
        background: #f7f7f7;
        margin-top: 10px;
        margin-bottom: 15px;
    }

    .team {
        text-align: center;
        font-size: 22px;
        font-weight: 700;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# 제목
# =========================================================

st.markdown(
    '<div class="main-title">'
    '⚽ 전종목 해외배당 분석'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="sub-title">'
    '스코어맨 자동수집 · 해외업체 최종배당 · '
    '실제결과 · 확률분석 · Turso 영구저장'
    '</div>',
    unsafe_allow_html=True
)


# =========================================================
# DB 상태
# =========================================================

status = database.get_database_status()

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "저장 경기",
    f"{status['matches']:,}"
)

c2.metric(
    "저장 최종배당",
    f"{status['odds']:,}"
)

c3.metric(
    "실제 저장 업체",
    f"{status['bookmakers']:,}"
)

if database.TURSO_DATABASE_URL:

    c4.metric(
        "DB",
        "Turso"
    )

else:

    c4.metric(
        "DB",
        "SQLite"
    )


# =========================================================
# DB 상태
# =========================================================

st.subheader(
    "🗄️ DB 상태"
)

if (
    database.TURSO_DATABASE_URL
    and database.TURSO_AUTH_TOKEN
):

    st.success(
        "🟢 Turso 영구 DB 연결 설정됨"
    )

else:

    st.warning(
        "🟡 로컬 SQLite 모드 — "
        "scoreman.db에 저장됩니다."
    )


# =========================================================
# 수집
# =========================================================

st.subheader(
    "📥 스코어맨 경기 자동수집"
)

st.write(
    "시작 ID와 마지막 ID를 입력하면 "
    "백그라운드에서 경기와 최종배당을 수집합니다."
)


col1, col2 = st.columns(2)

with col1:

    start_id = st.number_input(
        "시작 경기 ID",
        min_value=1,
        value=3001118,
        step=1
    )

with col2:

    end_id = st.number_input(
        "마지막 경기 ID",
        min_value=1,
        value=3001120,
        step=1
    )


if end_id >= start_id:

    st.caption(
        f"검색 대상: "
        f"{end_id - start_id + 1:,}개 경기 ID"
    )


# =========================================================
# 업체
# =========================================================

st.subheader(
    "🏢 수집할 해외업체 선택"
)

mode = st.radio(
    "수집 방식",
    [
        "전체 업체 자동수집",
        "특정 업체만 수집"
    ],
    horizontal=True
)


companies = analysis.get_company_list()


if mode == "특정 업체만 수집":

    selected = st.multiselect(
        "업체 선택",
        companies
    )

else:

    selected = None


st.info(
    "전체 업체 자동수집을 선택하면 "
    "Scoreman 배당 API에서 확인되는 업체의 "
    "최종배당을 저장합니다."
)


delay = st.number_input(
    "요청 간격(초)",
    min_value=0.1,
    max_value=10.0,
    value=0.5,
    step=0.1
)


# =========================================================
# 시작 / 중지
# =========================================================

b1, b2 = st.columns(2)

with b1:

    if st.button(
        "🚀 수집 시작",
        use_container_width=True
    ):

        if end_id < start_id:

            st.error(
                "마지막 ID가 시작 ID보다 작습니다."
            )

        elif (
            mode == "특정 업체만 수집"
            and not selected
        ):

            st.error(
                "업체를 하나 이상 선택하세요."
            )

        else:

            ok = collector.start_background_collection(

                start_id,

                end_id,

                selected,

                delay
            )

            if ok:

                st.success(
                    "백그라운드 수집을 시작했습니다."
                )

            else:

                st.warning(
                    "이미 수집 작업이 실행 중입니다."
                )


with b2:

    if st.button(
        "🛑 수집 중지",
        use_container_width=True
    ):

        if collector.stop_background_collection():

            st.warning(
                "수집 중지 요청을 보냈습니다."
            )

        else:

            st.info(
                "실행 중인 수집 작업이 없습니다."
            )


# =========================================================
# 작업 상태
# =========================================================

job = collector.get_job_status()


if job["running"]:

    st.subheader(
        "📊 현재 수집 상태"
    )

    progress = 0

    if job["total"]:

        progress = (
            job["current"]
            / job["total"]
        )

    st.progress(
        min(
            max(progress, 0),
            1
        )
    )

    a, b, c, d = st.columns(4)

    a.metric(
        "진행",
        f"{job['current']:,} / "
        f"{job['total']:,}"
    )

    b.metric(
        "신규",
        f"{job['success']:,}"
    )

    c.metric(
        "실패/배당없음",
        f"{job['failed']:,}"
    )

    d.metric(
        "최종배당",
        f"{job['odds']:,}"
    )

    if job["last_completed_id"]:

        st.caption(
            "마지막 저장 경기 ID: "
            f"{job['last_completed_id']:,}"
        )

    st.text_area(
        "수집 로그",
        job["log"],
        height=350
    )

    time.sleep(1)

    st.rerun()


elif job["finished"]:

    st.subheader(
        "✅ 마지막 수집 결과"
    )

    if job["result"]:

        r = job["result"]

        a, b, c, d = st.columns(4)

        a.metric(
            "전체",
            f"{r['total']:,}"
        )

        b.metric(
            "신규",
            f"{r['success']:,}"
        )

        c.metric(
            "실패/배당없음",
            f"{r['failed']:,}"
        )

        d.metric(
            "최종배당",
            f"{r['odds']:,}"
        )

    if job["stopped"]:

        st.warning(
            "수집이 중지되었습니다."
        )

    if job["error"]:

        st.error(
            job["error"]
        )

    st.text_area(
        "로그",
        job["log"],
        height=300
    )


# =========================================================
# 저장 경기
# =========================================================

st.subheader(
    "📋 저장된 전체 경기"
)

matches = database.get_all_matches()


if matches:

    st.dataframe(
        matches,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "아직 저장된 경기가 없습니다."
    )


# =========================================================
# 경기 조회
# =========================================================

st.subheader(
    "📱 경기별 최종배당 확인"
)

lookup_id = st.number_input(
    "경기 ID",
    min_value=1,
    value=3001118,
    step=1,
    key="lookup_id"
)


if st.button(
    "🔎 경기 조회",
    use_container_width=True
):

    match = database.get_match(
        lookup_id
    )

    if not match:

        st.error(
            "경기 정보를 찾을 수 없습니다."
        )

    else:

        st.success(
            "⚽ 경기 정보를 찾았습니다."
        )

        st.markdown(
            f"""
            <div class="match-box">

                <div class="team">

                    {match.get("home_team", "")}

                    <br>

                    <span style="
                        font-size:15px;
                        color:#777;
                    ">
                        VS
                    </span>

                    <br>

                    {match.get("away_team", "")}

                </div>

                <div style="
                    text-align:center;
                    color:#555;
                    margin-top:12px;
                ">

                    경기 ID:
                    <b>
                        {int(lookup_id):,}
                    </b>

                    <br>

                    경기일:
                    <b>
                        {match.get("match_date", "")}
                    </b>

                    <br>

                    실제 결과:
                    <b>
                        {match.get("result", "")}
                    </b>

                </div>

            </div>
            """,
            unsafe_allow_html=True
        )

        odds = database.get_match_final_odds(
            lookup_id
        )

        if not odds:

            st.error(
                "❌ 저장된 최종배당이 없습니다."
            )

        else:

            st.success(
                f"저장된 최종배당 "
                f"{len(odds)}개"
            )

            display = []

            for row in odds:

                display.append({

                    "업체":
                        row["bookmaker"],

                    "홈":
                        row["final_home"],

                    "무":
                        row["final_draw"],

                    "원정":
                        row["final_away"]
                })

            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True
            )


# =========================================================
# 분석
# =========================================================

st.subheader(
    "📈 저장 배당 확률 분석"
)

analysis_companies = st.multiselect(
    "분석 업체",
    companies,
    key="analysis_companies"
)


if analysis_companies:

    odds_input = {}

    st.write(
        "검색할 최종배당을 입력하세요."
    )

    for company in analysis_companies:

        st.markdown(
            f"**{company}**"
        )

        a, b, c = st.columns(3)

        with a:

            h = st.number_input(
                f"{company} 승",
                min_value=0.01,
                value=2.00,
                step=0.01,
                key=f"{company}_h"
            )

        with b:

            d = st.number_input(
                f"{company} 무",
                min_value=0.01,
                value=3.00,
                step=0.01,
                key=f"{company}_d"
            )

        with c:

            aw = st.number_input(
                f"{company} 패",
                min_value=0.01,
                value=3.00,
                step=0.01,
                key=f"{company}_a"
            )

        odds_input[company] = {

            "home":
                h,

            "draw":
                d,

            "away":
                aw
        }


    if st.button(
        "📊 배당 검색 및 분석",
        use_container_width=True
    ):

        result = analysis.run_search(

            analysis_companies,

            odds_input
        )

        if not result["success"]:

            st.error(
                result["message"]
            )

        else:

            stats = result["statistics"]

            st.success(
                f"검색 경기 "
                f"{len(result['results']):,}개"
            )

            if stats:

                a, b, c = st.columns(3)

                a.metric(
                    "실제 승률",
                    f"{stats['actual']['home']:.2f}%"
                )

                b.metric(
                    "실제 무승률",
                    f"{stats['actual']['draw']:.2f}%"
                )

                c.metric(
                    "실제 패율",
                    f"{stats['actual']['away']:.2f}%"
                )

                st.write(
                    "### 배당 기준 확률"
                )

                p1, p2, p3 = st.columns(3)

                p1.metric(
                    "승",
                    f"{stats['probability']['home']:.2f}%"
                )

                p2.metric(
                    "무",
                    f"{stats['probability']['draw']:.2f}%"
                )

                p3.metric(
                    "패",
                    f"{stats['probability']['away']:.2f}%"
                )

                st.write(
                    "### 실제 결과 - 배당 확률"
                )

                s1, s2, s3 = st.columns(3)

                s1.metric(
                    "승",
                    f"{stats['shortage']['home']:+.2f}%"
                )

                s2.metric(
                    "무",
                    f"{stats['shortage']['draw']:+.2f}%"
                )

                s3.metric(
                    "패",
                    f"{stats['shortage']['away']:+.2f}%"
                )

                st.info(
                    "가장 부족한 결과: "
                    + analysis.get_highest_shortage(
                        stats
                    )
                )

            if result["results"]:

                st.write(
                    "### 검색된 경기"
                )

                st.dataframe(
                    result["results"],
                    use_container_width=True,
                    hide_index=True
    )
