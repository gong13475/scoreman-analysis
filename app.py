# ============================================================
# app.py
# ⚽ Scoreman 전종목 해외배당 분석
#
# 기존 기능 유지 + 추가 기능
#
# 추가
# - 수동배당 업체 선택
# - 배당 입력 즉시 예상확률
# - 실제확률
# - 확률 차이
# - 부족확률
# - 중지 지점부터 이어받기
# - 마이크 녹음
# - 결과 듣기
# - 휴대폰 화면 대응
# ============================================================

import time
import html
import streamlit as st

import database
import collector
import analysis


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

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 0.8rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }

    div.stButton > button {
        min-height: 48px;
        font-weight: 700;
        border-radius: 10px;
    }

    div[data-testid="stMetric"] {
        border: 1px solid #dddddd;
        border-radius: 10px;
        padding: 8px;
    }

    .prob-box {
        border: 1px solid #dddddd;
        border-radius: 10px;
        padding: 12px;
        margin-top: 8px;
        margin-bottom: 8px;
    }

    .shortage {
        color: #d32f2f;
        font-weight: 800;
    }

    .positive {
        color: #1565c0;
        font-weight: 800;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# DB 초기화
# ============================================================

try:
    database.init_database()
except Exception as e:
    st.error(f"DB 초기화 오류: {e}")
    st.stop()


# ============================================================
# 숫자
# ============================================================

def safe_float(value, default=0.0):

    try:
        return float(value)
    except Exception:
        return default


# ============================================================
# 배당 → 정규화 예상확률
# ============================================================

def normalize_probabilities(home, draw, away):

    try:

        h = 1.0 / float(home)
        d = 1.0 / float(draw)
        a = 1.0 / float(away)

        total = h + d + a

        if total <= 0:
            return 0.0, 0.0, 0.0

        return (
            h / total * 100,
            d / total * 100,
            a / total * 100
        )

    except Exception:

        return 0.0, 0.0, 0.0


# ============================================================
# DB 상태
# ============================================================

def get_status():

    try:
        return database.get_database_status()
    except Exception:
        return {
            "matches": 0,
            "odds": 0,
            "bookmakers": 0
        }


def get_companies():

    try:
        return database.get_company_list()
    except Exception:
        return []


# ============================================================
# 음성 결과 듣기
# ============================================================

def speak_text(text_value):

    safe_text = html.escape(
        str(text_value)
    )

    st.components.v1.html(
        f"""
        <div style="
            display:flex;
            gap:8px;
            align-items:center;
            font-family:Arial;
        ">

        <button
            onclick="speakResult()"
            style="
                background:#1565c0;
                color:white;
                border:0;
                border-radius:10px;
                padding:12px 18px;
                font-size:16px;
                font-weight:bold;
                width:100%;
            "
        >
        🔊 결과 듣기
        </button>

        <script>

        function speakResult() {{

            if (!window.speechSynthesis) {{
                alert("이 브라우저는 음성 재생을 지원하지 않습니다.");
                return;
            }}

            window.speechSynthesis.cancel();

            const text = "{safe_text}";

            const utterance =
                new SpeechSynthesisUtterance(text);

            utterance.lang = "ko-KR";
            utterance.rate = 0.95;
            utterance.pitch = 1.0;

            window.speechSynthesis.speak(
                utterance
            );
        }}

        </script>
        </div>
        """,
        height=65
    )


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

status = get_status()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "저장 경기",
        f"{status.get('matches', 0):,}"
    )

with col2:
    st.metric(
        "저장 최종배당",
        f"{status.get('odds', 0):,}"
    )

with col3:
    st.metric(
        "실제 저장 업체",
        f"{status.get('bookmakers', 0):,}"
    )

with col4:

    try:
        info = database.get_database_info()
        using_turso = bool(
            info.get("using_turso")
        )
    except Exception:
        using_turso = False

    st.metric(
        "DB",
        "Turso" if using_turso else "SQLite"
    )


# ============================================================
# DB 상태 상세
# ============================================================

