import streamlit as st
import pandas as pd

import database

from crawler import build_database_progress


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
# 전체 경기 DB 자동 수집
# =========================================================

st.header(
    "🚀 스코어맨 전체 경기 DB 자동 수집"
)

st.info(
    "지정한 경기 ID 범위의 완료된 경기를 수집하고 "
    "경기정보와 업체별 초기/최종배당을 DB에 저장합니다."
)


# =========================================================
# 경기 ID
# =========================================================

col1, col2 = st.columns(2)

with col1:

    start_id = st.number_input(
        "시작 경기 ID",
        min_value=1,
        value=3001118,
        step=1
    )

with col2:

    end_id = st.number_input(
        "마지막 경기 ID",
        min_value=1,
        value=3001118,
        step=1
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
    min_value=0.20,
    max_value=2.00,
    value=0.50,
    step=0.10
)


# =========================================================
# 수집 실행
# =========================================================

if st.button(
    "🚀 DB 수집 시작",
    type="primary",
    use_container_width=True
):

    if end_id < start_id:

        st.error(
            "마지막 경기 ID가 시작 경기 ID보다 작습니다."
        )

        st.stop()


    progress = st.progress(
        0
    )


    st.subheader(
        "📡 크롤링 로그"
    )


    log_box = st.empty()

    logs = []


    # -----------------------------------------------------
    # 진행률
    # -----------------------------------------------------

    def progress_callback(value):

        try:

            progress.progress(
                min(
                    max(
                        float(value),
                        0.0
                    ),
                    1.0
                )
            )

        except Exception:

            pass


    # -----------------------------------------------------
    # 로그
    # -----------------------------------------------------

    def log_callback(message):

        logs.append(
            str(message)
        )

        log_box.code(
            "\n".join(
                logs[-300:]
            ),
            language="text"
        )


    # -----------------------------------------------------
    # 수집
    # -----------------------------------------------------

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
            "❌ 크롤링 오류"
        )

        st.exception(
            e
        )

        # 오류가 발생해도 로그 유지
        if logs:

            st.subheader(
                "📡 마지막 크롤링 로그"
            )

            st.code(
                "\n".join(logs),
                language="text"
            )

        st.stop()


    # -----------------------------------------------------
    # 완료
    # -----------------------------------------------------

    progress.progress(
        1.0
    )


    st.success(
        "✅ DB 수집 완료"
    )


    # -----------------------------------------------------
    # 결과
    # -----------------------------------------------------

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
            "신규 저장",
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
            "저장 배당",
            result.get(
                "odds",
                0
            )
        )


    # -----------------------------------------------------
    # 완료 후 로그를 다시 출력
    # -----------------------------------------------------

    st.subheader(
        "📡 수집 완료 로그"
    )


    if logs:

        st.code(
            "\n".join(logs),
            language="text"
        )

    else:

        st.warning(
            "크롤러에서 전달된 로그가 없습니다."
        )


st.divider()


# =========================================================
# 저장된 전체 경기
# =========================================================

st.header(
    "📋 저장된 전체 경기"
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

        if (
            row["home_score"] is not None
            and
            row["away_score"] is not None
        ):

            score = (
                f'{row["home_score"]} - '
                f'{row["away_score"]}'
            )

        else:

            score = "-"


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
                score,

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
        "저장된 경기가 없습니다."
    )


# =========================================================
# 업체별 완전일치 검색
# =========================================================

st.divider()

st.header(
    "🎯 업체별 초기/최종배당 완전일치 검색"
)

st.write(
    "여러 업체를 선택한 뒤 각 업체의 초기배당과 "
    "최종배당을 직접 입력하세요."
)

st.write(
    "선택한 모든 업체의 초기 승/무/패와 최종 승/무/패 "
    "6개 값이 DB와 모두 일치하는 경기만 검색합니다."
)


# =========================================================
# DB 업체 목록
# =========================================================

try:

    odds_rows = database.get_all_odds()

except Exception as e:

    odds_rows = []

    st.error(
        str(e)
    )


company_names = []


