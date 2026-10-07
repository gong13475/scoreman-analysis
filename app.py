# ============================================================
# app.py
# ⚽ Scoreman 전종목 해외배당 분석
# ============================================================

import time
import base64

import streamlit as st

import database
import collector
import analysis


# ============================================================
# 페이지
# ============================================================

st.set_page_config(
    page_title="Scoreman 해외배당 분석",
    page_icon="⚽",
    layout="wide"
)


# ============================================================
# DB
# ============================================================

database.init_database()


# ============================================================
# CSS
# ============================================================

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


# ============================================================
# 제목
# ============================================================

st.markdown(
    '<div class="main-title">'
    '⚽ 전종목 해외배당 분석'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="sub-title">'
    'Scoreman 자동수집 · 해외업체 최종배당 · '
    '실제결과 · 확률분석 · Turso 영구저장'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# DB 상태
# ============================================================

status = database.get_database_status()

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "저장 경기",
    f"{status.get('matches', 0):,}"
)

c2.metric(
    "저장 최종배당",
    f"{status.get('odds', 0):,}"
)

c3.metric(
    "실제 저장 업체",
    f"{status.get('bookmakers', 0):,}"
)

c4.metric(
    "DB",
    "Turso"
    if database._use_turso()
    else "SQLite"
)


# ============================================================
# DB 상태
# ============================================================

st.subheader(
    "🗄️ 데이터베이스 상태"
)

if database._use_turso():

    st.success(
        "🟢 Turso DB 연결 정상"
    )

else:

    st.warning(
        "🟡 로컬 SQLite fallback 모드"
    )


with st.expander(
    "🔧 DB 연결 상세정보"
):

    db_info = database.get_database_info()

    st.write(
        "Turso URL 설정:",
        "✅"
        if db_info.get(
            "database_url_configured"
        )
        else "❌"
    )

    st.write(
        "Turso Token 설정:",
        "✅"
        if db_info.get(
            "auth_token_configured"
        )
        else "❌"
    )

    st.write(
        "libSQL 모듈:",
        "✅"
        if db_info.get(
            "libsql_available"
        )
        else "❌"
    )

    st.write(
        "현재 사용 DB:",
        "Turso"
        if db_info.get(
            "using_turso"
        )
        else "SQLite"
    )


# ============================================================
# DB 용량
# ============================================================

st.subheader(
    "💾 DB 저장 용량"
)

usage = database.get_storage_usage()

if usage.get("success"):

    u1, u2 = st.columns(2)

    u1.metric(
        "현재 DB 저장 크기",
        f"{usage.get('size_mb', 0):.2f} MB"
    )

    u2.metric(
        "저장 방식",
        usage.get(
            "storage_type",
            "SQLite"
        )
    )


# ============================================================
# 업체별 저장량
# ============================================================

st.subheader(
    "🏢 업체별 저장 경기 수"
)

company_counts = (
    database.get_company_counts()
    or {}
)

if company_counts:

    st.dataframe(
        [
            {
                "업체": company,
                "저장 경기 수": int(count)
            }
            for company, count
            in company_counts.items()
        ],
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "저장된 업체별 데이터가 없습니다."
    )


# ============================================================
# 현재 상태
# ============================================================

state = (
    database.get_collection_state()
    or {}
)

last_id = state.get(
    "last_completed_id",
    0
)

try:
    last_id = int(last_id or 0)
except Exception:
    last_id = 0


# ============================================================
# Scoreman 수집
# ============================================================

st.subheader(
    "📥 Scoreman 경기 ID 구간 자동수집"
)

col1, col2 = st.columns(2)

with col1:

    start_id = st.number_input(
        "시작 ID",
        min_value=1,
        value=3001118,
        step=1
    )

with col2:

    end_id = st.number_input(
        "마지막 ID",
        min_value=1,
        value=start_id,
        step=1
    )


if end_id >= start_id:

    st.caption(
        f"검색 대상: "
        f"{end_id - start_id + 1:,}개"
    )

else:

    st.error(
        "마지막 ID가 시작 ID보다 작습니다."
    )


if last_id > 0:

    st.info(
        f"📌 마지막 성공 완료 ID: "
        f"{last_id:,}"
    )

    st.caption(
        f"다음 자동 시작 ID: "
        f"{last_id + 1:,}"
    )


# ============================================================
# 업체
# ============================================================

st.subheader(
    "🏢 수집 업체"
)

companies = (
    analysis.get_company_list()
    or []
)

mode = st.radio(
    "수집 방식",
    [
        "전체 업체 자동수집",
        "특정 업체만 수집"
    ],
    horizontal=True
)

