import time
import streamlit as st

import database
import collector
import analysis


# =========================================================
# 페이지 설정
# =========================================================

st.set_page_config(
    page_title="Scoreman 해외배당 분석",
    page_icon="⚽",
    layout="wide"
)


# =========================================================
# DB 초기화
# =========================================================

database.init_database()


# =========================================================
# CSS
# =========================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 32px;
        font-weight: 800;
        margin-bottom: 4px;
    }

    .sub-title {
        color: #777;
        margin-bottom: 20px;
    }

    .section-title {
        font-size: 22px;
        font-weight: 800;
        margin-top: 20px;
        margin-bottom: 12px;
    }

    .match-box {
        padding: 20px;
        border-radius: 15px;
        background: #f7f7f7;
        margin-top: 10px;
        margin-bottom: 15px;
    }

    .team {
        text-align: center;
        font-size: 23px;
        font-weight: 800;
    }

    .big-percent {
        font-size: 26px;
        font-weight: 800;
    }

    .status-box {
        padding: 15px;
        border-radius: 12px;
        background: #f5f7fa;
        margin: 10px 0;
    }

    div.stButton > button {
        font-weight: 700;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# 제목
# =========================================================

st.markdown(
    '<div class="main-title">⚽ 전종목 해외배당 분석</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="sub-title">'
    'Scoreman 자동수집 · 해외업체 최종배당 · '
    '실제결과 · 확률분석 · Turso 영구저장'
    '</div>',
    unsafe_allow_html=True
)


# =========================================================
# DB
# =========================================================

status = {
    "matches": 0,
    "odds": 0,
    "bookmakers": 0
}

try:
    status = database.get_database_status() or status
except Exception as e:
    st.error(f"DB 상태 오류: {e}")


st.subheader("🗄️ DB")

turso_url = getattr(
    database,
    "TURSO_DATABASE_URL",
    ""
)

turso_token = getattr(
    database,
    "TURSO_AUTH_TOKEN",
    ""
)

if turso_url and turso_token:
    st.success("🟢 Turso 연결 정상")
else:
    st.warning("🟡 로컬 SQLite 모드")


c1, c2, c3 = st.columns(3)

c1.metric(
    "저장 경기",
    f"{int(status.get('matches', 0)):,.0f}"
)

c2.metric(
    "최종배당",
    f"{int(status.get('odds', 0)):,.0f}"
)

c3.metric(
    "업체",
    f"{int(status.get('bookmakers', 0)):,.0f}"
)


st.divider()


# =========================================================
# 업체 목록
# =========================================================

try:
    companies = analysis.get_company_list() or []
except Exception:
    companies = []


# =========================================================
# Scoreman 수집
# =========================================================

st.markdown(
    '<div class="section-title">📥 Scoreman 자동수집</div>',
    unsafe_allow_html=True
)

try:
    resume_state = database.get_collection_state() or {}
except Exception:
    resume_state = {}


last_id = resume_state.get(
    "last_completed_id",
    0
)

try:
    last_id = int(last_id or 0)
except Exception:
    last_id = 0


saved_start = resume_state.get("start_id")
saved_end = resume_state.get("end_id")

try:
    saved_start = int(saved_start)
except Exception:
    saved_start = None

try:
    saved_end = int(saved_end)
except Exception:
    saved_end = None


col1, col2 = st.columns(2)


with col1:

    default_start = (
        saved_start
        if saved_start and saved_start > 0
        else 3001118
    )

    start_id = st.number_input(
        "시작 ID",
        min_value=1,
        value=default_start,
        step=1,
        key="start_id"
    )


with col2:

    default_end = (
        saved_end
        if saved_end and saved_end >= start_id
        else 3020000
    )

    end_id = st.number_input(
        "마지막 ID",
        min_value=1,
        value=default_end,
        step=1,
        key="end_id"
    )


# =========================================================
# 업체 선택
# =========================================================

st.markdown("**업체**")

company_options = ["전체 업체"] + companies

selected_mode = st.radio(
    "업체 선택",
    company_options,
    horizontal=True,
    label_visibility="collapsed"
)

if selected_mode == "전체 업체":
    selected_companies = None
else:
    selected_companies = [selected_mode]


# =========================================================
# 요청 간격
# =========================================================

delay = st.number_input(
    "요청 간격(초)",
    min_value=0.1,
    max_value=10.0,
    value=0.5,
    step=0.1
)


# =========================================================
# 시작 / 중지
# =========================================================

b1, b2 = st.columns(2)


with b1:

    if st.button(
        "🚀 수집 시작",
        use_container_width=True
    ):

        if end_id < start_id:

            st.error(
                "마지막 ID가 시작 ID보다 작습니다."
            )

        else:

            ok = collector.start_background_collection(
                int(start_id),
                int(end_id),
                selected_companies,
                float(delay)
            )

            if ok:
                st.success(
                    "🟢 백그라운드 수집을 시작했습니다."
                )
            else:
                st.warning(
                    "이미 수집 작업이 실행 중입니다."
                )


with b2:

    if st.button(
        "🛑 수집 중지",
        use_container_width=True
    ):

        ok = collector.stop_background_collection()

        if ok:
            st.warning(
                "🛑 수집 중지 요청을 보냈습니다."
            )
        else:
            st.info(
                "현재 실행 중인 작업이 없습니다."
            )


# =========================================================
# 작업 상태
# =========================================================

try:

    job = collector.get_job_status()

except Exception:

    job = {
        "running": False,
        "finished": False,
        "stopped": False,
        "current": 0,
        "total": 0,
        "success": 0,
        "exists": 0,
        "failed": 0,
        "odds": 0,
        "last_completed_id": None,
        "log": "",
        "result": None,
        "error": ""
    }


if job.get("running"):

    st.markdown(
        '<div class="section-title">🟢 현재 수집 중</div>',
        unsafe_allow_html=True
    )

    total = int(
        job.get("total", 0) or 0
    )

    current = int(
        job.get("current", 0) or 0
    )

    if total > 0:
        progress = current / total
    else:
        progress = 0

    progress = min(
        max(progress, 0),
        1
    )

    st.progress(progress)

    p1, p2, p3, p4 = st.columns(4)

    p1.metric(
        "현재",
        f"{current:,} / {total:,}"
    )

    p2.metric(
        "진행률",
        f"{progress * 100:.0f}%"
    )

    p3.metric(
        "신규",
        f"{int(job.get('success', 0) or 0):,}"
    )

    p4.metric(
        "최종배당",
        f"{int(job.get('odds', 0) or 0):,}"
    )

    current_last = job.get(
        "last_completed_id"
    )

    if current_last:

        st.info(
            f"📌 마지막 완료: {int(current_last):,}"
        )

    time.sleep(1)

    st.rerun()


elif job.get("finished"):

    if job.get("stopped"):

        st.warning(
            "🛑 수집 작업이 중지되었습니다."
        )

    else:

        st.success(
            "✅ 수집 작업이 완료되었습니다."
        )

    result = job.get("result") or {}

    if result:

        a, b, c, d = st.columns(4)

        a.metric(
            "전체",
            f"{int(result.get('total', 0)):,}"
        )

        b.metric(
            "신규",
            f"{int(result.get('success', 0)):,}"
        )

        c.metric(
            "실패/배당없음",
            f"{int(result.get('failed', 0)):,}"
        )

        d.metric(
            "최종배당",
            f"{int(result.get('odds', 0)):,}"
        )

    finished_last = job.get(
        "last_completed_id"
    )

    if finished_last:

        st.info(
            f"📌 마지막 완료: {int(finished_last):,}"
        )


# =========================================================
# 음성 명령
# =========================================================

st.divider()

st.subheader("🎙️ 음성 명령")

st.caption(
    "마이크 버튼을 누르고 "
    "예: '베트365 승 1.8 무 3.4 패 4.2'처럼 말할 수 있습니다."
)

voice_html = """
<script>
function startVoice() {

    const SpeechRecognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;

    if (!SpeechRecognition) {

        alert(
            "이 브라우저는 음성 인식을 지원하지 않습니다. "
            "Chrome 또는 Edge를 사용하세요."
        );

        return;
    }

    const recognition =
        new SpeechRecognition();

    recognition.lang = "ko-KR";

    recognition.interimResults = false;

    recognition.maxAlternatives = 1;

    recognition.start();

    recognition.onresult = function(event) {

        const text =
            event.results[0][0].transcript;

        document.getElementById(
            "voice_result"
        ).innerText =
            "🎤 " + text;
    };

    recognition.onerror = function(event) {

        document.getElementById(
            "voice_result"
        ).innerText =
            "❌ 음성 인식 오류: " +
            event.error;
    };
}
</script>

<button
    onclick="startVoice()"
    style="
        width:100%;
        height:55px;
        border:0;
        border-radius:12px;
        background:#111827;
        color:white;
        font-size:18px;
        font-weight:700;
        cursor:pointer;
    "
>
    🎤 말하기
</button>

<div
    id="voice_result"
    style="
        margin-top:10px;
        padding:12px;
        border-radius:10px;
        background:#f3f4f6;
        min-height:20px;
    "
>
    마이크를 눌러 말씀하세요.
</div>
"""

st.components.v1.html(
    voice_html,
    height=125
)


# =========================================================
# 배당 검색
# =========================================================

st.divider()

st.markdown(
    '<div class="section-title">'
    '🔎 승무패 배당으로 경기 검색'
    '</div>',
    unsafe_allow_html=True
)


if not companies:

    st.warning(
        "DB에 저장된 업체가 아직 없습니다."
    )

else:

    selected_company = st.selectbox(
        "업체",
        companies,
        key="search_company"
    )


    h1, h2, h3 = st.columns(3)


    with h1:

        search_home = st.number_input(
            "승",
            min_value=0.01,
            value=1.80,
            step=0.01,
            format="%.2f",
            key="search_home"
        )


    with h2:

        search_draw = st.number_input(
            "무",
            min_value=0.01,
            value=3.40,
            step=0.01,
            format="%.2f",
            key="search_draw"
        )


    with h3:

        search_away = st.number_input(
            "패",
            min_value=0.01,
            value=4.20,
            step=0.01,
            format="%.2f",
            key="search_away"
        )


    tolerance = st.number_input(
        "배당 허용 오차",
        min_value=0.0001,
        max_value=1.0,
        value=0.001,
        step=0.001,
        format="%.3f",
        help="예: 0.001이면 입력 배당과 거의 동일한 값만 검색합니다."
    )


    if st.button(
        "🔎 검색",
        use_container_width=True,
        type="primary"
    ):

        with st.spinner(
            "배당 데이터를 검색하는 중..."
        ):

            result = analysis.run_search(

                [selected_company],

                {
                    selected_company: {
                        "home": search_home,
                        "draw": search_draw,
                        "away": search_away
                    }
                },

                tolerance=float(tolerance)
            )


        if not result.get("success"):

            st.error(
                result.get(
                    "message",
                    "검색 오류"
                )
            )

        else:

            results = result.get(
                "results",
                []
            )

            stats = result.get(
                "statistics"
            )


            st.success(
                f"검색 경기: {len(results):,}개"
            )


            # -------------------------------------------------
            # 실제 승무패
            # -------------------------------------------------

            if stats:

                actual = stats.get(
                    "actual",
                    {}
                )

                probability = stats.get(
                    "probability",
                    {}
                )

                shortage = stats.get(
                    "shortage",
                    {}
                )


                st.markdown(
                    "### 실제 승률"
                )

                a, b, c = st.columns(3)

                a.metric(
                    "실제 승률",
                    f"{actual.get('home', 0):.2f}%"
                )

                b.metric(
                    "실제 무승률",
                    f"{actual.get('draw', 0):.2f}%"
                )

                c.metric(
                    "실제 패율",
                    f"{actual.get('away', 0):.2f}%"
                )


                # -------------------------------------------------
                # 배당 확률
                # -------------------------------------------------

                st.markdown(
                    "### 배당 확률"
                )

                a, b, c = st.columns(3)

                a.metric(
                    "승",
                    f"{probability.get('home', 0):.2f}%"
                )

                b.metric(
                    "무",
                    f"{probability.get('draw', 0):.2f}%"
                )

                c.metric(
                    "패",
                    f"{probability.get('away', 0):.2f}%"
                )


                # -------------------------------------------------
                # 실제 - 배당
                # -------------------------------------------------

                st.markdown(
                    "### 실제 - 배당"
                )

                a, b, c = st.columns(3)

                a.metric(
                    "승",
                    f"{shortage.get('home', 0):+.2f}%"
                )

                b.metric(
                    "무",
                    f"{shortage.get('draw', 0):+.2f}%"
                )

                c.metric(
                    "패",
                    f"{shortage.get('away', 0):+.2f}%"
                )


                highest = (
                    analysis.get_highest_shortage(
                        stats
                    )
                )

                if highest:

                    st.info(
                        f"📊 실제 결과가 배당 확률보다 "
                        f"가장 많이 높은 결과: {highest}"
                    )


            # -------------------------------------------------
            # 검색 결과
            # -------------------------------------------------

            st.divider()

            st.markdown(
                "### 📋 검색 결과"
            )


            if results:

                display = []

                for row in results:

                    display.append({

                        "경기일":
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

                        "업체":
                            row.get(
                                "bookmaker",
                                ""
                            ),

                        "승":
                            row.get(
                                "home_odds"
                            ),

                        "무":
                            row.get(
                                "draw_odds"
                            ),

                        "패":
                            row.get(
                                "away_odds"
                            ),

                        "결과":
                            row.get(
                                "result",
                                ""
                            )

                    })


                st.dataframe(
                    display,
                    use_container_width=True,
                    hide_index=True,
                    height=500
                )

            else:

                st.info(
                    "조건에 맞는 경기가 없습니다."
                )


# =========================================================
# 저장된 경기
# =========================================================

st.divider()

st.subheader("📋 저장된 경기")


try:

    matches = database.get_all_matches() or []

except Exception:

    matches = []


if matches:

    st.dataframe(
        matches,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "아직 저장된 경기가 없습니다."
    )


# =========================================================
# 경기 ID 조회
# =========================================================

st.divider()

st.subheader(
    "📱 경기별 최종배당"
)


lookup_default = (
    last_id
    if last_id > 0
    else 3001118
)


lookup_id = st.number_input(
    "경기 ID",
    min_value=1,
    value=int(lookup_default),
    step=1,
    key="lookup_id"
)


if st.button(
    "🔎 경기 조회",
    use_container_width=True
):

    try:

        match = database.get_match(
            lookup_id
        )

    except Exception as e:

        match = None

        st.error(
            f"조회 오류: {e}"
        )


    if not match:

        st.error(
            "경기 정보를 찾을 수 없습니다."
        )

    else:

        st.markdown(
            f"""
            <div class="match-box">

                <div class="team">
                    {match.get("home_team", "")}

                    <br>

                    <span style="
                        font-size:15px;
                        color:#777;
                    ">
                        VS
                    </span>

                    <br>

                    {match.get("away_team", "")}
                </div>

                <div style="
                    text-align:center;
                    margin-top:15px;
                    color:#555;
                ">

                    경기 ID:
                    <b>{int(lookup_id):,}</b>

                    <br>

                    경기일:
                    <b>{match.get("match_date", "")}</b>

                    <br>

                    실제 결과:
                    <b>{match.get("result", "")}</b>

                </div>

            </div>
            """,
            unsafe_allow_html=True
        )


        try:

            odds = database.get_odds_by_match(
                lookup_id
            ) or []

        except Exception:

            odds = []


        if odds:

            display = []

            for row in odds:

                display.append({

                    "업체":
                        row.get(
                            "bookmaker",
                            ""
                        ),

                    "승":
                        row.get(
                            "home_odds"
                        ),

                    "무":
                        row.get(
                            "draw_odds"
                        ),

                    "패":
                        row.get(
                            "away_odds"
                        )

                })


            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True
            )

        else:

            st.warning(
                "저장된 최종배당이 없습니다."
            )


# =========================================================
# 새로고침
# =========================================================

st.divider()

if st.button(
    "🔄 화면 새로고침",
    use_container_width=True
):

    st.rerun()
