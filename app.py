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
        font-size: 30px;
        font-weight: 800;
        margin-bottom: 5px;
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
    '스코어맨 자동수집 · 해외업체 최종배당 · '
    '실제결과 · 확률분석 · Turso 영구저장'
    '</div>',
    unsafe_allow_html=True
)


# =========================================================
# DB 상태
# =========================================================

try:

    status = database.get_database_status()

except Exception as e:

    st.error(
        f"DB 상태를 읽는 중 오류가 발생했습니다: {e}"
    )

    status = {
        "matches": 0,
        "odds": 0,
        "bookmakers": 0
    }


c1, c2, c3, c4 = st.columns(4)


c1.metric(
    "저장 경기",
    f"{status.get('matches', 0):,}"
)


c2.metric(
    "저장 최종배당",
    f"{status.get('odds', 0):,}"
)


c3.metric(
    "실제 저장 업체",
    f"{status.get('bookmakers', 0):,}"
)


if getattr(
    database,
    "TURSO_DATABASE_URL",
    ""
) and getattr(
    database,
    "TURSO_AUTH_TOKEN",
    ""
):

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
# Turso 상태
# =========================================================

st.subheader(
    "🗄️ 데이터베이스 상태"
)


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


# =========================================================
# 로컬 SQLite 사용량
# =========================================================

try:

    storage = database.get_storage_usage()

    if storage.get("success"):

        st.caption(
            "로컬 SQLite 사용량: "
            f"{storage.get('size_mb', 0):.2f} MB"
        )

except Exception:

    pass


# =========================================================
# 업체별 저장량
# =========================================================

st.subheader(
    "🏢 저장 업체별 경기 수"
)


try:

    company_counts = (
        database.get_company_counts()
        or {}
    )

except Exception:

    company_counts = {}


if company_counts:

    company_display = []

    for company, count in company_counts.items():

        company_display.append({
            "업체":
                company,

            "저장 경기 수":
                int(count)
        })

    st.dataframe(
        company_display,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "아직 저장된 업체별 배당 데이터가 없습니다."
    )


# =========================================================
# 마지막 수집 상태
# =========================================================

try:

    resume_state = database.get_collection_state()

except Exception:

    resume_state = None


if not isinstance(
    resume_state,
    dict
):

    resume_state = {}


last_id = resume_state.get(
    "last_completed_id",
    0
)


if last_id is None:

    last_id = 0


try:

    last_id = int(
        last_id
    )

except Exception:

    last_id = 0


last_start_id = resume_state.get(
    "start_id"
)


last_end_id = resume_state.get(
    "end_id"
)


try:

    if last_start_id is not None:

        last_start_id = int(
            last_start_id
        )

except Exception:

    last_start_id = None


try:

    if last_end_id is not None:

        last_end_id = int(
            last_end_id
        )

except Exception:

    last_end_id = None


# =========================================================
# 수집
# =========================================================

st.subheader(
    "📥 스코어맨 경기 자동수집"
)


st.write(
    "시작 ID와 마지막 ID를 입력한 뒤 "
    "수집 시작 버튼을 누르면 백그라운드에서 "
    "수집합니다."
)


col1, col2 = st.columns(2)


with col1:

    default_start = (
        last_start_id
        if last_start_id and last_start_id > 0
        else 3001118
    )

    start_id = st.number_input(
        "시작 경기 ID",
        min_value=1,
        value=default_start,
        step=1
    )


with col2:

    default_end = (
        last_end_id
        if last_end_id and last_end_id >= start_id
        else start_id
    )

    end_id = st.number_input(
        "마지막 경기 ID",
        min_value=1,
        value=default_end,
        step=1
    )


if end_id >= start_id:

    st.caption(
        f"검색 대상: "
        f"{end_id - start_id + 1:,}개"
    )

else:

    st.error(
        "마지막 ID가 시작 ID보다 작습니다."
    )


# =========================================================
# 마지막 완료 ID
# =========================================================

if last_id > 0:

    st.info(
        f"📌 마지막 저장 완료 경기 ID: "
        f"{last_id:,}"
    )

else:

    st.caption(
        "아직 저장된 수집 완료 위치가 없습니다."
    )


# =========================================================
# 이어서 수집
# =========================================================

