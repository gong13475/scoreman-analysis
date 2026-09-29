import streamlit as st
import pandas as pd
import database
import analysis

from build_database import build_database_progress


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="스코어맨 완전 동일배당 분석",
    page_icon="⚽",
    layout="wide"
)

database.init_database()


# =========================================================
# 제목
# =========================================================

st.title("⚽ 스코어맨 완전 동일배당 분석")

st.caption(
    "사이트별 초기배당 + 최종배당을 직접 입력하여 "
    "과거 DB에서 완전히 동일한 경기를 검색합니다."
)


# =========================================================
# DB 현황
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

st.header("🚀 과거 스코어맨 DB 자동 수집")

st.info(
    "완료된 경기를 검색하고 경기결과와 각 업체의 "
    "초기배당/최종배당을 DB에 저장합니다."
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
    - int(start_id)
    + 1
)

st.write(
    f"검색할 ID: **{total_ids:,}개**"
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

    try:

        with st.spinner(
            "스코어맨 과거 경기를 수집하고 있습니다..."
        ):

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
        "✅ DB 수집 완료"
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
            "저장 배당",
            result["odds"]
        )


st.divider()


# =========================================================
# 완전 동일배당 검색
# =========================================================

st.header(
    "🎯 사이트별 완전 동일배당 검색"
)

st.info(
    "회사별로 초기배당과 최종배당을 입력합니다. "
    "선택한 모든 회사의 배당이 DB와 완전히 동일한 경기만 검색합니다."
)


# =========================================================
# 저장된 회사 목록
# =========================================================

try:

    all_odds = database.get_all_odds()

except Exception as e:

    all_odds = []

    st.error(
        str(e)
    )


company_names = []

for row in all_odds:

    name = row["company_name"]

    if name:

        name = str(name).strip()

        if name and name not in company_names:

            company_names.append(name)


# 기본 회사 우선 배치

preferred_companies = [
    "Bet365",
    "Pinnacle",
    "1xBet"
]

ordered_companies = []

for company in preferred_companies:

    for db_company in company_names:

        if db_company.lower() == company.lower():

            if db_company not in ordered_companies:

                ordered_companies.append(
                    db_company
                )


for company in company_names:

    if company not in ordered_companies:

        ordered_companies.append(
            company
        )


if not ordered_companies:

    ordered_companies = [
        "Bet365",
        "Pinnacle",
        "1xBet"
    ]


# =========================================================
# 회사 선택
# =========================================================

selected_companies = st.multiselect(

    "🔽 검색할 배당업체를 선택하세요",

    options=ordered_companies,

    default=[
        company
        for company in ordered_companies
        if company in [
            "Bet365",
            "Pinnacle",
            "1xBet"
        ]
    ]

)


if not selected_companies:

    st.warning(
        "최소 한 개의 배당업체를 선택하세요."
    )

else:

    st.write(
        f"선택 업체: **{len(selected_companies)}개**"
    )


# =========================================================
# 회사별 입력
# =========================================================

company_inputs = {}


for company in selected_companies:

    st.markdown(
        f"### 🏢 {company}"
    )

    with st.container(border=True):

        st.write(
            "초기배당"
        )

        c1, c2, c3 = st.columns(3)

        with c1:

            initial_home = st.number_input(

                f"{company} 초기 승",

                min_value=1.01,

                value=1.50,

                step=0.01,

                format="%.2f",

                key=f"{company}_initial_home"

            )

        with c2:

            initial_draw = st.number_input(

                f"{company} 초기 무",

                min_value=1.01,

                value=3.50,

                step=0.01,

                format="%.2f",

                key=f"{company}_initial_draw"

            )

        with c3:

            initial_away = st.number_input(

                f"{company} 초기 패",

                min_value=1.01,

                value=5.00,

                step=0.01,

                format="%.2f",

                key=f"{company}_initial_away"

            )


        st.write(
            "최종배당"
        )

        c1, c2, c3 = st.columns(3)

        with c1:

            final_home = st.number_input(

                f"{company} 최종 승",

                min_value=1.01,

                value=1.50,

                step=0.01,

                format="%.2f",

                key=f"{company}_final_home"

            )

        with c2:

            final_draw = st.number_input(

                f"{company} 최종 무",

                min_value=1.01,

                value=3.50,

                step=0.01,

                format="%.2f",

                key=f"{company}_final_draw"

            )

        with c3:

            final_away = st.number_input(

                f"{company} 최종 패",

                min_value=1.01,

                value=5.00,

                step=0.01,

                format="%.2f",

                key=f"{company}_final_away"

            )


        company_inputs[company] = {

            "initial_home":
                float(initial_home),

            "initial_draw":
                float(initial_draw),

            "initial_away":
                float(initial_away),

            "final_home":
                float(final_home),

            "final_draw":
                float(final_draw),

            "final_away":
                float(final_away)

        }


