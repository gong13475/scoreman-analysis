# ============================================================
# app.py
# ⚽ 전종목 해외배당 분석
#
# Scoreman 자동수집
# 최종배당
# 실제결과
# 확률
# 부족확률
# 동일배당
# DB 용량
# 이어받기
# 음성
# ============================================================

import html
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

    button {
        min-height: 42px !important;
    }

    @media (max-width: 768px) {

        .block-container {
            padding-left: 0.55rem;
            padding-right: 0.55rem;
        }

        h1 {
            font-size: 24px !important;
        }

        h2 {
            font-size: 20px !important;
        }

        h3 {
            font-size: 17px !important;
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
    "Scoreman 자동수집 · "
    "해외업체 최종배당 · "
    "실제결과 · 확률 · 부족확률"
)


# ============================================================
# DB 상태
# ============================================================

status = database.get_database_status()

db_size = (
    database.get_database_size_bytes()
)

db_size_text = (
    database.format_bytes(
        db_size
    )
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
# 수집 상태 표시
# ============================================================

@st.fragment(
    run_every=1
)
def collection_status():

    progress = (
        collector.get_progress()
    )

    if progress["running"]:

        st.success(
            "🟢 현재 수집중입니다."
        )

    elif progress["finished"]:

        st.info(
            "⚪ 수집이 종료되었습니다."
        )

    else:

        st.caption(
            "현재 수집 대기 상태"
        )

    p1, p2, p3, p4 = (
        st.columns(4)
    )

    with p1:

        st.metric(
            "현재 ID",
            (
                f"{progress['current_id']:,}"
                if progress[
                    "current_id"
                ]
                else "-"
            ),
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

    percent = min(
        max(
            progress["percent"]
            / 100,
            0,
        ),
        1,
    )

    st.progress(
        percent
    )

    st.caption(
        f"진행률 "
        f"{progress['percent']:.1f}% · "
        f"{progress['current']:,} / "
        f"{progress['total']:,}"
    )

    st.caption(
        f"저장 배당 "
        f"{progress['odds']:,} · "
        f"결과 보정 "
        f"{progress['fixed']:,} · "
        f"마지막 완료 ID "
        f"{progress['last_completed_id'] or '-'}"
    )


# ============================================================
# TAB 1
# ============================================================

with tab1:

    st.subheader(
        "⚽ Scoreman 경기 수집"
    )

    st.info(
        "실패/배당 없음은 완료처리하지 않습니다. "
        "중지 후 이어받기를 누르면 저장된 마지막 완료 위치부터 시작합니다."
    )

    col1, col2 = st.columns(2)

    with col1:

        start_id = st.number_input(
            "시작 ID",
            min_value=1,
            value=2005000,
            step=1,
            key="start_id",
        )

    with col2:

        end_id = st.number_input(
            "종료 ID",
            min_value=1,
            value=2005000,
            step=1,
            key="end_id",
        )

    delay = st.number_input(
        "요청 간격(초)",
        min_value=0.0,
        max_value=60.0,
        value=0.50,
        step=0.10,
        format="%.2f",
        key="delay",
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

    st.markdown(
        "### 🚦 수집 제어"
    )

    b1, b2, b3 = st.columns(3)

    # --------------------------------------------------------
    # 수집 시작
    # --------------------------------------------------------

    with b1:

        if st.button(
            "🚀 수집시작",
            type="primary",
            width="stretch",
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
                else:
                    st.error(message)

    # --------------------------------------------------------
    # 이어받기
    # --------------------------------------------------------

    with b2:

        if st.button(
            "▶️ 이어받기",
            width="stretch",
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
                else:
                    st.warning(message)

    # --------------------------------------------------------
    # 중지
    # --------------------------------------------------------

    with b3:

        if st.button(
            "🛑 수집중지",
            width="stretch",
        ):

            if collector.stop_collection():

                st.warning(
                    "수집 중지 요청을 보냈습니다."
                )

            else:

                st.info(
                    "현재 실행 중인 수집이 없습니다."
                )

    st.markdown(
        "### 📈 수집 상태"
    )

    collection_status()

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

    # --------------------------------------------------------
    # 화면 꺼짐 안내
    # --------------------------------------------------------

    st.markdown(
        "### 📱 화면을 꺼도 수집되나요?"
    )

    st.caption(
        "수집 작업은 브라우저 화면이 아니라 "
        "서버의 백그라운드 작업으로 실행됩니다. "
        "따라서 휴대폰에서 다른 앱을 사용하는 동안에도 "
        "서버 프로세스가 살아 있으면 계속 진행됩니다. "
        "다만 Streamlit Cloud가 앱 자체를 절전/재시작하면 "
        "작업이 멈출 수 있으므로 이어받기 기능을 함께 사용합니다."
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

    stats = (
        analysis.analyze_rows(
            rows
        )
    )

    c1, c2, c3, c4 = (
        st.columns(4)
    )

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
    # 전체 배당 대비 확률
    # --------------------------------------------------------

    st.markdown(
        "### 📈 전체 경기 배당대비 확률 / 부족확률"
    )

    probability_rows = (
        analysis.overall_probability_analysis(
            rows
        )
    )

    if probability_rows:

        display = []

        for row in probability_rows:

            display.append(
                {
                    "결과":
                        row["결과"],

                    "전체경기":
                        row["전체경기"],

                    "실제수":
                        row["실제수"],

                    "실제비율":
                        f"{row['실제비율']:.2f}%",

                    "배당대비확률":
                        f"{row['배당대비확률']:.2f}%",

                    "부족확률":
                        f"{row['부족확률']:.2f}%",

                    "실제-확률":
                        f"{row['실제-확률차이']:+.2f}%",
                }
            )

        st.dataframe(
            display,
            width="stretch",
            hide_index=True,
        )

    else:

        st.info(
            "배당 확률을 계산할 데이터가 없습니다."
        )

    # --------------------------------------------------------
    # 결과별 실제비율
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

        display = []

        for row in result_summary:

            display.append(
                {
                    "결과":
                        row["결과"],

                    "수":
                        row["수"],

                    "실제비율":
                        f"{row['실제비율']:.2f}%",
                }
            )

        st.dataframe(
            display,
            width="stretch",
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

        display = []

        for row in bookmaker_stats:

            display.append(
                {
                    "업체":
                        row["bookmaker"],

                    "전체":
                        row["total"],

                    "승":
                        row["win"],

                    "승률":
                        f"{row['win_pct']:.2f}%",

                    "무":
                        row["draw"],

                    "무승부율":
                        f"{row['draw_pct']:.2f}%",

                    "패":
                        row["lose"],

                    "패율":
                        f"{row['lose_pct']:.2f}%",
                }
            )

        st.dataframe(
            display,
            width="stretch",
            hide_index=True,
        )

    # --------------------------------------------------------
    # 최근 저장 경기
    # --------------------------------------------------------

    st.markdown(
        "### ⚽ 최근 저장 경기"
    )

    if rows:

        display_rows = []

        for row in rows[:300]:

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

                    "스코어":
                        (
                            f"{row.get('home_score')}"
                            f"-"
                            f"{row.get('away_score')}"
                            if (
                                row.get(
                                    "home_score"
                                )
                                is not None
                                and
                                row.get(
                                    "away_score"
                                )
                                is not None
                            )
                            else "-"
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
            width="stretch",
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
        "허용오차 0.00 · 입력한 승/무/패 배당과 "
        "정확히 같은 배당만 검색합니다."
    )

    c1, c2, c3 = (
        st.columns(3)
    )

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
        [
            "전체 업체"
        ]
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
        "🔎 동일배당 분석",
        type="primary",
        width="stretch",
        key="same_search",
    ):

        result = (
            analysis.same_odds_analysis(
                same_rows,
                target_home,
                target_draw,
                target_away,
            )
        )

        stat = result[
            "stats"
        ]

        # ----------------------------------------------------
        # 상단 수치
        # ----------------------------------------------------

        c1, c2, c3, c4 = (
            st.columns(4)
        )

        with c1:

            st.metric(
                "동일배당 전체경기",
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

        # ----------------------------------------------------
        # 확률
        # ----------------------------------------------------

        probability = (
            result["probability"]
        )

        if probability:

            st.markdown(
                "### 📊 동일배당 "
                "배당대비 확률 / 실제 / 부족확률"
            )

            summary = result[
                "summary"
            ]

            table = []

            for key in (
                "승",
                "무",
                "패",
            ):

                item = summary[
                    key
                ]

                table.append(
                    {
                        "결과":
                            key,

                        "실제 경기수":
                            item["수"],

                        "실제 비율":
                            f"{item['실제비율']:.2f}%",

                        "배당대비 확률":
                            f"{item['배당확률']:.2f}%",

                        "부족확률":
                            f"{item['부족확률']:.2f}%",

                        "실제-확률":
                            f"{item['차이']:+.2f}%",
                    }
                )

            st.dataframe(
                table,
                width="stretch",
                hide_index=True,
            )

            st.markdown(
                "### 🎯 입력 배당의 시장확률"
            )

            pc1, pc2, pc3 = (
                st.columns(3)
            )

            with pc1:

                st.metric(
                    "승",
                    f"{probability['home']:.2f}%",
                )

            with pc2:

                st.metric(
                    "무",
                    f"{probability['draw']:.2f}%",
                )

            with pc3:

                st.metric(
                    "패",
                    f"{probability['away']:.2f}%",
                )

        # ----------------------------------------------------
        # 경기 목록
        # ----------------------------------------------------

        matched = result[
            "rows"
        ]

        if matched:

            st.markdown(
                "### ⚽ 동일배당 경기 목록"
            )

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

                        "스코어":
                            (
                                f"{row.get('home_score')}"
                                f"-"
                                f"{row.get('away_score')}"
                                if (
                                    row.get(
                                        "home_score"
                                    )
                                    is not None
                                    and
                                    row.get(
                                        "away_score"
                                    )
                                    is not None
                                )
                                else "-"
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
                width="stretch",
                hide_index=True,
            )

        else:

            st.warning(
                "정확히 같은 배당의 "
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
        "배당을 입력하면 "
        "승/무/패 시장확률을 계산합니다."
    )

    c1, c2, c3 = (
        st.columns(3)
    )

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

        c1, c2, c3 = (
            st.columns(3)
        )

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
        # 음성 듣기
        # ----------------------------------------------------

        st.markdown(
            "### 🔊 결과 음성듣기"
        )

        speech_text = (
            f"승리 확률 "
            f"{probability['승']:.1f} "
            f"퍼센트. "
            f"무승부 확률 "
            f"{probability['무']:.1f} "
            f"퍼센트. "
            f"패배 확률 "
            f"{probability['패']:.1f} "
            f"퍼센트."
        )

        safe_text = (
            html.escape(
                speech_text
            )
        )

        st.components.v1.html(
            f"""
            <button
                onclick="
                    const u =
                    new SpeechSynthesisUtterance(
                        `{safe_text}`
                    );

                    u.lang='ko-KR';
                    u.rate=0.9;

                    speechSynthesis.cancel();
                    speechSynthesis.speak(u);
                "
                style="
                    width:100%;
                    height:48px;
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

        # ----------------------------------------------------
        # 마이크
        # ----------------------------------------------------

        st.markdown(
            "### 🎤 마이크 음성입력"
        )

        st.caption(
            "마이크 버튼을 눌러 음성을 녹음할 수 있습니다."
        )

        audio = st.audio_input(
            "🎤 음성 녹음",
            sample_rate=16000,
            key="odds_voice",
        )

        if audio:

            st.success(
                "음성 녹음 완료"
            )

            st.audio(
                audio
            )

            st.caption(
                "위 재생 버튼으로 녹음된 음성을 들을 수 있습니다."
            )

    else:

        st.warning(
            "올바른 배당을 입력하세요."
        )


# ============================================================
# 하단 DB 정보
# ============================================================

st.divider()

final_status = (
    database.get_database_status()
)

final_size = (
    database.get_database_size_bytes()
)

st.caption(
    "⚽ Scoreman 데이터 분석 시스템 · "
    "최종배당 기준"
)

st.caption(
    f"DB: 경기 "
    f"{final_status['matches']:,}개 · "
    f"배당 "
    f"{final_status['odds']:,}개 · "
    f"업체 "
    f"{final_status['bookmakers']:,}개 · "
    f"용량 "
    f"{database.format_bytes(final_size)}"
    )