if last_id > 0:

    if st.button(
        f"▶️ 마지막 완료 ID 다음부터 계속 수집 "
        f"({last_id + 1:,})",
        use_container_width=True
    ):

        if end_id < last_id + 1:

            st.warning(
                "마지막 ID가 현재 완료 ID보다 작거나 같습니다."
            )

        else:

            ok = collector.start_background_collection(

                last_id + 1,

                end_id,

                None,

                0.5
            )

            if ok:

                st.success(
                    f"{last_id + 1:,}번부터 "
                    f"{end_id:,}번까지 "
                    "백그라운드 수집을 시작했습니다."
                )

            else:

                st.warning(
                    "이미 수집 작업이 실행 중입니다."
                )


# =========================================================
# 업체 선택
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


try:

    companies = (
        analysis.get_company_list()
        or []
    )

except Exception:

    companies = []


if mode == "특정 업체만 수집":

    selected = st.multiselect(
        "업체 선택",
        companies
    )

else:

    selected = None


st.success(
    "✅ Scoreman에서 제공하는 업체의 "
    "최종배당을 자동으로 수집합니다."
)


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

        elif (
            mode == "특정 업체만 수집"
            and not selected
        ):

            st.error(
                "업체를 하나 이상 선택하세요."
            )

        else:

            ok = collector.start_background_collection(

                int(start_id),

                int(end_id),

                selected,

                float(delay)
            )


            if ok:

                st.success(
                    "백그라운드 수집을 시작했습니다."
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

        if collector.stop_background_collection():

            st.warning(
                "수집 중지 요청을 보냈습니다."
            )

        else:

            st.info(
                "현재 실행 중인 수집 작업이 없습니다."
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
        "selected_companies": [],
        "log": "",
        "result": None,
        "error": ""
    }


# =========================================================
# 실행 중
# =========================================================

if job.get("running"):

    st.subheader(
        "📊 현재 수집 상태"
    )


    progress = 0


    total = int(
        job.get(
            "total",
            0
        ) or 0
    )


    current = int(
        job.get(
            "current",
            0
        ) or 0
    )


    if total > 0:

        progress = (
            current
            / total
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


    a, b, c, d = st.columns(4)


    a.metric(
        "진행",
        f"{current:,} / {total:,}"
    )


    b.metric(
        "신규",
        f"{int(job.get('success', 0) or 0):,}"
    )


    c.metric(
        "실패/배당없음",
        f"{int(job.get('failed', 0) or 0):,}"
    )


    d.metric(
        "최종배당",
        f"{int(job.get('odds', 0) or 0):,}"
    )


    current_last_id = job.get(
        "last_completed_id"
    )


    if current_last_id:

        st.info(
            f"📌 현재 마지막 완료 ID: "
            f"{int(current_last_id):,}"
        )


    # -----------------------------------------------------
    # 로그 숨김
    # -----------------------------------------------------

    if "show_collection_log" not in st.session_state:

        st.session_state[
            "show_collection_log"
        ] = False


    if st.button(
        (
            "👁️ 로그 보기"
            if not st.session_state["show_collection_log"]
            else "🙈 로그 숨기기"
        ),
        key="toggle_running_log"
    ):

        st.session_state[
            "show_collection_log"
        ] = not st.session_state[
            "show_collection_log"
        ]


    if st.session_state[
        "show_collection_log"
    ]:

        st.text_area(
            "수집 로그",
            job.get(
                "log",
                ""
            ),
            height=300
        )


    time.sleep(1)

    st.rerun()


# =========================================================
# 완료
# =========================================================

elif job.get("finished"):

    st.subheader(
        "✅ 마지막 수집 결과"
    )


    if job.get("stopped"):

        st.warning(
            "🛑 수집이 중지되었습니다."
        )


    result = job.get(
        "result"
    )


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


    finished_last_id = job.get(
        "last_completed_id"
    )


    if finished_last_id:

        st.success(
            f"📌 마지막 완료 경기 ID: "
            f"{int(finished_last_id):,}"
        )


    if job.get("error"):

        st.error(
            job.get("error")
        )


    # -----------------------------------------------------
    # 완료 로그 숨김
    # -----------------------------------------------------

    if "show_finished_log" not in st.session_state:

        st.session_state[
            "show_finished_log"
        ] = False


    if st.button(
        (
            "👁️ 로그 보기"
            if not st.session_state["show_finished_log"]
            else "🙈 로그 숨기기"
        ),
        key="toggle_finished_log"
    ):

        st.session_state[
            "show_finished_log"
        ] = not st.session_state[
            "show_finished_log"
        ]


    if st.session_state[
        "show_finished_log"
    ]:

        st.text_area(
            "로그",
            job.get(
                "log",
                ""
            ),
            height=250
        )


# =========================================================
# 저장된 경기
# =========================================================

st.subheader(
    "📋 저장된 전체 경기"
)


try:

    matches = (
        database.get_all_matches()
        or []
    )

except Exception as e:

    matches = []

    st.error(
        f"경기 데이터를 불러올 수 없습니다: {e}"
    )


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
# 경기별 최종배당
# =========================================================

st.subheader(
    "📱 경기별 최종배당 확인"
)


st.write(
    "휴대폰에서 경기 ID를 입력하면 "
    "해당 경기의 저장된 해외업체 최종배당을 "
    "바로 확인할 수 있습니다."
)


lookup_id = st.number_input(
    "경기 ID",
    min_value=1,
    value=(
        int(last_id)
        if last_id > 0
        else 3001118
    ),
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
            f"경기 조회 오류: {e}"
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
                    <b>
                        {int(lookup_id):,}
                    </b>

                    <br>

                    경기일:
                    <b>
                        {match.get("match_date", "")}
                    </b>

                    <br>

                    실제 결과:
                    <b>
                        {match.get("result", "")}
                    </b>

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


        if not odds:

            st.error(
                "❌ 이 경기에는 저장된 "
                "최종배당이 없습니다."
            )

        else:

            st.success(
                f"저장된 최종배당 "
                f"{len(odds)}개"
            )


            display = []


            for row in odds:

                display.append({

                    "업체":
                        row.get(
                            "bookmaker",
                            ""
                        ),

                    "홈":
                        row.get(
                            "home_odds"
                        ),

                    "무":
                        row.get(
                            "draw_odds"
                        ),

                    "원정":
                        row.get(
                            "away_odds"
                        )

                })


            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True
            )


# =========================================================
# 배당 분석
# =========================================================

st.subheader(
    "📈 저장 배당 확률 분석"
)


analysis_companies = st.multiselect(
    "분석 업체",
    companies,
    key="analysis_companies"
)


if analysis_companies:

    odds_input = {}


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


        try:

            result = analysis.run_search(
                analysis_companies,
                odds_input
            )

        except Exception as e:

            result = {

                "success":
                    False,

                "message":
                    str(e),

                "results":
                    [],

                "statistics":
                    None

            }


        if not result.get(
            "success",
            False
        ):

            st.error(
                result.get(
                    "message",
                    "분석 오류"
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
                f"검색 경기 "
                f"{len(results):,}개"
            )


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


                st.write(
                    "### 실제 결과"
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


                st.write(
                    "### 배당 기준 확률"
                )


                p1, p2, p3 = st.columns(3)


                p1.metric(
                    "승",
                    f"{probability.get('home', 0):.2f}%"
                )


                p2.metric(
                    "무",
                    f"{probability.get('draw', 0):.2f}%"
                )


                p3.metric(
                    "패",
                    f"{probability.get('away', 0):.2f}%"
                )


                st.write(
                    "### 실제 결과 - 배당 확률"
                )


                s1, s2, s3 = st.columns(3)


                s1.metric(
                    "승",
                    f"{shortage.get('home', 0):+.2f}%"
                )


                s2.metric(
                    "무",
                    f"{shortage.get('draw', 0):+.2f}%"
                )


                s3.metric(
                    "패",
                    f"{shortage.get('away', 0):+.2f}%"
                )


                try:

                    highest = (
                        analysis.get_highest_shortage(
                            stats
                        )
                    )

                except Exception:

                    highest = ""


                if highest:

                    st.info(
                        "가장 부족한 결과: "
                        + str(highest)
                    )


            if results:

                st.write(
                    "### 검색된 경기"
                )


                st.dataframe(
                    results,
                    use_container_width=True,
                    hide_index=True
                )


# =========================================================
# 하단 새로고침
# =========================================================

st.divider()


if st.button(
    "🔄 화면 새로고침",
    use_container_width=True
):

    st.rerun()
