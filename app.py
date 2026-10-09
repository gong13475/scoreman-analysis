# ============================================================
# app.py
# Scoreman 해외배당 분석
#
# 기능
# 1. 해외배당 자료 수집
# 2. Turso / SQLite 데이터베이스 상태
# 3. 업체별 저장 현황
# 4. 수집 진행 상태 및 로그
# 5. 실제 승무패 결과
# 6. 업체별 통계
# 7. 특정 업체 선택
# 8. 수동 배당 입력
# 9. 배당 대비 예상확률
# 10. 동일 배당 과거 실제확률
# 11. 부족확률
# 12. 과거 경기 목록
# 13. 음성 입력 및 결과 읽기
# 14. 모바일 최적화
#
# 배당 마진 표시 제거
# ============================================================

import json
import re
import time

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

import database
import collector
import analysis


# ============================================================
# 음성 입력
# ============================================================

try:

    from streamlit_mic_recorder import speech_to_text

    VOICE_AVAILABLE = True

except Exception:

    speech_to_text = None

    VOICE_AVAILABLE = False


# ============================================================
# 페이지 설정
# ============================================================

st.set_page_config(

    page_title="Scoreman 해외배당 분석",

    page_icon="⚽",

    layout="wide",

    initial_sidebar_state="collapsed",
)


# ============================================================
# 모바일 스타일
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        max-width: 1400px;
        padding-top: 1rem;
        padding-bottom: 3rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    [data-testid="stMetric"] {
        background: rgba(128, 128, 128, 0.08);
        border-radius: 12px;
        padding: 12px;
    }

    .stButton button {
        min-height: 46px;
        border-radius: 10px;
        font-weight: 600;
    }

    .stDownloadButton button {
        min-height: 44px;
    }

    div[data-testid="stDataFrame"] {
        width: 100%;
    }

    @media (max-width: 640px) {

        .block-container {
            padding-top: 0.6rem;
            padding-left: 0.65rem;
            padding-right: 0.65rem;
        }

        h1 {
            font-size: 1.55rem !important;
        }

        h2 {
            font-size: 1.25rem !important;
        }

        h3 {
            font-size: 1.05rem !important;
        }

        [data-testid="stMetric"] {
            padding: 8px;
            margin-bottom: 6px;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.15rem !important;
        }

        .stButton button {
            width: 100%;
            min-height: 48px;
        }

    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 데이터베이스 초기화
# ============================================================

@st.cache_resource
def initialize_database():

    database.init_database()

    return True


try:

    initialize_database()

except Exception as error:

    st.error("데이터베이스 초기화 실패")

    st.code(str(error))

    st.warning(
        "Turso 사용 시 TURSO_DATABASE_URL과 "
        "TURSO_AUTH_TOKEN을 확인하세요."
    )

    st.stop()


# ============================================================
# 제목
# ============================================================

st.title("⚽ Scoreman 해외배당 분석")

st.caption(
    "해외 최종배당 · 실제 결과 · 동일 배당 분석 · "
    "예상확률 · 실제확률 · 부족확률"
)


# ============================================================
# 데이터베이스 상태
# ============================================================

st.subheader("🗄️ 저장 데이터")

try:

    db = database.get_database_status()

    size = database.get_database_size()

except Exception as error:

    st.error(f"DB 상태 조회 실패: {error}")

    st.stop()


c1, c2, c3 = st.columns(3)

c1.metric(
    "저장 경기",
    f"{db['matches']:,}",
)

c2.metric(
    "최종배당",
    f"{db['odds']:,}",
)

c3.metric(
    "저장 업체",
    f"{db['bookmakers']:,}",
)


c4, c5 = st.columns(2)

c4.metric(
    "실제 결과",
    f"{db['results']:,}",
)

c5.metric(
    "결과 미확인",
    f"{db['unresolved']:,}",
)


if size["mode"] == "Turso":

    st.success("🟢 Turso 데이터베이스 연결")

    st.caption(
        f"저장 데이터 크기 추정치: "
        f"{size['mb']:.3f} MB "
        f"({size['gb']:.6f} GB)"
    )

    st.caption(
        "데이터 크기는 추정치이며 "
        "계정의 실제 사용량과 다를 수 있습니다."
    )

elif size["mode"] == "SQLite":

    st.warning(
        "현재 로컬 SQLite 모드입니다. "
        "Streamlit Cloud에서는 재시작 시 "
        "로컬 파일이 유지되지 않을 수 있습니다."
    )

    st.caption(
        f"로컬 DB 파일 크기: {size['mb']:.3f} MB"
    )

else:

    st.error(
        f"DB 연결 상태를 확인하세요: {size['mode']}"
    )


# ============================================================
# 업체별 저장 현황
# ============================================================

st.divider()

st.subheader("🏢 업체별 저장 현황")

try:

    bookmaker_rows = database.get_bookmakers()

except Exception as error:

    bookmaker_rows = []

    st.error(f"업체 목록 조회 실패: {error}")


if bookmaker_rows:

    company_df = pd.DataFrame(bookmaker_rows)

    company_df = company_df.rename(
        columns={

            "bookmaker": "해외업체",

            "games": "저장 경기 수",

            "odds_count": "저장 배당 수",
        }
    )

    st.dataframe(
        company_df,
        use_container_width=True,
        hide_index=True,
    )

else:

    st.info("저장된 업체 데이터가 없습니다.")


# ============================================================
# 업체 목록
# ============================================================

known_names = [

    "18Bet",
    "Bet365",
    "Crown",
    "Sbobet",
    "pinnacle",
    "Easybet",
    "Vcbet",
    "Interwetten",
]


for item in bookmaker_rows:

    name = item.get("bookmaker")

    if name and name not in known_names:

        known_names.append(name)


known_names = sorted(set(known_names))


# ============================================================
# 자료 수집
# ============================================================

st.divider()

st.header("📥 Scoreman 자료 수집")


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
    f"수집 대상 ID: "
    f"{max(0, int(end_id) - int(start_id) + 1):,}개"
)


