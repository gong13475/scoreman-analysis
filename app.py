# ============================================================
# app.py
# ⚽ 전종목 해외배당 분석
# Scoreman 자동수집 · 최종배당 · 실제결과 · 확률분석
# ============================================================

import time
from datetime import datetime

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
)


# ============================================================
# 초기화
# ============================================================

database.init_database()


# ============================================================
# 제목
# ============================================================

st.title(
    "⚽ 전종목 해외배당 분석"
)

st.caption(
    "스코어맨 자동수집 · 해외업체 최종배당 · "
    "실제결과 · 확률분석"
)


# ============================================================
# 사이드바
# ============================================================

with st.sidebar:

    st.header(
        "⚙️ 수집 설정"
    )

    start_id = st.number_input(
        "시작 ID",
        min_value=1,
        value=2800026,
        step=1,
    )

    end_id = st.number_input(
        "종료 ID",
        min_value=1,
        value=3000000,
        step=1,
    )

    st.write(
        f"수집 경기 수: "
        f"{max(0, int(end_id - start_id + 1)):,}"
    )

    delay = st.number_input(
        "요청 간격(초)",
        min_value=0.0,
        max_value=10.0,
        value=0.50,
        step=0.10,
    )

    st.divider()

    company_mode = st.radio(
        "업체 선택",
        [
            "전체 업체",
            "업체 선택",
        ],
    )

    companies = [
        "18Bet",
        "Bet365",
        "Crown",
        "Sbobet",
        "pinnacle",
    ]

    if company_mode == "업체 선택":

        selected_companies = (
            st.multiselect(
                "수집 업체",
                companies,
                default=[
                    "18Bet",
                    "Bet365",
                    "Crown",
                    "Sbobet",
                    "pinnacle",
                ],
            )
        )

    else:

        selected_companies = []


# ============================================================
# 수집 버튼
# ============================================================

col1, col2, col3 = st.columns(3)


with col1:

    if st.button(
        "▶️ 수집시작",
        type="primary",
        use_container_width=True,
    ):

        ok, message = (
            collector.start_background_collection(
                int(start_id),
                int(end_id),
                selected_companies,
                float(delay),
            )
        )

        if ok:

            st.success(
                message
            )

        else:

            st.warning(
                message
            )


with col2:

    if st.button(
        "⏹️ 수집중지",
        use_container_width=True,
    ):

        if collector.stop_collection():

            st.warning(
                "수집 중지 요청을 보냈습니다."
            )

        else:

            st.info(
                "현재 수집 중이 아닙니다."
            )


with col3:

    if st.button(
        "▶️ 마지막 완료 ID부터 이어받기",
        use_container_width=True,
    ):

        ok, message = (
            collector.resume_collection(
                int(end_id),
                selected_companies,
                float(delay),
            )
        )

        if ok:

            st.success(
                message
            )

        else:

            st.warning(
                message
            )


# ============================================================
# 진행 상태
# ============================================================

st.subheader(
    "📡 수집 상태"
)

progress = (
    collector.get_progress()
)

current = progress[
    "current"
]

total = progress[
    "total"
]

percent = progress[
    "percent"
]

if progress["running"]:

    st.info(
        "🟢 수집 중입니다."
    )

else:

    if progress["finished"]:

        st.success(
            "🔵 수집이 종료되었습니다."
        )

    else:

        st.warning(
            "🟡 대기 중입니다."
        )


if total > 0:

    st.progress(
        min(
            max(
                percent / 100,
                0
            ),
            1
        )
    )

    st.write(
        f"진행: {current:,} / "
        f"{total:,} "
        f"({percent:.2f}%)"
    )


# ============================================================
# 진행 숫자
# ============================================================

c1, c2, c3, c4, c5 = st.columns(5)


with c1:

    st.metric(
        "성공",
        f"{progress['success']:,}"
    )


with c2:

    st.metric(
        "중복",
        f"{progress['exists']:,}"
    )


with c3:

    st.metric(
        "실패",
        f"{progress['failed']:,}"
    )


with c4:

    st.metric(
        "저장 배당",
        f"{progress['odds']:,}"
    )


with c5:

    last_id = (
        progress[
            "last_completed_id"
        ]
    )

    st.metric(
        "마지막 완료 ID",
        f"{last_id:,}"
        if last_id
        else "-"
    )


# ============================================================
# 자동 갱신
# ============================================================

if progress["running"]:

    time.sleep(1)

    st.rerun()


# ============================================================
# DB 상태
# ============================================================

st.divider()

st.subheader(
    "🗄️ 데이터베이스 상태"
)

status = (
    database.get_database_status()
)

d1, d2, d3, d4, d5 = st.columns(5)


with d1:

    st.metric(
        "저장 경기",
        f"{status['matches']:,}"
    )


with d2:

    st.metric(
        "저장 최종배당",
        f"{status['odds']:,}"
    )


with d3:

    st.metric(
        "실제 저장 업체",
        f"{status['bookmakers']:,}"
    )


with d4:

    st.metric(
        "결과 확인 경기",
        f"{status['results']:,}"
    )