for row in odds_rows:

    company_name = row["company_name"]


    if company_name:

        company_name = str(
            company_name
        ).strip()


        if (
            company_name
            and
            company_name not in company_names
        ):

            company_names.append(
                company_name
            )


company_names = sorted(
    company_names
)


# =========================================================
# 업체 선택
# =========================================================

if not company_names:

    st.warning(
        "DB에 저장된 업체가 없습니다. "
        "먼저 경기 DB를 수집하세요."
    )

else:

    selected_companies = st.multiselect(

        "검색할 업체 선택",

        options=company_names,

        default=[
            company_names[0]
        ]

    )


    input_data = {}


    # =====================================================
    # 업체별 배당 입력
    # =====================================================

    for company in selected_companies:

        st.subheader(
            f"🏢 {company}"
        )


        st.markdown(
            "**초기배당**"
        )


        col1, col2, col3 = st.columns(3)


        with col1:

            initial_home = st.number_input(

                "초기 승",

                min_value=1.01,

                value=1.50,

                step=0.01,

                format="%.2f",

                key=
                    f"{company}_initial_home"

            )


        with col2:

            initial_draw = st.number_input(

                "초기 무",

                min_value=1.01,

                value=3.50,

                step=0.01,

                format="%.2f",

                key=
                    f"{company}_initial_draw"

            )


        with col3:

            initial_away = st.number_input(

                "초기 패",

                min_value=1.01,

                value=5.00,

                step=0.01,

                format="%.2f",

                key=
                    f"{company}_initial_away"

            )


        st.markdown(
            "**최종배당**"
        )


        col1, col2, col3 = st.columns(3)


        with col1:

            final_home = st.number_input(

                "최종 승",

                min_value=1.01,

                value=1.50,

                step=0.01,

                format="%.2f",

                key=
                    f"{company}_final_home"

            )


        with col2:

            final_draw = st.number_input(

                "최종 무",

                min_value=1.01,

                value=3.50,

                step=0.01,

                format="%.2f",

                key=
                    f"{company}_final_draw"

            )


        with col3:

            final_away = st.number_input(

                "최종 패",

                min_value=1.01,

                value=5.00,

                step=0.01,

                format="%.2f",

                key=
                    f"{company}_final_away"

            )


        input_data[company] = {

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


    # =====================================================
    # 검색
    # =====================================================

    if selected_companies:

        st.divider()


        if st.button(

            "🔎 완전일치 경기 검색",

            type="primary",

            use_container_width=True

        ):


            try:

                all_odds = (
                    database.get_all_odds()
                )

            except Exception as e:

                st.error(
                    str(e)
                )

                st.stop()


            if not all_odds:

                st.warning(
                    "DB에 배당 데이터가 없습니다."
                )

                st.stop()


            # -------------------------------------------------
            # 경기별 업체 데이터
            # -------------------------------------------------

            match_companies = {}


            for row in all_odds:

                schedule_id = str(
                    row["schedule_id"]
                )


                company = str(
                    row["company_name"]
                    or ""
                ).strip()


                if not company:

                    continue


                if (
                    schedule_id
                    not in
                    match_companies
                ):

                    match_companies[
                        schedule_id
                    ] = {}


                match_companies[
                    schedule_id
                ][company] = row


            # -------------------------------------------------
            # 완전 일치 검사
            # -------------------------------------------------

            matched_ids = []


            for schedule_id, companies in (
                match_companies.items()
            ):

                match_ok = True


                for company in selected_companies:

                    if company not in companies:

                        match_ok = False

                        break


                    db_row = companies[
                        company
                    ]


                    target = input_data[
                        company
                    ]


                    checks = [

                        (
                            db_row["initial_home"],
                            target["initial_home"]
                        ),

                        (
                            db_row["initial_draw"],
                            target["initial_draw"]
                        ),

                        (
                            db_row["initial_away"],
                            target["initial_away"]
                        ),

                        (
                            db_row["final_home"],
                            target["final_home"]
                        ),

                        (
                            db_row["final_draw"],
                            target["final_draw"]
                        ),

                        (
                            db_row["final_away"],
                            target["final_away"]
                        )

                    ]


                    for db_value, input_value in checks:

                        if db_value is None:

                            match_ok = False

                            break


                        if round(
                            float(db_value),
                            2
                        ) != round(
                            float(input_value),
                            2
                        ):

                            match_ok = False

                            break


                    if not match_ok:

                        break


                if match_ok:

                    matched_ids.append(
                        schedule_id
                    )


            # =================================================
            # 결과
            # =================================================

            if not matched_ids:

                st.warning(
                    "입력한 모든 업체의 초기/최종배당이 "
                    "완전히 일치하는 경기가 없습니다."
                )

            else:

                st.success(
                    f"🎯 완전일치 경기 "
                    f"**{len(matched_ids)}경기** 발견"
                )


                # -------------------------------------------------
                # 경기정보
                # -------------------------------------------------

                all_matches = (
                    database.get_all_matches()
                )


                match_map = {

                    str(row["schedule_id"]):
                        row

                    for row in all_matches

                }


                result_rows = []


                for schedule_id in matched_ids:

                    row = match_map.get(
                        str(schedule_id)
                    )


                    if row is None:

                        continue


                    if (
                        row["home_score"] is not None
                        and
                        row["away_score"] is not None
                    ):

                        score = (
                            f'{row["home_score"]} - '
                            f'{row["away_score"]}'
                        )

                    else:

                        score = "-"


                    result_rows.append({

                        "경기ID":
                            row["schedule_id"],

                        "날짜":
                            row["match_date"],

                        "홈팀":
                            row["home_team"],

                        "원정팀":
                            row["away_team"],

                        "스코어":
                            score,

                        "결과":
                            row["result"]

                    })


                result_df = pd.DataFrame(
                    result_rows
                )


                if not result_df.empty:

                    st.dataframe(

                        result_df,

                        use_container_width=True,

                        hide_index=True

                    )


                    # -------------------------------------------------
                    # 결과 통계
                    # -------------------------------------------------

                    total = len(
                        result_df
                    )


                    win = int(
                        (
                            result_df["결과"]
                            ==
                            "승"
                        ).sum()
                    )


                    draw = int(
                        (
                            result_df["결과"]
                            ==
                            "무"
                        ).sum()
                    )


                    lose = int(
                        (
                            result_df["결과"]
                            ==
                            "패"
                        ).sum()
                    )


                    st.subheader(
                        "📊 완전일치 경기 결과"
                    )


                    col1, col2, col3 = (
                        st.columns(3)
                    )


                    with col1:

                        st.metric(

                            "승",

                            f"{win / total * 100:.2f}%",

                            f"{win}경기"

                        )


                    with col2:

                        st.metric(

                            "무",

                            f"{draw / total * 100:.2f}%",

                            f"{draw}경기"

                        )


                    with col3:

                        st.metric(

                            "패",

                            f"{lose / total * 100:.2f}%",

                            f"{lose}경기"

                        )


# =========================================================
# 저장된 업체별 배당
# =========================================================

st.divider()

st.header(
    "🗃️ 저장된 업체별 배당 데이터"
)


with st.expander(
    "DB 배당 데이터 보기"
):

    try:

        all_odds = database.get_all_odds()

    except Exception as e:

        all_odds = []

        st.error(
            str(e)
        )


    if all_odds:

        rows = []


        for row in all_odds:

            rows.append({

                "경기ID":
                    row["schedule_id"],

                "업체":
                    row["company_name"],

                "초기 승":
                    row["initial_home"],

                "초기 무":
                    row["initial_draw"],

                "초기 패":
                    row["initial_away"],

                "최종 승":
                    row["final_home"],

                "최종 무":
                    row["final_draw"],

                "최종 패":
                    row["final_away"]

            })


        odds_df = pd.DataFrame(
            rows
        )


        st.dataframe(

            odds_df,

            use_container_width=True,

            hide_index=True

        )

    else:

        st.info(
            "저장된 배당 데이터가 없습니다."
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
