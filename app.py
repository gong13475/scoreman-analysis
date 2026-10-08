# ============================================================
# app.py
# ⚽ 전종목 해외배당 분석
# Scoreman 자동수집 / 최종배당 / 실제결과 / 확률분석
# ============================================================

import time
import streamlit as st
import streamlit.components.v1 as components

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

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 1rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    button {
        min-height: 42px !important;
    }

    .running-box {
        padding: 15px;
        border-radius: 10px;
        background: #e8f5e9;
        border: 1px solid #66bb6a;
        color: #1b5e20;
        font-weight: 700;
        margin-bottom: 15px;
    }

    .stop-box {
        padding: 15px;
        border-radius: 10px;
        background: #fff3e0;
        border: 1px solid #ff9800;
        color: #e65100;
        font-weight: 700;
        margin-bottom: 15px;
    }

    @media (max-width: 768px) {

        .block-container {
            padding-left: 0.6rem;
            padding-right: 0.6rem;
        }

        h1 {
            font-size: 25px !important;
        }

        h2 {
            font-size: 21px !important;
        }

        h3 {
            font-size: 18px !important;
        }
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 제목
# ============================================================

st.title(
    "⚽ 전종목 해외배당 분석"
)

st.caption(
    "스코어맨 자동수집 · 해외업체 최종배당 · "
    "실제결과 · 확률분석 · 영구저장 · 이어받기"
)


# ============================================================
# DB 상태
# ============================================================

status = (
    database.get_database_status()
)

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
        "DB 용량",
        f"{status['size_mb']:.2f} MB",
    )

st.caption(
    f"DB 방식: {status['type']} | "
    f"완료 경기: {status['completed']:,} | "
    f"마지막 완료 ID: "
    f"{status['last_completed_id']}"
)


st.divider()


# ============================================================
# 탭
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "⚽ 수집",
        "📊 전체 분석",
        "🎯 동일배당",
        "🔊 배당 분석",
    ]
)


# ============================================================
# TAB 1 수집
# ============================================================