# ============================================================
# 수집 방식
# ============================================================

collection_mode = st.radio(

    "수집 방식",

    [
        "전체 업체 수집",
        "특정 업체 선택",
    ],

    horizontal=True,
)


selected_companies = []


if collection_mode == "특정 업체 선택":

    selected_companies = st.multiselect(

        "수집할 해외업체",

        options=known_names,

        default=[],

        placeholder="수집할 업체를 선택하세요",
    )

    if selected_companies:

        st.info(
            "선택 업체: "
            + ", ".join(selected_companies)
        )

    else:

        st.warning(
            "수집할 업체를 한 개 이상 선택하세요."
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
    "실제 점수 검증 · 최종배당 euro.l 저장"
)


# ============================================================
# 수집 시작 및 중지
# ============================================================

b1, b2 = st.columns(2)


with b1:

    if st.button(

        "▶️ 수집 시작",

        type="primary",

        use_container_width=True,

    ):

        if end_id < start_id:

            st.error("ID 범위를 확인하세요.")

        elif (
            collection_mode == "특정 업체 선택"
            and not selected_companies
        ):

            st.error("수집할 업체를 선택하세요.")

        else:

            companies = (
                selected_companies
                if collection_mode == "특정 업체 선택"
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

        "⏹️ 수집 중지",

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


# ============================================================
# 이어받기
# ============================================================

if st.button(

    "▶️ 마지막 지점부터 이어받기",

    type="secondary",

    use_container_width=True,

):

    if end_id < start_id:

        st.error("ID 범위를 확인하세요.")

    elif (
        collection_mode == "특정 업체 선택"
        and not selected_companies
    ):

        st.error("수집할 업체를 선택하세요.")

    else:

        companies = (
            selected_companies
            if collection_mode == "특정 업체 선택"
            else []
        )

        ok, message = collector.resume_collection(

            int(end_id),

            companies,

            float(delay),

            int(start_id),
        )

        if ok:

            st.success(message)

        else:

            st.warning(message)


# ============================================================
# 진행 상태
# ============================================================

st.divider()

st.subheader("📊 실시간 수집 상태")

progress = collector.get_progress()


p1, p2, p3 = st.columns(3)

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


p4, p5 = st.columns(2)

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


status = collector.get_job_status()


if status["running"]:

    st.success("🟢 수집 중")

    current_id = (
        int(status["start_id"])
        + int(status["current"])
        - 1
    )

    if current_id >= int(status["start_id"]):

        st.write(
            f"현재 처리 중인 ID: **{current_id:,}**"
        )

elif status["finished"]:

    st.info(
        "🏁 수집 종료 · "
        + str(status["result"])
    )

else:

    st.info("⚪ 대기 중")


if progress.get("last_completed_id") is not None:

    st.write(
        "마지막 완료 ID: "
        f"**{progress['last_completed_id']:,}**"
    )


if status.get("error"):

    st.error(status["error"])


# ============================================================
# 수집 로그
# ============================================================

st.divider()

st.subheader("📋 수집 로그")


if "show_collection_log" not in st.session_state:

    st.session_state["show_collection_log"] = False


if st.button(
    "📋 수집 로그 보기 / 새로고침",
    use_container_width=True,
):

    st.session_state["show_collection_log"] = (
        not st.session_state["show_collection_log"]
    )


if st.session_state["show_collection_log"]:

    logs = collector.get_logs()

    if logs:

        st.code(
            "\n".join(logs[-500:]),
            language="text",
        )

    else:

        st.info("로그가 없습니다.")


# ============================================================
# 결과 미확인 경기
# ============================================================

st.divider()

st.subheader("⚠️ 결과 미확인 경기")


unresolved = database.get_unresolved_matches()


st.write(
    f"결과 미확인 경기: **{len(unresolved):,}개**"
)


if unresolved:

    st.dataframe(

        pd.DataFrame(unresolved),

        use_container_width=True,

        hide_index=True,
    )


# ============================================================
# 분석할 업체 선택
# ============================================================

st.divider()

st.header("📈 해외배당 분석")


analysis_options = [
    "전체 업체",
] + sorted({

    item["bookmaker"]

    for item in bookmaker_rows

    if item.get("bookmaker")
})


selected_bookmaker = st.selectbox(

    "분석할 업체",

    analysis_options,

    key="analysis_bookmaker",
)


if selected_bookmaker == "전체 업체":

    rows = database.get_analysis_rows()

else:

    rows = database.get_analysis_rows(
        selected_bookmaker
    )


# ============================================================
# 전체 승무패 통계
# ============================================================

stats = analysis.result_counts(rows)


st.subheader("⚽ 실제 승무패 결과")


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
# 업체별 통계
# 배당 마진 컬럼은 표시하지 않음
# ============================================================

st.subheader("🏢 업체별 분석")


company_stats = analysis.bookmaker_stats(rows)


if company_stats:

    company_df = pd.DataFrame(company_stats)

    # 평균마진 표시 제거
    company_df = company_df.drop(
        columns=["평균마진"],
        errors="ignore",
    )

    st.dataframe(

        company_df,

        use_container_width=True,

        hide_index=True,
    )

else:

    st.info(
        "분석할 업체별 데이터가 없습니다."
    )


# ============================================================
# 수동 배당 입력
# ============================================================

st.divider()

st.header("🧮 수동 배당 입력")


st.caption(
    "해외업체를 선택하고 승·무·패 배당을 입력하면 "
    "예상확률, 과거 실제확률, 부족확률을 계산합니다."
)


# ============================================================
# 수동 분석 업체 선택
# ============================================================

st.subheader("🏢 분석 대상 해외업체")


manual_company_options = sorted({

    item["bookmaker"]

    for item in bookmaker_rows

    if item.get("bookmaker")
})


if not manual_company_options:

    manual_company_options = known_names


manual_company = st.selectbox(

    "과거 경기와 비교할 업체",

    manual_company_options,

    key="manual_company",
)


st.caption(
    f"선택 업체: {manual_company}"
)


# ============================================================
# 음성 입력
# ============================================================

st.subheader("🎙️ 음성으로 배당 입력")


if VOICE_AVAILABLE:

    try:

        spoken = speech_to_text(

            language="ko",

            just_once=True,

            key="scoreman_voice_input",
        )


        if isinstance(spoken, dict):

            spoken = spoken.get("text", "")


        spoken = str(spoken or "").strip()


        if spoken:

            st.write(
                f"음성 인식 결과: **{spoken}**"
            )


            if (
                st.session_state.get(
                    "_last_voice_processed"
                ) != spoken
            ):

                numbers = re.findall(

                    r"\d+(?:\.\d+)?",

                    spoken,
                )


                if len(numbers) >= 3:

                    values = [

                        float(number)

                        for number in numbers[:3]
                    ]


                    if all(

                        1.01 <= value <= 1000

                        for value in values

                    ):

                        st.session_state["manual_home"] = (
                            values[0]
                        )

                        st.session_state["manual_draw"] = (
                            values[1]
                        )

                        st.session_state["manual_away"] = (
                            values[2]
                        )


                        st.success(
                            "배당 숫자 3개를 인식했습니다."
                        )

                    else:

                        st.warning(
                            "배당은 1.01 이상 1000 이하로 "
                            "입력해야 합니다."
                        )

                else:

                    st.warning(
                        "승·무·패 배당 숫자 3개를 "
                        "인식하지 못했습니다."
                    )


                st.session_state[
                    "_last_voice_processed"
                ] = spoken


    except Exception as error:

        st.warning(
            f"음성 입력을 사용할 수 없습니다: {error}"
        )


else:

    st.info(
        "음성 입력을 사용하려면 "
        "streamlit-mic-recorder를 설치하세요."
    )


# ============================================================
# 수동 배당 입력
# ============================================================

st.subheader("🎯 승 · 무 · 패 배당 입력")


d1, d2, d3 = st.columns(3)


with d1:

    manual_home = st.number_input(

        "홈 승 배당",

        min_value=1.01,

        max_value=1000.0,

        value=2.00,

        step=0.01,

        format="%.2f",

        key="manual_home",
    )


with d2:

    manual_draw = st.number_input(

        "무승부 배당",

        min_value=1.01,

        max_value=1000.0,

        value=3.20,

        step=0.01,

        format="%.2f",

        key="manual_draw",
    )


with d3:

    manual_away = st.number_input(

        "원정 승 배당",

        min_value=1.01,

        max_value=1000.0,

        value=3.50,

        step=0.01,

        format="%.2f",

        key="manual_away",
    )


# ============================================================
# 시장 예상확률
# ============================================================

manual_probs = analysis.odds_probability(

    manual_home,

    manual_draw,

    manual_away,
)


st.subheader("📊 배당 대비 예상확률")


if manual_probs:

    q1, q2, q3 = st.columns(3)


    q1.metric(
        "승 예상확률",
        f"{manual_probs['승']:.2f}%",
    )


    q2.metric(
        "무 예상확률",
        f"{manual_probs['무']:.2f}%",
    )


    q3.metric(
        "패 예상확률",
        f"{manual_probs['패']:.2f}%",
    )


    st.caption(
        "예상확률은 입력 배당의 역수를 계산한 뒤 "
        "세 결과의 합이 100%가 되도록 정규화합니다."
    )


# ============================================================
# 유사 배당 포함 여부
# ============================================================

st.divider()

st.subheader("🎯 동일 배당 과거 경기 분석")


approximate = st.checkbox(

    "완전 동일이 아닌 유사 배당도 포함",

    value=False,
)


tolerance = 0.0


if approximate:

    tolerance = st.number_input(

        "배당 허용 오차",

        min_value=0.01,

        max_value=1.0,

        value=0.01,

        step=0.01,

        format="%.2f",
    )


# ============================================================
# 선택한 업체의 데이터만 조회
# ============================================================

same_source_rows = database.get_analysis_rows(
    manual_company
)


# ============================================================
# 동일 배당 검색
# ============================================================

same_rows_all = analysis.same_odds_analysis(

    same_source_rows,

    manual_home,

    manual_draw,

    manual_away,

    tolerance,
)


# 실제 결과가 확인된 경기만 확률 계산에 사용
same_rows = [

    row

    for row in same_rows_all

    if row.get("result") in ("승", "무", "패")
]


# ============================================================
# 예상확률 / 실제확률 / 부족확률
# ============================================================

if same_rows and manual_probs:

    same_stats = analysis.result_counts(
        same_rows
    )


    st.success(
        f"선택 업체: {manual_company} · "
        f"실제 결과 확인 경기: "
        f"{same_stats['total']:,}경기"
    )


    # --------------------------------------------------------
    # 발생 횟수
    # --------------------------------------------------------

    s1, s2, s3 = st.columns(3)


    s1.metric(

        "승 발생",

        f"{same_stats['승']:,} "
        f"({same_stats['승률']:.2f}%)",
    )


    s2.metric(

        "무 발생",

        f"{same_stats['무']:,} "
        f"({same_stats['무율']:.2f}%)",
    )


    s3.metric(

        "패 발생",

        f"{same_stats['패']:,} "
        f"({same_stats['패율']:.2f}%)",
    )


    # --------------------------------------------------------
    # 핵심 확률 비교표
    # --------------------------------------------------------

    st.subheader(
        "📋 배당 · 예상확률 · 실제확률 · 부족확률"
    )


    comparison = []


    for result_key, odds in [

        ("승", manual_home),

        ("무", manual_draw),

        ("패", manual_away),

    ]:

        # 배당으로 계산한 시장 예상확률
        expected_rate = manual_probs[result_key]


        # 선택 업체의 동일 배당 과거 실제확률
        actual_rate = same_stats[
            f"{result_key}률"
        ]


        # 부족확률
        shortage = expected_rate - actual_rate


        comparison.append({

            "결과": result_key,

            "입력 배당": round(
                odds,
                2,
            ),

            "예상확률(%)": round(
                expected_rate,
                2,
            ),

            "실제확률(%)": round(
                actual_rate,
                2,
            ),

            "부족확률(%p)": round(
                shortage,
                2,
            ),

            "실제 발생 횟수": same_stats[
                result_key
            ],

            "전체 경기 수": same_stats[
                "total"
            ],
        })


    comparison_df = pd.DataFrame(
        comparison
    )


    st.dataframe(

        comparison_df,

        use_container_width=True,

        hide_index=True,
    )


    # --------------------------------------------------------
    # 부족확률 해석
    # --------------------------------------------------------

    st.markdown(
        """
        **부족확률 계산식**

        부족확률 = 예상확률 - 실제확률

        - 양수(+) : 과거 실제 발생률이 예상확률보다 낮음
        - 음수(-) : 과거 실제 발생률이 예상확률보다 높음
        - 0에 가까움 : 예상확률과 실제확률이 비슷함

        부족확률은 과거 데이터의 차이를 나타내며,
        미래 경기 결과를 보장하지 않습니다.
        """
    )


    # --------------------------------------------------------
    # 결과별 차이 요약
    # --------------------------------------------------------

    st.subheader("🔎 확률 차이 요약")


    for item in comparison:

        result_name = item["결과"]

        shortage = item["부족확률(%p)"]

        expected_rate = item["예상확률(%)"]

        actual_rate = item["실제확률(%)"]


        if shortage > 0:

            st.write(

                f"**{result_name}** — "
                f"예상 {expected_rate:.2f}% / "
                f"실제 {actual_rate:.2f}% / "
                f"부족 +{shortage:.2f}%p"
            )

        elif shortage < 0:

            st.write(

                f"**{result_name}** — "
                f"예상 {expected_rate:.2f}% / "
                f"실제 {actual_rate:.2f}% / "
                f"차이 {shortage:.2f}%p"
            )

        else:

            st.write(

                f"**{result_name}** — "
                f"예상확률과 실제확률이 같습니다."
            )


    # --------------------------------------------------------
    # 과거 경기 목록
    # --------------------------------------------------------

    st.subheader("📝 동일 배당 과거 경기 목록")


    recent_same = pd.DataFrame(
        same_rows
    )


    display_columns = [

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


    available_columns = [

        column

        for column in display_columns

        if column in recent_same.columns
    ]


    st.dataframe(

        recent_same[available_columns],

        use_container_width=True,

        hide_index=True,
    )


    # --------------------------------------------------------
    # CSV 다운로드
    # --------------------------------------------------------

    csv_data = recent_same[
        available_columns
    ].to_csv(
        index=False
    ).encode("utf-8-sig")


    st.download_button(

        "⬇️ 동일 배당 과거 경기 CSV 다운로드",

        data=csv_data,

        file_name="same_odds_matches.csv",

        mime="text/csv",

        use_container_width=True,
    )


else:

    st.info(
        f"선택 업체: {manual_company}\n\n"
        "입력한 배당과 일치하는 과거 경기 중 "
        "실제 결과가 확인된 경기가 없습니다. "
        "유사 배당 검색을 켜거나 다른 배당을 입력해 보세요."
    )


# ============================================================
# 전체 데이터 예상확률 대비 실제확률
# ============================================================

st.divider()

st.subheader("📉 전체 분석 데이터 확률 비교")


ev = analysis.expected_vs_actual(rows)


if ev:

    ev_df = pd.DataFrame(ev)


    # 부족확률과 실제확률을 포함해 표시
    st.dataframe(

        ev_df,

        use_container_width=True,

        hide_index=True,
    )


else:

    st.info(
        "예상확률을 계산할 수 있는 "
        "실제 결과 데이터가 없습니다."
    )


# ============================================================
# 분석 결과 음성 읽기
# ============================================================

st.divider()

st.subheader("🔊 분석 결과 듣기")


if manual_probs:

    if same_rows:

        speech_text = (

            f"선택 업체는 {manual_company}입니다. "

            f"동일 배당 과거 경기 "
            f"{same_stats['total']}경기를 분석했습니다. "

            f"승 실제 발생률 "
            f"{same_stats['승률']:.2f}퍼센트. "

            f"무승부 실제 발생률 "
            f"{same_stats['무율']:.2f}퍼센트. "

            f"패 실제 발생률 "
            f"{same_stats['패율']:.2f}퍼센트. "

            f"시장 예상 승 확률 "
            f"{manual_probs['승']:.2f}퍼센트. "

            f"시장 예상 무승부 확률 "
            f"{manual_probs['무']:.2f}퍼센트. "

            f"시장 예상 패 확률 "
            f"{manual_probs['패']:.2f}퍼센트."
        )

    else:

        speech_text = (

            f"시장 예상확률입니다. "

            f"승 {manual_probs['승']:.2f}퍼센트. "

            f"무승부 {manual_probs['무']:.2f}퍼센트. "

            f"패 {manual_probs['패']:.2f}퍼센트. "

            f"선택 업체는 {manual_company}입니다."
        )


    safe_text = json.dumps(

        speech_text,

        ensure_ascii=False,
    )


    components.html(

        f"""
        <div style="
            font-family: sans-serif;
            width: 100%;
        ">

            <button
                id="speakButton"
                style="
                    width: 100%;
                    min-height: 50px;
                    border: none;
                    border-radius: 10px;
                    background: #1769aa;
                    color: white;
                    font-size: 16px;
                    font-weight: bold;
                "
            >
                🔊 분석 결과 듣기
            </button>

            <script>

                const speechText = {safe_text};

                document
                    .getElementById("speakButton")
                    .addEventListener("click", function() {{

                        if (!("speechSynthesis" in window)) {{

                            alert(
                                "이 브라우저는 음성 읽기를 지원하지 않습니다."
                            );

                            return;
                        }}

                        window.speechSynthesis.cancel();

                        const utterance =
                            new SpeechSynthesisUtterance(
                                speechText
                            );

                        utterance.lang = "ko-KR";

                        utterance.rate = 0.95;

                        window.speechSynthesis.speak(
                            utterance
                        );

                    }});

            </script>

        </div>
        """,

        height=65,
    )


# ============================================================
# 최근 저장 경기
# ============================================================

st.divider()

st.subheader("📝 최근 저장 경기")


if rows:

    recent = pd.DataFrame(
        rows
    )


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
