# ============================================================
# app.py
# ⚽ 전종목 해외배당 분석
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

database.init_database()


# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

.main-title {
    font-size: 30px;
    font-weight: 800;
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

div.stButton > button {
    min-height: 48px;
    font-weight: 700;
}

</style>
""", unsafe_allow_html=True)


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

try:
    status = database.get_database_status()
except Exception:
    status = {
        "matches": 0,
        "odds": 0,
        "bookmakers": 0
    }


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
# DB 상세
# ============================================================

st.subheader("🗄️ 데이터베이스 상태")

if database._use_turso():

    st.success(
        "🟢 Turso DB 연결 정상"
    )

else:

    st.warning(
        "🟡 로컬 SQLite fallback 모드"
    )


with st.expander("🔧 DB 연결 상세정보"):

    info = database.get_database_info()

    st.write(
        "Turso URL 설정:",
        "✅" if info.get(
            "database_url_configured"
        ) else "❌"
    )

    st.write(
        "Turso Token 설정:",
        "✅" if info.get(
            "auth_token_configured"
        ) else "❌"
    )

    st.write(
        "libSQL 모듈:",
        "✅" if info.get(
            "libsql_available"
        ) else "❌"
    )

    st.write(
        "현재 사용 DB:",
        "Turso"
        if info.get("using_turso")
        else "SQLite"
    )


# ============================================================
# 저장 용량
# ============================================================

st.subheader("💾 DB 저장 용량")

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

else:

    st.error(
        "DB 저장 용량을 확인할 수 없습니다."
    )


# ============================================================
# 업체별 저장량
# ============================================================

st.subheader("🏢 업체별 저장 경기 수")

company_counts = database.get_company_counts()

if company_counts:

    st.dataframe(
        [
            {
                "업체": company,
                "저장 경기 수": count
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
# 마지막 상태
# ============================================================

state = database.get_collection_state()

last_id = int(
    state.get(
        "last_completed_id",
        0
    ) or 0
)

saved_start = state.get("start_id")
saved_end = state.get("end_id")

if saved_start:
    saved_start = int(saved_start)

if saved_end:
    saved_end = int(saved_end)


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
        value=(
            saved_start
            if saved_start and saved_start > 0
            else 3001118
        ),
        step=1
    )

with col2:

    end_id = st.number_input(
        "마지막 ID",
        min_value=1,
        value=(
            saved_end
            if saved_end and saved_end >= start_id
            else start_id
        ),
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
        f"📌 마지막 성공 완료 ID: {last_id:,}"
    )

    st.caption(
        f"다음 자동 시작 ID: {last_id + 1:,}"
    )


# ============================================================
# 업체
# ============================================================

st.subheader("🏢 수집 업체")

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
        "업체 선택",
        companies,
        key="collector_companies"
    )

else:

    selected = None

    st.success(
        "전체 업체의 최종배당을 자동수집합니다."
    )


delay = st.number_input(
    "요청 간격(초)",
    min_value=0.1,
    max_value=10.0,
    value=0.5,
    step=0.1
)


# ============================================================
# 이어받기
# ============================================================

if last_id > 0:

    if st.button(
        f"🔄 마지막 성공 지점부터 자동 이어받기 "
        f"({last_id + 1:,} → {end_id:,})",
        use_container_width=True
    ):

        ok = collector.start_background_collection(
            last_id + 1,
            int(end_id),
            selected,
            float(delay),
            resume=False
        )

        if ok:
            st.success(
                "백그라운드 수집을 시작했습니다."
            )
        else:
            st.warning(
                "이미 수집 중입니다."
            )


# ============================================================
# 시작 / 중지
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
# 작업 상태
# ============================================================

job = collector.get_job_status()


if job.get("running"):

    st.subheader("🟢 현재 수집 중")

    total = int(
        job.get("total", 0) or 0
    )

    current = int(
        job.get("current", 0) or 0
    )

    progress = (
        current / total
        if total
        else 0
    )

    st.progress(
        min(max(progress, 0), 1)
    )

    st.caption(
        f"{progress * 100:.1f}%"
    )

    a, b, c, d, e = st.columns(5)

    a.metric(
        "현재",
        f"{current:,} / {total:,}"
    )

    b.metric(
        "신규",
        f"{job.get('success', 0):,}"
    )

    c.metric(
        "실패",
        f"{job.get('failed', 0):,}"
    )

    d.metric(
        "배당 없음",
        f"{job.get('no_odds', 0):,}"
    )

    e.metric(
        "최종배당",
        f"{job.get('odds', 0):,}"
    )

    if job.get("last_completed_id"):

        st.info(
            f"📌 마지막 완료 ID: "
            f"{int(job['last_completed_id']):,}"
        )

    if "show_collection_log" not in st.session_state:
        st.session_state[
            "show_collection_log"
        ] = False

    if st.button(
        "📝 로그 보기"
        if not st.session_state["show_collection_log"]
        else "🙈 로그 숨기기",
        key="running_log"
    ):

        st.session_state[
            "show_collection_log"
        ] = not st.session_state[
            "show_collection_log"
        ]

    if st.session_state["show_collection_log"]:

        st.text_area(
            "수집 로그",
            job.get("log", ""),
            height=300
        )

    time.sleep(1)
    st.rerun()


elif job.get("finished"):

    st.subheader(
        "✅ 마지막 수집 결과"
    )

    if job.get("stopped"):

        st.warning(
            "🛑 수집이 중지되었습니다."
        )

    result = job.get("result") or {}

    a, b, c, d, e = st.columns(5)

    a.metric(
        "전체",
        f"{result.get('total', 0):,}"
    )

    b.metric(
        "신규",
        f"{result.get('success', 0):,}"
    )

    c.metric(
        "기존",
        f"{result.get('exists', 0):,}"
    )

    d.metric(
        "실패",
        f"{result.get('failed', 0):,}"
    )

    e.metric(
        "배당 없음",
        f"{result.get('no_odds', 0):,}"
    )

    st.metric(
        "최종배당",
        f"{result.get('odds', 0):,}"
    )

    if job.get("last_completed_id"):

        st.success(
            f"📌 마지막 성공 완료 ID: "
            f"{int(job['last_completed_id']):,}"
        )

    if job.get("error"):
        st.error(job["error"])


# ============================================================
# 저장 경기
# ============================================================

st.divider()

st.subheader(
    "📋 저장된 경기 전체 조회"
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
    value=last_id if last_id > 0 else 3001118,
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

        odds = database.get_odds_by_match(
            lookup_id
        )

        if odds:

            st.dataframe(
                [
                    {
                        "업체": x["bookmaker"],
                        "승": f"{float(x['home_odds']):.2f}",
                        "무": f"{float(x['draw_odds']):.2f}",
                        "패": f"{float(x['away_odds']):.2f}"
                    }
                    for x in odds
                ],
                use_container_width=True,
                hide_index=True
            )

        else:

            st.warning(
                "저장된 최종배당이 없습니다."
            )


# ============================================================
# 수동 최종배당 분석
# ============================================================

st.divider()

st.subheader(
    "📈 수동 최종배당 입력 / 동일배당 결과 분석"
)

st.caption(
    "소수점 둘째 자리까지 입력됩니다. "
    "예: 승 1.83 / 무 3.25 / 패 4.70"
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
                key=f"{company}_home"
            )

        with b:

            d = st.number_input(
                f"{company} 무",
                min_value=0.01,
                value=3.25,
                step=0.01,
                format="%.2f",
                key=f"{company}_draw"
            )

        with c:

            aw = st.number_input(
                f"{company} 패",
                min_value=0.01,
                value=4.70,
                step=0.01,
                format="%.2f",
                key=f"{company}_away"
            )

        odds_input[company] = {
            "home": h,
            "draw": d,
            "away": aw
        }

    if st.button(
        "🔎 동일배당 검색 / 분석",
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


    result = st.session_state.get(
        "analysis_result"
    )


    if result and result.get("success"):

        results = result.get(
            "results",
            []
        )

        stats = result.get(
            "statistics"
        )


        st.success(
            f"동일배당 경기: "
            f"{len(results):,}경기"
        )


        if stats:

            st.write("### 📊 실제 결과")

            a, b, c = st.columns(3)

            a.metric(
                "승",
                f"{stats['counts']['home']}경기 "
                f"({stats['actual']['home']:.2f}%)"
            )

            b.metric(
                "무",
                f"{stats['counts']['draw']}경기 "
                f"({stats['actual']['draw']:.2f}%)"
            )

            c.metric(
                "패",
                f"{stats['counts']['away']}경기 "
                f"({stats['actual']['away']:.2f}%)"
            )


            st.write(
                "### 🎯 배당 대비 확률"
            )

            a, b, c = st.columns(3)

            a.metric(
                "승 확률",
                f"{stats['probability']['home']:.2f}%"
            )

            b.metric(
                "무 확률",
                f"{stats['probability']['draw']:.2f}%"
            )

            c.metric(
                "패 확률",
                f"{stats['probability']['away']:.2f}%"
            )


            st.write(
                "### ⚠️ 실제 결과 - 배당 확률 "
                "(부족확률)"
            )

            a, b, c = st.columns(3)

            a.metric(
                "승",
                f"{stats['shortage']['home']:+.2f}%"
            )

            b.metric(
                "무",
                f"{stats['shortage']['draw']:+.2f}%"
            )

            c.metric(
                "패",
                f"{stats['shortage']['away']:+.2f}%"
            )


            highest = analysis.get_highest_shortage(
                stats
            )

            st.success(
                f"🏆 가장 높은 부족확률: {highest}"
            )


        if results:

            st.write("### 📋 동일배당 경기 결과")

            st.dataframe(
                [
                    {
                        "경기 ID":
                            row["schedule_id"],

                        "경기일":
                            row["match_date"],

                        "홈":
                            row["home_team"],

                        "원정":
                            row["away_team"],

                        "업체":
                            row["bookmaker"],

                        "승":
                            f"{float(row['home_odds']):.2f}",

                        "무":
                            f"{float(row['draw_odds']):.2f}",

                        "패":
                            f"{float(row['away_odds']):.2f}",

                        "결과":
                            row["result"]
                    }
                    for row in results
                ],
                use_container_width=True,
                hide_index=True
            )

    elif result:

        st.error(
            result.get(
                "message",
                "분석 오류"
            )
        )

else:

    st.info(
        "🏢 먼저 분석할 업체를 선택하세요."
    )


# ============================================================
# 음성
# ============================================================

st.divider()

st.subheader(
    "🎙️ 음성 배당 입력 / 결과 듣기"
)

st.caption(
    "마이크 녹음 기능을 사용할 수 있습니다."
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
        "음성 기능을 사용하려면 "
        "requirements.txt의 "
        "streamlit-mic-recorder 설치가 필요합니다."
    )


# ============================================================
# 분석 결과 음성
# ============================================================

if st.button(
    "🔊 현재 분석 결과 듣기",
    use_container_width=True,
    key="speak_result"
):

    saved = st.session_state.get(
        "analysis_result"
    )

    if not saved:

        st.warning(
            "먼저 동일배당 검색을 실행하세요."
        )

    else:

        stats = saved.get(
            "statistics"
        )

        if not stats:

            st.warning(
                "읽을 분석 결과가 없습니다."
            )

        else:

            speech = (
                "배당 분석 결과입니다. "
                f"총 {stats['total']}경기입니다. "
                f"실제 승률은 "
                f"{stats['actual']['home']:.1f} 퍼센트입니다. "
                f"실제 무승률은 "
                f"{stats['actual']['draw']:.1f} 퍼센트입니다. "
                f"실제 패율은 "
                f"{stats['actual']['away']:.1f} 퍼센트입니다. "
                f"배당 기준 승 확률은 "
                f"{stats['probability']['home']:.1f} 퍼센트입니다. "
                f"배당 기준 무 확률은 "
                f"{stats['probability']['draw']:.1f} 퍼센트입니다. "
                f"배당 기준 패 확률은 "
                f"{stats['probability']['away']:.1f} 퍼센트입니다."
            )

            encoded = base64.b64encode(
                speech.encode("utf-8")
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
                        speechSynthesis.cancel();

                        const msg =
                            new SpeechSynthesisUtterance(
                                text
                            );

                        msg.lang = "ko-KR";
                        msg.rate = 1.0;
                        msg.pitch = 1.0;

                        speechSynthesis.speak(msg);
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
