# ============================================================
# app.py
# ⚽ 전종목 해외배당 분석
# Scoreman 자동수집 / 최종배당 / 실제결과 / 확률분석
# ============================================================

import os
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


# 안전하게 숫자 가져오기
matches_count = status.get(
    "matches",
    0,
)

odds_count = status.get(
    "odds",
    0,
)

bookmakers_count = status.get(
    "bookmakers",
    0,
)


# ============================================================
# DB 저장용량
# ============================================================

def get_db_size_text():

    # --------------------------------------------------------
    # 1. database.py가 이미 용량을 반환하는 경우
    # --------------------------------------------------------

    possible_keys = [
        "db_size_mb",
        "database_size_mb",
        "size_mb",
        "db_size",
        "database_size",
    ]

    for key in possible_keys:

        value = status.get(key)

        if value is not None:

            try:

                number = float(value)

                return f"{number:,.2f} MB"

            except Exception:
                pass


    # --------------------------------------------------------
    # 2. database.py가 bytes를 반환하는 경우
    # --------------------------------------------------------

    possible_byte_keys = [
        "db_size_bytes",
        "database_size_bytes",
        "size_bytes",
    ]

    for key in possible_byte_keys:

        value = status.get(key)

        if value is not None:

            try:

                number = float(value)

                if number >= 1024 * 1024 * 1024:

                    return (
                        f"{number / (1024 * 1024 * 1024):,.2f} GB"
                    )

                return (
                    f"{number / (1024 * 1024):,.2f} MB"
                )

            except Exception:
                pass


    # --------------------------------------------------------
    # 3. 로컬 SQLite 파일 크기 확인
    # --------------------------------------------------------

    possible_files = [
        "scoreman.db",
        "historical_odds.db",
    ]

    for filename in possible_files:

        try:

            if os.path.exists(filename):

                size = os.path.getsize(
                    filename
                )

                if size >= 1024 * 1024 * 1024:

                    return (
                        f"{size / (1024 * 1024 * 1024):,.2f} GB"
                    )

                return (
                    f"{size / (1024 * 1024):,.2f} MB"
                )

        except Exception:
            pass


    # --------------------------------------------------------
    # 4. 원격 DB인데 database.py에서 용량을
    #    제공하지 않는 경우
    # --------------------------------------------------------

    return "확인 중"


db_size_text = get_db_size_text()


# ============================================================
# DB 상태 표시
# ============================================================

c1, c2, c3, c4 = st.columns(4)

with c1:

    st.metric(
        "저장 경기",
        f"{matches_count:,}",
    )

with c2:

    st.metric(
        "저장 최종배당",
        f"{odds_count:,}",
    )

with c3:

    st.metric(
        "실제 저장 업체",
        f"{bookmakers_count:,}",
    )

