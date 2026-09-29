import streamlit as st
import pandas as pd
import analysis
import database


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="스코어맨 배당 분석",
    page_icon="⚽",
    layout="wide"
)

database.init_database()


# =========================================================
# 제목
# =========================================================

st.title("⚽ 스코어맨 배당 분석")

st.caption(
    "스코어맨 전체 경기 DB + 업체별 초기/최종배당 완전일치 검색"
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

st.header("🚀 스코어맨 전체 경기 DB 자동 수집")

st.info(
    "지정한 경기 ID 범위의 완료된 경기를 수집하고 "
    "경기정보와 업체별 초기/최종배당을 DB에 저장합니다."
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


delay = st.slider(
    "요청 간격",
    min_value=0.2,
    max_value=2.0,
    value=0.5,
    step=0.1
)


if st.button(
    "🚀 전체 경기 자동 수집 시작",
    type="primary",
    use_container_width=True
):

    if end_id < start_id:

        st.error(
            "마지막 ID가 시작 ID보다 작습니다."
        )

        st.stop()

    try:

        from build_database import (
            build_database_progress
        )

    except Exception as e:

        st.error(
            "build_database.py를 찾을 수 없습니다."
        )

        st.code(str(e))

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
        "스코어맨 전체 경기 데이터를 수집하는 중..."
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
                "수집 중 오류가 발생했습니다."
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
            result.get("total", 0)
        )

    with col2:
        st.metric(
            "신규 저장",
            result.get("success", 0)
        )

    with col3:
        st.metric(
            "기존 경기",
            result.get("exists", 0)
        )

    with col4:
        st.metric(
            "저장 배당",
            result.get("odds", 0)
        )


st.divider()


# =========================================================
# 저장된 경기 확인
# =========================================================

st.header("📋 저장된 전체 경기")

try:

    matches = database.get_all_matches()

except Exception as e:

    matches = []

    st.error(str(e))


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


    matches_df = pd.DataFrame(rows)


    st.dataframe(
        matches_df,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "저장된 경기가 없습니다."
    )


# =========================================================
# 업체 목록
# =========================================================

st.divider()

st.header("🎯 업체별 초기/최종배당 완전일치 검색")

st.info(
    "여러 업체를 선택한 뒤 각 업체의 초기배당과 최종배당을 직접 입력하세요. "
    "입력한 배당 6개가 DB의 같은 업체 데이터와 모두 일치하는 경기만 검색합니다."
)


# =========================================================
# DB에서 업체 목록 가져오기
# =========================================================

try:

    odds_rows = database.get_all_odds()

except Exception as e:

    odds_rows = []

    st.error(str(e))


company_map = {}


for row in odds_rows:

    company_id = row["company_id"]

    company_name = row["company_name"]


    key = str(company_id)

    if not key:

        continue


    if key not in company_map:

        company_map[key] = (
            company_name
            if company_name
            else key
        )


# 업체가 DB에 없을 경우 기본 업체
default_companies = [
    "Bet365",
    "Pinnacle",
    "1xBet",
    "SBOBET",
    "188BET",
    "WilliamHill",
    "Ladbrokes",
    "Interwetten",
    "BetVictor",
    "Unibet",
    "Marathon"
]


for name in default_companies:

    if name not in company_map.values():

        company_map[
            f"manual_{name}"
        ] = name


company_options = list(
    company_map.values()
)


if not company_options:

    company_options = default_companies


# =========================================================
# 업체 선택
# =========================================================

selected_companies = st.multiselect(

    "검색할 업체 선택",

    options=company_options,

    default=company_options[:1],

    help="여러 업체를 동시에 선택할 수 있습니다."

)


# =========================================================
# 업체별 입력창
# =========================================================

company_inputs = {}


if selected_companies:

    st.subheader(
        "💰 선택 업체 배당 입력"
    )


    for company in selected_companies:

        with st.expander(
            f"🏢 {company}",
            expanded=True
        ):

            st.markdown(
                f"### {company}"
            )


            st.markdown(
                "**초기배당**"
            )


            c1, c2, c3 = st.columns(3)


            with c1:

                initial_home = st.number_input(

                    "초기 승",

                    min_value=1.01,

                    value=1.50,

                    step=0.01,

                    key=f"{company}_initial_home"

                )


            with c2:

                initial_draw = st.number_input(

                    "초기 무",

                    min_value=1.01,

                    value=3.50,

                    step=0.01,

                    key=f"{company}_initial_draw"

                )


            with c3:

                initial_away = st.number_input(

                    "초기 패",

                    min_value=1.01,

                    value=5.00,

                    step=0.01,

                    key=f"{company}_initial_away"

                )


            st.markdown(
                "**최종배당**"
            )


            c1, c2, c3 = st.columns(3)


            with c1:

                final_home = st.number_input(

                    "최종 승",

                    min_value=1.01,

                    value=1.50,

                    step=0.01,

                    key=f"{company}_final_home"

                )


            with c2:

                final_draw = st.number_input(

                    "최종 무",

                    min_value=1.01,

                    value=3.50,

                    step=0.01,

                    key=f"{company}_final_draw"

                )


            with c3:

                final_away = st.number_input(

                    "최종 패",

                    min_value=1.01,

                    value=5.00,

                    step=0.01,

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
# 완전일치 검색
# =========================================================

if selected_companies:

    st.divider()

    if st.button(
        "🔎 입력한 배당과 완전히 동일한 경기 찾기",
        type="primary",
        use_container_width=True
    ):

        try:

            all_odds = database.get_all_odds()

        except Exception as e:

            st.error(str(e))

            st.stop()


        if not all_odds:

            st.warning(
                "DB에 저장된 배당 데이터가 없습니다."
            )

            st.stop()


        odds_df = pd.DataFrame(
            [
                dict(row)
                for row in all_odds
            ]
        )


        if odds_df.empty:

            st.warning(
                "배당 데이터가 없습니다."
            )

            st.stop()


        # 숫자형 변환
        numeric_columns = [

            "initial_home",
            "initial_draw",
            "initial_away",
            "final_home",
            "final_draw",
            "final_away"

        ]


        for column in numeric_columns:

            odds_df[column] = pd.to_numeric(
                odds_df[column],
                errors="coerce"
            )


        # -------------------------------------------------
        # 경기 결과와 연결
        # -------------------------------------------------

        try:

            match_rows = database.get_all_matches()

            match_df = pd.DataFrame(
                [
                    dict(row)
                    for row in match_rows
                ]
            )

        except Exception:

            match_df = pd.DataFrame()


        if not match_df.empty:

            odds_df = odds_df.merge(

                match_df[
                    [
                        "schedule_id",
                        "match_date",
                        "home_team",
                        "away_team",
                        "home_score",
                        "away_score",
                        "result"
                    ]
                ],

                on="schedule_id",

                how="left"

            )


        # -------------------------------------------------
        # 업체별 완전일치
        # -------------------------------------------------

        for company in selected_companies:

            st.subheader(
                f"🏢 {company} 완전일치 결과"
            )


            values = company_inputs[
                company
            ]


            # 업체명 기준 검색
            company_df = odds_df[
                odds_df["company_name"].astype(str)
                ==
                str(company)
            ].copy()


            # -------------------------------------------------
            # 배당 6개 완전 동일
            # -------------------------------------------------

            matched = company_df[

                (
                    company_df["initial_home"]
                    ==
                    values["initial_home"]
                )

                &

                (
                    company_df["initial_draw"]
                    ==
                    values["initial_draw"]
                )

                &

                (
                    company_df["initial_away"]
                    ==
                    values["initial_away"]
                )

                &

                (
                    company_df["final_home"]
                    ==
                    values["final_home"]
                )

                &

                (
                    company_df["final_draw"]
                    ==
                    values["final_draw"]
                )

                &

                (
                    company_df["final_away"]
                    ==
                    values["final_away"]
                )

            ].copy()


            # 경기 중복 제거
            matched = matched.drop_duplicates(
                subset=["schedule_id"]
            )


            if matched.empty:

                st.warning(
                    "❌ 6개 배당이 모두 완전히 동일한 경기가 없습니다."
                )

                continue


            # -------------------------------------------------
            # 결과 통계
            # -------------------------------------------------

            total = len(matched)


            win = int(
                (
                    matched["result"]
                    ==
                    "승"
                ).sum()
            )


            draw = int(
                (
                    matched["result"]
                    ==
                    "무"
                ).sum()
            )


            lose = int(
                (
                    matched["result"]
                    ==
                    "패"
                ).sum()
            )


            st.success(
                f"✅ 완전일치 경기 {total}경기"
            )


            c1, c2, c3 = st.columns(3)


            with c1:

                percent = (
                    win / total * 100
                )

                st.metric(
                    "승",
                    f"{percent:.2f}%",
                    f"{win}경기"
                )


            with c2:

                percent = (
                    draw / total * 100
                )

                st.metric(
                    "무",
                    f"{percent:.2f}%",
                    f"{draw}경기"
                )


            with c3:

                percent = (
                    lose / total * 100
                )

                st.metric(
                    "패",
                    f"{percent:.2f}%",
                    f"{lose}경기"
                )


            # -------------------------------------------------
            # 추천
            # -------------------------------------------------

            result_counts = {

                "승": win,

                "무": draw,

                "패": lose

            }


            recommendation = max(
                result_counts,
                key=result_counts.get
            )


            recommendation_percent = (

                result_counts[
                    recommendation
                ]

                /

                total

                *

                100

            )


            st.info(

                f"🎯 완전일치 과거 결과 추천: "
                f"**{recommendation}** "
                f"({recommendation_percent:.2f}%)"

            )


            # -------------------------------------------------
            # 경기 목록
            # -------------------------------------------------

            display_columns = [

                "schedule_id",
                "match_date",
                "home_team",
                "away_team",
                "home_score",
                "away_score",

                "initial_home",
                "initial_draw",
                "initial_away",

                "final_home",
                "final_draw",
                "final_away",

                "result"

            ]


            display_columns = [

                column

                for column in display_columns

                if column in matched.columns

            ]


            display_df = matched[
                display_columns
            ].copy()


            st.dataframe(

                display_df.sort_values(
                    "match_date",
                    ascending=False
                ),

                use_container_width=True,

                hide_index=True

            )


# =========================================================
# DB 배당 데이터 확인
# =========================================================

st.divider()

st.header(
    "🗃️ 저장된 업체별 배당 데이터"
)


show_database = st.checkbox(
    "DB 배당 데이터 보기",
    value=False
)


if show_database:

    try:

        db_odds = database.get_all_odds()

        if db_odds:

            db_odds_df = pd.DataFrame(
                [
                    dict(row)
                    for row in db_odds
                ]
            )

            st.dataframe(
                db_odds_df,
                use_container_width=True,
                hide_index=True
            )

        else:

            st.info(
                "저장된 배당 데이터가 없습니다."
            )

    except Exception as e:

        st.error(str(e))


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
