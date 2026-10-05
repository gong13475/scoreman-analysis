import time
import re

import streamlit as st
import streamlit.components.v1 as components

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

st.markdown("""
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
    margin: 10px 0;
}

.team {
    text-align: center;
    font-size: 22px;
    font-weight: 700;
}

.big-button button {
    min-height: 55px;
    font-size: 18px;
}

</style>
""", unsafe_allow_html=True)


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
    '스코어맨 자동수집 · 해외업체 최종배당 · '
    '실제결과 · 확률분석 · Turso 영구저장'
    '</div>',
    unsafe_allow_html=True
)


# =========================================================
# DB
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

c4.metric(
    "DB",
    "Turso"
    if status["turso"]
    else "SQLite"
)


# =========================================================
# DB 상태
# =========================================================

st.subheader("🗄️ 데이터베이스 상태")

if status["turso"]:
    st.success(
        "🟢 Turso DB 연결 정상"
    )
else:
    st.warning(
        "🟡 로컬 SQLite 모드"
    )

    st.caption(
        "TURSO_DATABASE_URL / "
        "TURSO_AUTH_TOKEN을 확인하세요."
    )

usage = database.get_storage_usage()

if usage["success"]:
    label = (
        "논리적 추정 사용량"
        if usage.get("approximate")
        else "로컬 SQLite 사용량"
    )

    st.caption(
        f"{label}: "
        f"{usage['size_mb']:.2f} MB"
    )


# =========================================================
# 업체 저장 현황
# =========================================================