with c4:

    st.metric(
        "DB 저장용량",
        db_size_text,
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


    if progress["last_completed_id"]:

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


    # --------------------------------------------------------
    # 데이터
    # --------------------------------------------------------

    if selected_bookmaker == "전체 업체":

        rows = database.get_analysis_rows()

    else:

        rows = database.get_analysis_rows(
            selected_bookmaker
        )


    # --------------------------------------------------------
    # 기본 통계
    # --------------------------------------------------------

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


    # ========================================================
    # 전체 경기 배당 대비 확률
    # ========================================================

    st.markdown(
        "### 🎯 전체 경기 배당 대비 확률"
    )

    probability = (
        analysis.overall_probability_analysis(
            rows
        )
    )


    st.caption(
        "배당 기대확률 = 각 경기 최종 1X2 배당을 "
        "정규화한 확률의 평균 / "
        "부족확률 = 실제 발생확률 - 배당 기대확률"
    )


    probability_table = [

        {
            "결과": "승",
            "경기수":
                probability["win"]["count"],
            "배당 기대확률":
                f"{probability['win']['expected_pct']:.2f}%",
            "실제 발생확률":
                f"{probability['win']['actual_pct']:.2f}%",
            "부족확률":
                f"{probability['win']['shortfall_pct']:+.2f}%",
        },

        {
            "결과": "무",
            "경기수":
                probability["draw"]["count"],
            "배당 기대확률":
                f"{probability['draw']['expected_pct']:.2f}%",
            "실제 발생확률":
                f"{probability['draw']['actual_pct']:.2f}%",
            "부족확률":
                f"{probability['draw']['shortfall_pct']:+.2f}%",
        },

        {
            "결과": "패",
            "경기수":
                probability["lose"]["count"],
            "배당 기대확률":
                f"{probability['lose']['expected_pct']:.2f}%",
            "실제 발생확률":
                f"{probability['lose']['actual_pct']:.2f}%",
            "부족확률":
                f"{probability['lose']['shortfall_pct']:+.2f}%",
        },
    ]


    st.dataframe(
        probability_table,
        use_container_width=True,
        hide_index=True,
    )


    st.info(
        f"전체 분석 경기: {probability['total']:,}경기 · "
        f"유효한 1X2 최종배당이 있는 경기: "
        f"{probability['valid_odds_games']:,}경기"
    )


    # --------------------------------------------------------
    # 부족확률 설명
    # --------------------------------------------------------

    st.markdown(
        """
        **부족확률 해석**

        `+` 값 → 실제 결과가 배당에서 예상한 것보다 많이 발생

        `-` 값 → 실제 결과가 배당에서 예상한 것보다 적게 발생

        예: 부족확률 `+3.50%`
        → 실제 발생률이 배당 기대확률보다 3.50%p 높음
        """
    )


    # ========================================================
    # 결과별 실제 비율
    # ========================================================

    st.markdown(
        "### 📌 결과별 실제 비율"
    )


    result_summary = (
        analysis.result_probability_summary(
            rows
        )
    )


    if result_summary:

        result_display = []

        for item in result_summary:

            result_display.append(
                {
                    "결과":
                        item["result"],

                    "경기수":
                        item["count"],

                    "실제 발생확률":
                        f"{item['actual_pct']:.2f}%",

                    "배당 기대확률":
                        f"{item['expected_pct']:.2f}%",

                    "부족확률":
                        f"{item['shortfall_pct']:+.2f}%",
                }
            )

        st.dataframe(
            result_display,
            use_container_width=True,
            hide_index=True,
        )


    # ========================================================
    # 업체별
    # ========================================================

    st.markdown(
        "### 🏢 업체별 통계"
    )


    bookmaker_stats = (
        analysis.analyze_by_bookmaker(
            rows
        )
    )


    if bookmaker_stats:

        bookmaker_display = []

        for item in bookmaker_stats:

            bookmaker_display.append(
                {
                    "업체":
                        item["bookmaker"],

                    "경기수":
                        item["total"],

                    "승 실제":
                        f"{item['win_actual_pct']:.2f}%",

                    "승 기대":
                        f"{item['win_expected_pct']:.2f}%",

                    "승 부족":
                        f"{item['win_shortfall_pct']:+.2f}%",

                    "무 실제":
                        f"{item['draw_actual_pct']:.2f}%",

                    "무 기대":
                        f"{item['draw_expected_pct']:.2f}%",

                    "무 부족":
                        f"{item['draw_shortfall_pct']:+.2f}%",

                    "패 실제":
                        f"{item['lose_actual_pct']:.2f}%",

                    "패 기대":
                        f"{item['lose_expected_pct']:.2f}%",

                    "패 부족":
                        f"{item['lose_shortfall_pct']:+.2f}%",
                }
            )


        st.dataframe(
            bookmaker_display,
            use_container_width=True,
            hide_index=True,
        )


    # ========================================================
    # 최근 저장 경기
    # ========================================================

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
        "🎯 동일배당 과거 결과 분석"
    )

    st.caption(
        "입력한 승/무/패 배당과 "
        "**완전히 동일한 배당**만 검색합니다."
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


    # ========================================================
    # 허용오차 입력 삭제
    # ========================================================

    st.success(
        "허용오차: 0.00 "
        "→ 세 배당이 완전히 동일한 경기만 검색합니다."
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
        key="same_odds_bookmaker",
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

        # ----------------------------------------------------
        # tolerance를 아예 0으로 고정
        # ----------------------------------------------------

        result = analysis.same_odds_analysis(
            rows,
            target_home,
            target_draw,
            target_away,
            0.0,
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


        # ----------------------------------------------------
        # 동일배당의 배당 대비 확률
        # ----------------------------------------------------

        same_probability = result.get(
            "probability"
        )


        if same_probability:

            st.markdown(
                "### 📊 동일배당 확률 대비 결과"
            )


            same_table = [

                {
                    "결과": "승",
                    "배당 기대확률":
                        f"{same_probability['win']['expected_pct']:.2f}%",
                    "실제 발생확률":
                        f"{same_probability['win']['actual_pct']:.2f}%",
                    "부족확률":
                        f"{same_probability['win']['shortfall_pct']:+.2f}%",
                },

                {
                    "결과": "무",
                    "배당 기대확률":
                        f"{same_probability['draw']['expected_pct']:.2f}%",
                    "실제 발생확률":
                        f"{same_probability['draw']['actual_pct']:.2f}%",
                    "부족확률":
                        f"{same_probability['draw']['shortfall_pct']:+.2f}%",
                },

                {
                    "결과": "패",
                    "배당 기대확률":
                        f"{same_probability['lose']['expected_pct']:.2f}%",
                    "실제 발생확률":
                        f"{same_probability['lose']['actual_pct']:.2f}%",
                    "부족확률":
                        f"{same_probability['lose']['shortfall_pct']:+.2f}%",
                },
            ]


            st.dataframe(
                same_table,
                use_container_width=True,
                hide_index=True,
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


        # ----------------------------------------------------
        # 브라우저 음성
        # ----------------------------------------------------

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
