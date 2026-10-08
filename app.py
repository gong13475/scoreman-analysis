# ============================================================
# app.py
# ⚽ 전종목 해외배당 분석
# ============================================================

import time

import streamlit as st

import database
import collector
import analysis


# ============================================================
# 페이지
# ============================================================

st.set_page_config(
    page_title="⚽ 전종목 해외배당 분석",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

.block-container {
    padding-top: 1rem;
    padding-left: 0.7rem;
    padding-right: 0.7rem;
}

button {
    min-height: 44px !important;
}

.big-number {
    font-size: 28px;
    font-weight: 700;
}

@media (max-width:768px) {

    h1 {
        font-size: 24px !important;
    }

    h2 {
        font-size: 20px !important;
    }

    h3 {
        font-size: 18px !important;
    }

}

</style>
""", unsafe_allow_html=True)


# ============================================================
# 제목
# ============================================================

st.title("⚽ 전종목 해외배당 분석")

st.caption(
    "스코어맨 자동수집 · 최종배당 · 실제결과 · "
    "배당확률 · 부족확률"
)


# ============================================================
# DB 상태
# ============================================================

status = database.get_database_status()
db_size = database.get_database_size()

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        "저장 경기",
        f"{status['matches']:,}",
    )

with c2:
    st.metric(
        "저장 최종배당",
        f"{status['odds']:,}",
    )

with c3:
    st.metric(
        "실제 저장 업체",
        f"{status['bookmakers']:,}",
    )

with c4:
    st.metric(
        "실제 결과",
        f"{status['results']:,}",
    )

st.caption(
    f"🗄️ DB 용량: "
    f"{db_size['mb']:.2f} MB "
    f"({db_size['mode']})"
)

if status["unresolved"]:

    st.warning(
        f"⚠️ 결과 미확인 경기 "
        f"{status['unresolved']:,}건"
    )

st.divider()


# ============================================================
# 탭
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "⚽ 수집",
    "📊 전체 분석",
    "🎯 동일배당",
    "🔊 배당 분석",
])


# ============================================================
# TAB 1
# ============================================================

with tab1:

    st.subheader("⚽ Scoreman 경기 수집")

    progress = collector.get_progress()

    if progress["running"]:

        st.success(
            "🟢 현재 수집 중입니다."
        )

    else:

        st.info(
            "현재 수집 대기 상태입니다."
        )

    c1, c2 = st.columns(2)

    with c1:

        start_id = st.number_input(
            "시작 ID",
            min_value=1,
            value=2005000,
            step=1,
        )

    with c2:

        end_id = st.number_input(
            "종료 ID",
            min_value=1,
            value=2005000,
            step=1,
        )

    delay = st.number_input(
        "요청 간격(초)",
        min_value=0.0,
        max_value=60.0,
        value=0.50,
        step=0.10,
    )

    company_mode = st.radio(
        "업체 선택",
        [
            "전체 업체 자동수집",
            "선택 업체만 수집",
        ],
        horizontal=True,
    )

    selected_companies = []

    if company_mode == "선택 업체만 수집":

        company_list = [
            x["bookmaker"]
            for x in database.get_bookmakers()
        ]

        selected_companies = st.multiselect(
            "업체",
            company_list,
        )

    c1, c2, c3 = st.columns(3)

    with c1:

        if st.button(
            "🚀 수집시작",
            type="primary",
            use_container_width=True,
        ):

            if (
                company_mode
                == "선택 업체만 수집"
                and not selected_companies
            ):

                st.warning(
                    "업체를 선택하세요."
                )

            else:

                ok, msg = (
                    collector.start_background_collection(
                        start_id,
                        end_id,
                        selected_companies,
                        delay,
                    )
                )

                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

    with c2:

        if st.button(
            "🛑 수집중지",
            use_container_width=True,
        ):

            if collector.stop_collection():
                st.warning(
                    "수집 중지 요청을 보냈습니다."
                )
            else:
                st.info(
                    "현재 수집 중이 아닙니다."
                )

    with c3:

        if st.button(
            "▶️ 이어받기",
            use_container_width=True,
        ):

            ok, msg = (
                collector.resume_collection(
                    end_id,
                    selected_companies,
                    delay,
                )
            )

            if ok:
                st.success(msg)
            else:
                st.warning(msg)

    st.markdown("### 📈 수집 상태")

    progress = collector.get_progress()

    p1, p2, p3, p4, p5 = st.columns(5)

    with p1:
        st.metric(
            "진행",
            f"{progress['current']:,}/"
            f"{progress['total']:,}",
        )

    with p2:
        st.metric(
            "성공",
            f"{progress['success']:,}",
        )

    with p3:
        st.metric(
            "중복",
            f"{progress['exists']:,}",
        )

    with p4:
        st.metric(
            "실패",
            f"{progress['failed']:,}",
        )

    with p5:
        st.metric(
            "배당",
            f"{progress['odds']:,}",
        )

    st.progress(
        min(
            max(
                progress["percent"] / 100,
                0,
            ),
            1,
        )
    )

    st.write(
        f"진행률: "
        f"{progress['percent']:.1f}%"
    )

    if progress["last_completed_id"]:

        st.success(
            f"마지막 완료 ID: "
            f"{progress['last_completed_id']:,}"
        )

    # 자동 새로고침
    if progress["running"]:

        time.sleep(1)
        st.rerun()

    show_log = st.checkbox(
        "📜 수집 로그 보기"
    )

    if show_log:

        logs = collector.get_logs()

        if logs:

            st.code(
                "\n".join(logs),
                language="text",
            )

        else:

            st.info(
                "로그가 없습니다."
            )


# ============================================================
# TAB 2
# ============================================================

with tab2:

    st.subheader(
        "📊 전체 경기 분석"
    )

    bookmakers = database.get_bookmakers()

    bookmaker_options = (
        ["전체 업체"]
        + [
            x["bookmaker"]
            for x in bookmakers
        ]
    )

    selected_bookmaker = st.selectbox(
        "업체",
        bookmaker_options,
        key="analysis_bookmaker",
    )

    if selected_bookmaker == "전체 업체":

        rows = database.get_analysis_rows()

    else:

        rows = database.get_analysis_rows(
            selected_bookmaker
        )

    stats = analysis.analyze_rows(rows)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "실제 결과 경기",
            f"{stats['total']:,}",
        )

    with c2:
        st.metric(
            "승",
            f"{stats['win']:,} "
            f"({stats['win_pct']:.2f}%)",
        )

    with c3:
        st.metric(
            "무",
            f"{stats['draw']:,} "
            f"({stats['draw_pct']:.2f}%)",
        )

    with c4:
        st.metric(
            "패",
            f"{stats['lose']:,} "
            f"({stats['lose_pct']:.2f}%)",
        )

    st.markdown(
        "### 📊 전체 경기 "
        "배당 대비 확률 / 부족확률"
    )

    probability_rows = (
        analysis.probability_result_analysis(
            rows
        )
    )

    if probability_rows:

        st.dataframe(
            probability_rows,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "실제 결과와 최종배당이 모두 있는 "
            "데이터가 없습니다."
        )

    st.markdown("### 🏢 업체별 통계")

    bookmaker_stats = (
        analysis.analyze_by_bookmaker(
            rows
        )
    )

    if bookmaker_stats:

        st.dataframe(
            bookmaker_stats,
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("### ⚽ 최근 저장 경기")

    if rows:

        display = []

        for row in rows[:300]:

            display.append({
                "경기ID":
                    row.get("schedule_id"),

                "날짜":
                    row.get("match_date"),

                "홈":
                    row.get("home_team"),

                "스코어":
                    f"{row.get('home_score')}"
                    f" - "
                    f"{row.get('away_score')}",

                "원정":
                    row.get("away_team"),

                "결과":
                    row.get("result"),

                "업체":
                    row.get("bookmaker"),

                "승배당":
                    row.get("final_home"),

                "무배당":
                    row.get("final_draw"),

                "패배당":
                    row.get("final_away"),
            })

        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "분석할 데이터가 없습니다."
        )


# ============================================================
# TAB 3 동일배당
# ============================================================

with tab3:

    st.subheader(
        "🎯 동일배당 전체 경기 분석"
    )

    st.caption(
        "허용오차 0 — 승/무/패 배당이 "
        "완전히 동일한 경기만 검색합니다."
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        target_home = st.number_input(
            "승 배당",
            min_value=1.01,
            value=2.00,
            step=0.01,
            format="%.2f",
            key="same_home",
        )

    with c2:

        target_draw = st.number_input(
            "무 배당",
            min_value=1.01,
            value=3.20,
            step=0.01,
            format="%.2f",
            key="same_draw",
        )

    with c3:

        target_away = st.number_input(
            "패 배당",
            min_value=1.01,
            value=3.50,
            step=0.01,
            format="%.2f",
            key="same_away",
        )

    bookmaker = st.selectbox(
        "분석 업체",
        ["전체 업체"]
        + [
            x["bookmaker"]
            for x in database.get_bookmakers()
        ],
        key="same_bookmaker",
    )

    if bookmaker == "전체 업체":

        rows = database.get_analysis_rows()

    else:

        rows = database.get_analysis_rows(
            bookmaker
        )

    if st.button(
        "🔎 동일배당 분석",
        type="primary",
        use_container_width=True,
    ):

        result = analysis.same_odds_analysis(
            rows,
            target_home,
            target_draw,
            target_away,
        )

        stat = result["stats"]

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.metric(
                "동일배당 전체 경기",
                f"{stat['total']:,}",
            )

        with c2:
            st.metric(
                "승",
                f"{stat['win']:,} "
                f"({stat['win_pct']:.2f}%)",
            )

        with c3:
            st.metric(
                "무",
                f"{stat['draw']:,} "
                f"({stat['draw_pct']:.2f}%)",
            )

        with c4:
            st.metric(
                "패",
                f"{stat['lose']:,} "
                f"({stat['lose_pct']:.2f}%)",
            )

        st.markdown(
            "### 📊 배당 대비 결과확률"
        )

        if result["probability_rows"]:

            st.dataframe(
                result["probability_rows"],
                use_container_width=True,
                hide_index=True,
            )

        matched = result["rows"]

        if matched:

            display = []

            for row in matched[:1000]:

                display.append({
                    "날짜":
                        row.get("match_date"),

                    "홈":
                        row.get("home_team"),

                    "스코어":
                        f"{row.get('home_score')}"
                        f" - "
                        f"{row.get('away_score')}",

                    "원정":
                        row.get("away_team"),

                    "결과":
                        row.get("result"),

                    "업체":
                        row.get("bookmaker"),

                    "승":
                        row.get("final_home"),

                    "무":
                        row.get("final_draw"),

                    "패":
                        row.get("final_away"),
                })

            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True,
            )

        else:

            st.warning(
                "완전히 동일한 배당의 "
                "과거 경기가 없습니다."
            )


# ============================================================
# TAB 4
# ============================================================

with tab4:

    st.subheader(
        "🔊 배당 확률 분석"
    )

    st.caption(
        "배당 입력 → 시장 확률 계산"
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        home = st.number_input(
            "승 배당",
            min_value=1.01,
            value=2.00,
            step=0.01,
            format="%.2f",
            key="manual_home",
        )

    with c2:

        draw = st.number_input(
            "무 배당",
            min_value=1.01,
            value=3.20,
            step=0.01,
            format="%.2f",
            key="manual_draw",
        )

    with c3:

        away = st.number_input(
            "패 배당",
            min_value=1.01,
            value=3.50,
            step=0.01,
            format="%.2f",
            key="manual_away",
        )

    probability = analysis.analyze_manual_odds(
        home,
        draw,
        away,
    )

    if probability:

        c1, c2, c3 = st.columns(3)

        with c1:
            st.metric(
                "승 확률",
                f"{probability['승']:.2f}%",
            )

        with c2:
            st.metric(
                "무 확률",
                f"{probability['무']:.2f}%",
            )

        with c3:
            st.metric(
                "패 확률",
                f"{probability['패']:.2f}%",
            )

        st.bar_chart(
            probability
        )

        st.markdown(
            "### 🎤 음성 입력"
        )

        st.components.v1.html(
            """
            <div style="
                padding:10px;
                border:1px solid #ddd;
                border-radius:10px;
                text-align:center;
            ">

            <button
                id="mic"
                style="
                    width:100%;
                    height:48px;
                    font-size:18px;
                    border-radius:8px;
                    border:1px solid #aaa;
                    background:#f5f5f5;
                "
            >
            🎤 마이크 음성입력
            </button>

            <div id="text"
                 style="
                    margin-top:10px;
                    font-size:16px;
                    color:#333;
                 ">
            버튼을 누르고 말하세요.
            </div>

            <script>

            const SpeechRecognition =
                window.SpeechRecognition ||
                window.webkitSpeechRecognition;

            const button =
                document.getElementById("mic");

            const output =
                document.getElementById("text");

            if (!SpeechRecognition) {

                button.disabled = true;

                output.innerText =
                    "이 브라우저에서는 음성입력을 지원하지 않습니다.";

            } else {

                const recognition =
                    new SpeechRecognition();

                recognition.lang = "ko-KR";

                recognition.continuous = false;

                recognition.interimResults = false;

                button.onclick = function() {

                    output.innerText =
                        "🎤 듣는 중...";

                    recognition.start();

                };

                recognition.onresult =
                    function(event) {

                    const text =
                        event.results[0][0].transcript;

                    output.innerText =
                        "인식 결과: " + text;

                };

                recognition.onerror =
                    function() {

                    output.innerText =
                        "음성 인식에 실패했습니다.";

                };

            }

            </script>
            </div>
            """,
            height=150,
        )

        st.markdown(
            "### 🔊 결과 듣기"
        )

        speech_text = (
            f"승리 확률 "
            f"{probability['승']:.1f} 퍼센트. "
            f"무승부 확률 "
            f"{probability['무']:.1f} 퍼센트. "
            f"패배 확률 "
            f"{probability['패']:.1f} 퍼센트."
        )

        st.components.v1.html(
            f"""
            <button
                onclick="
                    const u =
                    new SpeechSynthesisUtterance(
                        `{speech_text}`
                    );

                    u.lang='ko-KR';
                    u.rate=0.9;

                    speechSynthesis.cancel();
                    speechSynthesis.speak(u);
                "
                style="
                    width:100%;
                    height:48px;
                    font-size:18px;
                    border-radius:8px;
                    border:1px solid #ccc;
                    background:#f5f5f5;
                "
            >
            🔊 결과 읽기
            </button>
            """,
            height=60,
        )


# ============================================================
# 하단
# ============================================================

st.divider()

st.caption(
    "⚽ Scoreman 데이터 분석 시스템 · "
    "최종배당 기준 · 실제 결과 기준"
                )
