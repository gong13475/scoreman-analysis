import time
import streamlit as st

import database
import collector
import analysis


# =========================================================
# 페이지
# =========================================================

st.set_page_config(
    page_title="Scoreman 해외배당 분석",
    page_icon="⚽",
    layout="wide"
)


database.init_database()


# =========================================================
# CSS
# =========================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 30px;
        font-weight: 800;
    }

    .sub-title {
        color: #666;
        margin-bottom: 20px;
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
        font-size: 22px;
        font-weight: 700;
    }

    div.stButton > button {
        min-height: 48px;
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
    '<div class="main-title">'
    '⚽ 전종목 해외배당 분석'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="sub-title">'
    'Scoreman 자동수집 · 최종배당 · 실제결과 · '
    '확률분석 · Turso 영구저장'
    '</div>',
    unsafe_allow_html=True
)


# =========================================================
# DB 상태
# =========================================================

status = database.get_database_status()

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "저장 경기",
    f"{status['matches']:,}"
)

c2.metric(
    "저장 최종배당",
    f"{status['odds']:,}"
)

c3.metric(
    "실제 저장 업체",
    f"{status['bookmakers']:,}"
)

if status["turso"]:

    c4.metric(
        "DB",
        "Turso"
    )

else:

    c4.metric(
        "DB",
        "SQLite"
    )


# =========================================================
# 저장공간
# =========================================================

storage = database.get_storage_usage()

st.subheader(
    "🗄️ 데이터베이스 상태"
)

if status["turso"]:

    st.success(
        "🟢 Turso DB 연결 정상"
    )

else:

    st.warning(
        "🟡 로컬 SQLite 모드"
    )

s1, s2, s3 = st.columns(3)

s1.metric(
    "현재 저장량",
    f"{storage['size_gb']:.4f} GB"
)

s2.metric(
    "무료 기준",
    "5 GB"
)

s3.metric(
    "사용률",
    f"{storage['used_percent']:.4f}%"
)

st.caption(
    "Turso의 실제 청구 저장공간과는 차이가 있을 수 있으며 "
    "현재 저장 데이터 기준 논리 추정치입니다."
)


# =========================================================
# 수집
# =========================================================

st.subheader(
    "📥 Scoreman 경기 자동수집"
)

col1, col2 = st.columns(2)

with col1:

    start_id = st.number_input(
        "시작 경기 ID",
        min_value=1,
        value=3001118,
        step=1
    )

with col2:

    end_id = st.number_input(
        "마지막 경기 ID",
        min_value=1,
        value=3001118,
        step=1
    )


if end_id >= start_id:

    st.caption(
        f"검색 대상: "
        f"{end_id - start_id + 1:,}개"
    )


# =========================================================
# 업체
# =========================================================

companies = analysis.get_company_list()

st.subheader(
    "🏢 수집 업체"
)

mode = st.radio(
    "수집 방식",
    [
        "전체 업체 자동수집",
        "특정 업체만 수집"
    ],
    horizontal=True
)


if mode == "특정 업체만 수집":

    selected = st.multiselect(
        "업체 선택",
        companies
    )

else:

    selected = None


delay = st.number_input(
    "요청 간격(초)",
    min_value=0.1,
    max_value=10.0,
    value=0.5,
    step=0.1
)


b1, b2, b3 = st.columns(3)


with b1:

    if st.button(
        "🚀 수집 시작",
        use_container_width=True
    ):

        if end_id < start_id:

            st.error(
                "마지막 ID가 시작 ID보다 작습니다."
            )

        elif (
            mode == "특정 업체만 수집"
            and not selected
        ):

            st.error(
                "업체를 선택하세요."
            )

        else:

            ok = collector.start_background_collection(

                start_id,
                end_id,
                selected,
                delay
            )

            if ok:

                st.success(
                    "백그라운드 수집을 시작했습니다."
                )

            else:

                st.warning(
                    "이미 수집 중입니다."
                )


with b2:

    if st.button(
        "🛑 수집 중지",
        use_container_width=True
    ):

        if collector.stop_background_collection():

            st.warning(
                "중지 요청을 보냈습니다."
            )

        else:

            st.info(
                "현재 수집 중이 아닙니다."
            )