with st.expander(
    "🏢 저장 업체별 경기 수",
    expanded=False
):
    counts = database.get_company_counts()

    if counts:
        st.dataframe(
            [
                {
                    "업체": name,
                    "저장 경기 수": count
                }
                for name, count
                in counts.items()
            ],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info(
            "저장된 업체 데이터가 없습니다."
        )


# =========================================================
# 수집
# =========================================================

st.subheader(
    "📥 스코어맨 경기 자동수집"
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

st.subheader(
    "🏢 수집할 해외업체"
)

mode = st.radio(
    "수집 방식",
    [
        "전체 업체 자동수집",
        "특정 업체만 수집"
    ],
    horizontal=True
)

companies = analysis.get_company_list()

if mode == "특정 업체만 수집":
    selected = st.multiselect(
        "업체 선택",
        companies
    )
else:
    selected = None


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
# 이어받기 상태
# =========================================================

resume_state = collector.get_resume_state()

last_id = resume_state.get(
    "last_completed_id"
)

if last_id:
    st.info(
        f"📌 마지막 완료 ID: "
        f"{int(last_id):,}"
    )


# =========================================================
# 버튼
# =========================================================

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
                "업체를 하나 이상 선택하세요."
            )
        else:
            ok = collector.start_background_collection(
                start_id,
                end_id,
                selected,
                delay,
                resume=False
            )

            if ok:
                st.success(
                    "백그라운드 수집을 시작했습니다."
                )
            else:
                st.warning(
                    "이미 실행 중이거나 "
                    "범위가 잘못되었습니다."
                )

with b2:
    if st.button(
        "▶️ 마지막 번호부터 재개",
        use_container_width=True
    ):
        if mode == "특정 업체만 수집" and not selected:
            st.error(
                "업체를 하나 이상 선택하세요."
            )
        else:
            ok = collector.start_background_collection(
                start_id,
                end_id,
                selected,
                delay,
                resume=True
            )

            if ok:
                st.success(
                    "마지막 완료 번호 다음부터 "
                    "수집을 재개했습니다."
                )
            else:
                st.warning(
                    "재개할 데이터가 없거나 "
                    "이미 실행 중입니다."
                )

with b3:
    if st.button(
        "🛑 수집 중지",
        use_container_width=True
    ):
        if collector.stop_background_collection():
            st.warning(
                "수집 중지 요청을 보냈습니다."
            )
        else:
            st.info(
                "실행 중인 수집 작업이 없습니다."
            )


# =========================================================
# 작업 상태
# =========================================================

job = collector.get_job_status()

st.subheader("📊 수집 상태")

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

if job["total"]:
    progress = (
        job["current"]
        / job["total"]
    )

    st.progress(
        min(max(progress, 0), 1)
    )


if job["last_completed_id"]:
    st.success(
        f"마지막 완료 ID: "
        f"{int(job['last_completed_id']):,}"
    )


# =========================================================
# 로그 숨김
# =========================================================

if "show_log" not in st.session_state:
    st.session_state.show_log = False

if st.button(
    "📜 로그 표시"
    if not st.session_state.show_log
    else "🙈 로그 숨기기"
):
    st.session_state.show_log = (
        not st.session_state.show_log
    )
    st.rerun()

if st.session_state.show_log:
    st.text_area(
        "수집 로그",
        job["log"],
        height=300
    )


# =========================================================
# 자동 갱신
# =========================================================

if job["running"]:
    time.sleep(1)
    st.rerun()


# =========================================================
# 마지막 결과
# =========================================================

if job["finished"] and job["result"]:
    r = job["result"]

    st.subheader(
        "✅ 마지막 수집 결과"
    )

    x1, x2, x3, x4 = st.columns(4)

    x1.metric(
        "전체",
        f"{r['total']:,}"
    )

    x2.metric(
        "신규",
        f"{r['success']:,}"
    )

    x3.metric(
        "실패/배당없음",
        f"{r['failed']:,}"
    )

    x4.metric(
        "최종배당",
        f"{r['odds']:,}"
    )

    if r.get("last_completed_id"):
        st.info(
            f"마지막 완료 ID: "
            f"{int(r['last_completed_id']):,}"
        )


# =========================================================
# 저장 경기
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
                    <span style="font-size:15px;color:#777">
                    VS
                    </span>
                    <br>
                    {match.get("away_team", "")}
                </div>

                <div style="text-align:center;margin-top:12px">
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
# 배당 검색 / 분석
# =========================================================

st.subheader(
    "📈 배당 대비 실제 결과 분석"
)

analysis_companies = st.multiselect(
    "분석 업체",
    companies,
    key="analysis_companies"
)

odds_input = {}

if analysis_companies:

    st.write(
        "검색할 최종배당을 입력하세요."
    )

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
            "home": h,
            "draw": d,
            "away": aw
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
                st.write(
                    "### 실제 결과"
                )

                x1, x2, x3 = st.columns(3)

                x1.metric(
                    "승률",
                    f"{stats['actual']['home']:.2f}%"
                )

                x2.metric(
                    "무승부",
                    f"{stats['actual']['draw']:.2f}%"
                )

                x3.metric(
                    "패율",
                    f"{stats['actual']['away']:.2f}%"
                )

                st.write(
                    "### 배당 기준 내재확률"
                )

                x1, x2, x3 = st.columns(3)

                x1.metric(
                    "승",
                    f"{stats['probability']['home']:.2f}%"
                )

                x2.metric(
                    "무",
                    f"{stats['probability']['draw']:.2f}%"
                )

                x3.metric(
                    "패",
                    f"{stats['probability']['away']:.2f}%"
                )

                st.write(
                    "### 실제 결과 - 배당확률"
                )

                x1, x2, x3 = st.columns(3)

                x1.metric(
                    "승",
                    f"{stats['shortage']['home']:+.2f}%"
                )

                x2.metric(
                    "무",
                    f"{stats['shortage']['draw']:+.2f}%"
                )

                x3.metric(
                    "패",
                    f"{stats['shortage']['away']:+.2f}%"
                )

                st.info(
                    "가장 높은 실제 결과 차이: "
                    + analysis.get_highest_shortage(
                        stats
                    )
                )

            if result["results"]:
                st.dataframe(
                    result["results"],
                    use_container_width=True,
                    hide_index=True
                )


# =========================================================
# 음성 배당 검색
# =========================================================

st.subheader(
    "🎙️ 음성으로 배당 검색"
)

st.write(
    "업체명이나 경기명을 말하지 말고 "
    "승·무·패 배당 숫자 3개만 말하세요."
)

st.code(
    "예: 2.1 3.2 3.5",
    language="text"
)

voice_placeholder = st.empty()


# =========================================================
# Web Speech API
# =========================================================

components.html(
    """
    <script>
    const SpeechRecognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        document.body.innerHTML =
            "<div style='color:red;font-size:16px'>"
            "이 브라우저는 음성인식을 지원하지 않습니다."
            "</div>";
    } else {

        const button =
            document.createElement("button");

        button.innerText =
            "🎙️ 배당 숫자 말하기";

        button.style.width = "100%";
        button.style.height = "55px";
        button.style.fontSize = "18px";
        button.style.borderRadius = "10px";
        button.style.border = "0";
        button.style.background = "#ff4b4b";
        button.style.color = "white";

        document.body.appendChild(button);

        const recognition =
            new SpeechRecognition();

        recognition.lang = "ko-KR";
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onstart = function() {
            button.innerText =
                "🎙️ 듣는 중... 2.1 3.2 3.5";
        };

        recognition.onend = function() {
            button.innerText =
                "🎙️ 배당 숫자 말하기";
        };

        recognition.onerror = function() {
            button.innerText =
                "❌ 인식 실패 - 다시 말하기";
        };

        recognition.onresult = function(event) {

            const text =
                event.results[0][0].transcript;

            const numbers =
                text.match(
                    /\\d+(?:[.,]\\d+)?/g
                );

            if (!numbers || numbers.length < 3) {
                alert(
                    "승 무 패 배당 3개를 말해주세요."
                );
                return;
            }

            const result =
                numbers.slice(0, 3)
                .join(" ");

            document.body.setAttribute(
                "data-odds",
                result
            );

            alert(
                "인식된 배당: " + result +
                "\\n\\n아래 입력창에 같은 숫자를 입력해 검색하세요."
            );
        };

        button.onclick = function() {
            recognition.start();
        };
    }
    </script>
    """,
    height=70
)

st.caption(
    "※ 브라우저의 음성인식 기능을 사용합니다. "
    "인식 결과는 승 / 무 / 패 순서입니다."
)

voice_h = st.number_input(
    "음성 검색 승 배당",
    min_value=0.01,
    value=2.00,
    step=0.01,
    key="voice_h"
)

voice_d = st.number_input(
    "음성 검색 무 배당",
    min_value=0.01,
    value=3.00,
    step=0.01,
    key="voice_d"
)

voice_a = st.number_input(
    "음성 검색 패 배당",
    min_value=0.01,
    value=3.00,
    step=0.01,
    key="voice_a"
)

if st.button(
    "🎯 입력한 배당으로 결과/확률 조회",
    use_container_width=True
):
    rows = database.search_odds(
        voice_h,
        voice_d,
        voice_a,
        tolerance=0.001
    )

    if not rows:
        st.warning(
            "일치하는 저장 경기가 없습니다."
        )
    else:
        stats = analysis.calculate_statistics(
            rows
        )

        st.success(
            f"일치 경기 {len(rows):,}개"
        )

        if stats:
            x1, x2, x3 = st.columns(3)

            x1.metric(
                "실제 승률",
                f"{stats['actual']['home']:.2f}%"
            )

            x2.metric(
                "실제 무승률",
                f"{stats['actual']['draw']:.2f}%"
            )

            x3.metric(
                "실제 패율",
                f"{stats['actual']['away']:.2f}%"
            )

            st.write(
                "### 배당 내재확률"
            )

            x1, x2, x3 = st.columns(3)

            x1.metric(
                "승",
                f"{stats['probability']['home']:.2f}%"
            )

            x2.metric(
                "무",
                f"{stats['probability']['draw']:.2f}%"
            )

            x3.metric(
                "패",
                f"{stats['probability']['away']:.2f}%"
            )

        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# 수집 작업 지속 안내
# =========================================================

st.divider()

st.caption(
    "📌 수집 작업은 휴대폰 화면과 별도의 서버 작업입니다. "
    "휴대폰 화면을 끄거나 다른 앱으로 이동해도 서버 프로세스가 "
    "살아있는 동안 계속 실행됩니다. "
    "서버가 재시작되는 경우 저장된 마지막 완료 ID부터 재개할 수 있습니다."
        )