with st.expander(
    "🗄️ 데이터베이스 상태",
    expanded=False
):

    try:

        info = database.get_database_info()

        if info.get("using_turso"):

            st.success(
                "🟢 Turso DB 연결 정상"
            )

        else:

            st.warning(
                "🟡 SQLite fallback 모드"
            )

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.write(
                "Turso URL:",
                "✅"
                if info.get(
                    "database_url_configured"
                )
                else "❌"
            )

        with c2:
            st.write(
                "Turso Token:",
                "✅"
                if info.get(
                    "auth_token_configured"
                )
                else "❌"
            )

        with c3:
            st.write(
                "libSQL:",
                "✅"
                if info.get(
                    "libsql_available"
                )
                else "❌"
            )

        with c4:
            st.write(
                "현재 DB:",
                "Turso"
                if info.get("using_turso")
                else "SQLite"
            )

    except Exception as e:

        st.error(
            f"DB 상태 확인 오류: {e}"
        )


# ============================================================
# 저장 용량
# ============================================================

with st.expander(
    "💾 DB 저장 용량",
    expanded=False
):

    try:

        storage = database.get_storage_usage()

        if storage.get("success"):

            size_mb = safe_float(
                storage.get("size_mb")
            )

            size_gb = safe_float(
                storage.get("size_gb")
            )

            st.metric(
                "현재 DB 크기",
                f"{size_mb:.2f} MB"
            )

            st.caption(
                f"{storage.get('storage_type', '')} "
                f"· 약 {size_gb:.4f} GB"
            )

        else:

            st.warning(
                storage.get(
                    "error",
                    "저장 용량 확인 불가"
                )
            )

    except Exception as e:

        st.warning(
            f"저장 용량 확인 실패: {e}"
        )


# ============================================================
# 업체별 저장 경기
# ============================================================

with st.expander(
    "🏢 업체별 저장 경기 수",
    expanded=False
):

    try:

        company_counts = (
            database.get_company_counts()
        )

        if company_counts:

            rows = []

            for name, count in company_counts.items():

                rows.append({
                    "업체": name,
                    "저장 경기": int(count)
                })

            st.dataframe(
                rows,
                use_container_width=True,
                hide_index=True
            )

        else:

            st.info(
                "저장된 업체 데이터가 없습니다."
            )

    except Exception as e:

        st.warning(
            f"업체 통계 오류: {e}"
        )


# ============================================================
# 자동수집
# ============================================================

st.markdown("---")
st.header("📥 Scoreman 경기 ID 구간 자동수집")


# ============================================================
# 저장된 수집상태
# ============================================================

try:

    collection_state = (
        database.get_collection_state()
        or {}
    )

except Exception:

    collection_state = {}


last_completed = int(
    collection_state.get(
        "last_completed_id",
        0
    )
    or 0
)


# ============================================================
# 현재 작업
# ============================================================

job_before = collector.get_job_status()

if job_before.get("running"):

    default_start = int(
        job_before.get(
            "start_id",
            2005000
        )
        or 2005000
    )

else:

    default_start = (
        last_completed + 1
        if last_completed > 0
        else 2005000
    )


c1, c2 = st.columns(2)

with c1:

    start_id = st.number_input(
        "시작 ID",
        min_value=1,
        value=int(default_start),
        step=1,
        format="%d",
        key="collector_start_id"
    )

with c2:

    end_id = st.number_input(
        "마지막 ID",
        min_value=1,
        value=int(default_start),
        step=1,
        format="%d",
        key="collector_end_id"
    )


search_count = (
    int(end_id)
    - int(start_id)
    + 1
)

if search_count < 0:
    search_count = 0


st.caption(
    f"검색 대상: {search_count:,}개"
)


# ============================================================
# 마지막 성공 ID
# ============================================================

if last_completed > 0:

    st.info(
        f"📌 마지막 성공 완료 ID: "
        f"{last_completed:,}\n\n"
        f"다음 시작 가능 ID: "
        f"{last_completed + 1:,}"
    )


# ============================================================
# 업체 선택
# ============================================================

st.markdown("### 🏢 수집 업체")

