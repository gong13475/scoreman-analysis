# ============================================================
# app.py
# ⚽ 전종목 해외배당 분석 - 최종본
# ============================================================

import streamlit as st
import pandas as pd
import streamlit.components.v1 as components

import database
import analysis
import collector


# ============================================================
# 기본 설정
# ============================================================

st.set_page_config(
    page_title="전종목 해외배당 분석",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

database.init_database()


# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

.block-container {
    padding-top: 1rem;
    padding-bottom: 2rem;
    max-width: 1200px;
}

button {
    min-height: 42px !important;
}

[data-testid="stMetricValue"] {
    font-size: 1.5rem;
}

.small-help {
    color: #777;
    font-size: 0.85rem;
}

</style>
""", unsafe_allow_html=True)


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

db_status = database.get_database_status()
db_info = database.get_database_info()
storage = database.get_storage_usage()


c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        "저장 경기",
        f"{db_status['matches']:,}"
    )

with c2:
    st.metric(
        "저장 최종배당",
        f"{db_status['odds']:,}"
    )

with c3:
    st.metric(
        "실제 저장 업체",
        f"{db_status['bookmakers']:,}"
    )

with c4:
    st.metric(
        "DB",
        "Turso" if db_info["using_turso"] else "SQLite"
    )


# ============================================================
# DB 상세
# ============================================================

with st.expander("🗄️ 데이터베이스 상태", expanded=True):

    if db_info["using_turso"]:

        st.success("🟢 Turso DB 연결 정상")

    else:

        st.warning(
            "🟡 SQLite fallback 모드"
        )

    a, b, c = st.columns(3)

    with a:
        st.write(
            "Turso URL 설정:",
            "✅" if db_info["database_url_configured"] else "❌"
        )

    with b:
        st.write(
            "Turso Token 설정:",
            "✅" if db_info["auth_token_configured"] else "❌"
        )

    with c:
        st.write(
            "libSQL 모듈:",
            "✅" if db_info["libsql_available"] else "❌"
        )

    st.write(
        "현재 사용 DB:",
        "Turso" if db_info["using_turso"] else "SQLite"
    )

    st.divider()

    st.subheader("💾 DB 저장 용량")

    if storage.get("success"):

        st.metric(
            "현재 DB 저장 크기",
            f"{storage.get('size_mb', 0):.2f} MB"
        )

        st.write(
            f"약 {storage.get('size_gb', 0):.4f} GB"
        )

        st.write(
            "저장 방식:",
            storage.get(
                "storage_type",
                "SQLite"
            )
        )

    else:

        st.warning(
            storage.get(
                "error",
                "DB 저장 용량을 확인할 수 없습니다."
            )
        )


# ============================================================
# 업체별 저장 현황
# ============================================================

st.subheader("🏢 업체별 저장 경기 수")

company_counts = database.get_company_counts()

if company_counts:

    company_df = pd.DataFrame(
        [
            {
                "업체": k,
                "저장 경기": v
            }
            for k, v in company_counts.items()
        ]
    )

    st.dataframe(
        company_df,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "저장된 업체별 데이터가 없습니다."
    )


# ============================================================
# 자동 수집
# ============================================================

st.divider()

st.subheader(
    "📥 Scoreman 경기 ID 구간 자동수집"
)

state = database.get_collection_state()

last_completed = int(
    state.get(
        "last_completed_id",
        0
    ) or 0
)

default_start = (
    last_completed + 1
    if last_completed > 0
    else 2005000
)

col1, col2 = st.columns(2)

with col1:

    start_id = st.number_input(
        "시작 ID",
        min_value=1,
        value=int(default_start),
        step=1,
        format="%d"
    )

with col2:

    end_id = st.number_input(
        "마지막 ID",
        min_value=1,
        value=int(default_start),
        step=1,
        format="%d"
    )

if end_id >= start_id:

    st.caption(
        f"검색 대상: {end_id - start_id + 1:,}개"
    )


if last_completed > 0:

    st.info(
        f"📌 마지막 성공 완료 ID: "
        f"{last_completed:,}"
    )

    st.caption(
        f"다음 자동 시작 ID: "
        f"{last_completed + 1:,}"
    )


# ============================================================
# 업체 선택
# ============================================================

st.subheader("🏢 수집 업체")

mode = st.radio(
    "수집 방식",
    [
        "전체 업체 자동수집",
        "특정 업체만 수집"
    ],
    horizontal=True
)

selected_companies = None

all_companies = database.get_company_list()

if mode == "특정 업체만 수집":

    if all_companies:

        selected_companies = st.multiselect(
            "수집할 업체 선택",
            all_companies
        )

    else:

        selected_companies = st.text_input(
            "업체명 입력",
            placeholder="예: Bet365, 18Bet, Sbobet"
        )

        if selected_companies.strip():

            selected_companies = [
                x.strip()
                for x in selected_companies.split(",")
                if x.strip()
            ]

        else:

            selected_companies = []

else:

    st.caption(
        "Scoreman에서 확인되는 전체 업체의 "
        "최종배당을 자동 저장합니다."
    )


delay = st.number_input(
    "요청 간격(초)",
    min_value=0.10,
    max_value=10.0,
    value=0.50,
    step=0.10,
    format="%.2f"
)


resume = st.checkbox(
    "🔄 마지막 성공 ID 다음부터 이어받기",
    value=True
)


# ============================================================
# 시작 / 중지
# ============================================================

b1, b2 = st.columns(2)

with b1:

    if st.button(
        "▶️ 수집시작",
        use_container_width=True,
        type="primary"
    ):

        if end_id < start_id:

            st.error(
                "마지막 ID가 시작 ID보다 작습니다."
            )

        elif mode == "특정 업체만 수집" and not selected_companies:

            st.error(
                "수집할 업체를 선택하세요."
            )

        else:

            ok = collector.start_background_collection(
                int(start_id),
                int(end_id),
                selected_companies,
                float(delay),
                resume=resume
            )

            if ok:

                st.success(
                    "수집을 시작했습니다."
                )

                st.rerun()

            else:

                st.warning(
                    "이미 수집 중이거나 "
                    "수집할 ID가 없습니다."
                )


with b2:

    if st.button(
        "⏹️ 수집중지",
        use_container_width=True
    ):

        if collector.stop_background_collection():

            st.warning(
                "수집 중지 요청을 보냈습니다."
            )

            st.rerun()

        else:

            st.info(
                "현재 실행 중인 수집 작업이 없습니다."
            )


# ============================================================
# 작업 상태
# ============================================================

job = collector.get_job_status()

if job.get("running"):

    st.subheader("📊 현재 수집 상태")

    total = int(
        job.get("total", 0) or 0
    )

    current = int(
        job.get("current", 0) or 0
    )

    progress = (
        current / total
        if total > 0
        else 0
    )

    st.progress(
        min(max(progress, 0.0), 1.0)
    )

    p1, p2, p3, p4, p5 = st.columns(5)

    p1.metric("진행", f"{current:,}/{total:,}")
    p2.metric("신규", job.get("success", 0))
    p3.metric("기존", job.get("exists", 0))
    p4.metric("실패", job.get("failed", 0))
    p5.metric("배당", job.get("odds", 0))

    st.caption(
        f"마지막 성공 ID: "
        f"{job.get('last_completed_id', 0):,}"
    )

    st.info(
        "📱 다른 앱을 사용하거나 화면을 꺼도 "
        "서버의 백그라운드 작업은 계속 실행되도록 구성되어 있습니다. "
        "단, Streamlit Cloud 자체가 절전/재시작되면 작업이 중단될 수 있습니다."
    )


elif job.get("finished"):

    result = job.get("result") or {}

    st.success("수집 작업 완료")

    q1, q2, q3, q4, q5 = st.columns(5)

    q1.metric("신규", result.get("success", 0))
    q2.metric("기존", result.get("exists", 0))
    q3.metric("실패", result.get("failed", 0))
    q4.metric("배당없음", result.get("no_odds", 0))
    q5.metric("최종배당", result.get("odds", 0))


# ============================================================
# 로그
# ============================================================

show_log = st.checkbox(
    "📝 수집 로그 보기",
    value=False
)

if show_log:

    st.text_area(
        "수집 로그",
        job.get("log", ""),
        height=300
    )


# ============================================================
# 수동 배당 분석
# ============================================================

st.divider()

st.header(
    "🎯 수동 최종배당 분석"
)

st.caption(
    "업체를 선택하고 최종 승/무/패 배당을 입력하면 "
    "동일배당 과거 결과와 확률을 계산합니다."
)


manual_companies = database.get_company_list()

if manual_companies:

    manual_company = st.selectbox(
        "🏢 업체",
        manual_companies,
        key="manual_company"
    )

else:

    manual_company = st.text_input(
        "🏢 업체명",
        value="Bet365"
    )


o1, o2, o3 = st.columns(3)

with o1:

    home_odds = st.number_input(
        "승 배당",
        min_value=1.01,
        max_value=100.00,
        value=1.83,
        step=0.01,
        format="%.2f"
    )

with o2:

    draw_odds = st.number_input(
        "무 배당",
        min_value=1.01,
        max_value=100.00,
        value=3.50,
        step=0.01,
        format="%.2f"
    )

with o3:

    away_odds = st.number_input(
        "패 배당",
        min_value=1.01,
        max_value=100.00,
        value=4.20,
        step=0.01,
        format="%.2f"
    )


if st.button(
    "🔎 이 배당 과거결과 분석",
    use_container_width=True
):

    result = analysis.analyze_manual_odds(
        manual_company,
        float(home_odds),
        float(draw_odds),
        float(away_odds)
    )

    st.session_state[
        "manual_analysis"
    ] = result


manual_result = st.session_state.get(
    "manual_analysis"
)


if manual_result:

    st.subheader("📊 분석 결과")

    prob = manual_result["implied_probability"]

    hist = manual_result["historical"]

    expected = manual_result["expected_probability"]

    shortage = manual_result["shortage_probability"]

    r1, r2, r3 = st.columns(3)

    with r1:
        st.metric(
            "승",
            f"{prob['home']:.2f}%"
        )

    with r2:
        st.metric(
            "무",
            f"{prob['draw']:.2f}%"
        )

    with r3:
        st.metric(
            "패",
            f"{prob['away']:.2f}%"
        )

    st.write(
        f"입력 배당: "
        f"승 **{home_odds:.2f}** / "
        f"무 **{draw_odds:.2f}** / "
        f"패 **{away_odds:.2f}**"
    )

    st.divider()

    st.subheader(
        "📈 동일배당 과거 결과"
    )

    h1, h2, h3, h4 = st.columns(4)

    h1.metric(
        "전체",
        hist["total"]
    )

    h2.metric(
        "승",
        f"{hist['home_count']} "
        f"({hist['home_pct']:.2f}%)"
    )

    h3.metric(
        "무",
        f"{hist['draw_count']} "
        f"({hist['draw_pct']:.2f}%)"
    )

    h4.metric(
        "패",
        f"{hist['away_count']} "
        f"({hist['away_pct']:.2f}%)"
    )

    st.subheader(
        "📉 배당 대비 실제 확률 / 부족확률"
    )

    table = pd.DataFrame(
        [
            {
                "구분": "승",
                "배당": f"{home_odds:.2f}",
                "배당확률": f"{prob['home']:.2f}%",
                "실제확률": f"{expected['home']:.2f}%",
                "부족확률": f"{shortage['home']:.2f}%p"
            },
            {
                "구분": "무",
                "배당": f"{draw_odds:.2f}",
                "배당확률": f"{prob['draw']:.2f}%",
                "실제확률": f"{expected['draw']:.2f}%",
                "부족확률": f"{shortage['draw']:.2f}%p"
            },
            {
                "구분": "패",
                "배당": f"{away_odds:.2f}",
                "배당확률": f"{prob['away']:.2f}%",
                "실제확률": f"{expected['away']:.2f}%",
                "부족확률": f"{shortage['away']:.2f}%p"
            }
        ]
    )

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True
    )

    matches = hist.get(
        "matches",
        []
    )

    if matches:

        st.subheader(
            "🔎 동일배당 경기 목록"
        )

        df = pd.DataFrame(matches)

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "조건에 맞는 과거 경기가 없습니다."
        )


# ============================================================
# 마이크 음성입력
# ============================================================

st.divider()

st.header("🎤 음성 배당 입력")

st.caption(
    "브라우저에서 마이크 권한을 허용한 후 "
    "배당 숫자를 말할 수 있습니다."
)

components.html(
    """
    <div style="font-family:sans-serif;">
      <button onclick="startSpeech()"
              style="
              width:100%;
              height:48px;
              font-size:18px;
              border-radius:10px;
              border:1px solid #ccc;
              background:#f5f5f5;">
        🎤 마이크 시작
      </button>

      <p id="status">대기 중</p>
      <p id="text"
         style="font-size:20px;font-weight:bold;"></p>
    </div>

    <script>
    function startSpeech() {

        const SpeechRecognition =
            window.SpeechRecognition ||
            window.webkitSpeechRecognition;

        if (!SpeechRecognition) {

            document.getElementById("status").innerText =
                "이 브라우저는 음성인식을 지원하지 않습니다.";

            return;
        }

        const recognition =
            new SpeechRecognition();

        recognition.lang = "ko-KR";
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onstart = function() {

            document.getElementById("status").innerText =
                "🎤 듣는 중...";
        };

        recognition.onresult = function(event) {

            const value =
                event.results[0][0].transcript;

            document.getElementById("text").innerText =
                "인식 결과: " + value;

            document.getElementById("status").innerText =
                "완료";
        };

        recognition.onerror = function(event) {

            document.getElementById("status").innerText =
                "오류: " + event.error;
        };

        recognition.start();
    }
    </script>
    """,
    height=180
)


# ============================================================
# 음성 결과 듣기
# ============================================================

st.subheader("🔊 분석 결과 음성듣기")

speech_text = st.text_area(
    "읽어줄 내용",
    value=(
        "승 무 패 배당을 입력하면 "
        "분석 결과를 음성으로 들을 수 있습니다."
    )
)

components.html(
    f"""
    <div style="font-family:sans-serif;">
      <button onclick="speakText()"
              style="
              width:100%;
              height:48px;
              font-size:18px;
              border-radius:10px;
              border:1px solid #ccc;
              background:#f5f5f5;">
        🔊 음성듣기
      </button>

      <script>

      function speakText() {{

          const text =
              {speech_text!r};

          if (!window.speechSynthesis) {{

              alert(
                "이 브라우저는 음성합성을 지원하지 않습니다."
              );

              return;
          }}

          window.speechSynthesis.cancel();

          const utter =
              new SpeechSynthesisUtterance(text);

          utter.lang = "ko-KR";
          utter.rate = 0.95;

          window.speechSynthesis.speak(utter);
      }}

      </script>
    </div>
    """,
    height=80
)


# ============================================================
# 새로고침
# ============================================================

st.divider()

if st.button(
    "🔄 현재 상태 새로고침",
    use_container_width=True
):

    st.rerun()