with d5:

    st.metric(
        "결과 미확인",
        f"{status['unresolved']:,}"
    )


# ============================================================
# DB 모드
# ============================================================

size = (
    database.get_database_size()
)

st.caption(
    f"DB 모드: {size['mode']} · "
    f"용량: {size['mb']:.2f} MB"
)


# ============================================================
# 로그
# ============================================================

st.divider()

show_log = st.checkbox(
    "📜 수집 로그 보기"
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
            "표시할 로그가 없습니다."
        )


# ============================================================
# 분석
# ============================================================

st.divider()

st.header(
    "📊 경기 분석"
)

bookmakers = (
    database.get_bookmakers()
)

bookmaker_names = [
    x["bookmaker"]
    for x in bookmakers
]

analysis_option = st.selectbox(
    "분석 업체",
    ["전체 업체"]
    + bookmaker_names,
)


if analysis_option == "전체 업체":

    bookmaker_filter = None

else:

    bookmaker_filter = (
        analysis_option
    )


summary = (
    analysis.get_summary(
        bookmaker_filter
    )
)


a1, a2, a3, a4 = st.columns(4)


with a1:

    st.metric(
        "전체 경기",
        f"{summary['total']:,}"
    )


with a2:

    st.metric(
        "승",
        f"{summary['win']:,} "
        f"({summary['win_pct']:.2f}%)"
    )


with a3:

    st.metric(
        "무",
        f"{summary['draw']:,} "
        f"({summary['draw_pct']:.2f}%)"
    )


with a4:

    st.metric(
        "패",
        f"{summary['loss']:,} "
        f"({summary['loss_pct']:.2f}%)"
    )


# ============================================================
# 업체별 분석
# ============================================================

st.subheader(
    "🏢 업체별 실제 결과"
)

bookmaker_summary = (
    analysis.get_bookmaker_summary()
)

if bookmaker_summary:

    st.dataframe(
        bookmaker_summary,
        use_container_width=True,
        hide_index=True,
    )

else:

    st.info(
        "업체별 분석 데이터가 없습니다."
    )


# ============================================================
# 동일배당 분석
# ============================================================

st.divider()

st.subheader(
    "🎯 동일배당 과거 결과 분석"
)

o1, o2, o3, o4 = st.columns(4)


with o1:

    input_home = st.number_input(
        "승 배당",
        min_value=1.01,
        value=2.00,
        step=0.01,
    )


with o2:

    input_draw = st.number_input(
        "무 배당",
        min_value=1.01,
        value=3.20,
        step=0.01,
    )


with o3:

    input_away = st.number_input(
        "패 배당",
        min_value=1.01,
        value=3.50,
        step=0.01,
    )


with o4:

    tolerance = st.number_input(
        "허용오차",
        min_value=0.001,
        max_value=0.5,
        value=0.01,
        step=0.01,
    )


if st.button(
    "🔎 동일배당 분석",
    use_container_width=True,
):

    same = (
        analysis.same_odds_summary(
            input_home,
            input_draw,
            input_away,
            tolerance,
            bookmaker_filter,
        )
    )

    s1, s2, s3, s4 = st.columns(4)

    with s1:

        st.metric(
            "동일배당 경기",
            f"{same['total']:,}"
        )

    with s2:

        st.metric(
            "승",
            f"{same['win']:,} "
            f"({same['win_pct']:.2f}%)"
        )

    with s3:

        st.metric(
            "무",
            f"{same['draw']:,} "
            f"({same['draw_pct']:.2f}%)"
        )

    with s4:

        st.metric(
            "패",
            f"{same['loss']:,} "
            f"({same['loss_pct']:.2f}%)"
        )

    if same["rows"]:

        st.dataframe(
            same["rows"],
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# 결과 미확인 경기
# ============================================================

st.divider()

st.subheader(
    "⚠️ 결과 미확인 경기"
)

unresolved = (
    database.get_unresolved_matches()
)

if unresolved:

    st.warning(
        f"결과 미확인 경기 "
        f"{len(unresolved):,}건"
    )

    st.dataframe(
        unresolved,
        use_container_width=True,
        hide_index=True,
    )

else:

    st.success(
        "결과 미확인 경기가 없습니다."
    )


# ============================================================
# 최근 분석 데이터
# ============================================================

st.divider()

st.subheader(
    "📋 최근 저장 경기"
)

rows = database.get_analysis_rows(
    bookmaker_filter
)

if rows:

    display_rows = []

    for row in rows[:200]:

        item = {

            "ID":
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

            "스코어":
                (
                    f"{row.get('home_score')}"
                    f" - "
                    f"{row.get('away_score')}"
                ),

            "원정":
                row.get(
                    "away_team"
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

        display_rows.append(
            item
        )

    st.dataframe(
        display_rows,
        use_container_width=True,
        hide_index=True,
    )

else:

    st.info(
        "분석할 저장 데이터가 없습니다."
    )


# ============================================================
# 완료 상태
# ============================================================

if progress["finished"]:

    st.success(
        "🏁 "
        + str(
            collector.get_job_status().get(
                "result",
                ""
            )
        )
    )