collection_mode = st.radio(
    "수집 방식",
    [
        "전체 업체 자동수집",
        "특정 업체만 수집"
    ],
    horizontal=True,
    key="collection_mode"
)


companies = get_companies()

selected_companies = None


if collection_mode == "특정 업체만 수집":

    if companies:

        selected_companies = st.multiselect(
            "수집할 업체",
            options=companies,
            key="selected_companies"
        )

        if not selected_companies:

            st.warning(
                "업체를 1개 이상 선택하세요."
            )

    else:

        st.warning(
            "저장된 업체 목록이 없습니다. "
            "먼저 전체 업체 수집을 실행하세요."
        )

else:

    st.caption(
        "Scoreman에서 확인되는 전체 업체를 자동수집합니다."
    )


# ============================================================
# 요청 간격
# ============================================================

delay = st.number_input(
    "요청 간격(초)",
    min_value=0.10,
    max_value=10.0,
    value=0.50,
    step=0.10,
    format="%.2f",
    key="collector_delay"
)


# ============================================================
# 중지 지점부터 이어받기
# ============================================================

resume_state = (
    database.get_collection_state()
    or {}
)

resume_last = int(
    resume_state.get(
        "last_completed_id",
        0
    )
    or 0
)

resume_end = int(
    resume_state.get(
        "end_id",
        0
    )
    or 0
)


if (
    resume_last > 0
    and resume_end > resume_last
    and not collector.is_running()
):

    st.markdown("### 🔄 중지 지점 이어받기")

    st.info(
        f"마지막 성공 ID: {resume_last:,}  →  "
        f"다음 ID: {resume_last + 1:,}  →  "
        f"종료 ID: {resume_end:,}"
    )

    resume_button = st.button(
        "▶️ 중지 지점부터 이어받기",
        use_container_width=True,
        type="primary",
        key="resume_collection_button"
    )

else:

    resume_button = False


# ============================================================
# 시작 / 중지
# ============================================================

b1, b2 = st.columns(2)

with b1:

    start_button = st.button(
        "▶️ 수집시작",
        use_container_width=True,
        type="primary",
        key="start_collection_button"
    )

with b2:

    stop_button = st.button(
        "🛑 수집중지",
        use_container_width=True,
        key="stop_collection_button"
    )


# ============================================================
# 이어받기 실행
# ============================================================

if resume_button:

    started = collector.start_background_collection(
        resume_last + 1,
        resume_end,
        selected_companies,
        float(delay),
        resume=False
    )

    if started:

        st.success(
            f"▶️ {resume_last + 1:,}번부터 "
            f"{resume_end:,}번까지 이어받기를 시작했습니다."
        )

        time.sleep(0.3)
        st.rerun()

    else:

        st.warning(
            "이미 수집 중이거나 이어받을 수 없습니다."
        )


# ============================================================
# 새 수집 시작
# ============================================================

if start_button:

    if int(end_id) < int(start_id):

        st.error(
            "마지막 ID가 시작 ID보다 작습니다."
        )

    elif (
        collection_mode == "특정 업체만 수집"
        and not selected_companies
    ):

        st.error(
            "수집할 업체를 선택하세요."
        )

    else:

        started = collector.start_background_collection(
            int(start_id),
            int(end_id),
            selected_companies,
            float(delay),
            resume=True
        )

        if started:

            st.success(
                "수집을 시작했습니다."
            )

            time.sleep(0.3)
            st.rerun()

        else:

            st.warning(
                "이미 수집 중이거나 "
                "수집할 ID가 없습니다."
            )


# ============================================================
# 중지
# ============================================================

if stop_button:

    stopped = (
        collector.stop_background_collection()
    )

    if stopped:

        st.warning(
            "🛑 수집 중지 요청을 전달했습니다."
        )

    else:

        st.info(
            "현재 실행 중인 수집 작업이 없습니다."
        )


# ============================================================
# 현재 수집 상태
# ============================================================

job = collector.get_job_status()


