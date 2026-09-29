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

st.title("⚽ 스코어맨 완전동일배당 분석")

st.caption(
    "스코어맨 과거 경기 DB + 업체별 초기/최종배당 완전일치 검색"
)


# =========================================================
# 현재 DB 현황
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
# 과거 경기 자동 수집
# =========================================================

st.header("🚀 과거 경기 자동 수집")

st.info(
    "완료된 스코어맨 경기를 검색하여 경기결과와 업체별 "
    "초기배당 및 최종배당을 DB에 저장합니다."
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
    f"검색 ID: **{total_ids:,}개**"
)


delay = st.slider(
    "요청 간격",
    min_value=0.2,
    max_value=2.0,
    value=0.5,
    step=0.1
)


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
        "스코어맨 경기와 배당을 수집하고 있습니다..."
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
        "✅ 과거 경기 DB 수집 완료"
    )


    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "전체 검색",
            result.get(
                "total",
                0
            )
        )

    with col2:

        st.metric(
            "저장 성공",
            result.get(
                "success",
                0
            )
        )

    with col3:

        st.metric(
            "기존 경기",
            result.get(
                "exists",
                0
            )
        )

    with col4:

        st.metric(
            "배당 저장",
            result.get(
                "odds",
                0
            )
        )


st.divider()


# =========================================================
# 사이트별 배당 입력
# =========================================================

st.header("🎯 사이트별 배당 입력")

st.write(
    "여러 배당업체를 선택한 뒤 업체별로 "
    "**최초배당 3개 + 최종배당 3개**를 입력하세요."
)

st.info(
    "검색 조건은 완전일치입니다. "
    "승·무·패 초기배당과 최종배당 6개가 모두 동일해야 검색됩니다."
)


# =========================================================
# 분석 DB 읽기
# =========================================================

try:

    analysis_df = (
        analysis.get_all_analysis_data()
    )

except Exception as e:

    analysis_df = pd.DataFrame()

    st.error(
        str(e)
    )


if analysis_df.empty:

    st.warning(
        "현재 분석할 배당 데이터가 없습니다. "
        "먼저 과거 경기 자동 수집을 실행하세요."
    )

