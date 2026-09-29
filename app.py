import streamlit as st
import pandas as pd
import database
import analysis

from build_database import build_database_progress


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="스코어맨 배당 분석",
    page_icon="⚽",
    layout="wide"
)


# =========================================================
# DB 초기화
# =========================================================

database.init_database()


# =========================================================
# 제목
# =========================================================

st.title("⚽ 스코어맨 배당 분석")

st.caption(
    "스코어맨 경기결과 + 회사별 초기배당 + 직접입력 최종배당 분석"
)


# =========================================================
# 현재 DB
# =========================================================

col1, col2 = st.columns(2)

with col1:
    st.metric(
        "저장 경기",
        database.get_match_count()
    )

with col2:
    st.metric(
        "저장 배당",
        database.get_odds_count()
    )


st.divider()


# =========================================================
# 자동 DB 수집
# =========================================================

st.header(
    "🚀 과거 스코어맨 DB 자동 수집"
)

st.info(
    "완료된 스코어맨 경기만 확인하여 경기결과와 배당을 SQLite DB에 저장합니다."
)


col1, col2 = st.columns(2)

with col1:

    start_id = st.number_input(
        "시작 경기 ID",
        min_value=1,
        value=2500000,
        step=1000
    )

with col2:

    end_id = st.number_input(
        "마지막 경기 ID",
        min_value=1,
        value=2717000,
        step=1000
    )


total_ids = (
    int(end_id)
    -
    int(start_id)
    +
    1
)


st.write(
    f"검색할 ID: **{total_ids:,}개**"
)


# =========================================================
# 요청 간격
# =========================================================

delay = st.slider(
    "요청 간격",
    min_value=0.2,
    max_value=2.0,
    value=0.5,
    step=0.1
)


# =========================================================
# 자동 수집 시작
# =========================================================

if st.button(
    "🚀 과거 경기 자동 수집 시작",
    type="primary",
    use_container_width=True
):

    if end_id < start_id:

        st.error(
            "마지막 ID가 시작 ID보다 작습니다."
        )

        st.stop()


    progress = st.progress(0)

    log_box = st.empty()

    logs = []


    def progress_callback(value):

        progress.progress(
            min(
                max(
                    float(value),
                    0.0
                ),
                1.0
            )
        )


    def log_callback(message):

        logs.append(
            str(message)
        )

        log_box.code(
            "\n".join(
                logs[-100:]
            )
        )


    with st.spinner(
        "스코어맨 과거 경기를 검색하고 있습니다..."
    ):

        try:

            result = build_database_progress(

                int(start_id),

                int(end_id),

                progress_callback=
                    progress_callback,

                log_callback=
                    log_callback,

                delay=
                    float(delay)

            )

        except Exception as e:

            st.error(
                "수집 오류"
            )

            st.code(
                str(e)
            )

            st.stop()


    progress.progress(1.0)


    st.success(
        "✅ 과거 DB 수집 완료"
    )


    col1, col2, col3, col4 = st.columns(4)


    with col1:

        st.metric(
            "전체 검색",
            result["total"]
        )


    with col2:

        st.metric(
            "저장 성공",
            result["success"]
        )


    with col3:

        st.metric(
            "기존 데이터",
            result["exists"]
        )


    with col4:

        st.metric(
            "배당 업체",
            result["odds"]
        )


st.divider()


# =========================================================
# 저장된 경기
# =========================================================

st.header(
    "📋 저장된 과거 경기"
)


try:

    matches = database.get_all_matches()

except Exception as e:

    matches = []

    st.error(
        str(e)
    )


if matches:

    rows = []

    for row in matches:

        rows.append({

            "경기ID":
                row["schedule_id"],

            "날짜":
                row["match_date"],

            "홈팀":
                row["home_team"],

            "원정팀":
                row["away_team"],

            "스코어":
                (
                    f'{row["home_score"]} - '
                    f'{row["away_score"]}'
                    if
                    row["home_score"] is not None
                    and
                    row["away_score"] is not None
                    else "-"
                ),

            "결과":
                row["result"],

            "출처":
                row["source"]

        })


    matches_df = pd.DataFrame(
        rows
    )


    st.dataframe(
        matches_df,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "아직 저장된 경기가 없습니다."
    )