with tab1:

    st.subheader(
        "⚽ Scoreman 경기 수집"
    )

    progress = (
        collector.get_progress()
    )

    # --------------------------------------------------------
    # 수집중 표시
    # --------------------------------------------------------

    if progress["running"]:

        current_id = (
            progress["current_id"]
        )

        st.markdown(
            f"""
            <div class="running-box">
            🟢 현재 수집중<br>
            현재 경기 ID:
            {current_id if current_id else '-'}<br>
            진행:
            {progress['current']:,}
            /
            {progress['total']:,}
            </div>
            """,
            unsafe_allow_html=True,
        )

    else:

        st.info(
            "현재 수집 대기 상태입니다."
        )

    st.info(
        "실패 경기 / 배당 없음은 완료처리하지 않습니다. "
        "중단 후에는 DB에 저장된 마지막 정상 완료 ID 다음부터 "
        "이어받을 수 있습니다."
    )

    col1, col2 = st.columns(2)

    with col1:

        start_id = st.number_input(
            "시작 ID",
            min_value=1,
            value=2005000,
            step=1,
            key="collector_start",
        )

    with col2:

        end_id = st.number_input(
            "종료 ID",
            min_value=1,
            value=2005000,
            step=1,
            key="collector_end",
        )

    delay = st.number_input(
        "요청 간격(초)",
        min_value=0.0,
        max_value=60.0,
        value=0.50,
        step=0.10,
        key="collector_delay",
    )

    st.markdown(
        "### 🏢 수집 업체"
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

    if (
        company_mode
        == "선택 업체만 수집"
    ):

        available = (
            database.get_bookmakers()
        )

        company_names = [
            x["bookmaker"]
            for x in available
        ]

        selected_companies = (
            st.multiselect(
                "업체 선택",
                company_names,
                default=[],
            )
        )

    # --------------------------------------------------------
    # 버튼
    # --------------------------------------------------------

    c1, c2, c3 = st.columns(3)

    with c1:

        if st.button(
            "🚀 수집시작",
            type="primary",
            use_container_width=True,
            disabled=progress["running"],
        ):

            if (
                company_mode
                == "선택 업체만 수집"
                and not selected_companies
            ):

                st.warning(
                    "수집할 업체를 선택하세요."
                )

            else:

                ok, message = (
                    collector.start_background_collection(
                        start_id,
                        end_id,
                        selected_companies,
                        delay,
                    )
                )

                if ok:
                    st.success(message)
                    st.rerun()

                else:
                    st.error(message)

    with c2:

        if st.button(
            "🔄 이어받기",
            use_container_width=True,
            disabled=progress["running"],
        ):

            if (
                company_mode
                == "선택 업체만 수집"
                and not selected_companies
            ):

                st.warning(
                    "수집할 업체를 선택하세요."
                )

            else:

                ok, message = (
                    collector.resume_collection(
                        start_id,
                        end_id,
                        selected_companies,
                        delay,
                    )
                )

                if ok:
                    st.success(message)
                    st.rerun()

                else:
                    st.warning(message)

    with c3:

        if st.button(
            "🛑 수집중지",
            use_container_width=True,
            disabled=not progress["running"],
        ):

            if collector.stop_collection():

                st.warning(
                    "수집 중지 요청을 보냈습니다."
                )

                time.sleep(0.3)

                st.rerun()

    # --------------------------------------------------------
    # DB 기준 이어받기 위치
    # --------------------------------------------------------

    last_completed = (
        database.get_last_completed_id_in_range(
            start_id,
            end_id,
        )
    )

    st.markdown(
        "### 🔄 영구 이어받기 상태"
    )

    if last_completed is not None:

        next_id = (
            last_completed + 1
        )

        st.success(
            f"마지막 정상 저장 ID: "
            f"{last_completed:,}  "
            f"→ 다음 이어받기 ID: "
            f"{next_id:,}"
        )

    else:

        st.info(
            "지정 범위에서 완료된 ID가 없습니다."
        )

    # --------------------------------------------------------
    # 진행상태
    # --------------------------------------------------------

    st.markdown(
        "### 📈 수집 상태"
    )

    progress = (
        collector.get_progress()
    )

    p1, p2, p3, p4 = st.columns(4)

    with p1:

        st.metric(
            "진행",
            f"{progress['current']:,} / "
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

    st.progress(
        min(
            max(
                progress["percent"]
                / 100,
                0,
            ),
            1,
        )
    )

    st.write(
        f"진행률: "
        f"{progress['percent']:.1f}%"
    )

    st.write(
        f"현재 ID: "
        f"{progress['current_id'] or '-'}"
    )

    st.write(
        f"이번 수집 저장 배당: "
        f"{progress['odds']:,}"
    )

    if progress[
        "last_completed_id"
    ]:

        st.write(
            "이번 실행 마지막 완료 ID:",
            progress[
                "last_completed_id"
            ],
        )

    # --------------------------------------------------------
    # 자동 새로고침
    # --------------------------------------------------------

    if progress["running"]:

        time.sleep(1)

        st.rerun()

    # --------------------------------------------------------
    # 로그
    # --------------------------------------------------------

    show_log = st.checkbox(
        "📜 수집 로그 보기",
        value=False,
    )

    if show_log:

        logs = (
            collector.get_logs()
        )

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
# TAB 2 전체 분석
# ============================================================

with tab2:

    st.subheader(
        "📊 전체 경기 분석"
    )

    bookmakers = (
        database.get_bookmakers()
    )

    bookmaker_options = (
        ["전체 업체"]
        + [
            x["bookmaker"]
            for x in bookmakers
        ]
    )

    selected_bookmaker = (
        st.selectbox(
            "업체",
            bookmaker_options,
            key="analysis_bookmaker",
        )
    )

    if (
        selected_bookmaker
        == "전체 업체"
    ):

        rows = (
            database.get_analysis_rows()
        )

    else:

        rows = (
            database.get_analysis_rows(
                selected_bookmaker
            )
        )

    stats = analysis.analyze_rows(
        rows
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "전체 경기",
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

    # --------------------------------------------------------
    # 전체 배당대비 확률
    # --------------------------------------------------------

    st.markdown(
        "### 🎯 전체 경기 "
        "배당대비 확률 / 부족확률"
    )

    overall_probability = (
        analysis.overall_probability_analysis(
            rows
        )
    )

    probability_table = []

    for outcome in [
        "승",
        "무",
        "패",
    ]:

        item = (
            overall_probability[
                outcome
            ]
        )

        probability_table.append(
            {
                "결과":
                    outcome,

                "실제 경기 수":
                    item["count"],

                "실제 비율":
                    f"{item['actual_pct']:.2f}%",

                "배당대비 확률":
                    f"{item['expected_pct']:.2f}%",

                "부족확률":
                    f"{item['shortfall']:.2f}%p",

                "초과확률":
                    f"{item['excess']:.2f}%p",
            }
        )

    st.dataframe(
        probability_table,
        use_container_width=True,
        hide_index=True,
    )

    # --------------------------------------------------------
    # 결과별
    # --------------------------------------------------------

    st.markdown(
        "### 📌 결과별 실제 비율"
    )

    result_summary = (
        analysis.result_probability_summary(
            rows
        )
    )

    if result_summary:

        st.dataframe(
            result_summary,
            use_container_width=True,
            hide_index=True,
        )

    # --------------------------------------------------------
    # 업체별
    # --------------------------------------------------------

    st.markdown(
        "### 🏢 업체별 통계"
    )

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

    # --------------------------------------------------------
    # 최근 경기
    # --------------------------------------------------------

    st.markdown(
        "### ⚽ 최근 저장 경기"
    )

    if rows:

        display_rows = []

        for row in rows[:200]:

            display_rows.append(
                {
                    "경기ID":
                        row.get(
                            "schedule_id"
                        ),

                    "날짜":
                        row.get(
                            "match_date"
                        ),

                    "홈":
                        row.get(
                            "home_team"
                        ),

                    "원정":
                        row.get(
                            "away_team"
                        ),

                    "결과":
                        row.get(
                            "result"
                        ),

                    "업체":
                        row.get(
                            "bookmaker"
                        ),

                    "승배당":
                        row.get(
                            "final_home"
                        ),

                    "무배당":
                        row.get(
                            "final_draw"
                        ),

                    "패배당":
                        row.get(
                            "final_away"
                        ),
                }
            )

        st.dataframe(
            display_rows,
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
        "허용오차 없음. "
        "입력한 승/무/패 배당과 정확히 같은 "
        "과거 경기만 검색합니다."
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

    if (
        bookmaker
        == "전체 업체"
    ):

        same_rows = (
            database.get_analysis_rows()
        )

    else:

        same_rows = (
            database.get_analysis_rows(
                bookmaker
            )
        )

    if st.button(
        "🔎 정확히 동일한 배당 검색",
        type="primary",
        use_container_width=True,
    ):

        result = (
            analysis.same_odds_analysis(
                same_rows,
                target_home,
                target_draw,
                target_away,
            )
        )

        stat = result["stats"]

        probability = (
            result["probability"]
        )

        summary = (
            result["summary"]
        )

        # ----------------------------------------------------
        # 경기 수
        # ----------------------------------------------------

        st.markdown(
            "### 📊 동일배당 전체 경기"
        )

        st.metric(
            "동일배당 경기 수",
            f"{stat['total']:,}",
        )

        # ----------------------------------------------------
        # 배당확률
        # ----------------------------------------------------

        if probability:

            st.markdown(
                "### 🎯 배당대비 확률"
            )

            c1, c2, c3 = st.columns(3)

            with c1:

                st.metric(
                    "승",
                    f"{probability['home']:.2f}%",
                )

            with c2:

                st.metric(
                    "무",
                    f"{probability['draw']:.2f}%",
                )

            with c3:

                st.metric(
                    "패",
                    f"{probability['away']:.2f}%",
                )

        # ----------------------------------------------------
        # 실제 결과
        # ----------------------------------------------------

        st.markdown(
            "### 📈 실제 결과 vs 배당확률"
        )

        table = []

        for outcome in [
            "승",
            "무",
            "패",
        ]:

            item = summary.get(
                outcome,
                {},
            )

            table.append(
                {
                    "결과":
                        outcome,

                    "실제 수":
                        item.get(
                            "count",
                            0,
                        ),

                    "실제 비율":
                        f"{item.get('actual_pct', 0):.2f}%",

                    "배당대비 확률":
                        f"{item.get('expected_pct', 0):.2f}%",

                    "부족확률":
                        f"{item.get('shortfall', 0):.2f}%p",

                    "초과확률":
                        f"{item.get('excess', 0):.2f}%p",
                }
            )

        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
        )

        # ----------------------------------------------------
        # 결과별 강조
        # ----------------------------------------------------

        if stat["total"] > 0:

            worst = max(
                summary.items(),
                key=lambda x:
                x[1]["shortfall"],
            )

            closest = min(
                summary.items(),
                key=lambda x:
                x[1]["shortfall"],
            )

            st.warning(
                f"가장 부족한 결과: "
                f"{worst[0]} "
                f"{worst[1]['shortfall']:.2f}%p"
            )

            st.success(
                f"배당확률 대비 가장 가까운 결과: "
                f"{closest[0]}"
            )

        # ----------------------------------------------------
        # 경기목록
        # ----------------------------------------------------

        st.markdown(
            "### ⚽ 동일배당 해당 경기"
        )

        matched = result[
            "rows"
        ]

        if matched:

            display = []

            for row in matched[:1000]:

                display.append(
                    {
                        "경기ID":
                            row.get(
                                "schedule_id"
                            ),

                        "날짜":
                            row.get(
                                "match_date"
                            ),

                        "홈":
                            row.get(
                                "home_team"
                            ),

                        "원정":
                            row.get(
                                "away_team"
                            ),

                        "결과":
                            row.get(
                                "result"
                            ),

                        "업체":
                            row.get(
                                "bookmaker"
                            ),

                        "승":
                            row.get(
                                "final_home"
                            ),

                        "무":
                            row.get(
                                "final_draw"
                            ),

                        "패":
                            row.get(
                                "final_away"
                            ),
                    }
                )

            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True,
            )

        else:

            st.warning(
                "정확히 동일한 배당의 "
                "과거 경기가 없습니다."
            )


# ============================================================
# TAB 4 배당 분석
# ============================================================

with tab4:

    st.subheader(
        "🔊 배당 확률 분석"
    )

    st.caption(
        "배당을 직접 입력하거나 "
        "마이크 음성입력 보조를 사용할 수 있습니다."
    )

    # --------------------------------------------------------
    # 음성입력
    # --------------------------------------------------------

    st.markdown(
        "### 🎤 마이크 음성입력"
    )

    st.caption(
        "예: '2.00 3.20 3.50'이라고 말하면 "
        "아래 입력칸에 붙여넣을 숫자를 보여줍니다."
    )

    components.html(
        """
        <div style="
            padding:10px;
            border:1px solid #ddd;
            border-radius:10px;
        ">

        <button
            id="mic"
            style="
                width:100%;
                height:48px;
                font-size:17px;
                border-radius:8px;
                border:1px solid #aaa;
                background:#f5f5f5;
            "
        >
        🎤 마이크 시작
        </button>

        <div id="status"
             style="
                margin-top:10px;
                color:#666;
             ">
        대기중
        </div>

        <div id="result"
             style="
                margin-top:10px;
                font-size:20px;
                font-weight:bold;
             ">
        -
        </div>

        <button
            id="copy"
            style="
                width:100%;
                height:42px;
                margin-top:10px;
                border-radius:8px;
            "
        >
        📋 결과 복사
        </button>

        </div>

        <script>

        const button =
            document.getElementById("mic");

        const status =
            document.getElementById("status");

        const result =
            document.getElementById("result");

        const copy =
            document.getElementById("copy");

        const SpeechRecognition =
            window.SpeechRecognition ||
            window.webkitSpeechRecognition;

        if (!SpeechRecognition) {

            status.innerText =
                "이 브라우저는 음성인식을 지원하지 않습니다.";

            button.disabled = true;

        } else {

            const recognition =
                new SpeechRecognition();

            recognition.lang =
                "ko-KR";

            recognition.continuous =
                false;

            recognition.interimResults =
                false;

            button.onclick = function() {

                status.innerText =
                    "🎤 듣는 중...";

                result.innerText =
                    "-";

                recognition.start();
            };

            recognition.onresult =
                function(event) {

                    const text =
                        event.results[0][0].transcript;

                    result.innerText =
                        text;

                    status.innerText =
                        "인식 완료";

                };

            recognition.onerror =
                function(event) {

                    status.innerText =
                        "음성인식 오류: "
                        + event.error;

                };

            recognition.onend =
                function() {

                    if (
                        status.innerText
                        === "🎤 듣는 중..."
                    ) {

                        status.innerText =
                            "인식 종료";

                    }
                };
        }

        copy.onclick = function() {

            const text =
                result.innerText;

            if (
                text &&
                text !== "-"
            ) {

                navigator.clipboard.writeText(
                    text
                );

                status.innerText =
                    "📋 복사 완료";

            }
        };

        </script>
        """,
        height=240,
    )

    # --------------------------------------------------------
    # 숫자 입력
    # --------------------------------------------------------

    c1, c2, c3 = st.columns(3)

    with c1:

        manual_home = st.number_input(
            "승 배당",
            min_value=1.01,
            value=2.00,
            step=0.01,
            format="%.2f",
            key="manual_home",
        )

    with c2:

        manual_draw = st.number_input(
            "무 배당",
            min_value=1.01,
            value=3.20,
            step=0.01,
            format="%.2f",
            key="manual_draw",
        )

    with c3:

        manual_away = st.number_input(
            "패 배당",
            min_value=1.01,
            value=3.50,
            step=0.01,
            format="%.2f",
            key="manual_away",
        )

    probability = (
        analysis.analyze_manual_odds(
            manual_home,
            manual_draw,
            manual_away,
        )
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

        st.markdown(
            "### 📊 확률"
        )

        st.bar_chart(
            probability
        )

        # ----------------------------------------------------
        # 듣기
        # ----------------------------------------------------

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

        components.html(
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
                    height:50px;
                    font-size:17px;
                    border-radius:8px;
                    border:1px solid #ccc;
                    background:#f5f5f5;
                "
            >
            🔊 확률 읽어주기
            </button>
            """,
            height=65,
        )

    else:

        st.warning(
            "올바른 배당을 입력하세요."
        )


# ============================================================
# 하단 DB 상태
# ============================================================

st.divider()

final_status = (
    database.get_database_status()
)

st.caption(
    f"⚽ Scoreman 데이터 분석 시스템 | "
    f"DB: {final_status['type']} | "
    f"경기 {final_status['matches']:,} | "
    f"배당 {final_status['odds']:,} | "
    f"용량 {final_status['size_mb']:.2f} MB"
    )
