# ============================================================
# app.py
# ⚽ 전종목 해외배당 분석
# ============================================================

import time
import streamlit as st
import pandas as pd

import database
import collector
import analysis


# ============================================================
# 기본 설정
# ============================================================

st.set_page_config(
    page_title="⚽ 전종목 해외배당 분석",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# 제목
# ============================================================

st.title("⚽ 전종목 해외배당 분석")

st.caption(
    "스코어맨 자동수집 · 해외업체 최종배당 · "
    "실제결과 · 확률분석"
)


# ============================================================
# DB 상태
# ============================================================

database.init_database()

db = database.get_database_status()
size = database.get_database_size()

st.subheader("🗄️ 데이터베이스 상태")

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric(
    "저장 경기",
    f"{db['matches']:,}",
)

c2.metric(
    "저장 최종배당",
    f"{db['odds']:,}",
)

c3.metric(
    "실제 저장 업체",
    f"{db['bookmakers']:,}",
)

c4.metric(
    "실제 결과",
    f"{db['results']:,}",
)

c5.metric(
    "결과 미확인",
    f"{db['unresolved']:,}",
)

st.caption(
    f"DB: {size['mode']} · "
    f"{size['mb']:.2f} MB"
)


# ============================================================
# 수집
# ============================================================

st.divider()

st.header("📥 Scoreman 백그라운드 수집")

col1, col2 = st.columns(2)

with col1:

    start_id = st.number_input(
        "시작 ID",
        min_value=1,
        value=2005000,
        step=1,
        format="%d",
    )

with col2:

    end_id = st.number_input(
        "종료 ID",
        min_value=1,
        value=3001118,
        step=1,
        format="%d",
    )


# ============================================================
# 업체
# ============================================================

bookmakers = database.get_bookmakers()

known_names = [
    "18Bet",
    "Bet365",
    "Crown",
    "Sbobet",
    "pinnacle",
]

for item in bookmakers:

    name = item.get("bookmaker")

    if name and name not in known_names:
        known_names.append(name)


mode = st.radio(
    "수집 업체",
    [
        "전체 업체 자동수집",
        "업체 선택",
    ],
    horizontal=True,
)

selected = []

if mode == "업체 선택":

    selected = st.multiselect(
        "수집할 업체",
        known_names,
        default=[],
    )


delay = st.number_input(
    "요청 간격(초)",
    min_value=0.0,
    max_value=10.0,
    value=0.5,
    step=0.1,
)


# ============================================================
# 버튼
# ============================================================

b1, b2, b3 = st.columns(3)

with b1:

    if st.button(
        "▶️ 수집시작",
        type="primary",
        use_container_width=True,
    ):

        ok, message = collector.start_background_collection(
            int(start_id),
            int(end_id),
            selected,
            delay,
        )

        if ok:
            st.success(message)
        else:
            st.error(message)


with b2:

    if st.button(
        "⏹️ 수집중지",
        use_container_width=True,
    ):

        if collector.stop_collection():
            st.warning("수집 중지 요청을 보냈습니다.")
        else:
            st.info("현재 실행 중인 수집이 없습니다.")


with b3:

    if st.button(
        "▶️ 마지막 완료부터 이어받기",
        use_container_width=True,
    ):

        ok, message = collector.resume_collection(
            int(end_id),
            selected,
            delay,
        )

        if ok:
            st.success(message)
        else:
            st.warning(message)


# ============================================================
# 진행상태
# ============================================================

st.subheader("📊 수집 진행상태")

progress = collector.get_progress()

p1, p2, p3, p4, p5 = st.columns(5)

p1.metric(
    "진행",
    f"{progress['current']:,} / {progress['total']:,}",
)

p2.metric(
    "성공",
    f"{progress['success']:,}",
)

p3.metric(
    "중복",
    f"{progress['exists']:,}",
)

p4.metric(
    "실패",
    f"{progress['failed']:,}",
)

p5.metric(
    "저장 배당",
    f"{progress['odds']:,}",
)

st.progress(
    min(
        max(
            progress["percent"] / 100,
            0.0,
        ),
        1.0,
    )
)

if progress["last_completed_id"]:

    st.info(
        f"마지막 정상 완료 ID: "
        f"{progress['last_completed_id']:,}"
    )


# ============================================================
# 실행 상태
# ============================================================

status = collector.get_job_status()

if status["running"]:

    st.success("🟢 수집 실행 중")

elif status["finished"]:

    st.info(
        "🏁 수집 종료 · "
        + str(status["result"])
    )

else:

    st.info("⚪ 대기 중")


# ============================================================
# 자동 새로고침
# ============================================================

if status["running"]:

    time.sleep(1)

    st.rerun()


# ============================================================
# 로그
# ============================================================

st.divider()

st.subheader("📋 수집 로그")

show_log = st.checkbox(
    "로그 보기",
    value=False,
)

if show_log:

    logs = collector.get_logs()

    if logs:

        st.code(
            "\n".join(logs),
            language="text",
        )

    else:

        st.info("로그가 없습니다.")


# ============================================================
# 결과 없는 경기
# ============================================================

st.divider()

st.subheader("⚠️ 결과 미확인 경기")

unresolved = database.get_unresolved_matches()

st.write(
    f"결과 미확인: **{len(unresolved):,}경기**"
)

if unresolved:

    unresolved_df = pd.DataFrame(
        unresolved
    )

    st.dataframe(
        unresolved_df,
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "이 경기들은 완료 ID로 처리되지 않았기 때문에 "
        "다시 수집할 수 있습니다."
    )


# ============================================================
# 분석
# ============================================================

st.divider()

st.header("📈 경기 분석")

bookmaker_options = ["전체"]

for item in database.get_bookmakers():

    name = item.get("bookmaker")

    if name:
        bookmaker_options.append(name)


selected_bookmaker = st.selectbox(
    "분석 업체",
    bookmaker_options,
)


if selected_bookmaker == "전체":

    rows = database.get_analysis_rows()

else:

    rows = database.get_analysis_rows(
        selected_bookmaker
    )


stats = analysis.result_counts(rows)

a1, a2, a3, a4 = st.columns(4)

a1.metric(
    "분석 경기",
    f"{stats['total']:,}",
)

a2.metric(
    "승",
    f"{stats['승']:,} ({stats['승률']:.2f}%)",
)

a3.metric(
    "무",
    f"{stats['무']:,} ({stats['무율']:.2f}%)",
)

a4.metric(
    "패",
    f"{stats['패']:,} ({stats['패율']:.2f}%)",
)


# ============================================================
# 업체별
# ============================================================

st.subheader("🏢 업체별 결과")

company_stats = analysis.bookmaker_stats(rows)

if company_stats:

    st.dataframe(
        pd.DataFrame(company_stats),
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# 동일배당 분석
# ============================================================

st.subheader("🎯 동일배당 과거결과 분석")

x1, x2, x3, x4 = st.columns(4)

with x1:
    target_home = st.number_input(
        "홈 승",
        value=2.00,
        step=0.01,
        format="%.2f",
    )

with x2:
    target_draw = st.number_input(
        "무",
        value=3.20,
        step=0.01,
        format="%.2f",
    )

with x3:
    target_away = st.number_input(
        "원정 승",
        value=3.50,
        step=0.01,
        format="%.2f",
    )

with x4:
    tolerance = st.number_input(
        "허용오차",
        value=0.01,
        min_value=0.0,
        step=0.01,
        format="%.2f",
    )


same_rows = analysis.same_odds_analysis(
    rows,
    target_home,
    target_draw,
    target_away,
    tolerance,
)

if same_rows:

    same_stats = analysis.result_counts(
        same_rows
    )

    st.success(
        f"동일배당 경기 {same_stats['total']}경기"
    )

    s1, s2, s3 = st.columns(3)

    s1.metric(
        "승",
        f"{same_stats['승']} ({same_stats['승률']:.2f}%)",
    )

    s2.metric(
        "무",
        f"{same_stats['무']} ({same_stats['무율']:.2f}%)",
    )

    s3.metric(
        "패",
        f"{same_stats['패']} ({same_stats['패율']:.2f}%)",
    )

    st.dataframe(
        pd.DataFrame(same_rows),
        use_container_width=True,
        hide_index=True,
    )

else:

    st.info("동일배당 과거 경기가 없습니다.")


# ============================================================
# 예상확률 vs 실제확률
# ============================================================

st.subheader("📊 예상확률 대비 실제결과")

ev = analysis.expected_vs_actual(rows)

if ev:

    st.dataframe(
        pd.DataFrame(ev),
        use_container_width=True,
        hide_index=True,
    )

else:

    st.info("분석 가능한 결과 데이터가 없습니다.")


# ============================================================
# 최근 경기
# ============================================================

st.subheader("📝 최근 저장 경기")

if rows:

    recent = pd.DataFrame(rows)

    columns = [
        "schedule_id",
        "match_date",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "result",
        "bookmaker",
        "final_home",
        "final_draw",
        "final_away",
    ]

    available = [
        c for c in columns
        if c in recent.columns
    ]

    st.dataframe(
        recent[available].head(100),
        use_container_width=True,
        hide_index=True,
    )

else:

    st.info("저장된 분석 데이터가 없습니다.")