with b3:

    if st.button(
        "▶️ 중단 지점부터 계속",
        use_container_width=True
    ):

        ok = collector.resume_background_collection(

            end_id,

            selected,

            delay
        )

        if ok:

            st.success(
                "마지막 완료 ID 다음부터 재개했습니다."
            )

        else:

            st.warning(
                "재개할 작업이 없습니다."
            )


# =========================================================
# 작업 상태
# =========================================================

job = collector.get_job_status()

state = database.get_collection_state()


if job["running"]:

    st.subheader(
        "📊 현재 수집 상태"
    )

    progress = 0

    if job["total"]:

        progress = (
            job["current"]
            / job["total"]
        )

    st.progress(
        min(progress, 1.0)
    )

    a, b, c, d = st.columns(4)

    a.metric(
        "진행",
        f"{job['current']:,} / {job['total']:,}"
    )

    b.metric(
        "신규",
        f"{job['success']:,}"
    )

    c.metric(
        "실패/배당없음",
        f"{job['failed']:,}"
    )

    d.metric(
        "최종배당",
        f"{job['odds']:,}"
    )

    if job["last_completed_id"]:

        st.info(
            "📌 마지막 정상 완료 ID: "
            f"{job['last_completed_id']:,}"
        )

    show_log = st.toggle(
        "📋 로그 표시",
        value=False,
        key="running_log"
    )

    if show_log:

        st.text_area(
            "수집 로그",
            job["log"],
            height=300
        )

    time.sleep(1)

    st.rerun()


elif job["finished"]:

    st.subheader(
        "📊 마지막 수집 결과"
    )

    if job["result"]:

        r = job["result"]

        a, b, c, d = st.columns(4)

        a.metric(
            "전체",
            f"{r['total']:,}"
        )

        b.metric(
            "신규",
            f"{r['success']:,}"
        )

        c.metric(
            "실패/배당없음",
            f"{r['failed']:,}"
        )

        d.metric(
            "최종배당",
            f"{r['odds']:,}"
        )

    if job["last_completed_id"]:

        st.success(
            "📌 마지막 정상 완료 ID: "
            f"{job['last_completed_id']:,}"
        )

    if job["stopped"]:

        st.warning(
            "🛑 수집이 중지되었습니다."
        )

    if job["error"]:

        st.error(
            job["error"]
        )

    show_log = st.toggle(
        "📋 로그 표시",
        value=False,
        key="finished_log"
    )

    if show_log:

        st.text_area(
            "수집 로그",
            job["log"],
            height=250
        )


elif state:

    last_id = state.get(
        "last_completed_id"
    )

    if last_id:

        st.info(
            "📌 저장된 마지막 정상 완료 ID: "
            f"{int(last_id):,}"
        )


# =========================================================
# 저장된 경기
# =========================================================

st.subheader(
    "📋 저장된 전체 경기"
)

matches = database.get_all_matches()

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
# 경기 조회
# =========================================================

st.subheader(
    "📱 경기별 최종배당"
)

lookup_id = st.number_input(
    "경기 ID",
    min_value=1,
    value=3001118,
    step=1,
    key="lookup_id"
)


if st.button(
    "🔎 경기 조회",
    use_container_width=True
):

    match = database.get_match(
        lookup_id
    )

    if not match:

        st.error(
            "경기 정보를 찾을 수 없습니다."
        )

    else:

        st.success(
            "⚽ 경기 정보를 찾았습니다."
        )

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
                    color:#555;
                    margin-top:12px;
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

        odds = database.get_match_final_odds(
            lookup_id
        )

        if odds:

            display = []

            for row in odds:

                display.append({

                    "업체":
                        row["bookmaker"],

                    "홈":
                        row["home_odds"],

                    "무":
                        row["draw_odds"],

                    "원정":
                        row["away_odds"]
                })

            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True
            )

        else:

            st.error(
                "저장된 최종배당이 없습니다."
            )


# =========================================================
# 배당 숫자 음성 검색
# =========================================================

st.subheader(
    "🎤 배당 숫자 3개 음성 검색"
)

st.caption(
    "업체명이나 경기번호를 말하지 마세요. "
    "홈배당 → 무배당 → 원정배당 순서로 숫자 3개만 말하세요."
)