if mode == "특정 업체만 수집":

    selected = st.multiselect(
        "🏢 업체 선택",
        companies,
        key="collector_companies"
    )

else:

    selected = None

    st.success(
        "Scoreman에서 확인되는 전체 업체의 "
        "최종배당을 자동 저장합니다."
    )


# ============================================================
# 요청 간격
# ============================================================

delay = st.number_input(
    "요청 간격(초)",
    min_value=0.1,
    max_value=10.0,
    value=0.5,
    step=0.1
)


# ============================================================
# 수집 시작 / 중지
# ============================================================

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
                int(start_id),
                int(end_id),
                selected,
                float(delay),
                resume=True
            )

            if ok:

                st.success(
                    "백그라운드 수집을 시작했습니다."
                )

            else:

                st.warning(
                    "이미 수집 중이거나 "
                    "수집할 ID가 없습니다."
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
                "현재 실행 중인 수집 작업이 없습니다."
            )


# ============================================================
# 수집 상태
# ============================================================

job = collector.get_job_status()

if job.get("running"):

    st.subheader(
        "🟢 현재 수집 중"
    )

    total = int(
        job.get("total", 0) or 0
    )

    current = int(
        job.get("current", 0) or 0
    )

    progress = (
        current / total
        if total > 0
        else 0
    )

    st.progress(
        min(
            max(progress, 0),
            1
        )
    )

    a, b, c, d, e = st.columns(5)

    a.metric(
        "현재",
        f"{current:,} / {total:,}"
    )

    b.metric(
        "신규",
        f"{int(job.get('success', 0) or 0):,}"
    )

    c.metric(
        "기존",
        f"{int(job.get('exists', 0) or 0):,}"
    )

    d.metric(
        "실패",
        f"{int(job.get('failed', 0) or 0):,}"
    )

    e.metric(
        "배당",
        f"{int(job.get('odds', 0) or 0):,}"
    )

    if job.get("last_completed_id"):

        st.info(
            f"📌 마지막 완료 ID: "
            f"{int(job.get('last_completed_id')):,}"
        )

    time.sleep(1)

    st.rerun()


elif job.get("finished"):

    st.subheader(
        "✅ 마지막 수집 결과"
    )

    result = job.get(
        "result"
    )

    if result:

        a, b, c, d, e = st.columns(5)

        a.metric(
            "전체",
            f"{int(result.get('total', 0)):,}"
        )

        b.metric(
            "신규",
            f"{int(result.get('success', 0)):,}"
        )

        c.metric(
            "기존",
            f"{int(result.get('exists', 0)):,}"
        )

        d.metric(
            "실패",
            f"{int(result.get('failed', 0)):,}"
        )

        e.metric(
            "배당 없음",
            f"{int(result.get('no_odds', 0)):,}"
        )

        st.metric(
            "최종배당 저장",
            f"{int(result.get('odds', 0)):,}"
        )


# ============================================================
# 저장 경기
# ============================================================

st.divider()

st.subheader(
    "📋 저장된 경기 전체 조회"
)

matches = (
    database.get_all_matches()
    or []
)

if matches:

    st.dataframe(
        matches,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "저장된 경기가 없습니다."
    )


# ============================================================
# 경기별 최종배당
# ============================================================

st.subheader(
    "🔎 경기별 최종배당 조회"
)

