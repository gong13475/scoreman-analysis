# ============================================================
# app.py
# ⚽ 전종목 해외배당 분석
# Scoreman 자동수집 / 최종배당 / 실제결과 / 확률분석
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

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 1rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    .big-number {
        font-size: 28px;
        font-weight: 700;
    }

    .small-text {
        color: #777;
        font-size: 13px;
    }

    button {
        min-height: 42px !important;
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
    "실제결과 · 확률분석"
)


# ============================================================
# DB 상태
# ============================================================

status = database.get_database_status()

c1, c2, c3 = st.columns(3)

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

    st.info(
        "자동 재시도 없음 · "
        "실패/배당 없음은 완료처리하지 않습니다."
    )

    col1, col2 = st.columns(2)

    with col1:

        start_id = st.number_input(
            "시작 ID",
            min_value=1,
            value=2005000,
            step=1,
        )

    with col2:

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

    if company_mode == "선택 업체만 수집":

        available = database.get_bookmakers()

        company_names = [
            x["bookmaker"]
            for x in available
        ]

        selected_companies = st.multiselect(
            "업체 선택",
            company_names,
            default=[],
        )

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "🚀 수집시작",
            type="primary",
            use_container_width=True,
        ):

            if company_mode == "선택 업체만 수집":

                if not selected_companies:

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
                    else:
                        st.error(message)

            else:

                ok, message = (
                    collector.start_background_collection(
                        start_id,
                        end_id,
                        [],
                        delay,
                    )
                )

                if ok:
                    st.success(message)
                else:
                    st.error(message)

    with col2:

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
                    "현재 실행 중인 수집이 없습니다."
                )


    # --------------------------------------------------------
    # 진행상태
    # --------------------------------------------------------

    st.markdown(
        "### 📈 수집 상태"
    )

    progress = collector.get_progress()

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

    st.write(
        f"저장된 배당: "
        f"{progress['odds']:,}"
    )

    if progress[
        "last_completed_id"
    ]:

        st.write(
            "마지막 완료 ID:",
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
# TAB 2 전체 분석
# ============================================================

with tab2:

    st.subheader(
        "📊 전체 경기 분석"
    )

    bookmakers = database.get_bookmakers()

    bookmaker_options = [
        "전체 업체"
    ] + [
        x["bookmaker"]
        for x in bookmakers
    ]

    selected_bookmaker = st.selectbox(
        "업체",
        bookmaker_options,
    )

    if selected_bookmaker == "전체 업체":

        rows = database.get_analysis_rows()

    else:

        rows = database.get_analysis_rows(
            selected_bookmaker
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

    st.markdown(
        "### ⚽ 최근 저장 경기"
    )

    if rows:

        display_rows = []

        for row in rows[:200]:

            display_rows.append(
                {
                    "경기ID":
                        row.get("schedule_id"),

                    "날짜":
                        row.get("match_date"),

                    "홈":
                        row.get("home_team"),

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
        "🎯 동일배당 과거 결과 분석"
    )

    st.caption(
        "지정한 승/무/패 배당과 동일하거나 "
        "허용오차 안에 있는 과거 경기를 찾습니다."
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        target_home = st.number_input(
            "승 배당",
            min_value=1.01,
            value=2.00,
            step=0.01,
            format="%.2f",
        )

    with c2:

        target_draw = st.number_input(
            "무 배당",
            min_value=1.01,
            value=3.20,
            step=0.01,
            format="%.2f",
        )

    with c3:

        target_away = st.number_input(
            "패 배당",
            min_value=1.01,
            value=3.50,
            step=0.01,
            format="%.2f",
        )

    tolerance = st.number_input(
        "허용 오차",
        min_value=0.001,
        value=0.01,
        step=0.01,
        format="%.3f",
    )

    bookmaker = st.selectbox(
        "분석 업체",
        [
            "전체 업체"
        ]
        + [
            x["bookmaker"]
            for x in database.get_bookmakers()
        ],
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
            tolerance,
        )

        stat = result["stats"]

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.metric(
                "동일배당 경기",
                stat["total"],
            )

        with c2:
            st.metric(
                "승",
                f"{stat['win']} "
                f"({stat['win_pct']:.2f}%)",
            )

        with c3:
            st.metric(
                "무",
                f"{stat['draw']} "
                f"({stat['draw_pct']:.2f}%)",
            )

        with c4:
            st.metric(
                "패",
                f"{stat['lose']} "
                f"({stat['lose_pct']:.2f}%)",
            )

        matched = result["rows"]

        if matched:

            display = []

            for row in matched[:500]:

                display.append(
                    {
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
                "조건에 맞는 과거 경기가 없습니다."
            )


# ============================================================
# TAB 4 수동 배당
# ============================================================

with tab4:

    st.subheader(
        "🔊 배당 확률 분석"
    )

    st.caption(
        "배당을 직접 입력하면 "
        "승/무/패 시장확률을 계산합니다."
    )

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

    probability = analysis.analyze_manual_odds(
        manual_home,
        manual_draw,
        manual_away,
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

        st.markdown(
            "### 🔊 결과 음성듣기"
        )

        text = (
            f"승리 확률 "
            f"{probability['승']:.1f} 퍼센트. "
            f"무승부 확률 "
            f"{probability['무']:.1f} 퍼센트. "
            f"패배 확률 "
            f"{probability['패']:.1f} 퍼센트."
        )

        # 브라우저 음성
        st.components.v1.html(
            f"""
            <button
                onclick="
                const u = new SpeechSynthesisUtterance(
                    `{text}`
                );
                u.lang='ko-KR';
                u.rate=0.9;
                speechSynthesis.cancel();
                speechSynthesis.speak(u);
                "
                style="
                width:100%;
                height:45px;
                font-size:17px;
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

    else:

        st.warning(
            "올바른 배당을 입력하세요."
        )


# ============================================================
# 하단
# ============================================================

st.divider()

st.caption(
    "⚽ Scoreman 데이터 분석 시스템 · "
    "최종배당 기준"
    )
