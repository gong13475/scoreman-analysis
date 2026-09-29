import streamlit as st
import pandas as pd

import database
import analysis

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
# ID 입력
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
# DB 수집
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


    progress = st.progress(0)

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
                logs[-200:]
            )
        )


    # -----------------------------------------------------
    # 수집 실행
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

        st.exception(e)

        st.stop()


    progress.progress(
        1.0
    )


    st.success(
        "✅ DB 수집 완료"
    )


    # -----------------------------------------------------
    # 수집 결과
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


    st.rerun()


# =========================================================
# 저장된 전체 경기
# =========================================================

st.divider()

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
        "저장된 경기가 없습니다."
    )


# =========================================================
# 업체 목록
# =========================================================

st.divider()

st.header(
    "🎯 업체별 초기/최종배당 완전일치 검색"
)

st.write(
    "여러 업체를 선택한 뒤 각 업체의 "
    "초기배당 3개 + 최종배당 3개를 직접 입력하세요."
)

st.write(
    "입력한 배당 6개가 DB의 같은 업체 데이터와 "
    "**모두 완전히 일치하는 경기**만 검색합니다."
)


# =========================================================
# DB에서 실제 업체 목록 가져오기
# =========================================================

try:

    odds_rows = database.get_all_odds()

except Exception:

    odds_rows = []


company_names = []

for row in odds_rows:

    name = row["company_name"]

    if name:

        name = str(name).strip()

        if name and name not in company_names:

            company_names.append(
                name
            )


company_names = sorted(
    company_names
)


# =========================================================
# 업체가 아직 없을 경우
# =========================================================

if not company_names:

    st.warning(
        "DB에 저장된 업체 배당이 없습니다. "
        "먼저 경기 DB를 수집하세요."
    )

else:

    selected_companies = st.multiselect(

        "검색할 업체 선택",

        options=company_names,

        default=(
            company_names[:1]
            if company_names
            else []
        )

    )


    # =====================================================
    # 선택 업체별 배당 입력
    # =====================================================

    input_data = {}


    for company in selected_companies:

        st.subheader(
            f"🏢 {company}"
        )


        initial_col1, initial_col2, initial_col3 = (
            st.columns(3)
        )


        with initial_col1:

            initial_home = st.number_input(

                f"{company} 초기 승",

                min_value=1.01,

                value=1.50,

                step=0.01,

                format="%.2f",

                key=f"{company}_initial_home"

            )


        with initial_col2:

            initial_draw = st.number_input(

                f"{company} 초기 무",

                min_value=1.01,

                value=3.50,

                step=0.01,

                format="%.2f",

                key=f"{company}_initial_draw"

            )


        with initial_col3:

            initial_away = st.number_input(

                f"{company} 초기 패",

                min_value=1.01,

                value=5.00,

                step=0.01,

                format="%.2f",

                key=f"{company}_initial_away"

            )


        st.caption(
            "최종배당"
        )


        final_col1, final_col2, final_col3 = (
            st.columns(3)
        )


        with final_col1:

            final_home = st.number_input(

                f"{company} 최종 승",

                min_value=1.01,

                value=1.50,

                step=0.01,

                format="%.2f",

                key=f"{company}_final_home"

            )


        with final_col2:

            final_draw = st.number_input(

                f"{company} 최종 무",

                min_value=1.01,

                value=3.50,

                step=0.01,

                format="%.2f",

                key=f"{company}_final_draw"

            )


        with final_col3:

            final_away = st.number_input(

                f"{company} 최종 패",

                min_value=1.01,

                value=5.00,

                step=0.01,

                format="%.2f",

                key=f"{company}_final_away"

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
    # 완전일치 검색
    # =====================================================

    if selected_companies:

        st.divider()

        if st.button(
            "🔎 완전일치 경기 검색",
            type="primary",
            use_container_width=True
        ):

            try:

                all_odds = database.get_all_odds()

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
            # schedule_id별 업체 데이터 구성
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


                if schedule_id not in match_companies:

                    match_companies[
                        schedule_id
                    ] = {}


                match_companies[
                    schedule_id
                ][company] = row


            # -------------------------------------------------
            # 모든 선택 업체가 완전히 일치해야 함
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


                    row = companies[
                        company
                    ]

                    target = input_data[
                        company
                    ]


                    fields = [

                        (
                            "initial_home",
                            target["initial_home"]
                        ),

                        (
                            "initial_draw",
                            target["initial_draw"]
                        ),

                        (
                            "initial_away",
                            target["initial_away"]
                        ),

                        (
                            "final_home",
                            target["final_home"]
                        ),

                        (
                            "final_draw",
                            target["final_draw"]
                        ),

                        (
                            "final_away",
                            target["final_away"]
                        )

                    ]


                    for field, value in fields:

                        db_value = row[field]


                        if db_value is None:

                            match_ok = False

                            break


                        if round(
                            float(db_value),
                            2
                        ) != round(
                            float(value),
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


                # ---------------------------------------------
                # 경기정보 가져오기
                # ---------------------------------------------

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


                result_df = pd.DataFrame(
                    result_rows
                )


                if not result_df.empty:

                    st.dataframe(

                        result_df,

                        use_container_width=True,

                        hide_index=True

                    )


                    # -----------------------------------------
                    # 결과별 통계
                    # -----------------------------------------

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
# 저장된 업체별 배당 데이터
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

        odds_rows = []


        for row in all_odds:

            odds_rows.append({

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
            odds_rows
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