if job.get("running"):

    st.markdown("---")
    st.subheader("🔄 현재 수집 상태")

    total = int(
        job.get("total", 0)
        or 0
    )

    current = int(
        job.get("current", 0)
        or 0
    )

    progress = (
        current / total
        if total > 0
        else 0
    )

    progress = max(
        0.0,
        min(progress, 1.0)
    )

    st.progress(progress)

    st.write(
        f"진행: {current:,} / {total:,} "
        f"({progress * 100:.1f}%)"
    )

    start_value = int(
        job.get("start_id", 0)
        or 0
    )

    end_value = int(
        job.get("end_id", 0)
        or 0
    )

    current_id = (
        start_value + current - 1
        if current > 0
        else start_value
    )

    st.write(
        f"현재 ID: {current_id:,} / "
        f"{end_value:,}"
    )

    a, b, c, d, e = st.columns(5)

    with a:
        st.metric(
            "신규",
            f"{int(job.get('success', 0) or 0):,}"
        )

    with b:
        st.metric(
            "기존",
            f"{int(job.get('exists', 0) or 0):,}"
        )

    with c:
        st.metric(
            "실패",
            f"{int(job.get('failed', 0) or 0):,}"
        )

    with d:
        st.metric(
            "배당없음",
            f"{int(job.get('no_odds', 0) or 0):,}"
        )

    with e:
        st.metric(
            "최종배당",
            f"{int(job.get('odds', 0) or 0):,}"
        )


# ============================================================
# 최근 수집 결과
# ============================================================

elif job.get("finished"):

    result = (
        job.get("result")
        or {}
    )

    st.markdown("---")
    st.subheader("✅ 최근 수집 결과")

    a, b, c, d, e = st.columns(5)

    with a:
        st.metric(
            "신규",
            f"{int(result.get('success', 0) or 0):,}"
        )

    with b:
        st.metric(
            "기존",
            f"{int(result.get('exists', 0) or 0):,}"
        )

    with c:
        st.metric(
            "실패",
            f"{int(result.get('failed', 0) or 0):,}"
        )

    with d:
        st.metric(
            "배당없음",
            f"{int(result.get('no_odds', 0) or 0):,}"
        )

    with e:
        st.metric(
            "최종배당",
            f"{int(result.get('odds', 0) or 0):,}"
        )

    if result.get("stopped"):

        st.warning(
            "🛑 수집이 중지되었습니다. "
            "아래 이어받기 버튼으로 계속할 수 있습니다."
        )

    else:

        st.success(
            "수집 작업이 완료되었습니다."
        )


# ============================================================
# 수집 로그
# ============================================================

with st.expander(
    "📋 수집 로그 보기",
    expanded=False
):

    log_text = job.get(
        "log",
        ""
    )

    if log_text:

        st.code(
            log_text,
            language="text"
        )

    else:

        st.info(
            "현재 표시할 로그가 없습니다."
        )


# ============================================================
# 자동 새로고침
# ============================================================

if job.get("running"):

    time.sleep(1.5)
    st.rerun()


# ============================================================
# 수동 최종배당 분석
# ============================================================

st.markdown("---")
st.header("🎯 수동 최종배당 입력 / 분석")

st.caption(
    "업체를 선택하고 승·무·패 배당을 입력하면 "
    "배당 예상확률과 과거 실제확률을 비교합니다."
)


# ============================================================
# 업체 선택
# ============================================================

manual_companies = get_companies()


if manual_companies:

    manual_company = st.selectbox(
        "🏢 회사 선택",
        manual_companies,
        key="manual_company"
    )

else:

    manual_company = st.text_input(
        "🏢 회사명 직접 입력",
        value="Bet365",
        key="manual_company_text"
    )


# ============================================================
# 배당 입력
# ============================================================

o1, o2, o3 = st.columns(3)

with o1:

    manual_home = st.number_input(
        "승 배당",
        min_value=1.01,
        value=1.83,
        step=0.01,
        format="%.2f",
        key="manual_home"
    )

with o2:

    manual_draw = st.number_input(
        "무 배당",
        min_value=1.01,
        value=3.50,
        step=0.01,
        format="%.2f",
        key="manual_draw"
    )

