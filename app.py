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
    "스코어맨 경기결과 + 초기배당 + 최종배당 + 과거 통계 분석"
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


# =========================================================
# ID 범위
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
    f"검색할 ID: **{total_ids:,}개**"
)


# =========================================================
# 속도
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
    "🚀 과거 경기 자동 수집 시작",
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


    progress.progress(
        1.0
    )


    st.success(
        "✅ 과거 DB 수집 완료"
    )


    # =====================================================
    # 결과
    # =====================================================

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


    df = pd.DataFrame(
        rows
    )


    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "아직 저장된 경기가 없습니다."
    )


# =========================================================
# 배당 분석
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
# 배당 직접 입력
# =========================================================

st.divider()

st.header(
    "🎯 배당 입력 → 과거 결과 분석"
)


col1, col2, col3 = st.columns(3)


with col1:

    home_odds = st.number_input(
        "승 배당",
        min_value=1.01,
        value=1.65,
        step=0.01
    )


with col2:

    draw_odds = st.number_input(
        "무 배당",
        min_value=1.01,
        value=3.70,
        step=0.01
    )


with col3:

    away_odds = st.number_input(
        "패 배당",
        min_value=1.01,
        value=5.20,
        step=0.01
    )


if st.button(
    "🔎 유사 배당 분석",
    use_container_width=True
):

    try:

        df = (
            analysis.get_all_analysis_data()
        )

    except Exception as e:

        st.error(
            str(e)
        )

        st.stop()


    if df.empty:

        st.warning(
            "과거 데이터가 없습니다."
        )

        st.stop()


    df = df.copy()


    df["차이"] = (

        abs(
            df["initial_home"]
            -
            home_odds
        )

        +

        abs(
            df["initial_draw"]
            -
            draw_odds
        )

        +

        abs(
            df["initial_away"]
            -
            away_odds
        )

    )


    similar = df[
        df["차이"] <= 0.30
    ].copy()


    if similar.empty:

        st.warning(
            "비슷한 과거 경기가 없습니다."
        )

        st.stop()


    similar = similar.drop_duplicates(
        subset=["schedule_id"]
    )


    total = len(
        similar
    )


    win = int(
        (
            similar["result"]
            ==
            "승"
        ).sum()
    )


    draw = int(
        (
            similar["result"]
            ==
            "무"
        ).sum()
    )


    lose = int(
        (
            similar["result"]
            ==
            "패"
        ).sum()
    )


    col1, col2, col3 = st.columns(3)


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


    results = {

        "승":
            win,

        "무":
            draw,

        "패":
            lose

    }


    recommendation = max(
        results,
        key=results.get
    )


    st.success(
        f"🎯 과거 통계 추천: "
        f"**{recommendation}**"
    )


    st.write(
        f"분석 경기: **{total}경기**"
    )


    st.subheader(
        "유사 과거 경기"
    )


    show_columns = [

        "schedule_id",
        "match_date",
        "home_team",
        "away_team",
        "initial_home",
        "initial_draw",
        "initial_away",
        "result"

    ]


    show_columns = [

        c
        for c in show_columns
        if c in similar.columns

    ]


    st.dataframe(

        similar[
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


# =========================================================
# 최종 현황
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
