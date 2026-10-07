# ============================================================
# app.py
# ⚽ Scoreman 전종목 해외배당 분석
#
# 기능
# - Turso 영구저장
# - SQLite fallback
# - Scoreman 백그라운드 자동수집
# - 수집 시작 / 중지
# - 휴대폰 화면을 꺼도 백그라운드 작업은 서버에서 계속 실행
# - 전체 업체 / 특정 업체 선택
# - 최종 승 / 무 / 패 배당 수동 입력
# - 소수점 2자리 배당 표시
# - 동일배당 과거 경기 검색
# - 실제 승 / 무 / 패 결과
# - 배당 기준 예상확률
# - 실제 결과확률
# - 부족확률
# - 업체별 통계
# - 마이크 녹음 / 음성 재생
# ============================================================

import time
import math

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
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }

    div.stButton > button {
        min-height: 46px;
        font-weight: 700;
        border-radius: 10px;
    }

    div[data-testid="stMetric"] {
        border: 1px solid #dddddd;
        border-radius: 10px;
        padding: 8px;
    }

    .small-text {
        font-size: 0.85rem;
        color: #666;
    }

    .result-win {
        color: #1565c0;
        font-weight: 800;
    }

    .result-draw {
        color: #555;
        font-weight: 800;
    }

    .result-loss {
        color: #d32f2f;
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
# 숫자 변환
# ============================================================

def safe_float(value, default=0.0):

    try:
        return float(value)
    except Exception:
        return default


def odds_probability(odds):

    odds = safe_float(odds)

    if odds <= 0:
        return 0.0

    return (1.0 / odds) * 100.0


def normalize_probabilities(home, draw, away):

    total = (
        odds_probability(home)
        + odds_probability(draw)
        + odds_probability(away)
    )

    if total <= 0:
        return 0.0, 0.0, 0.0

    return (
        odds_probability(home) / total * 100,
        odds_probability(draw) / total * 100,
        odds_probability(away) / total * 100
    )


# ============================================================
# 데이터 조회
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
    using_turso = False

    try:
        info = database.get_database_info()
        using_turso = bool(
            info.get("using_turso")
        )
    except Exception:
        pass

    st.metric(
        "DB",
        "Turso" if using_turso else "SQLite"
    )


# ============================================================
# DB 상세
# ============================================================

with st.expander(
    "🗄️ 데이터베이스 상태",
    expanded=True
):

    try:

        info = database.get_database_info()

        if info.get("using_turso"):

            st.success(
                "🟢 Turso DB 연결 정상"
            )

        else:

            st.warning(
                "🟡 로컬 SQLite fallback 모드"
            )

        st.markdown(
            "### 🔧 DB 연결 상세정보"
        )

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.write(
                "Turso URL 설정:",
                "✅" if info.get(
                    "database_url_configured"
                ) else "❌"
            )

        with c2:
            st.write(
                "Turso Token 설정:",
                "✅" if info.get(
                    "auth_token_configured"
                ) else "❌"
            )

        with c3:
            st.write(
                "libSQL 모듈:",
                "✅" if info.get(
                    "libsql_available"
                ) else "❌"
            )

        with c4:
            st.write(
                "현재 사용 DB:",
                "Turso"
                if info.get("using_turso")
                else "SQLite"
            )

    except Exception as e:

        st.error(
            f"DB 상태 확인 오류: {e}"
        )


# ============================================================
# Turso 저장 용량
# ============================================================

st.markdown("### 💾 DB 저장 용량")

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
            "현재 DB 저장 크기",
            f"{size_mb:.2f} MB"
        )

        st.caption(
            f"저장 방식: {storage.get('storage_type', '')} "
            f"· 약 {size_gb:.4f} GB"
        )

    else:

        st.warning(
            storage.get(
                "error",
                "DB 저장 용량을 확인할 수 없습니다."
            )
        )

except Exception as e:

    st.warning(
        f"DB 저장 용량 확인 실패: {e}"
    )


# ============================================================
# 업체별 저장 경기 수
# ============================================================

st.markdown("### 🏢 업체별 저장 경기 수")

try:

    company_counts = database.get_company_counts()

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
            "저장된 업체별 데이터가 없습니다."
        )

except Exception as e:

    st.warning(
        f"업체별 통계를 불러올 수 없습니다: {e}"
    )


# ============================================================
# 자동수집
# ============================================================

st.markdown("---")
st.header("📥 Scoreman 경기 ID 구간 자동수집")


# ------------------------------------------------------------
# 이전 수집 상태
# ------------------------------------------------------------

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

default_start = (
    last_completed + 1
    if last_completed > 0
    else 2005000
)

# ------------------------------------------------------------
# 실행 중이면 현재 작업의 시작값을 우선
# ------------------------------------------------------------

job_before = collector.get_job_status()

