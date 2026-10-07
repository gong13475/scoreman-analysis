# ============================================================
# app.py
# ⚽ 전종목 해외배당 분석
# ============================================================

import streamlit as st
import time
from pathlib import Path

import database
import analysis
import collector


# ============================================================
# 페이지 설정
# ============================================================

st.set_page_config(
    page_title="전종목 해외배당 분석",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

.block-container {
    padding-top: 1rem;
    padding-bottom: 3rem;
    max-width: 1200px;
}

h1 {
    font-size: 1.8rem !important;
}

h2 {
    font-size: 1.35rem !important;
}

h3 {
    font-size: 1.1rem !important;
}

div.stButton > button {
    width: 100%;
    min-height: 44px;
}

.metric-card {
    padding: 15px;
    border-radius: 12px;
    background: #f5f7fa;
    text-align: center;
    margin-bottom: 10px;
}

.big-number {
    font-size: 28px;
    font-weight: 700;
}

.small-label {
    color: #666;
    font-size: 14px;
}

.good {
    color: #008000;
    font-weight: 700;
}

.bad {
    color: #d00000;
    font-weight: 700;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# DB 초기화
# ============================================================

try:
    database.init_database()
except Exception:
    pass


# ============================================================
# 제목
# ============================================================

st.title("⚽ 전종목 해외배당 분석")

st.caption(
    "Scoreman 자동수집 · 해외업체 최종배당 · 실제결과 · "
    "확률분석 · Turso 영구저장"
)


# ============================================================
# DB 상태
# ============================================================

status = database.get_database_status()
info = database.get_database_info()
storage = database.get_storage_usage()


c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        "저장 경기",
        f"{status.get('matches', 0):,}"
    )

with c2:
    st.metric(
        "저장 최종배당",
        f"{status.get('odds', 0):,}"
    )

with c3:
    st.metric(
        "실제 저장 업체",
        f"{status.get('bookmakers', 0):,}"
    )

with c4:
    st.metric(
        "DB",
        "Turso" if info.get("using_turso") else "SQLite"
    )


# ============================================================
# DB 상세
# ============================================================

with st.expander("🗄️ 데이터베이스 상태", expanded=True):

    if info.get("using_turso"):
        st.success("🟢 Turso DB 연결 정상")
    else:
        st.warning("🟡 로컬 SQLite fallback 모드")

    st.markdown("### 🔧 DB 연결 상세정보")

    a, b, c, d = st.columns(4)

    with a:
        st.write(
            "Turso URL 설정:",
            "✅" if info.get("database_url_configured") else "❌"
        )

    with b:
        st.write(
            "Turso Token 설정:",
            "✅" if info.get("auth_token_configured") else "❌"
        )

    with c:
        st.write(
            "libSQL 모듈:",
            "✅" if info.get("libsql_available") else "❌"
        )

    with d:
        st.write(
            "현재 사용 DB:",
            "Turso" if info.get("using_turso") else "SQLite"
        )

    st.markdown("### 💾 DB 저장 용량")

    if storage.get("success"):
        st.metric(
            "현재 DB 저장 크기",
            f"{storage.get('size_mb', 0):.2f} MB"
        )
        st.write(
            "저장 방식:",
            storage.get("storage_type", "")
        )
    else:
        st.write("DB 저장 용량을 확인할 수 없습니다.")


# ============================================================
# 업체별 저장 경기
# ============================================================

st.subheader("🏢 업체별 저장 경기 수")

company_counts = database.get_company_counts()

if company_counts:

    for name, count in company_counts.items():

        col1, col2 = st.columns([4, 1])

        with col1:
            st.write(name)

        with col2:
            st.write(f"{count:,}")

else:

    st.info("저장된 업체별 데이터가 없습니다.")


# ============================================================
# Scoreman 자동수집
# ============================================================

st.subheader("📥 Scoreman 경기 ID 구간 자동수집")

state = database.get_collection_state() or {}

last_completed = int(
    state.get("last_completed_id") or 0
)

default_start = (
    last_completed + 1
    if last_completed
    else 2005000
)

start_id = st.number_input(
    "시작 ID",
    min_value=1,
    value=int(default_start),
    step=1
)

end_id = st.number_input(
    "마지막 ID",
    min_value=1,
    value=int(start_id),
    step=1
)

if end_id >= start_id:
    st.caption(
        f"검색 대상: {end_id - start_id + 1:,}개"
    )


if last_completed:

    st.info(
        f"📌 마지막 성공 완료 ID: "
        f"{last_completed:,}\n\n"
        f"다음 자동 시작 ID: "
        f"{last_completed + 1:,}"
    )


# ============================================================
# 업체 선택
# ============================================================

st.subheader("🏢 수집 업체")

collect_mode = st.radio(
    "수집 방식",
    [
        "전체 업체 자동수집",
        "특정 업체만 수집"
    ],
    horizontal=True
)

selected_companies = None

all_companies = database.get_company_list()

if collect_mode == "특정 업체만 수집":

    if all_companies:

        selected_companies = st.multiselect(
            "수집할 업체",
            all_companies
        )

    else:

        st.warning(
            "현재 DB에 업체 목록이 없습니다. "
            "먼저 전체 업체 자동수집을 실행하세요."
        )

else:

    st.caption(
        "Scoreman에서 확인되는 전체 업체의 "
        "최종배당을 자동 저장합니다."
    )


# ============================================================
# 속도
# ============================================================

delay = st.number_input(
    "요청 간격(초)",
    min_value=0.10,
    max_value=10.0,
    value=0.50,
    step=0.10,
    format="%.2f"
)


# ============================================================
# 수집 버튼
# ============================================================

col1, col2 = st.columns(2)

with col1:

    if st.button(
        "▶️ 수집시작",
        type="primary"
    ):

        if end_id < start_id:

            st.error(
                "마지막 ID가 시작 ID보다 작습니다."
            )

        elif (
            collect_mode == "특정 업체만 수집"
            and not selected_companies
        ):

            st.error(
                "수집할 업체를 선택하세요."
            )

        else:

            ok = collector.start_background_collection(
                start_id=int(start_id),
                end_id=int(end_id),
                selected_companies=selected_companies,
                delay=float(delay),
                resume=True
            )

            if ok:
                st.success("수집을 시작했습니다.")
                st.rerun()
            else:
                st.warning(
                    "이미 수집 중이거나 "
                    "수집할 ID가 없습니다."
                )


with col2:

    if st.button("⏹️ 수집중지"):

        if collector.stop_background_collection():

            st.warning(
                "수집 중지 요청을 보냈습니다."
            )

        else:

            st.info(
                "현재 실행 중인 수집 작업이 없습니다."
            )


# ============================================================
# 수집 상태
# ============================================================

job = collector.get_job_status()

if job.get("running"):

    st.subheader("🔄 현재 수집 상태")

    total = max(
        int(job.get("total") or 1),
        1
    )

    current = int(
        job.get("current") or 0
    )

    progress = min(
        current / total,
        1.0
    )

    st.progress(progress)

    a, b, c, d, e = st.columns(5)

    a.metric("진행", f"{current:,}/{total:,}")
    b.metric("신규", f"{job.get('success', 0):,}")
    c.metric("기존", f"{job.get('exists', 0):,}")
    d.metric("실패", f"{job.get('failed', 0):,}")
    e.metric("배당", f"{job.get('odds', 0):,}")

    st.write(
        f"현재 ID: "
        f"{job.get('start_id', 0) + current - 1:,}"
    )

    time.sleep(1)
    st.rerun()


elif job.get("finished"):

    result = job.get("result") or {}

    st.subheader("✅ 최근 수집 결과")

    a, b, c, d, e = st.columns(5)

    a.metric(
        "신규",
        f"{result.get('success', 0):,}"
    )

    b.metric(
        "기존",
        f"{result.get('exists', 0):,}"
    )

    c.metric(
        "실패",
        f"{result.get('failed', 0):,}"
    )

    d.metric(
        "배당없음",
        f"{result.get('no_odds', 0):,}"
    )

    e.metric(
        "최종배당",
        f"{result.get('odds', 0):,}"
    )


# ============================================================
# 로그
# ============================================================

with st.expander("📋 수집 로그"):

    if job.get("log"):
        st.code(
            job.get("log"),
            language="text"
        )
    else:
        st.info("로그가 없습니다.")


# ============================================================
# 수동 최종배당 분석
# ============================================================

st.divider()

st.header("🎯 수동 최종배당 분석")

st.caption(
    "업체를 선택하고 최종 승/무/패 배당을 입력하면 "
    "내재확률과 과거 동일배당 실제 결과확률을 계산합니다."
)


companies = database.get_company_list()

if companies:

    manual_company = st.selectbox(
        "업체 선택",
        companies,
        key="manual_company"
    )

else:

    manual_company = st.text_input(
        "업체명",
        value="Bet365",
        key="manual_company_text"
    )


m1, m2, m3 = st.columns(3)

with m1:

    manual_home = st.number_input(
        "승 배당",
        min_value=1.01,
        value=1.83,
        step=0.01,
        format="%.2f"
    )

with m2:

    manual_draw = st.number_input(
        "무 배당",
        min_value=1.01,
        value=3.50,
        step=0.01,
        format="%.2f"
    )

with m3:

    manual_away = st.number_input(
        "패 배당",
        min_value=1.01,
        value=4.20,
        step=0.01,
        format="%.2f"
    )


if st.button(
    "🔎 배당 분석",
    type="primary"
):

    result = analysis.analyze_manual_odds(
        company_name=manual_company,
        home_odds=manual_home,
        draw_odds=manual_draw,
        away_odds=manual_away
    )

    if result:

        st.subheader("📊 분석 결과")

        a, b, c = st.columns(3)

        with a:
            st.metric(
                "승",
                f"{manual_home:.2f}"
            )

        with b:
            st.metric(
                "무",
                f"{manual_draw:.2f}"
            )

        with c:
            st.metric(
                "패",
                f"{manual_away:.2f}"
            )

        st.markdown("### 배당 기준 내재확률")

        p1, p2, p3 = st.columns(3)

        p1.metric(
            "승 확률",
            f"{result['implied_home']:.2f}%"
        )

        p2.metric(
            "무 확률",
            f"{result['implied_draw']:.2f}%"
        )

        p3.metric(
            "패 확률",
            f"{result['implied_away']:.2f}%"
        )

        st.markdown(
            f"**과거 동일배당 경기: "
            f"{result['sample_count']:,}경기**"
        )

        st.markdown("### 실제 결과 확률")

        q1, q2, q3 = st.columns(3)

        q1.metric(
            "실제 승",
            f"{result['historical_home']:.2f}%"
        )

        q2.metric(
            "실제 무",
            f"{result['historical_draw']:.2f}%"
        )

        q3.metric(
            "실제 패",
            f"{result['historical_away']:.2f}%"
        )

        st.markdown("### 📉 부족확률")

        r1, r2, r3 = st.columns(3)

        r1.metric(
            "승 부족확률",
            f"{result['shortage_home']:.2f}%"
        )

        r2.metric(
            "무 부족확률",
            f"{result['shortage_draw']:.2f}%"
        )

        r3.metric(
            "패 부족확률",
            f"{result['shortage_away']:.2f}%"
        )

        st.info(
            "부족확률 = 과거 동일배당 실제확률 "
            "− 현재 배당 내재확률"
        )

        if result["sample_count"] > 0:

            st.subheader("📋 동일배당 과거 경기")

            rows = result.get(
                "matches",
                []
            )

            if rows:

                st.dataframe(
                    rows,
                    use_container_width=True,
                    hide_index=True
                )

    else:

        st.warning(
            "분석할 데이터를 찾을 수 없습니다."
        )


# ============================================================
# 수동 실제 결과 입력
# ============================================================

st.divider()

st.header("📝 수동 경기 결과 분석")

result_choice = st.radio(
    "실제 결과",
    ["승", "무", "패"],
    horizontal=True
)

if st.button("🎯 결과까지 반영"):

    result = analysis.analyze_manual_odds(
        company_name=manual_company,
        home_odds=manual_home,
        draw_odds=manual_draw,
        away_odds=manual_away
    )

    if result and result["sample_count"] > 0:

        if result_choice == "승":
            actual = result["historical_home"]

        elif result_choice == "무":
            actual = result["historical_draw"]

        else:
            actual = result["historical_away"]

        st.success(
            f"실제 결과: {result_choice} / "
            f"동일배당 과거 해당 결과 확률: "
            f"{actual:.2f}%"
        )

        st.write(
            f"현재 배당 내재확률 대비 "
            f"{actual - result[f'implied_{\"home\" if result_choice == \"승\" else \"draw\" if result_choice == \"무\" else \"away\"}']:.2f}%p"
        )

    else:

        st.warning(
            "동일배당 과거 데이터가 없습니다."
        )


# ============================================================
# 음성 기능
# ============================================================

st.divider()

st.header("🎙️ 음성 기능")

st.caption(
    "휴대폰 브라우저의 음성 입력 기능을 사용할 수 있습니다."
)

st.markdown("""
<script>
function speakText(text) {
    if ('speechSynthesis' in window) {
        const u = new SpeechSynthesisUtterance(text);
        u.lang = 'ko-KR';
        u.rate = 0.9;
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(u);
    }
}
</script>
""", unsafe_allow_html=True)

speech_text = st.text_input(
    "읽어줄 내용",
    value="승 확률과 무 확률을 확인하세요."
)

st.markdown(
    f"""
    <button onclick="speakText({speech_text!r})"
    style="
    width:100%;
    height:45px;
    border-radius:8px;
    border:1px solid #ccc;
    background:#f5f5f5;
    font-size:16px;">
    🔊 결과 음성 듣기
    </button>
    """,
    unsafe_allow_html=True
    )
