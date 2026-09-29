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
    "완료된 스코어맨 경기만 확인하여 경기결과와 초기배당을 SQLite DB에 저장합니다."
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

                progress_callback=progress_callback,

                log_callback=log_callback,

                delay=float(delay)

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


    df_matches = pd.DataFrame(
        rows
    )


    st.dataframe(
        df_matches,
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
# 완전 동일 초기배당 검색
# =========================================================

st.divider()

st.header(
    "🎯 완전 동일 초기배당 검색"
)

st.info(
    "승·무·패 초기배당 3개가 모두 정확히 같은 과거 경기만 검색합니다."
)


col1, col2, col3 = st.columns(3)


with col1:

    home_odds = st.number_input(
        "승 배당",
        min_value=1.01,
        value=1.65,
        step=0.01,
        format="%.2f"
    )


with col2:

    draw_odds = st.number_input(
        "무 배당",
        min_value=1.01,
        value=3.70,
        step=0.01,
        format="%.2f"
    )


with col3:

    away_odds = st.number_input(
        "패 배당",
        min_value=1.01,
        value=5.20,
        step=0.01,
        format="%.2f"
    )


# =========================================================
# 검색 버튼
# =========================================================

if st.button(
    "🔎 완전 동일배당 검색",
    use_container_width=True,
    type="primary"
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


    # =====================================================
    # 숫자 변환
    # =====================================================

    for column in [
        "initial_home",
        "initial_draw",
        "initial_away"
    ]:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )


    # =====================================================
    # 완전 동일배당
    # =====================================================

    similar = df[
        (df["initial_home"] == float(home_odds)) &
        (df["initial_draw"] == float(draw_odds)) &
        (df["initial_away"] == float(away_odds))
    ].copy()


    # =====================================================
    # 회사별 중복 제거
    #
    # 같은 경기라도 업체가 다르면 각각 유지
    # =====================================================

    duplicate_columns = [
        "schedule_id",
        "company_name"
    ]

    duplicate_columns = [
        column
        for column in duplicate_columns
        if column in similar.columns
    ]

    if duplicate_columns:

        similar = similar.drop_duplicates(
            subset=duplicate_columns
        )


    # =====================================================
    # 검색 결과 없음
    # =====================================================

    if similar.empty:

        st.warning(
            "완전히 동일한 초기배당의 과거 경기가 없습니다."
        )

        st.info(
            f"검색 배당: "
            f"{home_odds:.2f} / "
            f"{draw_odds:.2f} / "
            f"{away_odds:.2f}"
        )

        st.stop()


    # =====================================================
    # 경기 수
    # =====================================================

    total_rows = len(similar)

    unique_matches = (
        similar["schedule_id"]
        .nunique()
    )


    # =====================================================
    # 승무패 통계
    # =====================================================

    win = int(
        (
            similar["result"] ==
            "승"
        ).sum()
    )


    draw = int(
        (
            similar["result"] ==
            "무"
        ).sum()
    )


    lose = int(
        (
            similar["result"] ==
            "패"
        ).sum()
    )


    result_total = (
        win +
        draw +
        lose
    )


    # =====================================================
    # 결과 표시
    # =====================================================

    st.success(
        f"✅ 완전 동일 초기배당 발견: "
        f"**{unique_matches}경기 / {total_rows}개 업체 데이터**"
    )


    st.write(
        f"검색 배당: **"
        f"{home_odds:.2f} / "
        f"{draw_odds:.2f} / "
        f"{away_odds:.2f}"
        f"**"
    )


    # =====================================================
    # 승무패 카드
    # =====================================================

    col1, col2, col3 = st.columns(3)


    with col1:

        win_percent = (
            win /
            result_total *
            100
            if result_total
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
            result_total *
            100
            if result_total
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
            result_total *
            100
            if result_total
            else 0
        )

        st.metric(
            "패",
            f"{lose_percent:.2f}%",
            f"{lose}경기"
        )


    # =====================================================
    # 추천
    # =====================================================

    results = {
        "승": win,
        "무": draw,
        "패": lose
    }


    recommendation = max(
        results,
        key=results.get
    )


    recommendation_count = (
        results[recommendation]
    )


    recommendation_percent = (
        recommendation_count /
        result_total *
        100
        if result_total
        else 0
    )


    st.success(
        f"🎯 과거 동일배당 최다 결과: "
        f"**{recommendation}** "
        f"({recommendation_count}경기 / "
        f"{recommendation_percent:.2f}%)"
    )


    # =====================================================
    # 업체별 동일배당
    # =====================================================

    st.subheader(
        "🏢 동일 초기배당 업체별 결과"
    )


    if "company_name" in similar.columns:

        company_rows = []


        for company, group in similar.groupby(
            "company_name",
            dropna=False
        ):

            company_name = (
                str(company)
                if pd.notna(company)
                else "알 수 없음"
            )


            company_win = int(
                (
                    group["result"] ==
                    "승"
                ).sum()
            )


            company_draw = int(
                (
                    group["result"] ==
                    "무"
                ).sum()
            )


            company_lose = int(
                (
                    group["result"] ==
                    "패"
                ).sum()
            )


            company_total = (
                company_win +
                company_draw +
                company_lose
            )


            company_rows.append({

                "배당업체":
                    company_name,

                "경기수":
                    company_total,

                "승":
                    company_win,

                "무":
                    company_draw,

                "패":
                    company_lose,

                "승률":
                    (
                        f"{company_win / company_total * 100:.2f}%"
                        if company_total
                        else "0.00%"
                    ),

                "무율":
                    (
                        f"{company_draw / company_total * 100:.2f}%"
                        if company_total
                        else "0.00%"
                    ),

                "패율":
                    (
                        f"{company_lose / company_total * 100:.2f}%"
                        if company_total
                        else "0.00%"
                    )

            })


        company_result = pd.DataFrame(
            company_rows
        )


        st.dataframe(
            company_result,
            use_container_width=True,
            hide_index=True
        )


    # =====================================================
    # 과거 동일배당 경기
    # =====================================================

    st.subheader(
        "📋 완전 동일배당 과거 경기"
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
        if column in similar.columns
    ]


    result_table = (
        similar[
            show_columns
        ]
        .sort_values(
            "match_date",
            ascending=False
        )
        .head(200)
        .copy()
    )


    st.dataframe(
        result_table,
        use_container_width=True,
        hide_index=True
    )


    # =====================================================
    # 결과별 요약
    # =====================================================

    st.subheader(
        "📊 동일배당 결과 요약"
    )


    result_summary = pd.DataFrame({

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

            f"{win / result_total * 100:.2f}%"
            if result_total
            else "0.00%",

            f"{draw / result_total * 100:.2f}%"
            if result_total
            else "0.00%",

            f"{lose / result_total * 100:.2f}%"
            if result_total
            else "0.00%"

        ]

    })


    st.dataframe(
        result_summary,
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