if job_before.get("running"):

    default_start = int(
        job_before.get(
            "start_id",
            default_start
        )
        or default_start
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
        f"다음 자동 시작 ID: "
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
            "수집할 업체 선택",
            options=companies,
            key="selected_companies"
        )

        if not selected_companies:

            st.warning(
                "업체를 1개 이상 선택하세요."
            )

    else:

        st.warning(
            "아직 저장된 업체 목록이 없습니다. "
            "전체 업체 자동수집을 먼저 실행하세요."
        )

else:

    st.caption(
        "Scoreman에서 확인되는 전체 업체의 "
        "최종배당을 자동 저장합니다."
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
# 수집 버튼
# ============================================================

b1, b2 = st.columns(2)

with b1:

    start_button = st.button(
        "▶️ 수집시작",
        use_container_width=True,
        type="primary"
    )

with b2:

    stop_button = st.button(
        "🛑 수집중지",
        use_container_width=True
    )


# ============================================================
# 시작
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

        started = (
            collector.start_background_collection(
                int(start_id),
                int(end_id),
                selected_companies,
                float(delay),
                resume=True
            )
        )

        if started:

            st.success(
                "수집을 시작했습니다. "
                "이제 다른 앱을 사용하거나 휴대폰 화면이 "
                "꺼져도 Streamlit 서버의 백그라운드 작업은 "
                "계속 진행됩니다."
            )

            time.sleep(0.5)
            st.rerun()

        else:

            st.warning(
                "이미 수집 중이거나 수집할 ID가 없습니다."
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
# 현재 작업 상태
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

    if total > 0:

        progress = (
            current / total
        )

        progress = max(
            0.0,
            min(
                progress,
                1.0
            )
        )

        st.progress(
            progress
        )

        st.write(
            f"진행: {current:,} / {total:,} "
            f"({progress * 100:.1f}%)"
        )

    current_start = job.get(
        "start_id",
        0
    )

    current_end = job.get(
        "end_id",
        0
    )

    current_id = (
        int(current_start or 0)
        + current
        - 1
        if current > 0
        else int(current_start or 0)
    )

    st.write(
        f"현재 ID: {current_id:,} / "
        f"{int(current_end or 0):,}"
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

else:

    if job.get("finished"):

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
                "수집이 중지되었습니다."
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
            "현재 표시할 수집 로그가 없습니다."
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
st.header("🎯 수동 최종배당 분석")

st.caption(
    "업체를 선택하고 최종 승·무·패 배당을 입력하면 "
    "해당 배당의 예상확률과 과거 실제 결과를 비교합니다."
)


# ------------------------------------------------------------
# 업체
# ------------------------------------------------------------

companies = get_companies()

if companies:

    manual_company = st.selectbox(
        "업체 선택",
        companies,
        key="manual_company"
    )

else:

    manual_company = st.text_input(
        "업체명 직접 입력",
        value="Bet365",
        key="manual_company_text"
    )


# ------------------------------------------------------------
# 배당 입력
# ------------------------------------------------------------

o1, o2, o3 = st.columns(3)

with o1:

    manual_home = st.number_input(
        "최종 승 배당",
        min_value=1.01,
        value=1.83,
        step=0.01,
        format="%.2f",
        key="manual_home"
    )

with o2:

    manual_draw = st.number_input(
        "최종 무 배당",
        min_value=1.01,
        value=3.50,
        step=0.01,
        format="%.2f",
        key="manual_draw"
    )

with o3:

    manual_away = st.number_input(
        "최종 패 배당",
        min_value=1.01,
        value=4.20,
        step=0.01,
        format="%.2f",
        key="manual_away"
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

st.markdown("### 🎙️ 음성 기능")

st.caption(
    "휴대폰에서 마이크 버튼을 눌러 음성을 녹음할 수 있으며, "
    "녹음한 음성은 바로 재생할 수 있습니다."
)

try:

    audio_value = st.audio_input(
        "🎙️ 마이크로 녹음",
        key="manual_audio"
    )

    if audio_value:

        st.audio(
            audio_value
        )

        st.success(
            "음성 녹음 완료 · 재생 버튼으로 확인할 수 있습니다."
        )

except Exception:

    st.info(
        "현재 Streamlit 버전에서는 "
        "마이크 입력 기능을 사용할 수 없습니다."
    )


# ============================================================
# 분석 버튼
# ============================================================

analyze_button = st.button(
    "🔎 이 배당 과거결과 분석",
    use_container_width=True,
    type="primary"
)


# ============================================================
# 분석
# ============================================================

if analyze_button:

    if not manual_company:

        st.error(
            "업체명을 입력하세요."
        )

    else:

        # ----------------------------------------------------
        # 예상확률
        # ----------------------------------------------------

        hp, dp, ap = normalize_probabilities(
            manual_home,
            manual_draw,
            manual_away
        )

        st.markdown("### 📊 배당 기준 예상확률")

        p1, p2, p3 = st.columns(3)

        with p1:

            st.metric(
                "승 예상확률",
                f"{hp:.2f}%"
            )

        with p2:

            st.metric(
                "무 예상확률",
                f"{dp:.2f}%"
            )

        with p3:

            st.metric(
                "패 예상확률",
                f"{ap:.2f}%"
            )

        # ----------------------------------------------------
        # 과거 동일배당 검색
        # ----------------------------------------------------

        try:

            historical = (
                database.search_same_odds(
                    manual_company,
                    manual_home,
                    manual_draw,
                    manual_away,
                    tolerance=0.0001
                )
            )

        except Exception as e:

            historical = []

            st.error(
                f"과거배당 검색 오류: {e}"
            )


        # ----------------------------------------------------
        # 과거 결과 통계
        # ----------------------------------------------------

        total_history = len(
            historical
        )

        win_count = sum(
            1
            for row in historical
            if row.get("result") == "승"
        )

        draw_count = sum(
            1
            for row in historical
            if row.get("result") == "무"
        )

        loss_count = sum(
            1
            for row in historical
            if row.get("result") == "패"
        )

        if total_history > 0:

            actual_win = (
                win_count
                / total_history
                * 100
            )

            actual_draw = (
                draw_count
                / total_history
                * 100
            )

            actual_loss = (
                loss_count
                / total_history
                * 100
            )

        else:

            actual_win = 0
            actual_draw = 0
            actual_loss = 0


        # ----------------------------------------------------
        # 부족확률
        #
        # 실제 결과확률 - 배당 예상확률
        # ----------------------------------------------------

        shortage_win = (
            actual_win - hp
        )

        shortage_draw = (
            actual_draw - dp
        )

        shortage_loss = (
            actual_loss - ap
        )


        st.markdown(
            "### 📈 동일배당 과거 실제 결과"
        )

        st.write(
            f"검색 업체: **{manual_company}**"
        )

        st.write(
            f"완전 동일배당 경기: "
            f"**{total_history:,}경기**"
        )


        r1, r2, r3 = st.columns(3)

        with r1:

            st.metric(
                "승",
                f"{win_count:,}경기 "
                f"({actual_win:.2f}%)"
            )

        with r2:

            st.metric(
                "무",
                f"{draw_count:,}경기 "
                f"({actual_draw:.2f}%)"
            )

        with r3:

            st.metric(
                "패",
                f"{loss_count:,}경기 "
                f"({actual_loss:.2f}%)"
            )


        # ----------------------------------------------------
        # 확률 대비 부족/초과
        # ----------------------------------------------------

        st.markdown(
            "### ⚖️ 배당 예상확률 대비 실제 결과"
        )

        table = [

            {
                "결과": "승",
                "배당 예상확률": f"{hp:.2f}%",
                "실제 결과확률": f"{actual_win:.2f}%",
                "부족확률": f"{shortage_win:+.2f}%p"
            },

            {
                "결과": "무",
                "배당 예상확률": f"{dp:.2f}%",
                "실제 결과확률": f"{actual_draw:.2f}%",
                "부족확률": f"{shortage_draw:+.2f}%p"
            },

            {
                "결과": "패",
                "배당 예상확률": f"{ap:.2f}%",
                "실제 결과확률": f"{actual_loss:.2f}%",
                "부족확률": f"{shortage_loss:+.2f}%p"
            }

        ]

        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True
        )


        # ----------------------------------------------------
        # 결과 해석
        # ----------------------------------------------------

        if total_history > 0:

            differences = {
                "승": shortage_win,
                "무": shortage_draw,
                "패": shortage_loss
            }

            best_result = max(
                differences,
                key=differences.get
            )

            best_value = differences[
                best_result
            ]

            if best_value > 0:

                st.success(
                    f"📌 과거 데이터 기준으로 "
                    f"**{best_result}** 결과가 "
                    f"배당 예상확률보다 "
                    f"{best_value:.2f}%p 높았습니다."
                )

            else:

                st.info(
                    "과거 실제 결과확률이 "
                    "배당 예상확률보다 높은 결과가 "
                    "확인되지 않았습니다."
                )

        else:

            st.warning(
                "현재 DB에 완전히 동일한 배당의 "
                "과거 경기가 없습니다."
            )


        # ----------------------------------------------------
        # 과거 경기 목록
        # ----------------------------------------------------

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

                    "승배당":
                        f"{safe_float(row.get('home_odds')):.2f}",

                    "무배당":
                        f"{safe_float(row.get('draw_odds')):.2f}",

                    "패배당":
                        f"{safe_float(row.get('away_odds')):.2f}"

                })

            st.dataframe(
                history_rows,
                use_container_width=True,
                hide_index=True
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
    use_container_width=True
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
                    f"날짜: {match.get('match_date', '')}"
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
    use_container_width=True
):

    st.rerun()


# ============================================================
# 안내
# ============================================================

st.caption(
    "⚠️ 확률은 배당의 역수로 계산한 시장확률을 정규화한 값이며, "
    "과거 동일배당 결과는 참고용 통계입니다."
)

st.caption(
    "📱 수집 작업은 브라우저가 아니라 Streamlit 서버의 "
    "백그라운드 스레드에서 실행되므로 휴대폰 화면을 끄거나 "
    "다른 앱을 사용하는 동안에도 서버가 계속 실행되는 한 "
    "수집은 진행됩니다."
            )