else:

    # -----------------------------------------------------
    # 업체 목록
    # -----------------------------------------------------

    companies = analysis.get_company_list(
        analysis_df
    )


    if not companies:

        st.warning(
            "DB에서 배당업체를 찾을 수 없습니다."
        )

    else:

        # -------------------------------------------------
        # 업체 선택
        # -------------------------------------------------

        selected_companies = st.multiselect(

            "배당업체 선택",

            options=companies,

            default=[],

            help=(
                "여러 업체를 동시에 선택할 수 있습니다."
            )
        )


        # -------------------------------------------------
        # 업체 입력
        # -------------------------------------------------

        company_inputs = []


        if selected_companies:

            st.subheader(
                "📌 업체별 배당 입력"
            )


            for index, company in enumerate(
                selected_companies
            ):

                with st.expander(
                    f"🏦 {company}",
                    expanded=True
                ):

                    st.markdown(
                        f"### {company}"
                    )


                    st.write(
                        "최초배당"
                    )


                    col1, col2, col3 = st.columns(3)


                    with col1:

                        initial_home = st.number_input(

                            "최초 승",

                            min_value=1.01,

                            value=1.50,

                            step=0.01,

                            format="%.2f",

                            key=(
                                f"initial_home_"
                                f"{index}_"
                                f"{company}"
                            )
                        )


                    with col2:

                        initial_draw = st.number_input(

                            "최초 무",

                            min_value=1.01,

                            value=3.50,

                            step=0.01,

                            format="%.2f",

                            key=(
                                f"initial_draw_"
                                f"{index}_"
                                f"{company}"
                            )
                        )


                    with col3:

                        initial_away = st.number_input(

                            "최초 패",

                            min_value=1.01,

                            value=5.00,

                            step=0.01,

                            format="%.2f",

                            key=(
                                f"initial_away_"
                                f"{index}_"
                                f"{company}"
                            )
                        )


                    st.write(
                        "최종배당"
                    )


                    col1, col2, col3 = st.columns(3)


                    with col1:

                        final_home = st.number_input(

                            "최종 승",

                            min_value=1.01,

                            value=1.50,

                            step=0.01,

                            format="%.2f",

                            key=(
                                f"final_home_"
                                f"{index}_"
                                f"{company}"
                            )
                        )


                    with col2:

                        final_draw = st.number_input(

                            "최종 무",

                            min_value=1.01,

                            value=3.50,

                            step=0.01,

                            format="%.2f",

                            key=(
                                f"final_draw_"
                                f"{index}_"
                                f"{company}"
                            )
                        )


                    with col3:

                        final_away = st.number_input(

                            "최종 패",

                            min_value=1.01,

                            value=5.00,

                            step=0.01,

                            format="%.2f",

                            key=(
                                f"final_away_"
                                f"{index}_"
                                f"{company}"
                            )
                        )


                    company_inputs.append({

                        "company_name":
                            company,

                        "initial_home":
                            initial_home,

                        "initial_draw":
                            initial_draw,

                        "initial_away":
                            initial_away,

                        "final_home":
                            final_home,

                        "final_draw":
                            final_draw,

                        "final_away":
                            final_away

                    })


            st.divider()


            # -------------------------------------------------
            # 검색 버튼
            # -------------------------------------------------

            search_clicked = st.button(

                "🔎 완전동일배당 경기 검색",

                type="primary",

                use_container_width=True
            )


            if search_clicked:

                if not company_inputs:

                    st.warning(
                        "배당업체를 선택하세요."
                    )

                    st.stop()


                # ---------------------------------------------
                # 선택 업체 전체가 각각 완전일치하는 경기
                # ---------------------------------------------

                result_df = (
                    analysis.find_matches_matching_all_companies(
                        analysis_df,
                        company_inputs
                    )
                )


                # ---------------------------------------------
                # 결과 없음
                # ---------------------------------------------

                if result_df.empty:

                    st.warning(
                        "❌ 입력한 배당 6개가 "
                        "완전히 동일한 과거 경기를 찾지 못했습니다."
                    )

                    st.info(
                        "배당 하나라도 다르면 제외됩니다. "
                        "유사배당 ±0.1 / ±0.3은 사용하지 않습니다."
                    )


                else:

                    # -----------------------------------------
                    # 결과 통계
                    # -----------------------------------------

                    stats = (
                        analysis.calculate_exact_result_stats(
                            result_df
                        )
                    )


                    total = stats["전체"]


                    st.success(
                        f"🎯 완전일치 경기 "
                        f"**{total}경기** 발견"
                    )


                    col1, col2, col3, col4 = (
                        st.columns(4)
                    )


                    with col1:

                        st.metric(
                            "전체",
                            f"{total}경기"
                        )


                    with col2:

                        st.metric(
                            "승",
                            (
                                f'{stats["승"]["percent"]}% '
                                f'({stats["승"]["count"]}경기)'
                            )
                        )


                    with col3:

                        st.metric(
                            "무",
                            (
                                f'{stats["무"]["percent"]}% '
                                f'({stats["무"]["count"]}경기)'
                            )
                        )


                    with col4:

                        st.metric(
                            "패",
                            (
                                f'{stats["패"]["percent"]}% '
                                f'({stats["패"]["count"]}경기)'
                            )
                        )


                    # -----------------------------------------
                    # 추천
                    # -----------------------------------------

                    recommendation = (
                        analysis.get_recommendation(
                            stats
                        )
                    )


                    confidence = (
                        analysis.get_confidence(
                            total
                        )
                    )


                    if recommendation:

                        st.success(

                            f"🎯 과거 완전일치 결과 추천: "
                            f"**{recommendation}**  "
                            f"| 표본 {total}경기 "
                            f"| 신뢰도: **{confidence}**"

                        )


                    # -----------------------------------------
                    # 경기 목록
                    # -----------------------------------------

                    st.subheader(
                        "📋 완전일치 과거 경기"
                    )


                    display_columns = [

                        "schedule_id",

                        "match_date",

                        "home_team",

                        "away_team",

                        "home_score",

                        "away_score",

                        "result"

                    ]


                    display_columns = [

                        column

                        for column in display_columns

                        if column in result_df.columns

                    ]


                    display_df = (
                        result_df[
                            display_columns
                        ]
                        .drop_duplicates(
                            subset=["schedule_id"]
                        )
                        .sort_values(
                            "match_date",
                            ascending=False
                        )
                    )


                    st.dataframe(

                        display_df,

                        use_container_width=True,

                        hide_index=True

                    )


                    # -----------------------------------------
                    # 업체별 완전일치 배당 확인
                    # -----------------------------------------

                    st.subheader(
                        "🏦 업체별 완전일치 배당"
                    )


                    detail_rows = []


                    for _, match_row in display_df.iterrows():

                        schedule_id = (
                            match_row[
                                "schedule_id"
                            ]
                        )


                        match_details = (
                            analysis.get_exact_match_details(
                                analysis_df,
                                schedule_id
                            )
                        )


                        for _, row in match_details.iterrows():

                            if (
                                row["company_name"]
                                in selected_companies
                            ):

                                detail_rows.append({

                                    "경기ID":
                                        row["schedule_id"],

                                    "날짜":
                                        row["match_date"],

                                    "홈팀":
                                        row["home_team"],

                                    "원정팀":
                                        row["away_team"],

                                    "결과":
                                        row["result"],

                                    "업체":
                                        row["company_name"],

                                    "최초승":
                                        row["initial_home"],

                                    "최초무":
                                        row["initial_draw"],

                                    "최초패":
                                        row["initial_away"],

                                    "최종승":
                                        row["final_home"],

                                    "최종무":
                                        row["final_draw"],

                                    "최종패":
                                        row["final_away"]

                                })


                    if detail_rows:

                        detail_df = pd.DataFrame(
                            detail_rows
                        )


                        st.dataframe(

                            detail_df,

                            use_container_width=True,

                            hide_index=True

                        )


# =========================================================
# 저장된 경기 확인
# =========================================================

st.divider()

st.header(
    "📋 저장된 경기"
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


    match_df = pd.DataFrame(
        rows
    )


    st.dataframe(

        match_df,

        use_container_width=True,

        hide_index=True

    )

else:

    st.info(
        "저장된 경기가 없습니다."
    )


# =========================================================
# 최종 DB 현황
# =========================================================

st.divider()

st.header(
    "📊 DB 현황"
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
