import streamlit as st
import pandas as pd

import database

from build_database import build_database_progress


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(

    page_title="스코어맨 완전동일배당 분석",

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

st.title(
    "⚽ 스코어맨 완전동일배당 분석"
)

st.caption(
    "회사별 초기배당 3개 + 최종배당 3개가 모두 완전히 같은 과거 경기 검색"
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
    "🚀 스코어맨 자동 배당 수집"
)

st.info(
    "완료된 경기의 회사별 최초배당과 최종배당을 자동으로 저장합니다. "
    "이미 DB에 있는 경기 역시 다시 확인하여 배당을 업데이트합니다."
)


# =========================================================
# ID
# =========================================================

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
# 자동 수집
# =========================================================

if st.button(

    "🚀 자동 수집 시작",

    type="primary",

    use_container_width=True

):

    if end_id < start_id:

        st.error(
            "마지막 ID가 시작 ID보다 작습니다."
        )

        st.stop()


    progress = st.progress(
        0
    )

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
        "스코어맨 데이터를 수집하고 있습니다..."
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


    progress.progress(
        1.0
    )


    st.success(
        "✅ 자동 수집 및 배당 업데이트 완료"
    )


    col1, col2, col3 = st.columns(3)


    with col1:

        st.metric(
            "검색 ID",
            result["total"]
        )


    with col2:

        st.metric(
            "저장/업데이트 경기",
            result["success"]
        )


    with col3:

        st.metric(
            "저장/업데이트 배당",
            result["odds"]
        )


st.divider()


# =========================================================
# 완전동일배당 검색
# =========================================================

st.header(
    "🎯 완전동일배당 검색"
)

st.info(
    "선택한 배당업체의 초기배당 3개와 최종배당 3개가 "
    "모두 정확히 일치하는 과거 경기만 검색합니다."
)


# =========================================================
# 업체 목록
# =========================================================

try:

    all_odds = database.get_all_odds()

except Exception as e:

    all_odds = []

    st.error(
        f"배당 데이터를 읽을 수 없습니다: {e}"
    )


companies = []

for row in all_odds:

    name = row["company_name"]

    if name:

        name = str(name).strip()

        if name and name not in companies:

            companies.append(name)


companies.sort()


if not companies:

    st.warning(
        "DB에 배당업체가 없습니다. 먼저 자동수집을 실행하세요."
    )

    st.stop()


# =========================================================
# 업체 선택
# =========================================================

selected_company = st.selectbox(

    "🏢 배당업체",

    companies

)


st.markdown(
    f"### {selected_company} 배당 입력"
)


# =========================================================
# 초기배당
# =========================================================

st.subheader(
    "① 최초배당"
)


col1, col2, col3 = st.columns(3)


with col1:

    initial_home = st.number_input(

        "최초 승",

        min_value=1.01,

        value=1.50,

        step=0.01,

        format="%.2f",

        key="initial_home"

    )


with col2:

    initial_draw = st.number_input(

        "최초 무",

        min_value=1.01,

        value=3.50,

        step=0.01,

        format="%.2f",

        key="initial_draw"

    )


with col3:

    initial_away = st.number_input(

        "최초 패",

        min_value=1.01,

        value=5.00,

        step=0.01,

        format="%.2f",

        key="initial_away"

    )


# =========================================================
# 최종배당
# =========================================================

st.subheader(
    "② 최종배당"
)


col1, col2, col3 = st.columns(3)


with col1:

    final_home = st.number_input(

        "최종 승",

        min_value=1.01,

        value=1.50,

        step=0.01,

        format="%.2f",

        key="final_home"

    )


with col2:

    final_draw = st.number_input(

        "최종 무",

        min_value=1.01,

        value=3.50,

        step=0.01,

        format="%.2f",

        key="final_draw"

    )


with col3:

    final_away = st.number_input(

        "최종 패",

        min_value=1.01,

        value=5.00,

        step=0.01,

        format="%.2f",

        key="final_away"

    )


# =========================================================
# 입력 확인
# =========================================================

st.subheader(
    "③ 검색 조건"
)


input_data = pd.DataFrame({

    "구분": [
        "최초배당",
        "최종배당"
    ],

    "승": [
        f"{initial_home:.2f}",
        f"{final_home:.2f}"
    ],

    "무": [
        f"{initial_draw:.2f}",
        f"{final_draw:.2f}"
    ],

    "패": [
        f"{initial_away:.2f}",
        f"{final_away:.2f}"
    ]

})


st.dataframe(

    input_data,

    use_container_width=True,

    hide_index=True

)


# =========================================================
# 완전일치 검색
# =========================================================

if st.button(

    "🔎 완전동일배당 경기 찾기",

    type="primary",

    use_container_width=True

):

    try:

        conn = database.get_connection()

        query = """

            SELECT

                m.schedule_id,

                m.match_date,

                m.home_team,

                m.away_team,

                m.home_score,

                m.away_score,

                m.result,

                o.company_name,

                o.initial_home,

                o.initial_draw,

                o.initial_away,

                o.final_home,

                o.final_draw,

                o.final_away

            FROM matches m

            INNER JOIN odds o

                ON m.schedule_id = o.schedule_id

            WHERE

                o.company_name = ?

                AND ROUND(o.initial_home, 2)
                    = ROUND(?, 2)

                AND ROUND(o.initial_draw, 2)
                    = ROUND(?, 2)

                AND ROUND(o.initial_away, 2)
                    = ROUND(?, 2)

                AND ROUND(o.final_home, 2)
                    = ROUND(?, 2)

                AND ROUND(o.final_draw, 2)
                    = ROUND(?, 2)

                AND ROUND(o.final_away, 2)
                    = ROUND(?, 2)

                AND m.result IN (
                    '승',
                    '무',
                    '패'
                )

            ORDER BY

                m.match_date DESC,

                m.id DESC

        """

        params = (

            selected_company,

            float(initial_home),

            float(initial_draw),

            float(initial_away),

            float(final_home),

            float(final_draw),

            float(final_away)

        )


        result_df = pd.read_sql_query(

            query,

            conn,

            params=params

        )


        conn.close()


    except Exception as e:

        st.error(
            f"검색 오류: {e}"
        )

        st.stop()


    # =====================================================
    # 검색 결과
    # =====================================================

    if result_df.empty:

        st.warning(
            "❌ 6개 배당이 모두 완전히 일치하는 과거 경기가 없습니다."
        )

    else:

        st.success(

            f"✅ 완전동일배당 경기 "
            f"**{len(result_df)}경기** 발견"

        )


        # -------------------------------------------------
        # 결과 통계
        # -------------------------------------------------

        win_count = int(

            (
                result_df["result"]
                ==
                "승"
            ).sum()

        )


        draw_count = int(

            (
                result_df["result"]
                ==
                "무"
            ).sum()

        )


        lose_count = int(

            (
                result_df["result"]
                ==
                "패"
            ).sum()

        )


        total = len(
            result_df
        )


        col1, col2, col3, col4 = st.columns(4)


        with col1:

            st.metric(
                "완전일치",
                f"{total}경기"
            )


        with col2:

            st.metric(

                "승",

                f"{win_count}경기",

                f"{win_count / total * 100:.2f}%"

            )


        with col3:

            st.metric(

                "무",

                f"{draw_count}경기",

                f"{draw_count / total * 100:.2f}%"

            )


        with col4:

            st.metric(

                "패",

                f"{lose_count}경기",

                f"{lose_count / total * 100:.2f}%"

            )


        # -------------------------------------------------
        # 가장 많이 나온 결과
        # -------------------------------------------------

        result_counts = {

            "승":
                win_count,

            "무":
                draw_count,

            "패":
                lose_count

        }


        recommendation = max(

            result_counts,

            key=result_counts.get

        )


        recommendation_count = (
            result_counts[
                recommendation
            ]
        )


        recommendation_percent = (

            recommendation_count
            /
            total
            *
            100

        )


        st.success(

            f"🎯 완전동일배당 과거 결과상 "
            f"**{recommendation}** "
            f"가장 많음 "
            f"({recommendation_count}경기 / "
            f"{recommendation_percent:.2f}%)"

        )


        # -------------------------------------------------
        # 결과표
        # -------------------------------------------------

        st.subheader(
            "📋 완전동일배당 과거 경기"
        )


        display_df = result_df.copy()


        display_df["배당업체"] = (
            display_df["company_name"]
        )


        display_df["초기배당"] = (

            display_df["initial_home"]
            .map(lambda x: f"{x:.2f}")

            + " / "

            +

            display_df["initial_draw"]
            .map(lambda x: f"{x:.2f}")

            + " / "

            +

            display_df["initial_away"]
            .map(lambda x: f"{x:.2f}")

        )


        display_df["최종배당"] = (

            display_df["final_home"]
            .map(
                lambda x:
                    f"{x:.2f}"
                    if pd.notna(x)
                    else "-"
            )

            + " / "

            +

            display_df["final_draw"]
            .map(
                lambda x:
                    f"{x:.2f}"
                    if pd.notna(x)
                    else "-"
            )

            + " / "

            +

            display_df["final_away"]
            .map(
                lambda x:
                    f"{x:.2f}"
                    if pd.notna(x)
                    else "-"
            )

        )


        display_df["스코어"] = (

            display_df["home_score"]
            .astype(str)

            + " - "

            +

            display_df["away_score"]
            .astype(str)

        )


        display_df = display_df[[

            "schedule_id",

            "match_date",

            "home_team",

            "away_team",

            "스코어",

            "result",

            "배당업체",

            "초기배당",

            "최종배당"

        ]]


        display_df.columns = [

            "경기ID",

            "날짜",

            "홈팀",

            "원정팀",

            "스코어",

            "결과",

            "업체",

            "초기배당",

            "최종배당"

        ]


        st.dataframe(

            display_df,

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


    matches_df = pd.DataFrame(
        rows
    )


    st.dataframe(

        matches_df.head(100),

        use_container_width=True,

        hide_index=True

    )

else:

    st.info(
        "저장된 경기가 없습니다."
    )


# =========================================================
# 최종 현황
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
    "✅ 완전동일배당 분석 프로그램 정상 작동"
        )