with o3:

    manual_away = st.number_input(
        "패 배당",
        min_value=1.01,
        value=4.20,
        step=0.01,
        format="%.2f",
        key="manual_away"
    )


# ============================================================
# 입력 즉시 배당 예상확률
# ============================================================

hp, dp, ap = normalize_probabilities(
    manual_home,
    manual_draw,
    manual_away
)


st.markdown("### 📊 현재 입력 배당의 예상확률")

p1, p2, p3 = st.columns(3)

with p1:

    st.metric(
        "승",
        f"{hp:.2f}%"
    )

with p2:

    st.metric(
        "무",
        f"{dp:.2f}%"
    )

with p3:

    st.metric(
        "패",
        f"{ap:.2f}%"
    )


st.caption(
    f"입력 배당: "
    f"승 {manual_home:.2f} / "
    f"무 {manual_draw:.2f} / "
    f"패 {manual_away:.2f}"
)


# ============================================================
# 마이크
# ============================================================

st.markdown("### 🎙️ 마이크 / 음성")

st.caption(
    "휴대폰에서 마이크로 말을 녹음할 수 있습니다."
)

try:

    audio_value = st.audio_input(
        "🎙️ 말하기 / 녹음",
        key="manual_audio"
    )

    if audio_value:

        st.success(
            "🎙️ 녹음 완료"
        )

        st.audio(
            audio_value
        )

except Exception:

    st.info(
        "현재 Streamlit 버전에서는 "
        "마이크 입력을 지원하지 않습니다."
    )


# ============================================================
# 분석 버튼
# ============================================================

analyze_button = st.button(
    "🔎 입력 배당 과거결과 분석",
    use_container_width=True,
    type="primary",
    key="manual_analysis_button"
)


# ============================================================
# 분석
# ============================================================