# =========================================================
# 전체 배당 분석
# =========================================================

st.divider()

st.header(
    "📊 과거 배당 승무패 분석"
)


try:

    analysis_df = (
        analysis.get_all_analysis_data()
    )

except Exception as e:

    analysis_df = pd.DataFrame()

    st.error(
        str(e)
    )


if not analysis_df.empty:

    stats = analysis.calculate_result_stats(
        analysis_df
    )


    col1, col2, col3 = st.columns(3)


    with col1:

        st.metric(
            "승",
            f'{stats["승"]["percent"]}% '
            f'({stats["승"]["count"]}경기)'
        )


    with col2:

        st.metric(
            "무",
            f'{stats["무"]["percent"]}% '
            f'({stats["무"]["count"]}경기)'
        )


    with col3:

        st.metric(
            "패",
            f'{stats["패"]["percent"]}% '
            f'({stats["패"]["count"]}경기)'
        )


    # =====================================================
    # 배당 구간
    # =====================================================

    st.subheader(
        "배당 구간별 통계"
    )


    try:

        table = analysis.make_odds_range_table(
            analysis_df,
            side="home"
        )

        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True
        )

    except Exception as e:

        st.warning(
            f"배당 구간 분석 오류: {e}"
        )


    # =====================================================
    # 업체별 전체 통계
    # =====================================================

    st.subheader(
        "배당업체별 통계"
    )


    try:

        company_table = (
            analysis.get_company_stats(
                analysis_df
            )
        )

        st.dataframe(
            company_table,
            use_container_width=True,
            hide_index=True
        )

    except Exception as e:

        st.warning(
            f"업체별 분석 오류: {e}"
        )


else:

    st.info(
        "과거 경기 데이터를 먼저 수집하세요."
    )


# =========================================================
# 회사별 초기 + 최종 완전 동일배당 검색
# =========================================================

st.divider()

st.header(
    "🎯 회사별 초기 + 최종 완전 동일배당 검색"
)

st.info(
    "선택한 회사의 초기 승/무/패 3개와 "
    "직접 입력한 최종 승/무/패 3개가 "
    "모두 정확히 같은 과거 경기만 검색합니다."
)


# =========================================================
# 배당 데이터
# =========================================================

try:

    odds_df = (
        analysis.get_all_analysis_data()
    )

except Exception as e:

    odds_df = pd.DataFrame()

    st.error(
        f"배당 데이터 오류: {e}"
    )


if odds_df.empty:

    st.warning(
        "배당 데이터가 없습니다."
    )

