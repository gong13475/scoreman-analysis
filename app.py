# ============================================================
# app.py
# ⚽ Scoreman 전종목 해외배당 분석 최종본
# ============================================================

import html
import time

import streamlit as st

import database
import collector
import analysis


# ============================================================
# 페이지
# ============================================================

st.set_page_config(

    page_title=
        "전종목 해외배당 분석",

    page_icon=
        "⚽",

    layout=
        "wide",

    initial_sidebar_state=
        "collapsed"

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

    st.error(
        f"DB 초기화 오류: {e}"
    )

    st.stop()


# ============================================================
# 공통
# ============================================================

def safe_float(
    value,
    default=0.0
):

    try:

        return float(value)

    except Exception:

        return default


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
# 확률
# ============================================================

def normalize_probabilities(

    home,
    draw,
    away

):

    try:

        h = 1 / float(home)

        d = 1 / float(draw)

        a = 1 / float(away)

        total = h + d + a

        if total <= 0:

            return 0, 0, 0

        return (

            h / total * 100,

            d / total * 100,

            a / total * 100

        )

    except Exception:

        return 0, 0, 0


# ============================================================
# 음성
# ============================================================

def speak_text(
    text_value
):

    safe_text = html.escape(
        str(text_value)
    )

    st.components.v1.html(

        f"""
        <button
            onclick="speakResult()"
            style="
                background:#1565c0;
                color:white;
                border:0;
                border-radius:10px;
                padding:12px;
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

                alert(
                    "이 브라우저는 음성 재생을 지원하지 않습니다."
                );

                return;
            }}

            window.speechSynthesis.cancel();

            const utterance =
                new SpeechSynthesisUtterance(
                    "{safe_text}"
                );

            utterance.lang = "ko-KR";

            utterance.rate = 0.95;

            utterance.pitch = 1.0;

            window.speechSynthesis.speak(
                utterance
            );

        }}

        </script>
        """,

        height=60

    )


# ============================================================
# 제목
# ============================================================

st.title(
    "⚽ 전종목 해외배당 분석"
)

st.caption(
    "Scoreman 자동수집 · 해외업체 최종배당 · "
    "실제결과 · 완전 동일배당 분석 · Turso 영구저장"
)


# ============================================================
# DB 상태
# ============================================================

status = get_status()

c1, c2, c3, c4 = st.columns(4)

with c1:

    st.metric(
        "저장 경기",
        f"{status['matches']:,}"
    )

with c2:

    st.metric(
        "저장 최종배당",
        f"{status['odds']:,}"
    )

with c3:

    st.metric(
        "실제 저장 업체",
        f"{status['bookmakers']:,}"
    )

with c4:

    info = database.get_database_info()

    st.metric(

        "DB",

        "Turso"
        if info.get(
            "using_turso"
        )
        else "SQLite"

    )


# ============================================================
# DB 상세
# ============================================================

with st.expander(
    "🗄️ 데이터베이스 상태",
    expanded=False
):

    info = database.get_database_info()

    if info.get(
        "using_turso"
    ):

        st.success(
            "🟢 Turso DB 연결 정상"
        )

    else:

        st.warning(
            "🟡 SQLite fallback 모드"
        )

    a, b, c, d = st.columns(4)

    with a:

        st.write(
            "Turso URL:",
            "✅"
            if info.get(
                "database_url_configured"
            )
            else "❌"
        )

    with b:

        st.write(
            "Turso Token:",
            "✅"
            if info.get(
                "auth_token_configured"
            )
            else "❌"
        )

    with c:

        st.write(
            "libSQL:",
            "✅"
            if info.get(
                "libsql_available"
            )
            else "❌"
        )

    with d:

        st.write(
            "현재 DB:",
            "Turso"
            if info.get(
                "using_turso"
            )
            else "SQLite"
        )


# ============================================================
# 저장용량
# ============================================================

with st.expander(
    "💾 DB 저장 용량",
    expanded=False
):

    storage = (
        database.get_storage_usage()
    )

    if storage.get(
        "success"
    ):

        st.metric(

            "현재 DB 크기",

            f"{storage.get('size_mb', 0):.2f} MB"

        )

        st.caption(

            f"{storage.get('storage_type', '')}"
            f" · 약 "
            f"{storage.get('size_gb', 0):.4f} GB"

        )

    else:

        st.warning(
            storage.get(
                "error",
                "용량 확인 실패"
            )
        )


# ============================================================
# 업체별 통계
# ============================================================

with st.expander(
    "🏢 업체별 저장 경기 수",
    expanded=False
):

    counts = (
        database.get_company_counts()
    )

    if counts:

        rows = [

            {

                "업체":
                    name,

                "저장 경기":
                    count

            }

            for name, count
            in counts.items()

        ]

        st.dataframe(

            rows,

            use_container_width=True,

            hide_index=True

        )

    else:

        st.info(
            "저장된 업체 데이터가 없습니다."
        )


# ============================================================
# 자동수집
# ============================================================

st.markdown("---")

st.header(
    "📥 Scoreman 경기 ID 구간 자동수집"
)

state = (
    database.get_collection_state()
    or {}
)

last_completed = int(

    state.get(
        "last_completed_id",
        0
    )
    or 0

)

job = collector.get_job_status()


if job.get(
    "running"
):

    default_start = int(

        job.get(
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

        value=default_start,

        step=1,

        format="%d",

        key="start_id"

    )

with c2:

    end_id = st.number_input(

        "마지막 ID",

        min_value=1,

        value=default_start,

        step=1,

        format="%d",

        key="end_id"

    )


count = (

    int(end_id)
    - int(start_id)
    + 1

)

if count < 0:

    count = 0


st.caption(
    f"검색 대상: {count:,}개"
)


if last_completed > 0:

    st.info(

        f"📌 마지막 성공 완료 ID: "
        f"{last_completed:,} "
        f"→ 다음 시작: "
        f"{last_completed + 1:,}"

    )


# ============================================================
# 업체 선택
# ============================================================

st.markdown(
    "### 🏢 수집 업체"
)

collection_mode = st.radio(

    "수집 방식",

    [

        "전체 업체 자동수집",

        "특정 업체만 수집"

    ],

    horizontal=True

)


companies = get_companies()

selected_companies = None


if (
    collection_mode
    == "특정 업체만 수집"
):

    if companies:

        selected_companies = st.multiselect(

            "업체 선택",

            companies

        )

    else:

        st.warning(
            "현재 저장된 업체가 없습니다. "
            "먼저 전체 업체를 1경기 이상 수집하세요."
        )

else:

    st.caption(
        "Scoreman에서 확인되는 모든 업체의 "
        "최종배당을 자동수집합니다."
    )


delay = st.number_input(

    "요청 간격(초)",

    min_value=0.10,

    max_value=10.0,

    value=0.50,

    step=0.10,

    format="%.2f"

)


# ============================================================
# 이어받기
# ============================================================

resume_end = int(

    state.get(
        "end_id",
        0
    )
    or 0

)

if (

    last_completed > 0

    and resume_end > last_completed

    and not collector.is_running()

):

    st.markdown(
        "### 🔄 중지 지점 이어받기"
    )

    st.info(

        f"{last_completed + 1:,}"
        f" → "
        f"{resume_end:,}"

    )

    resume_button = st.button(

        "▶️ 중지 지점부터 이어받기",

        use_container_width=True,

        type="primary"

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

        type="primary"

    )

with b2:

    stop_button = st.button(

        "🛑 수집중지",

        use_container_width=True

    )


# ============================================================
# 이어받기
# ============================================================

if resume_button:

    started = (

        collector.start_background_collection(

            last_completed + 1,

            resume_end,

            selected_companies,

            delay,

            resume=True

        )

    )

    if started:

        st.success(
            "이어받기를 시작했습니다."
        )

        time.sleep(0.3)

        st.rerun()

    else:

        st.warning(
            "이미 수집 중입니다."
        )


# ============================================================
# 새 수집
# ============================================================

if start_button:

    if int(end_id) < int(start_id):

        st.error(
            "마지막 ID가 시작 ID보다 작습니다."
        )

    elif (

        collection_mode
        == "특정 업체만 수집"

        and not selected_companies

    ):

        st.error(
            "업체를 선택하세요."
        )

    else:

        started = (

            collector.start_background_collection(

                int(start_id),

                int(end_id),

                selected_companies,

                delay,

                resume=True

            )

        )

        if started:

            st.success(
                "수집을 시작했습니다."
            )

            time.sleep(0.3)

            st.rerun()

        else:

            st.warning(
                "이미 수집 중입니다."
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
            "현재 수집 중인 작업이 없습니다."
        )


# ============================================================
# 수집 상태
# ============================================================

job = collector.get_job_status()


if job.get(
    "running"
):

    st.markdown("---")

    st.subheader(
        "🔄 현재 수집 상태"
    )

    total = int(

        job.get(
            "total",
            0
        )
        or 0

    )

    current = int(

        job.get(
            "current",
            0
        )
        or 0

    )

    progress = (

        current / total

        if total > 0

        else 0

    )

    st.progress(

        min(
            max(
                progress,
                0
            ),
            1
        )

    )

    st.write(

        f"진행: "
        f"{current:,} / "
        f"{total:,} "
        f"({progress * 100:.1f}%)"

    )

    current_id = (

        int(
            job.get(
                "start_id",
                0
            )
            or 0
        )

        + current
        - 1

    )

    st.write(

        f"현재 ID: "
        f"{current_id:,} / "
        f"{int(job.get('end_id', 0) or 0):,}"

    )

    a, b, c, d, e = st.columns(5)

    with a:

        st.metric(
            "신규",
            job.get(
                "success",
                0
            )
        )

    with b:

        st.metric(
            "기존",
            job.get(
                "exists",
                0
            )
        )

    with c:

        st.metric(
            "실패",
            job.get(
                "failed",
                0
            )
        )

    with d:

        st.metric(
            "배당없음",
            job.get(
                "no_odds",
                0
            )
        )

    with e:

        st.metric(
            "최종배당",
            job.get(
                "odds",
                0
            )
        )


elif job.get(
    "finished"
):

    result = (
        job.get(
            "result",
            {}
        )
        or {}
    )

    st.markdown("---")

    st.subheader(
        "✅ 최근 수집 결과"
    )

    a, b, c, d, e = st.columns(5)

    with a:

        st.metric(
            "신규",
            result.get(
                "success",
                0
            )
        )

    with b:

        st.metric(
            "기존",
            result.get(
                "exists",
                0
            )
        )

    with c:

        st.metric(
            "실패",
            result.get(
                "failed",
                0
            )
        )

    with d:

        st.metric(
            "배당없음",
            result.get(
                "no_odds",
                0
            )
        )

    with e:

        st.metric(
            "최종배당",
            result.get(
                "odds",
                0
            )
        )

    if result.get(
        "stopped"
    ):

        st.warning(
            "🛑 수집이 중지되었습니다."
        )

    else:

        st.success(
            "수집 작업이 완료되었습니다."
        )


# ============================================================
# 로그
# ============================================================

with st.expander(
    "📋 수집 로그 보기",
    expanded=False
):

    log = job.get(
        "log",
        ""
    )

    if log:

        st.code(
            log,
            language="text"
        )

    else:

        logs = (
            database.get_collection_logs()
        )

        if logs:

            st.code(

                "\n".join(

                    x.get(
                        "message",
                        ""
                    )

                    for x in logs

                ),

                language="text"

            )

        else:

            st.info(
                "로그가 없습니다."
            )


# ============================================================
# 자동 새로고침
# ============================================================

if job.get(
    "running"
):

    time.sleep(1.5)

    st.rerun()


# ============================================================
# 수동 배당 분석
# ============================================================

st.markdown("---")

st.header(
    "🎯 수동 최종배당 입력 / 분석"
)

st.caption(
    "회사와 승·무·패 배당을 입력하면 "
    "완전히 동일한 배당의 과거 결과만 검색합니다."
)


# ============================================================
# 회사 선택
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

        "🏢 회사명",

        "Bet365",

        key="manual_company_text"

    )


# ============================================================
# 완전 동일배당 안내
# ============================================================

st.info(
    "🔒 현재 분석은 오차 없이 완전 동일배당만 검색합니다. "
    "예: 1.83 / 3.50 / 4.20 입력 → "
    "DB의 1.83 / 3.50 / 4.20만 검색합니다."
)


# ============================================================
# 기간
# ============================================================

period = st.radio(

    "분석 기간",

    [

        "전체 기간",

        "최근 5년"

    ],

    horizontal=True,

    key="analysis_period"

)


recent_years = (

    5

    if period == "최근 5년"

    else None

)


# ============================================================
# 배당
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
# 예상확률
# ============================================================

hp, dp, ap = normalize_probabilities(

    manual_home,

    manual_draw,

    manual_away

)


st.markdown(
    "### 📊 배당 예상확률"
)

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


# ============================================================
# 음성
# ============================================================

st.markdown(
    "### 🎙️ 음성 녹음"
)

try:

    audio = st.audio_input(
        "🎙️ 말하기 / 녹음"
    )

    if audio:

        st.success(
            "녹음 완료"
        )

        st.audio(
            audio
        )

except Exception:

    st.info(
        "현재 Streamlit에서 "
        "마이크 입력을 지원하지 않습니다."
    )


# ============================================================
# 분석 버튼
# ============================================================

analyze_button = st.button(

    "🔎 완전 동일배당 과거결과 분석",

    use_container_width=True,

    type="primary"

)


# ============================================================
# 분석
# ============================================================

if analyze_button:

    result = analysis.analyze_manual_odds(

        manual_company,

        manual_home,

        manual_draw,

        manual_away,

        tolerance=0,

        recent_years=recent_years

    )

    if not result.get(
        "success"
    ):

        st.error(

            result.get(
                "error",
                "분석 실패"
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
                "actual_home"
            )

        )

        actual_draw = safe_float(

            result.get(
                "actual_draw"
            )

        )

        actual_loss = safe_float(

            result.get(
                "actual_away"
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
            0,
            -win_gap
        )

        draw_shortage = max(
            0,
            -draw_gap
        )

        loss_shortage = max(
            0,
            -loss_gap
        )


        # ----------------------------------------------------
        # 실제 결과
        # ----------------------------------------------------

        st.markdown(
            "### 📈 과거 실제 결과"
        )

        st.write(
            f"업체: **{manual_company}**"
        )

        st.write(
            f"분석 기간: **{period}**"
        )

        st.write(
            f"검색 조건: "
            f"**{manual_home:.2f} / "
            f"{manual_draw:.2f} / "
            f"{manual_away:.2f}**"
        )

        st.write(
            f"완전 동일배당 표본: "
            f"**{total:,}경기**"
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


        # ----------------------------------------------------
        # 비교표
        # ----------------------------------------------------

        st.markdown(
            "### ⚖️ 배당 대비 실제확률"
        )

        table = [

            {

                "결과":
                    "승",

                "배당":
                    f"{manual_home:.2f}",

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

                "결과":
                    "무",

                "배당":
                    f"{manual_draw:.2f}",

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

                "결과":
                    "패",

                "배당":
                    f"{manual_away:.2f}",

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


        # ----------------------------------------------------
        # 판단
        # ----------------------------------------------------

        gaps = {

            "승":
                win_gap,

            "무":
                draw_gap,

            "패":
                loss_gap

        }

        best_result = max(

            gaps,

            key=gaps.get

        )

        best_gap = gaps[
            best_result
        ]


        shortage = {

            "승":
                win_shortage,

            "무":
                draw_shortage,

            "패":
                loss_shortage

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

                    f"📌 배당 예상확률 대비 "
                    f"실제확률이 가장 높은 결과: "
                    f"**{best_result} "
                    f"({best_gap:+.2f}%p)**"

                )

            else:

                st.info(

                    "실제확률이 배당 예상확률보다 "
                    "높은 결과가 없습니다."

                )

            if shortage_value > 0:

                st.warning(

                    f"⚠️ 부족확률 최대: "
                    f"**{shortage_result} "
                    f"({shortage_value:.2f}%p)**"

                )


        # ----------------------------------------------------
        # 음성
        # ----------------------------------------------------

        voice = (

            f"{manual_company} 분석 결과. "

            f"표본 {total}경기. "

            f"승 실제확률 "
            f"{actual_win:.2f}퍼센트. "

            f"무 실제확률 "
            f"{actual_draw:.2f}퍼센트. "

            f"패 실제확률 "
            f"{actual_loss:.2f}퍼센트. "

            f"배당 대비 실제확률이 가장 높은 결과는 "
            f"{best_result}입니다."

        )

        st.markdown(
            "### 🔊 분석 결과 듣기"
        )

        speak_text(
            voice
        )


        # ----------------------------------------------------
        # 과거 경기
        # ----------------------------------------------------

        historical = result.get(
            "rows",
            []
        )

        if historical:

            st.markdown(
                "### 📋 완전 동일배당 과거 경기"
            )

            history = []

            for row in historical:

                history.append({

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
                        (
                            f"{row.get('home_score', '')}"
                            f" - "
                            f"{row.get('away_score', '')}"
                        ),

                    "결과":
                        row.get(
                            "result",
                            ""
                        ),

                    "승":
                        (
                            f"{safe_float(row.get('home_odds')):.2f}"
                        ),

                    "무":
                        (
                            f"{safe_float(row.get('draw_odds')):.2f}"
                        ),

                    "패":
                        (
                            f"{safe_float(row.get('away_odds')):.2f}"
                        )

                })

            st.dataframe(

                history,

                use_container_width=True,

                hide_index=True

            )

        else:

            st.warning(

                "조건에 맞는 완전 동일배당 "
                "과거 경기가 없습니다."

            )


# ============================================================
# 경기 ID 조회
# ============================================================

st.markdown("---")

st.header(
    "📚 저장 경기 / 배당 조회"
)

lookup_id = st.text_input(
    "경기 ID 입력"
)


if st.button(

    "경기 조회",

    use_container_width=True

):

    if lookup_id.strip():

        match = database.get_match(
            lookup_id.strip()
        )

        if not match:

            st.warning(
                "해당 경기 ID가 없습니다."
            )

        else:

            st.subheader(

                f"{match.get('home_team', '')}"
                f" vs "
                f"{match.get('away_team', '')}"

            )

            st.write(

                f"날짜: "
                f"{match.get('match_date', '')}"

            )

            st.write(

                f"스코어: "
                f"{match.get('home_score', '')}"
                f" - "
                f"{match.get('away_score', '')}"

            )

            st.write(

                f"결과: **"
                f"{match.get('result', '')}"
                f"**"

            )

            odds = (
                database.get_odds_by_match(
                    lookup_id.strip()
                )
            )

            if odds:

                rows = []

                for row in odds:

                    rows.append({

                        "업체":
                            row.get(
                                "company_name",
                                ""
                            ),

                        "승":
                            (
                                f"{safe_float(row.get('final_home')):.2f}"
                            ),

                        "무":
                            (
                                f"{safe_float(row.get('final_draw')):.2f}"
                            ),

                        "패":
                            (
                                f"{safe_float(row.get('final_away')):.2f}"
                            )

                    })

                st.dataframe(

                    rows,

                    use_container_width=True,

                    hide_index=True

                )

            else:

                st.info(
                    "저장된 최종배당이 없습니다."
                )


# ============================================================
# 전체 경기
# ============================================================

with st.expander(

    "📊 전체 저장 경기 보기",

    expanded=False

):

    matches = (
        database.get_all_matches()
    )

    if matches:

        rows = []

        for row in matches[:500]:

            rows.append({

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
                    (
                        f"{row.get('home_score', '')}"
                        f" - "
                        f"{row.get('away_score', '')}"
                    ),

                "결과":
                    row.get(
                        "result",
                        ""
                    )

            })

        st.dataframe(

            rows,

            use_container_width=True,

            hide_index=True

        )

        if len(matches) > 500:

            st.caption(
                "최근 500경기만 표시합니다."
            )

    else:

        st.info(
            "저장된 경기가 없습니다."
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

    "⚠️ 배당 예상확률 = "
    "1/배당을 승·무·패에 대해 정규화한 값입니다."

)

st.caption(

    "🔒 동일배당 분석은 "
    "승·무·패 배당 3개가 모두 완전히 같은 경기만 검색합니다."

)

st.caption(

    "⚠️ 과거 동일배당 통계는 참고용이며 "
    "미래 결과를 보장하지 않습니다."

)

st.caption(

    "📱 수집은 Streamlit 서버의 "
    "백그라운드 작업으로 실행됩니다."

)