if analyze_button:

    if not manual_company:

        st.error(
            "회사를 선택하거나 입력하세요."
        )

    else:

        try:

            result = analysis.analyze_manual_odds(
                manual_company,
                manual_home,
                manual_draw,
                manual_away,
                tolerance=0.0001
            )

        except Exception as e:

            result = {
                "success": False,
                "error": str(e),
                "rows": []
            }


        if not result.get("success"):

            st.error(
                result.get(
                    "error",
                    "분석에 실패했습니다."
                )
            )

        else:

            total = int(
                result.get(
                    "total",
                    0
                )
                or 0
            )

            actual_win = safe_float(
                result.get(
                    "actual_home",
                    0
                )
            )

            actual_draw = safe_float(
                result.get(
                    "actual_draw",
                    0
                )
            )

            actual_loss = safe_float(
                result.get(
                    "actual_away",
                    0
                )
            )


            win_count = int(
                result.get(
                    "home_count",
                    0
                )
                or 0
            )

            draw_count = int(
                result.get(
                    "draw_count",
                    0
                )
                or 0
            )

            loss_count = int(
                result.get(
                    "away_count",
                    0
                )
                or 0
            )


            # ------------------------------------------------
            # 부족확률
            # ------------------------------------------------

            win_gap = (
                actual_win - hp
            )

            draw_gap = (
                actual_draw - dp
            )

            loss_gap = (
                actual_loss - ap
            )


            win_shortage = max(
                0.0,
                -win_gap
            )

            draw_shortage = max(
                0.0,
                -draw_gap
            )

            loss_shortage = max(
                0.0,
                -loss_gap
            )


            # ------------------------------------------------
            # 실제 결과
            # ------------------------------------------------

            st.markdown(
                "### 📈 동일배당 과거 실제 결과"
            )

            st.write(
                f"업체: **{manual_company}**"
            )

            st.write(
                f"동일배당 표본: **{total:,}경기**"
            )


            r1, r2, r3 = st.columns(3)

            with r1:

                st.metric(
                    "승",
                    f"{win_count:,}경기",
                    f"{actual_win:.2f}%"
                )

            with r2:

                st.metric(
                    "무",
                    f"{draw_count:,}경기",
                    f"{actual_draw:.2f}%"
                )

            with r3:

                st.metric(
                    "패",
                    f"{loss_count:,}경기",
                    f"{actual_loss:.2f}%"
                )


            # ------------------------------------------------
            # 핵심 비교표
            # ------------------------------------------------

            st.markdown(
                "### ⚖️ 배당 대비 실제확률 / 부족확률"
            )

            table = [

                {
                    "결과": "승",
                    "배당": f"{manual_home:.2f}",
                    "배당 예상확률":
                        f"{hp:.2f}%",
                    "실제확률":
                        f"{actual_win:.2f}%",
                    "차이":
                        f"{win_gap:+.2f}%p",
                    "부족확률":
                        f"{win_shortage:.2f}%p"
                },

                {
                    "결과": "무",
                    "배당": f"{manual_draw:.2f}",
                    "배당 예상확률":
                        f"{dp:.2f}%",
                    "실제확률":
                        f"{actual_draw:.2f}%",
                    "차이":
                        f"{draw_gap:+.2f}%p",
                    "부족확률":
                        f"{draw_shortage:.2f}%p"
                },

                {
                    "결과": "패",
                    "배당": f"{manual_away:.2f}",
                    "배당 예상확률":
                        f"{ap:.2f}%",
                    "실제확률":
                        f"{actual_loss:.2f}%",
                    "차이":
                        f"{loss_gap:+.2f}%p",
                    "부족확률":
                        f"{loss_shortage:.2f}%p"
                }

            ]

            st.dataframe(
                table,
                use_container_width=True,
                hide_index=True
            )


            # ------------------------------------------------
            # 결과 판단
            # ------------------------------------------------

            gaps = {
                "승": win_gap,
                "무": draw_gap,
                "패": loss_gap
            }

            best_result = max(
                gaps,
                key=gaps.get
            )

            best_gap = gaps[
                best_result
            ]


            shortage = {
                "승": win_shortage,
                "무": draw_shortage,
                "패": loss_shortage
            }

            shortage_result = max(
                shortage,
                key=shortage.get
            )

            shortage_value = shortage[
                shortage_result
            ]


            if total > 0:

                if best_gap > 0:

                    st.success(
                        f"📌 실제확률이 배당 예상확률보다 "
                        f"가장 높은 결과: "
                        f"**{best_result} "
                        f"(+{best_gap:.2f}%p)**"
                    )

                else:

                    st.info(
                        "과거 실제확률이 배당 예상확률보다 "
                        "높은 결과가 없습니다."
                    )

                if shortage_value > 0:

                    st.warning(
                        f"⚠️ 부족확률이 가장 큰 결과: "
                        f"**{shortage_result} "
                        f"({shortage_value:.2f}%p 부족)**"
                    )


            # ------------------------------------------------
            # 음성 결과
            # ------------------------------------------------

            voice_text = (
                f"{manual_company} 분석 결과. "
                f"표본 {total}경기. "
                f"승 실제확률 {actual_win:.2f}퍼센트. "
                f"무 실제확률 {actual_draw:.2f}퍼센트. "
                f"패 실제확률 {actual_loss:.2f}퍼센트. "
                f"배당 대비 가장 높은 결과는 "
                f"{best_result}입니다."
            )

            st.markdown(
                "### 🔊 분석 결과 듣기"
            )

            speak_text(
                voice_text
            )


            # ------------------------------------------------
            # 과거 경기
            # ------------------------------------------------

            historical = result.get(
                "rows",
                []
            )

            if historical:

                st.markdown(
                    "### 📋 동일배당 과거 경기"
                )

                history_rows = []

                for row in historical:

                    history_rows.append({

                        "날짜":
                            row.get(
                                "match_date",
                                ""
                            ),

                        "홈":
                            row.get(
                                "home_team",
                                ""
                            ),

                        "원정":
                            row.get(
                                "away_team",
                                ""
                            ),

                        "스코어":
                            f"{row.get('home_score', '')}"
                            f" - "
                            f"{row.get('away_score', '')}",

                        "결과":
                            row.get(
                                "result",
                                ""
                            ),

                        "승":
                            f"{safe_float(row.get('home_odds')):.2f}",

                        "무":
                            f"{safe_float(row.get('draw_odds')):.2f}",

                        "패":
                            f"{safe_float(row.get('away_odds')):.2f}"

                    })

                st.dataframe(
                    history_rows,
                    use_container_width=True,
                    hide_index=True
                )

            else:

                st.warning(
                    "완전히 동일한 배당의 "
                    "과거 경기가 없습니다."
                )