# =========================================================
# 검색
# =========================================================

if selected_companies:

    st.divider()

    search_button = st.button(

        "🔎 완전 동일배당 검색",

        type="primary",

        use_container_width=True

    )

    if search_button:

        try:

            analysis_df = (
                analysis.get_all_analysis_data()
            )

        except Exception as e:

            st.error(
                str(e)
            )

            st.stop()


        if analysis_df.empty:

            st.warning(
                "DB에 분석할 배당 데이터가 없습니다."
            )

            st.stop()


        # -------------------------------------------------
        # 각 회사별 완전일치 조건
        # -------------------------------------------------

        matching_schedule_ids = None

        company_match_tables = {}

        for company in selected_companies:

            values = company_inputs[
                company
            ]

            company_df = analysis_df[
                analysis_df["company_name"].astype(str).str.strip()
                .str.lower()
                ==
                str(company).strip().lower()
            ].copy()


            if company_df.empty:

                company_match_tables[
                    company
                ] = pd.DataFrame()

                matching_ids = set()

            else:

                # 숫자를 정확히 비교
                matching = company_df[

                    (
                        company_df[
                            "initial_home"
                        ].round(2)
                        ==
                        round(
                            values["initial_home"],
                            2
                        )
                    )

                    &

                    (
                        company_df[
                            "initial_draw"
                        ].round(2)
                        ==
                        round(
                            values["initial_draw"],
                            2
                        )
                    )

                    &

                    (
                        company_df[
                            "initial_away"
                        ].round(2)
                        ==
                        round(
                            values["initial_away"],
                            2
                        )
                    )

                    &

                    (
                        company_df[
                            "final_home"
                        ].round(2)
                        ==
                        round(
                            values["final_home"],
                            2
                        )
                    )

                    &

                    (
                        company_df[
                            "final_draw"
                        ].round(2)
                        ==
                        round(
                            values["final_draw"],
                            2
                        )
                    )

                    &

                    (
                        company_df[
                            "final_away"
                        ].round(2)
                        ==
                        round(
                            values["final_away"],
                            2
                        )
                    )

                ].copy()


                company_match_tables[
                    company
                ] = matching

                matching_ids = set(
                    matching[
                        "schedule_id"
                    ].astype(str)
                )


            if matching_schedule_ids is None:

                matching_schedule_ids = (
                    matching_ids
                )

            else:

                matching_schedule_ids = (
                    matching_schedule_ids
                    &
                    matching_ids
                )


        # =================================================
        # 결과
        # =================================================

        st.divider()

        st.subheader(
            "📊 완전 동일배당 검색 결과"
        )


        if not matching_schedule_ids:

            st.error(
                "❌ 선택한 모든 회사의 배당이 "
                "완전히 일치하는 과거 경기가 없습니다."
            )


            # 회사별 개별 결과
            st.subheader(
                "회사별 일치 경기"
            )

            for company in selected_companies:

                table = company_match_tables.get(
                    company,
                    pd.DataFrame()
                )

                st.write(
                    f"**{company}**"
                )

                if table.empty:

                    st.write(
                        "일치 경기 없음"
                    )

                else:

                    st.write(
                        f"{len(table)}경기 일치"
                    )

                    show_columns = [

                        "schedule_id",
                        "match_date",
                        "home_team",
                        "away_team",
                        "initial_home",
                        "initial_draw",
                        "initial_away",
                        "final_home",
                        "final_draw",
                        "final_away",
                        "result"

                    ]

                    show_columns = [

                        c
                        for c in show_columns
                        if c in table.columns

                    ]

                    st.dataframe(

                        table[
                            show_columns
                        ]
                        .sort_values(
                            "match_date",
                            ascending=False
                        )
                        .head(100),

                        use_container_width=True,

                        hide_index=True

                    )

        else:

            # -------------------------------------------------
            # 공통 경기
            # -------------------------------------------------

            common_df = analysis_df[
                analysis_df[
                    "schedule_id"
                ].astype(str).isin(
                    matching_schedule_ids
                )
            ].copy()


            common_df = (
                common_df
                .drop_duplicates(
                    subset=["schedule_id"]
                )
                .sort_values(
                    "match_date",
                    ascending=False
                )
            )


            st.success(

                f"✅ 완전 동일 경기 "
                f"**{len(common_df)}경기** 발견"

            )


            # -------------------------------------------------
            # 승무패 통계
            # -------------------------------------------------

            total = len(
                common_df
            )

            win = int(
                (
                    common_df["result"]
                    ==
                    "승"
                ).sum()
            )

            draw = int(
                (
                    common_df["result"]
                    ==
                    "무"
                ).sum()
            )

            lose = int(
                (
                    common_df["result"]
                    ==
                    "패"
                ).sum()
            )


            c1, c2, c3 = st.columns(3)


            with c1:

                st.metric(
                    "승",
                    f"{win / total * 100:.2f}%",
                    f"{win}경기"
                )


            with c2:

                st.metric(
                    "무",
                    f"{draw / total * 100:.2f}%",
                    f"{draw}경기"
                )


            with c3:

                st.metric(
                    "패",
                    f"{lose / total * 100:.2f}%",
                    f"{lose}경기"
                )


            result_counts = {

                "승": win,
                "무": draw,
                "패": lose

            }


            recommendation = max(
                result_counts,
                key=result_counts.get
            )


            st.success(
                f"🎯 과거 동일배당 최다 결과: "
                f"**{recommendation}**"
            )


            # -------------------------------------------------
            # 경기 기본정보
            # -------------------------------------------------

            st.subheader(
                "📋 완전 동일 경기"
            )


            match_columns = [

                "schedule_id",
                "match_date",
                "home_team",
                "away_team",
                "home_score",
                "away_score",
                "result"

            ]


            match_columns = [

                c
                for c in match_columns
                if c in common_df.columns

            ]


            st.dataframe(

                common_df[
                    match_columns
                ],

                use_container_width=True,

                hide_index=True

            )


            # -------------------------------------------------
            # 회사별 배당
            # -------------------------------------------------

            st.subheader(
                "🏢 회사별 동일배당"
            )


            for company in selected_companies:

                company_table = (
                    company_match_tables[
                        company
                    ]
                )

                company_table = company_table[
                    company_table[
                        "schedule_id"
                    ].astype(str).isin(
                        matching_schedule_ids
                    )
                ].copy()


                show_columns = [

                    "schedule_id",

                    "initial_home",
                    "initial_draw",
                    "initial_away",

                    "final_home",
                    "final_draw",
                    "final_away",

                    "result"

                ]


                show_columns = [

                    c
                    for c in show_columns
                    if c in company_table.columns

                ]


                st.markdown(
                    f"**{company}**"
                )


                st.dataframe(

                    company_table[
                        show_columns
                    ]
                    .sort_values(
                        "schedule_id"
                    ),

                    use_container_width=True,

                    hide_index=True

                )


# =========================================================
# 저장된 경기
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
                row["result"]

        })


    st.dataframe(

        pd.DataFrame(rows),

        use_container_width=True,

        hide_index=True

    )

else:

    st.info(
        "아직 저장된 경기가 없습니다."
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
