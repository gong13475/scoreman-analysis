# ============================================================
# app.py
# Scoreman 해외배당 분석
# ============================================================

import time

import streamlit as st
import pandas as pd

import database
import collector
import analysis


# ============================================================
# 페이지 설정
# ============================================================

st.set_page_config(

    page_title="⚽ Scoreman 해외배당 분석",

    page_icon="⚽",

    layout="wide",

    initial_sidebar_state="collapsed",
)


# ============================================================
# 화면 스타일
# ============================================================

st.markdown("""
<style>

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 3rem;
}

[data-testid="stMetric"] {
    background-color: rgba(128, 128, 128, 0.08);
    padding: 12px;
    border-radius: 10px;
}

.stButton button {
    min-height: 42px;
    border-radius: 8px;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# DB 초기화
# ============================================================

@st.cache_resource
def initialize_database():

    database.init_database()

    return True


try:

    initialize_database()

except Exception as error:

    st.error(
        "데이터베이스 연결 또는 초기화에 실패했습니다."
    )

    st.code(
        str(error),
        language="text",
    )

    st.warning(
        "Turso를 사용 중이라면 "
        "TURSO_DATABASE_URL과 TURSO_AUTH_TOKEN을 "
        "확인하세요."
    )

    st.stop()


# ============================================================
# 제목
# ============================================================

st.title("⚽ Scoreman 해외배당 분석")

st.caption(
    "축구 1X2 · 해외업체 최종배당 · "
    "실제 결과 · 시장 예상확률 · 과거 통계"
)


# ============================================================
# DB 상태
# ============================================================

st.subheader("🗄️ 데이터베이스 상태")

try:

    db = database.get_database_status()

    size = database.get_database_size()

except Exception as error:

    st.error(
        f"DB 상태 조회 실패: {error}"
    )

    st.stop()


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
    "저장 업체",
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
    f"DB 모드: {size['mode']} · "
    f"확인 가능한 DB 용량: {size['mb']:.2f} MB"
)


if size["mode"] == "SQLite":

    st.warning(
        "현재 로컬 SQLite 모드입니다. "
        "Streamlit Cloud에서는 앱 재시작이나 "
        "재배포 후 로컬 파일이 유지되지 않을 수 있습니다. "
        "영구 저장이 필요하면 Turso 연결을 확인하세요."
    )

elif size["mode"] != "Turso":

    st.error(
        "Turso 연결 상태를 확인해야 합니다. "
        "현재 데이터가 영구 DB에 저장되는지 "
        "확인하기 전에는 대량 수집을 시작하지 마세요."
    )


# ============================================================
# 수집 설정
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


if end_id < start_id:

    st.error(
        "종료 ID는 시작 ID보다 작을 수 없습니다."
    )


st.caption(
    f"수집 대상 ID 수: "
    f"{max(0, int(end_id) - int(start_id) + 1):,}"
)


# ============================================================
# 업체 목록
# ============================================================

bookmaker_rows = database.get_bookmakers()

known_names = [

    "18Bet",
    "Bet365",
    "Crown",
    "Sbobet",
    "pinnacle",
]

for item in bookmaker_rows:

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

        sorted(known_names),

        default=[],
    )

    if not selected:

        st.info(
            "수집할 업체를 하나 이상 선택하세요."
        )


# ============================================================
# 요청 간격
# ============================================================

delay = st.number_input(

    "요청 간격(초)",

    min_value=0.1,

    max_value=10.0,

    value=0.5,

    step=0.1,
)


st.caption(
    "자동 재시도는 사용하지 않습니다. "
    "서버 응답이나 데이터 형식이 잘못된 경기는 "
    "실패로 기록합니다."
)


# ============================================================
# 수집 버튼
# ============================================================

b1, b2, b3 = st.columns(3)


with b1:

    if st.button(

        "▶️ 수집시작",

        type="primary",

        use_container_width=True,

    ):

        if end_id < start_id:

            st.error(
                "ID 범위를 확인하세요."
            )

        elif (
            mode == "업체 선택"
            and not selected
        ):

            st.error(
                "수집 업체를 선택하세요."
            )

        else:

            companies = (
                selected
                if mode == "업체 선택"
                else []
            )

            ok, message = (
                collector.start_background_collection(

                    int(start_id),

                    int(end_id),

                    companies,

                    float(delay),
                )
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

            st.warning(
                "수집 중지 요청을 보냈습니다."
            )

        else:

            st.info(
                "실행 중인 수집이 없습니다."
            )


with b3:

    if st.button(

        "▶️ 실패 ID부터 이어받기",

        use_container_width=True,

    ):

        if end_id < start_id:

            st.error(
                "ID 범위를 확인하세요."
            )

        elif (
            mode == "업체 선택"
            and not selected
        ):

            st.error(
                "수집 업체를 선택하세요."
            )

        else:

            companies = (
                selected
                if mode == "업체 선택"
                else []
            )

            ok, message = (
                collector.resume_collection(

                    int(end_id),

                    companies,

                    float(delay),

                    int(start_id),
                )
            )

            if ok:

                st.success(message)

            else:

                st.warning(message)


# ============================================================
# 진행 상태
# ============================================================

st.divider()

st.subheader("📊 수집 진행상태")

progress = collector.get_progress()

p1, p2, p3, p4, p5 = st.columns(5)

p1.metric(

    "진행",

    f"{progress['current']:,} / "
    f"{progress['total']:,}",
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


if progress["last_completed_id"] is not None:

    st.info(
        f"이번 작업의 마지막 정상 완료 ID: "
        f"{progress['last_completed_id']:,}"
    )


status = collector.get_job_status()


if status["running"]:

    st.success(
        "🟢 수집 실행 중"
    )

elif status["finished"]:

    st.info(
        "🏁 수집 종료 · "
        + str(status["result"])
    )

else:

    st.info(
        "⚪ 대기 중"
    )


if status.get("error"):

    st.error(
        status["error"]
    )


# ============================================================
# 수집 로그
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

            "\n".join(logs[-500:]),

            language="text",
        )

    else:

        st.info(
            "로그가 없습니다."
        )


# ============================================================
# 결과 미확인 경기
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
        "이 목록은 결과가 없거나 점수가 확인되지 않은 "
        "경기입니다."
    )


# ============================================================
# 분석 데이터
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


# ============================================================
# 전체 승무패 통계
# ============================================================

stats = analysis.result_counts(
    rows
)


a1, a2, a3, a4 = st.columns(4)


a1.metric(

    "분석 경기",

    f"{stats['total']:,}",
)


a2.metric(

    "승",

    f"{stats['승']:,} "
    f"({stats['승률']:.2f}%)",
)


a3.metric(

    "무",

    f"{stats['무']:,} "
    f"({stats['무율']:.2f}%)",
)


a4.metric(

    "패",

    f"{stats['패']:,} "
    f"({stats['패율']:.2f}%)",
)


st.caption(
    "전체 업체 분석에서는 같은 경기의 여러 업체 배당을 "
    "동일 경기로 한 번만 집계합니다."
)


# ============================================================
# 배당 마진
# ============================================================

st.subheader("📉 시장 배당 마진")

market = analysis.market_summary(
    rows
)


m1, m2, m3, m4 = st.columns(4)


m1.metric(

    "분석 경기",

    f"{market['경기수']:,}",
)


m2.metric(

    "평균 마진",

    f"{market['평균마진']:.2f}%",
)


m3.metric(

    "최저 마진",

    f"{market['최저마진']:.2f}%",
)


m4.metric(

    "최고 마진",

    f"{market['최고마진']:.2f}%",
)


# ============================================================
# 업체별 분석
# ============================================================

st.subheader("🏢 업체별 결과 및 가상 ROI")

company_stats = analysis.bookmaker_stats(
    rows
)


if company_stats:

    company_df = pd.DataFrame(
        company_stats
    )

    st.dataframe(

        company_df,

        use_container_width=True,

        hide_index=True,
    )

    st.caption(
        "ROI는 과거 실제 결과에 고정 단위로 베팅했다고 "
        "가정한 계산값입니다. 수수료, 베팅 한도, "
        "체결 조건은 반영하지 않았으며 미래 수익을 "
        "보장하지 않습니다."
    )

else:

    st.info(
        "업체별 분석 데이터가 없습니다."
    )


# ============================================================
# 동일 배당 분석
# ============================================================

st.divider()

st.subheader("🎯 동일 배당 과거결과 분석")


x1, x2, x3, x4 = st.columns(4)


with x1:

    target_home = st.number_input(

        "홈 승 배당",

        min_value=1.01,

        value=2.00,

        step=0.01,

        format="%.2f",
    )


with x2:

    target_draw = st.number_input(

        "무승부 배당",

        min_value=1.01,

        value=3.20,

        step=0.01,

        format="%.2f",
    )


with x3:

    target_away = st.number_input(

        "원정 승 배당",

        min_value=1.01,

        value=3.50,

        step=0.01,

        format="%.2f",
    )


with x4:

    tolerance = st.number_input(

        "허용오차",

        min_value=0.0,

        value=0.01,

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
        f"동일 배당 경기 "
        f"{same_stats['total']:,}경기"
    )


    s1, s2, s3 = st.columns(3)


    s1.metric(

        "승",

        f"{same_stats['승']:,} "
        f"({same_stats['승률']:.2f}%)",
    )


    s2.metric(

        "무",

        f"{same_stats['무']:,} "
        f"({same_stats['무율']:.2f}%)",
    )


    s3.metric(

        "패",

        f"{same_stats['패']:,} "
        f"({same_stats['패율']:.2f}%)",
    )


    st.dataframe(

        pd.DataFrame(same_rows),

        use_container_width=True,

        hide_index=True,
    )


else:

    st.info(
        "해당 배당 범위에 일치하는 과거 경기가 없습니다."
    )


# ============================================================
# 예상확률 대비 실제 결과
# ============================================================

st.divider()

st.subheader("📊 시장 예상확률 대비 실제 결과")


ev = analysis.expected_vs_actual(
    rows
)


if ev:

    st.dataframe(

        pd.DataFrame(ev),

        use_container_width=True,

        hide_index=True,
    )

    st.caption(
        "차이(%p)가 양수이면 해당 결과가 시장 예상확률보다 "
        "더 자주 발생했고, 음수이면 덜 발생했다는 뜻입니다. "
        "표본이 적으면 차이가 크게 흔들릴 수 있습니다."
    )


else:

    st.info(
        "분석 가능한 결과 데이터가 없습니다."
    )


# ============================================================
# 직접 배당 입력
# ============================================================

st.divider()

st.header("🧮 직접 배당 입력 · 확률 계산")

st.caption(
    "분석하려는 경기의 배당을 직접 입력해 "
    "시장 예상확률과 배당 마진을 계산할 수 있습니다."
)


d1, d2, d3 = st.columns(3)


with d1:

    manual_home = st.number_input(

        "직접 입력 · 홈 승",

        min_value=1.01,

        value=2.00,

        step=0.01,

        format="%.2f",

        key="manual_home",
    )


with d2:

    manual_draw = st.number_input(

        "직접 입력 · 무승부",

        min_value=1.01,

        value=3.20,

        step=0.01,

        format="%.2f",

        key="manual_draw",
    )


with d3:

    manual_away = st.number_input(

        "직접 입력 · 원정 승",

        min_value=1.01,

        value=3.50,

        step=0.01,

        format="%.2f",

        key="manual_away",
    )


manual_probs = analysis.odds_probability(

    manual_home,

    manual_draw,

    manual_away,
)


manual_margin = analysis.odds_overround(

    manual_home,

    manual_draw,

    manual_away,
)


if manual_probs:

    st.subheader("계산 결과")


    q1, q2, q3, q4 = st.columns(4)


    q1.metric(

        "홈 승 예상확률",

        f"{manual_probs['승']:.2f}%",
    )


    q2.metric(

        "무승부 예상확률",

        f"{manual_probs['무']:.2f}%",
    )


    q3.metric(

        "원정 승 예상확률",

        f"{manual_probs['패']:.2f}%",
    )


    q4.metric(

        "배당 마진",

        f"{manual_margin:.2f}%",
    )


    st.caption(
        "예상확률은 배당의 역수에서 계산한 뒤 "
        "합계가 100%가 되도록 정규화한 값입니다. "
        "실제 경기 결과 확률이나 적중 보장은 아닙니다."
    )


# ============================================================
# 최근 경기
# ============================================================

st.divider()

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

        column

        for column in columns

        if column in recent.columns
    ]


    st.dataframe(

        recent[available].head(100),

        use_container_width=True,

        hide_index=True,
    )


else:

    st.info(
        "저장된 분석 데이터가 없습니다."
    )


# ============================================================
# 자동 새로고침
# ============================================================

if collector.is_running():

    time.sleep(1)

    st.rerun()