# ============================================================
# 저장 경기 조회
# ============================================================

st.markdown("---")
st.header("📚 저장 경기 / 배당 조회")


lookup_id = st.text_input(
    "경기 ID 입력",
    key="lookup_id"
)


if st.button(
    "경기 조회",
    use_container_width=True,
    key="lookup_button"
):

    if lookup_id.strip():

        try:

            match = database.get_match(
                lookup_id.strip()
            )

            if not match:

                st.warning(
                    "해당 경기 ID가 없습니다."
                )

            else:

                st.markdown(
                    f"### "
                    f"{match.get('home_team', '')} "
                    f"vs "
                    f"{match.get('away_team', '')}"
                )

                st.write(
                    f"날짜: "
                    f"{match.get('match_date', '')}"
                )

                st.write(
                    f"스코어: "
                    f"{match.get('home_score', '')} - "
                    f"{match.get('away_score', '')}"
                )

                st.write(
                    f"실제 결과: "
                    f"**{match.get('result', '')}**"
                )

                odds = (
                    database.get_odds_by_match(
                        lookup_id.strip()
                    )
                )

                if odds:

                    odds_rows = []

                    for row in odds:

                        odds_rows.append({

                            "업체":
                                row.get(
                                    "company_name",
                                    ""
                                ),

                            "승":
                                f"{safe_float(row.get('final_home')):.2f}",

                            "무":
                                f"{safe_float(row.get('final_draw')):.2f}",

                            "패":
                                f"{safe_float(row.get('final_away')):.2f}"

                        })

                    st.dataframe(
                        odds_rows,
                        use_container_width=True,
                        hide_index=True
                    )

                else:

                    st.info(
                        "저장된 최종배당이 없습니다."
                    )

        except Exception as e:

            st.error(
                f"경기 조회 오류: {e}"
            )


# ============================================================
# 전체 저장 데이터
# ============================================================

with st.expander(
    "📊 전체 저장 경기 보기",
    expanded=False
):

    try:

        all_matches = (
            database.get_all_matches()
        )

        if all_matches:

            display_rows = []

            for row in all_matches[:500]:

                display_rows.append({

                    "ID":
                        row.get(
                            "schedule_id",
                            ""
                        ),

                    "날짜":
                        row.get(
                            "match_date",
                            ""
                        ),

                    "홈":
                        row.get(
                            "home_team",
                            ""
                        ),

                    "원정":
                        row.get(
                            "away_team",
                            ""
                        ),

                    "스코어":
                        f"{row.get('home_score', '')}"
                        f" - "
                        f"{row.get('away_score', '')}",

                    "결과":
                        row.get(
                            "result",
                            ""
                        )

                })

            st.dataframe(
                display_rows,
                use_container_width=True,
                hide_index=True
            )

            if len(all_matches) > 500:

                st.caption(
                    "최근 500경기만 표시합니다."
                )

        else:

            st.info(
                "저장된 경기가 없습니다."
            )

    except Exception as e:

        st.warning(
            f"저장 경기 조회 오류: {e}"
        )


# ============================================================
# 새로고침
# ============================================================

st.markdown("---")

if st.button(
    "🔄 데이터 새로고침",
    use_container_width=True,
    key="refresh_button"
):

    st.rerun()


# ============================================================
# 안내
# ============================================================

st.caption(
    "⚠️ 배당 예상확률은 1/배당을 정규화한 값입니다. "
    "과거 동일배당 결과는 참고용 통계입니다."
)

st.caption(
    "📱 수집은 Streamlit 서버의 백그라운드 작업으로 실행됩니다."
)