else:

    odds_df = odds_df.copy()


    # =====================================================
    # 숫자 변환
    # =====================================================

    odds_columns = [

        "initial_home",
        "initial_draw",
        "initial_away",

        "final_home",
        "final_draw",
        "final_away"

    ]


    for column in odds_columns:

        if column in odds_df.columns:

            odds_df[column] = pd.to_numeric(
                odds_df[column],
                errors="coerce"
            )


    # =====================================================
    # 업체 목록
    # =====================================================

    if "company_name" not in odds_df.columns:

        st.error(
            "company_name 컬럼이 없습니다."
        )

    else:

        companies = sorted(

            odds_df["company_name"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()

        )


        if not companies:

            st.warning(
                "등록된 배당업체가 없습니다."
            )

        else:

            # =================================================
            # 업체 선택
            # =================================================

            company = st.selectbox(
                "🏢 배당업체 선택",
                companies
            )


            st.subheader(
                f"{company} 배당 입력"
            )


            # =================================================
            # 초기배당
            # =================================================

            st.markdown(
                "### ① 초기배당"
            )


            col1, col2, col3 = st.columns(3)


            with col1:

                initial_home = st.number_input(
                    "초기 승",
                    min_value=1.01,
                    value=1.36,
                    step=0.01,
                    format="%.2f",
                    key="initial_home_input"
                )


            with col2:

                initial_draw = st.number_input(
                    "초기 무",
                    min_value=1.01,
                    value=4.33,
                    step=0.01,
                    format="%.2f",
                    key="initial_draw_input"
                )


            with col3:

                initial_away = st.number_input(
                    "초기 패",
                    min_value=1.01,
                    value=8.00,
                    step=0.01,
                    format="%.2f",
                    key="initial_away_input"
                )


            # =================================================
            # 최종배당
            # =================================================

            st.markdown(
                "### ② 최종배당"
            )


            col1, col2, col3 = st.columns(3)


            with col1:

                final_home = st.number_input(
                    "최종 승",
                    min_value=1.01,
                    value=1.45,
                    step=0.01,
                    format="%.2f",
                    key="final_home_input"
                )


            with col2:

                final_draw = st.number_input(
                    "최종 무",
                    min_value=1.01,
                    value=3.90,
                    step=0.01,
                    format="%.2f",
                    key="final_draw_input"
                )


            with col3:

                final_away = st.number_input(
                    "최종 패",
                    min_value=1.01,
                    value=6.50,
                    step=0.01,
                    format="%.2f",
                    key="final_away_input"
                )


            # =================================================
            # 현재 입력값
            # =================================================

            st.info(
                f"**{company}**  |  "
                f"초기: {initial_home:.2f} / "
                f"{initial_draw:.2f} / "
                f"{initial_away:.2f}  |  "
                f"최종: {final_home:.2f} / "
                f"{final_draw:.2f} / "
                f"{final_away:.2f}"
            )


            # =================================================
            # 검색
            # =================================================

            if st.button(
                "🔎 초기 + 최종 완전일치 경기 검색",
                type="primary",
                use_container_width=True
            ):

                search_df = odds_df.copy()


                # =============================================
                # 선택한 업체만 검색
                # =============================================

                search_df = search_df[
                    search_df["company_name"]
                    .astype(str)
                    ==
                    str(company)
                ].copy()


                # =============================================
                # ★ 핵심
                #
                # 초기 3개 + 최종 3개
                # 총 6개 배당 모두 완전히 동일
                #
                # 허용오차 없음
                # =============================================

                search_df = search_df[
                    (search_df["initial_home"] == float(initial_home)) &
                    (search_df["initial_draw"] == float(initial_draw)) &
                    (search_df["initial_away"] == float(initial_away)) &
                    (search_df["final_home"] == float(final_home)) &
                    (search_df["final_draw"] == float(final_draw)) &
                    (search_df["final_away"] == float(final_away))
                ].copy()


                # =============================================
                # 결과 없음
                # =============================================

                if search_df.empty:

                    st.warning(
                        "❌ 초기배당과 최종배당이 "
                        "모두 완전히 일치하는 경기가 없습니다."
                    )

                    st.stop()


                # =============================================
                # 같은 경기 중복 제거
                # =============================================

                search_df = search_df.drop_duplicates(
                    subset=["schedule_id"]
                ).copy()


                # =============================================
                # 경기 수
                # =============================================

                total = len(search_df)


                # =============================================
                # 승
                # =============================================

                win = int(
                    (
                        search_df["result"]
                        ==
                        "승"
                    ).sum()
                )


                # =============================================
                # 무
                # =============================================

                draw = int(
                    (
                        search_df["result"]
                        ==
                        "무"
                    ).sum()
                )


                # =============================================
                # 패
                # =============================================

                lose = int(
                    (
                        search_df["result"]
                        ==
                        "패"
                    ).sum()
                )


                # =============================================
                # 성공 메시지
                # =============================================

                st.success(
                    f"✅ 완전 일치 경기 "
                    f"**{total}경기** 발견"
                )


                # =============================================
                # 승무패
                # =============================================

                col1, col2, col3 = st.columns(3)


                with col1:

                    win_percent = (
                        win /
                        total *
                        100
                        if total
                        else 0
                    )

                    st.metric(
                        "승",
                        f"{win_percent:.2f}%",
                        f"{win}경기"
                    )


                with col2:

                    draw_percent = (
                        draw /
                        total *
                        100
                        if total
                        else 0
                    )

                    st.metric(
                        "무",
                        f"{draw_percent:.2f}%",
                        f"{draw}경기"
                    )


                with col3:

                    lose_percent = (
                        lose /
                        total *
                        100
                        if total
                        else 0
                    )

                    st.metric(
                        "패",
                        f"{lose_percent:.2f}%",
                        f"{lose}경기"
                    )


                # =============================================
                # 최다 결과
                # =============================================

                result_count = {

                    "승":
                        win,

                    "무":
                        draw,

                    "패":
                        lose

                }


                recommendation = max(
                    result_count,
                    key=result_count.get
                )


                recommendation_count = (
                    result_count[
                        recommendation
                    ]
                )


                recommendation_percent = (
                    recommendation_count /
                    total *
                    100
                    if total
                    else 0
                )


                st.success(
                    f"🎯 동일배당 최다 결과: "
                    f"**{recommendation}** "
                    f"({recommendation_count}경기 / "
                    f"{recommendation_percent:.2f}%)"
                )


                # =============================================
                # 검색 조건
                # =============================================

                st.subheader(
                    "🔍 완전일치 검색 조건"
                )


                condition_df = pd.DataFrame({

                    "업체": [
                        company
                    ],

                    "초기 승": [
                        f"{initial_home:.2f}"
                    ],

                    "초기 무": [
                        f"{initial_draw:.2f}"
                    ],

                    "초기 패": [
                        f"{initial_away:.2f}"
                    ],

                    "최종 승": [
                        f"{final_home:.2f}"
                    ],

                    "최종 무": [
                        f"{final_draw:.2f}"
                    ],

                    "최종 패": [
                        f"{final_away:.2f}"
                    ]

                })


                st.dataframe(
                    condition_df,
                    use_container_width=True,
                    hide_index=True
                )


                # =============================================
                # 완전 일치 경기 목록
                # =============================================

                st.subheader(
                    "📋 완전 일치 경기"
                )


                show_columns = [

                    "schedule_id",
                    "match_date",
                    "home_team",
                    "away_team",

                    "company_name",

                    "initial_home",
                    "initial_draw",
                    "initial_away",

                    "final_home",
                    "final_draw",
                    "final_away",

                    "result"

                ]


                show_columns = [

                    column
                    for column in show_columns
                    if column in search_df.columns

                ]


                result_table = (
                    search_df[
                        show_columns
                    ]
                    .sort_values(
                        "match_date",
                        ascending=False
                    )
                    .copy()
                )


                st.dataframe(
                    result_table,
                    use_container_width=True,
                    hide_index=True
                )


                # =============================================
                # 결과 요약
                # =============================================

                st.subheader(
                    "📊 결과 요약"
                )


                summary_df = pd.DataFrame({

                    "결과": [
                        "승",
                        "무",
                        "패"
                    ],

                    "경기수": [
                        win,
                        draw,
                        lose
                    ],

                    "비율": [

                        (
                            f"{win / total * 100:.2f}%"
                            if total
                            else "0.00%"
                        ),

                        (
                            f"{draw / total * 100:.2f}%"
                            if total
                            else "0.00%"
                        ),

                        (
                            f"{lose / total * 100:.2f}%"
                            if total
                            else "0.00%"
                        )

                    ]

                })


                st.dataframe(
                    summary_df,
                    use_container_width=True,
                    hide_index=True
                )


# =========================================================
# 최종 DB 현황
# =========================================================

st.divider()

st.header(
    "📊 최종 DB 현황"
)


col1, col2 = st.columns(2)


with col1:

    st.metric(
        "전체 경기",
        database.get_match_count()
    )


with col2:

    st.metric(
        "전체 배당",
        database.get_odds_count()
    )


st.success(
    "✅ 프로그램 정상 작동"
)