voice_html = """
<div style="
    padding:20px;
    border-radius:15px;
    background:#f5f7fa;
    text-align:center;
">

<button id="voiceBtn" style="
    width:100%;
    min-height:70px;
    border:none;
    border-radius:15px;
    background:#2563eb;
    color:white;
    font-size:22px;
    font-weight:800;
">
🎤 배당 말하기
</button>

<div id="voiceStatus"
     style="margin-top:15px;color:#555;">
대기 중
</div>

</div>

<script>

const btn =
document.getElementById("voiceBtn");

const status =
document.getElementById("voiceStatus");

const SpeechRecognition =
window.SpeechRecognition ||
window.webkitSpeechRecognition;

if (!SpeechRecognition) {

    status.innerText =
        "이 브라우저는 음성 인식을 지원하지 않습니다.";

} else {

    const recognition =
        new SpeechRecognition();

    recognition.lang = "ko-KR";

    recognition.continuous = false;

    recognition.interimResults = false;

    btn.onclick = function() {

        status.innerText =
            "🎤 듣는 중... 배당 3개를 말하세요.";

        recognition.start();
    };

    recognition.onresult = function(event) {

        const text =
            event.results[0][0].transcript;

        status.innerText =
            "인식: " + text;

        const numbers =
            text.match(
                /\\d+(?:\\.\\d+)?/g
            );

        if (
            numbers &&
            numbers.length >= 3
        ) {

            const value =
                numbers.slice(0, 3).join(" ");

            const input =
                window.parent.document
                .querySelector(
                    'input[aria-label="음성 배당 입력"]'
                );

            if (input) {

                const nativeInputValueSetter =
                    Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype,
                        "value"
                    ).set;

                nativeInputValueSetter.call(
                    input,
                    value
                );

                input.dispatchEvent(
                    new Event(
                        "input",
                        {bubbles:true}
                    )
                );
            }

        } else {

            status.innerText =
                "숫자 3개를 인식하지 못했습니다.";

        }
    };

    recognition.onerror = function(event) {

        status.innerText =
            "음성 인식 오류: "
            + event.error;
    };
}

</script>
"""

st.components.v1.html(
    voice_html,
    height=160
)


voice_input = st.text_input(
    "음성 배당 입력",
    placeholder="예: 2.10 3.20 3.50",
    key="voice_odds_input"
)


v1, v2 = st.columns(2)

with v1:

    voice_search = st.button(
        "🔎 이 배당 검색",
        use_container_width=True
    )

with v2:

    voice_clear = st.button(
        "🧹 입력 초기화",
        use_container_width=True
    )


if voice_clear:

    st.session_state[
        "voice_odds_input"
    ] = ""

    st.rerun()


if voice_search:

    parsed = analysis.parse_voice_odds(
        voice_input
    )

    if not parsed:

        st.error(
            "배당 숫자 3개를 입력하세요. "
            "예: 2.10 3.20 3.50"
        )

    else:

        st.session_state[
            "voice_search_result"
        ] = parsed