lookup_id = st.number_input(
    "경기 ID",
    min_value=1,
    value=(
        last_id
        if last_id > 0
        else 3001118
    ),
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

            <span style="font-size:15px;color:#777;">
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
            <b>{int(lookup_id):,}</b>

            <br>

            경기일:
            <b>{match.get("match_date", "")}</b>

            <br>

            실제 스코어:
            <b>
            {match.get("home_score", "")}
            :
            {match.get("away_score", "")}
            </b>

            <br>

            실제 결과:
            <b>{match.get("result", "")}</b>

            </div>

            </div>
            """,
            unsafe_allow_html=True
        )

        odds = (
            database.get_odds_by_match(
                lookup_id
            )
            or []
        )

        if odds:

            st.dataframe(
                [
                    {

                        "업체":
                            row.get(
                                "company_name",
                                ""
                            ),

                        "승":
                            f"{float(row.get('final_home', 0)):.2f}",

                        "무":
                            f"{float(row.get('final_draw', 0)):.2f}",

                        "패":
                            f"{float(row.get('final_away', 0)):.2f}"

                    }

                    for row in odds

                ],
                use_container_width=True,
                hide_index=True
            )

        else:

            st.warning(
                "저장된 최종배당이 없습니다."
            )


# ============================================================
# 수동 동일배당 분석
# ============================================================

st.divider()

st.subheader(
    "📈 수동 최종배당 동일 경기 분석"
)

st.caption(
    "업체를 선택하고 최종 승/무/패 배당을 입력하면 "
    "저장된 과거 동일배당 경기를 검색합니다."
)


analysis_companies = st.multiselect(
    "🏢 분석 업체 선택",
    companies,
    key="analysis_companies"
)


if analysis_companies:

    odds_input = {}

    for company in analysis_companies:

        st.markdown(
            f"### 🏢 {company}"
        )

        a, b, c = st.columns(3)

        with a:

            h = st.number_input(
                f"{company} 승",
                min_value=0.01,
                value=1.83,
                step=0.01,
                format="%.2f",
                key=f"manual_{company}_home"
            )

        with b:

            d = st.number_input(
                f"{company} 무",
                min_value=0.01,
                value=3.40,
                step=0.01,
                format="%.2f",
                key=f"manual_{company}_draw"
            )

        with c:

            aw = st.number_input(
                f"{company} 패",
                min_value=0.01,
                value=4.20,
                step=0.01,
                format="%.2f",
                key=f"manual_{company}_away"
            )

        odds_input[company] = {

            "home": h,

            "draw": d,

            "away": aw

        }


    if st.button(
        "🔎 동일배당 검색 및 분석",
        use_container_width=True,
        key="search_odds"
    ):

        result = analysis.run_search(
            analysis_companies,
            odds_input
        )

        st.session_state[
            "analysis_result"
        ] = result


# ============================================================
# 분석 결과 표시
# ============================================================

saved_result = st.session_state.get(
    "analysis_result"
)


if saved_result:

    if not saved_result.get(
        "success",
        False
    ):

        st.error(
            saved_result.get(
                "message",
                "분석 오류"
            )
        )

    else:

        stats = saved_result.get(
            "statistics"
        )

        results = saved_result.get(
            "results",
            []
        )

        if stats:

            st.success(
                f"동일배당 경기 "
                f"{stats.get('count', 0):,}개"
            )

            actual = stats.get(
                "actual",
                {}
            )

            probability = stats.get(
                "probability",
                {}
            )

            shortage = stats.get(
                "shortage",
                {}
            )

            st.markdown(
                "### 📊 실제 결과"
            )

            a, b, c = st.columns(3)

            a.metric(
                "승",
                f"{actual.get('home', 0):.2f}%"
            )

            b.metric(
                "무",
                f"{actual.get('draw', 0):.2f}%"
            )

            c.metric(
                "패",
                f"{actual.get('away', 0):.2f}%"
            )

            st.markdown(
                "### 🎯 배당 기반 확률"
            )

            a, b, c = st.columns(3)

            a.metric(
                "승",
                f"{probability.get('home', 0):.2f}%"
            )

            b.metric(
                "무",
                f"{probability.get('draw', 0):.2f}%"
            )

            c.metric(
                "패",
                f"{probability.get('away', 0):.2f}%"
            )

            st.markdown(
                "### 📉 부족 / 초과 확률"
            )

            st.caption(
                "실제 발생확률 − 배당 기반 확률"
            )

            a, b, c = st.columns(3)

            a.metric(
                "승",
                f"{shortage.get('home', 0):+.2f}%"
            )

            b.metric(
                "무",
                f"{shortage.get('draw', 0):+.2f}%"
            )

            c.metric(
                "패",
                f"{shortage.get('away', 0):+.2f}%"
            )

            highest = (
                analysis.get_highest_shortage(
                    stats
                )
            )

            if highest:

                st.success(
                    f"🏆 가장 큰 차이: {highest}"
                )


        # ----------------------------------------------------
        # 업체별 통계
        # ----------------------------------------------------

        company_stats = (
            saved_result.get(
                "company_statistics",
                {}
            )
        )

        if company_stats:

            st.markdown(
                "### 🏢 업체별 분석"
            )

            summary = (
                analysis.get_company_summary(
                    company_stats
                )
            )

            if summary:

                st.dataframe(
                    summary,
                    use_container_width=True,
                    hide_index=True
                )


        # ----------------------------------------------------
        # 경기 결과
        # ----------------------------------------------------

        if results:

            st.markdown(
                "### 📋 동일배당 경기 결과"
            )

            st.dataframe(
                [
                    {

                        "경기 ID":
                            row.get(
                                "schedule_id",
                                ""
                            ),

                        "경기일":
                            row.get(
                                "match_date",
                                ""
                            ),

                        "홈":
                            row.get(
                                "home_team",
                                ""
                            ),

                        "원정":
                            row.get(
                                "away_team",
                                ""
                            ),

                        "업체":
                            row.get(
                                "bookmaker",
                                ""
                            ),

                        "승":
                            f"{float(row.get('home_odds', 0)):.2f}",

                        "무":
                            f"{float(row.get('draw_odds', 0)):.2f}",

                        "패":
                            f"{float(row.get('away_odds', 0)):.2f}",

                        "결과":
                            row.get(
                                "result",
                                ""
                            )

                    }

                    for row in results

                ],
                use_container_width=True,
                hide_index=True
            )

        else:

            st.info(
                "조건에 맞는 동일배당 경기가 없습니다."
            )


# ============================================================
# 음성
# ============================================================

st.divider()

st.subheader(
    "🎙️ 음성 기능"
)

st.caption(
    "배당 입력 음성은 브라우저/휴대폰의 "
    "음성 입력 기능을 사용할 수 있습니다."
)


try:

    from streamlit_mic_recorder import mic_recorder

    audio = mic_recorder(
        start_prompt="🎤 말하기",
        stop_prompt="⏹️ 녹음 중지",
        just_once=True,
        use_container_width=True,
        key="odds_voice"
    )

    if audio:

        st.success(
            "🎤 음성이 입력되었습니다."
        )

        st.audio(
            audio["bytes"],
            format="audio/wav"
        )

except ImportError:

    st.warning(
        "음성 녹음 기능을 사용하려면 "
        "streamlit-mic-recorder가 필요합니다."
    )


# ============================================================
# 분석 결과 음성 듣기
# ============================================================

if st.button(
    "🔊 현재 분석 결과 듣기",
    use_container_width=True,
    key="speak_result"
):

    result = st.session_state.get(
        "analysis_result"
    )

    if not result:

        st.warning(
            "먼저 동일배당 검색을 실행하세요."
        )

    else:

        stats = result.get(
            "statistics"
        )

        if not stats:

            st.warning(
                "읽을 분석 결과가 없습니다."
            )

        else:

            actual = stats.get(
                "actual",
                {}
            )

            probability = stats.get(
                "probability",
                {}
            )

            shortage = stats.get(
                "shortage",
                {}
            )

            text = (

                "배당 분석 결과입니다. "

                f"총 {stats.get('count', 0)}경기입니다. "

                f"실제 승률 "
                f"{actual.get('home', 0):.1f}퍼센트. "

                f"실제 무승률 "
                f"{actual.get('draw', 0):.1f}퍼센트. "

                f"실제 패율 "
                f"{actual.get('away', 0):.1f}퍼센트. "

                f"배당 기반 승 확률 "
                f"{probability.get('home', 0):.1f}퍼센트. "

                f"배당 기반 무 확률 "
                f"{probability.get('draw', 0):.1f}퍼센트. "

                f"배당 기반 패 확률 "
                f"{probability.get('away', 0):.1f}퍼센트. "

                f"승 부족 또는 초과 "
                f"{shortage.get('home', 0):+.1f}퍼센트. "

                f"무 부족 또는 초과 "
                f"{shortage.get('draw', 0):+.1f}퍼센트. "

                f"패 부족 또는 초과 "
                f"{shortage.get('away', 0):+.1f}퍼센트."

            )

            encoded = base64.b64encode(
                text.encode("utf-8")
            ).decode("ascii")

            st.markdown(
                f"""
                <script>
                (() => {{
                    const binary = atob("{encoded}");
                    const bytes = Uint8Array.from(
                        binary,
                        c => c.charCodeAt(0)
                    );

                    const text = new TextDecoder(
                        "utf-8"
                    ).decode(bytes);

                    if ("speechSynthesis" in window) {{

                        window.speechSynthesis.cancel();

                        const msg =
                            new SpeechSynthesisUtterance(
                                text
                            );

                        msg.lang = "ko-KR";
                        msg.rate = 1.0;
                        msg.pitch = 1.0;

                        window.speechSynthesis.speak(
                            msg
                        );

                    }} else {{

                        alert(
                            "이 브라우저는 음성 읽기를 지원하지 않습니다."
                        );

                    }}

                }})();
                </script>
                """,
                unsafe_allow_html=True
            )


# ============================================================
# 새로고침
# ============================================================

st.divider()

if st.button(
    "🔄 화면 새로고침",
    use_container_width=True
):

    st.rerun()