if (
    "voice_search_result"
    in st.session_state
):

    odds = st.session_state[
        "voice_search_result"
    ]

    st.write(
        "### 🎯 검색 배당"
    )

    x1, x2, x3 = st.columns(3)

    x1.metric(
        "홈",
        f"{odds['home']:.2f}"
    )

    x2.metric(
        "무",
        f"{odds['draw']:.2f}"
    )

    x3.metric(
        "원정",
        f"{odds['away']:.2f}"
    )

    results = analysis.search_by_odds(

        odds["home"],
        odds["draw"],
        odds["away"]
    )

    stats = analysis.calculate_statistics(
        results
    )

    if not results:

        st.warning(
            "일치하는 저장 경기가 없습니다."
        )

    else:

        st.success(
            f"{len(results):,}경기를 찾았습니다."
        )

        if stats:

            st.write(
                "### 📊 실제 결과"
            )

            a, b, c = st.columns(3)

            a.metric(
                "홈승",
                f"{stats['actual']['home']:.2f}%"
            )

            b.metric(
                "무승부",
                f"{stats['actual']['draw']:.2f}%"
            )

            c.metric(
                "원정승",
                f"{stats['actual']['away']:.2f}%"
            )

            st.write(
                "### 📈 배당 기준 확률"
            )

            a, b, c = st.columns(3)

            a.metric(
                "홈승",
                f"{stats['probability']['home']:.2f}%"
            )

            b.metric(
                "무승부",
                f"{stats['probability']['draw']:.2f}%"
            )

            c.metric(
                "원정승",
                f"{stats['probability']['away']:.2f}%"
            )

            st.write(
                "### 📉 배당 대비 실제 결과"
            )

            a, b, c = st.columns(3)

            a.metric(
                "홈승",
                f"{stats['shortage']['home']:+.2f}%"
            )

            b.metric(
                "무승부",
                f"{stats['shortage']['draw']:+.2f}%"
            )

            c.metric(
                "원정승",
                f"{stats['shortage']['away']:+.2f}%"
            )

            st.info(
                "가장 높은 실제 결과: "
                + analysis.get_highest_shortage(
                    stats
                )
            )

            voice_text = analysis.make_voice_summary(

                odds,
                results,
                stats
            )

            st.write(
                "### 🔊 분석 음성"
            )

            st.caption(
                voice_text
            )

            speak_html = f"""
            <button
                onclick="speakResult()"
                style="
                    width:100%;
                    min-height:60px;
                    border:none;
                    border-radius:15px;
                    background:#16a34a;
                    color:white;
                    font-size:20px;
                    font-weight:800;
                "
            >
            🔊 분석 결과 읽어주기
            </button>

            <script>

            function speakResult() {{

                const text =
                {voice_text!r};

                const utterance =
                new SpeechSynthesisUtterance(text);

                utterance.lang =
                "ko-KR";

                utterance.rate =
                0.95;

                speechSynthesis.cancel();

                speechSynthesis.speak(
                    utterance
                );
            }}

            </script>
            """

            st.components.v1.html(
                speak_html,
                height=80
            )

        st.write(
            "### 📋 검색 경기"
        )

        st.dataframe(
            results,
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# 일반 업체 분석
# =========================================================

st.subheader(
    "📈 업체별 배당 분석"
)

analysis_companies = st.multiselect(
    "분석 업체",
    companies,
    key="analysis_companies"
)


if analysis_companies:

    odds_input = {}

    for company in analysis_companies:

        st.markdown(
            f"**{company}**"
        )

        a, b, c = st.columns(3)

        with a:

            h = st.number_input(
                f"{company} 승",
                min_value=0.01,
                value=2.00,
                step=0.01,
                key=f"{company}_h"
            )

        with b:

            d = st.number_input(
                f"{company} 무",
                min_value=0.01,
                value=3.00,
                step=0.01,
                key=f"{company}_d"
            )

        with c:

            aw = st.number_input(
                f"{company} 패",
                min_value=0.01,
                value=3.00,
                step=0.01,
                key=f"{company}_a"
            )

        odds_input[company] = {

            "home":
                h,

            "draw":
                d,

            "away":
                aw
        }

    if st.button(
        "📊 배당 검색 및 분석",
        use_container_width=True
    ):

        result = analysis.run_search(
            analysis_companies,
            odds_input
        )

        if not result["success"]:

            st.error(
                result["message"]
            )

        else:

            stats = result["statistics"]

            st.success(
                f"검색 경기 "
                f"{len(result['results']):,}개"
            )

            if stats:

                a, b, c = st.columns(3)

                a.metric(
                    "실제 승률",
                    f"{stats['actual']['home']:.2f}%"
                )

                b.metric(
                    "실제 무승률",
                    f"{stats['actual']['draw']:.2f}%"
                )

                c.metric(
                    "실제 패율",
                    f"{stats['actual']['away']:.2f}%"
                )

                p1, p2, p3 = st.columns(3)

                p1.metric(
                    "배당 승 확률",
                    f"{stats['probability']['home']:.2f}%"
                )

                p2.metric(
                    "배당 무 확률",
                    f"{stats['probability']['draw']:.2f}%"
                )

                p3.metric(
                    "배당 패 확률",
                    f"{stats['probability']['away']:.2f}%"
                )

            if result["results"]:

                st.dataframe(
                    result["results"],
                    use_container_width=True,
                    hide_index=True
)
