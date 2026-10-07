import time
import base64
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
    layout="wide",
    initial_sidebar_state="collapsed"
)


# =========================================================
# DB 초기화
# =========================================================

try:
    database.init_database()
except Exception as e:
    st.error(f"DB 초기화 오류: {e}")


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

    .status-box {
        padding: 15px;
        border-radius: 12px;
        background: #f5f7fa;
        margin: 10px 0;
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
# DB 상태
# =========================================================

try:
    status = database.get_database_status()
except Exception as e:
    st.error(f"DB 상태 오류: {e}")
    status = {
        "matches": 0,
        "odds": 0,
        "bookmakers": 0
    }


c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "저장 경기",
    f"{int(status.get('matches', 0)): ,}".replace(" ", "")
)

c2.metric(
    "저장 최종배당",
    f"{int(status.get('odds', 0)): ,}".replace(" ", "")
)

c3.metric(
    "실제 저장 업체",
    f"{int(status.get('bookmakers', 0)): ,}".replace(" ", "")
)

try:
    using_turso = database._use_turso()
except Exception:
    using_turso = False

c4.metric(
    "DB",
    "Turso" if using_turso else "SQLite"
)


# =========================================================
# DB 상태
# =========================================================

st.subheader("🗄️ 데이터베이스 상태")

if using_turso:

    st.success("🟢 Turso DB 연결 정상")

    st.caption(
        "현재 앱은 Turso DB에 연결되어 "
        "데이터를 영구 저장합니다."
    )

else:

    st.warning("🟡 로컬 SQLite fallback 모드")

    st.caption(
        "TURSO_DATABASE_URL / TURSO_AUTH_TOKEN이 "
        "없거나 libSQL 모듈을 사용할 수 없어 "
        "SQLite로 동작하고 있습니다."
    )


# =========================================================
# DB 상세정보
# =========================================================

try:
    db_info = database.get_database_info()
except Exception:
    db_info = {}


with st.expander("🔧 DB 연결 상세정보"):

    st.write(
        "Turso URL 설정:",
        "✅" if db_info.get("database_url_configured") else "❌"
    )

    st.write(
        "Turso Token 설정:",
        "✅" if db_info.get("auth_token_configured") else "❌"
    )

    st.write(
        "libSQL 모듈:",
        "✅" if db_info.get("libsql_available") else "❌"
    )

    st.write(
        "현재 사용 DB:",
        "Turso" if db_info.get("using_turso") else "SQLite"
    )

    connection_test = db_info.get("connection_test")

    if connection_test:

        if connection_test.get("connected"):
            st.success(
                connection_test.get(
                    "message",
                    "Turso 연결 성공"
                )
            )
        else:
            st.error(
                connection_test.get(
                    "message",
                    "Turso 연결 실패"
                )
            )

            if connection_test.get("error"):
                st.caption(
                    connection_test.get("error")
                )


# =========================================================
# DB 저장 용량
# =========================================================

st.subheader("💾 DB 저장 용량")

try:
    usage = database.get_storage_usage()
except Exception as e:
    usage = {
        "success": False,
        "size_mb": 0,
        "size_gb": 0,
        "storage_type": "SQLite",
        "error": str(e)
    }


if usage.get("success"):

    u1, u2 = st.columns(2)

    u1.metric(
        "현재 DB 저장 크기",
        f"{float(usage.get('size_mb', 0)):.2f} MB"
    )

    u2.metric(
        "저장 방식",
        usage.get("storage_type", "SQLite")
    )

    if usage.get("storage_type") == "Turso":

        st.caption(
            "현재 표시되는 크기는 연결된 "
            "Turso DB의 논리적 저장 크기입니다."
        )

    else:

        st.caption(
            f"현재 SQLite DB 저장 크기: "
            f"{float(usage.get('size_gb', 0)):.4f} GB"
        )

else:

    st.error("DB 저장 용량을 확인할 수 없습니다.")

    if usage.get("error"):
        st.caption(usage.get("error"))


# =========================================================
# 업체별 저장량
# =========================================================

st.subheader("🏢 업체별 저장 경기 수")

try:
    company_counts = database.get_company_counts() or {}
except Exception:
    company_counts = {}


if company_counts:

    st.dataframe(
        [
            {
                "업체": company,
                "저장 경기 수": int(count)
            }
            for company, count
            in company_counts.items()
        ],
        use_container_width=True,
        hide_index=True
    )

else:

    st.info("저장된 업체별 데이터가 없습니다.")


# =========================================================
# 현재 수집 상태
# =========================================================

try:
    state = database.get_collection_state() or {}
except Exception:
    state = {}


last_id = state.get("last_completed_id")

try:
    last_id = int(last_id) if last_id is not None else 0
except Exception:
    last_id = 0


saved_start = state.get("start_id")
saved_end = state.get("end_id")


try:
    saved_start = (
        int(saved_start)
        if saved_start is not None
        else None
    )
except Exception:
    saved_start = None


try:
    saved_end = (
        int(saved_end)
        if saved_end is not None
        else None
    )
except Exception:
    saved_end = None


# =========================================================
# Scoreman 자동수집
# =========================================================

st.divider()

st.subheader("📥 Scoreman 경기 ID 구간 자동수집")


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
        value=int(default_start),
        step=1,
        key="start_id"
    )


with col2:

    default_end = (
        saved_end
        if saved_end and saved_end >= start_id
        else start_id
    )

    end_id = st.number_input(
        "마지막 ID",
        min_value=1,
        value=int(default_end),
        step=1,
        key="end_id"
    )


if end_id >= start_id:

    st.caption(
        f"검색 대상: {end_id - start_id + 1:,}개"
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
        f"📌 마지막 성공 완료 ID: {last_id:,}"
    )

    st.caption(
        f"다음 자동 시작 ID: {last_id + 1:,}"
    )

else:

    st.caption(
        "아직 성공적으로 저장된 완료 ID가 없습니다."
    )


# =========================================================
# 업체 목록
# =========================================================

st.subheader("🏢 수집 업체")

try:
    companies = analysis.get_company_list() or []
except Exception:
    companies = []


mode = st.radio(
    "수집 방식",
    [
        "전체 업체 자동수집",
        "특정 업체만 수집"
    ],
    horizontal=True,
    key="collection_mode"
)


if mode == "특정 업체만 수집":

    selected = st.multiselect(
        "🏢 업체 선택",
        companies,
        key="collector_companies",
        placeholder="수집할 업체를 선택하세요"
    )

else:

    selected = None

    st.success(
        "전체 업체 자동수집을 사용합니다."
    )


# =========================================================
# 요청 간격
# =========================================================

delay = st.number_input(
    "요청 간격(초)",
    min_value=0.1,
    max_value=10.0,
    value=0.5,
    step=0.1,
    format="%.1f",
    key="collector_delay"
)


# =========================================================
# 자동 이어받기
# =========================================================

if last_id > 0:

    if st.button(
        f"🔄 마지막 성공 지점부터 자동 이어받기 "
        f"({last_id + 1:,} → {end_id:,})",
        use_container_width=True,
        key="resume_button"
    ):

        if end_id < last_id + 1:

            st.warning(
                "이어받을 경기 ID가 없습니다."
            )

        else:

            try:

                ok = collector.start_background_collection(
                    int(last_id + 1),
                    int(end_id),
                    selected,
                    float(delay),
                    resume=False
                )

                if ok:

                    st.success(
                        f"{last_id + 1:,}번부터 "
                        f"{end_id:,}번까지 "
                        "백그라운드 수집을 시작했습니다."
                    )

                    time.sleep(0.5)
                    st.rerun()

                else:

                    st.warning(
                        "이미 수집 작업이 실행 중입니다."
                    )

            except TypeError:

                try:

                    ok = collector.start_background_collection(
                        int(last_id + 1),
                        int(end_id),
                        selected,
                        float(delay)
                    )

                    if ok:

                        st.success(
                            "백그라운드 수집을 시작했습니다."
                        )

                        time.sleep(0.5)
                        st.rerun()

                    else:

                        st.warning(
                            "이미 수집 작업이 실행 중입니다."
                        )

                except Exception as e:

                    st.error(
                        f"수집 시작 오류: {e}"
                    )

            except Exception as e:

                st.error(
                    f"수집 시작 오류: {e}"
                )


# =========================================================
# 시작 / 중지
# =========================================================

b1, b2 = st.columns(2)


with b1:

    if st.button(
        "🚀 수집 시작",
        use_container_width=True,
        key="start_collection"
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

            try:

                ok = collector.start_background_collection(
                    int(start_id),
                    int(end_id),
                    selected,
                    float(delay),
                    resume=True
                )

                if ok:

                    st.success(
                        "백그라운드 수집을 시작했습니다."
                    )

                    time.sleep(0.5)
                    st.rerun()

                else:

                    st.warning(
                        "이미 수집 중이거나 "
                        "수집할 ID가 없습니다."
                    )

            except TypeError:

                try:

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

                        time.sleep(0.5)
                        st.rerun()

                    else:

                        st.warning(
                            "이미 수집 중입니다."
                        )

                except Exception as e:

                    st.error(
                        f"수집 시작 오류: {e}"
                    )

            except Exception as e:

                st.error(
                    f"수집 시작 오류: {e}"
                )


with b2:

    if st.button(
        "🛑 수집 중지",
        use_container_width=True,
        key="stop_collection"
    ):

        try:

            stopped = (
                collector.stop_background_collection()
            )

            if stopped:

                st.warning(
                    "🛑 수집 중지 요청을 보냈습니다."
                )

            else:

                st.info(
                    "현재 실행 중인 수집 작업이 없습니다."
                )

        except Exception as e:

            st.error(
                f"중지 오류: {e}"
            )


# =========================================================
# Collector 작업 상태
# =========================================================

try:

    job = collector.get_job_status() or {}

except Exception as e:

    job = {
        "running": False,
        "finished": False,
        "error": str(e)
    }


# =========================================================
# 수집 중
# =========================================================

if job.get("running"):

    st.divider()

    st.subheader("🟢 현재 수집 중")

    total = int(
        job.get("total", 0) or 0
    )

    current = int(
        job.get("current", 0) or 0
    )

    success = int(
        job.get("success", 0) or 0
    )

    exists = int(
        job.get("exists", 0) or 0
    )

    failed = int(
        job.get("failed", 0) or 0
    )

    no_odds = int(
        job.get("no_odds", 0) or 0
    )

    odds_count = int(
        job.get("odds", 0) or 0
    )


    progress = (
        current / total
        if total > 0
        else 0
    )


    st.progress(
        min(
            max(progress, 0),
            1
        )
    )

    st.caption(
        f"진행률 {progress * 100:.1f}%"
    )


    a, b, c, d, e, f = st.columns(6)


    a.metric(
        "현재",
        f"{current:,} / {total:,}"
    )

    b.metric(
        "신규",
        f"{success:,}"
    )

    c.metric(
        "기존",
        f"{exists:,}"
    )

    d.metric(
        "실패",
        f"{failed:,}"
    )

    e.metric(
        "배당 없음",
        f"{no_odds:,}"
    )

    f.metric(
        "최종배당",
        f"{odds_count:,}"
    )


    current_id = job.get("current_id")

    if current_id:

        st.info(
            f"🔎 현재 처리 ID: {int(current_id):,}"
        )


    current_last = job.get(
        "last_completed_id"
    )

    if current_last:

        st.success(
            f"📌 마지막 완료 ID: "
            f"{int(current_last):,}"
        )


    # -----------------------------------------------------
    # 로그 표시 여부
    # -----------------------------------------------------

    if "show_collection_log" not in st.session_state:

        st.session_state[
            "show_collection_log"
        ] = False


    if st.button(
        (
            "📝 로그 보기"
            if not st.session_state["show_collection_log"]
            else "🙈 로그 숨기기"
        ),
        key="running_log"
    ):

        st.session_state[
            "show_collection_log"
        ] = not st.session_state[
            "show_collection_log"
        ]

        st.rerun()


    if st.session_state["show_collection_log"]:

        st.text_area(
            "수집 로그",
            job.get("log", ""),
            height=300,
            key="running_log_text"
        )


    # -----------------------------------------------------
    # 자동 새로고침
    # -----------------------------------------------------

    time.sleep(1)

    st.rerun()


# =========================================================
# 수집 완료
# =========================================================

elif job.get("finished"):

    st.divider()

    st.subheader("✅ 마지막 수집 결과")


    if job.get("stopped"):

        st.warning(
            "🛑 수집이 중지되었습니다."
        )

    else:

        st.success(
            "✅ 수집 작업이 완료되었습니다."
        )


    result = job.get("result") or {}


    if result:

        a, b, c, d, e, f = st.columns(6)


        a.metric(
            "전체",
            f"{int(result.get('total', 0) or 0):,}"
        )

        b.metric(
            "신규",
            f"{int(result.get('success', 0) or 0):,}"
        )

        c.metric(
            "기존",
            f"{int(result.get('exists', 0) or 0):,}"
        )

        d.metric(
            "실패",
            f"{int(result.get('failed', 0) or 0):,}"
        )

        e.metric(
            "배당 없음",
            f"{int(result.get('no_odds', 0) or 0):,}"
        )

        f.metric(
            "최종배당",
            f"{int(result.get('odds', 0) or 0):,}"
        )


    finished_last = job.get(
        "last_completed_id"
    )


    if finished_last:

        st.success(
            f"📌 마지막 성공 완료 ID: "
            f"{int(finished_last):,}"
        )


    if job.get("error"):

        st.error(
            job.get("error")
        )


    if "show_finished_log" not in st.session_state:

        st.session_state[
            "show_finished_log"
        ] = False


    if st.button(
        (
            "📝 로그 보기"
            if not st.session_state["show_finished_log"]
            else "🙈 로그 숨기기"
        ),
        key="finished_log"
    ):

        st.session_state[
            "show_finished_log"
        ] = not st.session_state[
            "show_finished_log"
        ]

        st.rerun()


    if st.session_state["show_finished_log"]:

        st.text_area(
            "수집 로그",
            job.get("log", ""),
            height=300,
            key="finished_log_text"
        )


# =========================================================
# 저장된 경기 전체 조회
# =========================================================

st.divider()

st.subheader("📋 저장된 경기 전체 조회")


try:

    matches = database.get_all_matches() or []

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
        "저장된 경기가 없습니다."
    )


# =========================================================
# 경기별 최종배당
# =========================================================

st.subheader("🔎 경기별 최종배당 조회")


lookup_default = (
    last_id
    if last_id > 0
    else int(start_id)
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
    use_container_width=True,
    key="lookup_match"
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
                    <b>{int(lookup_id):,}</b>

                    <br>

                    경기일:
                    <b>{match.get("match_date", "")}</b>

                    <br>

                    실제 스코어:
                    <b>
                        {match.get("home_score", "")}
                        :
                        {match.get("away_score", "")}
                    </b>

                    <br>

                    실제 결과:
                    <b>{match.get("result", "")}</b>

                </div>

            </div>
            """,
            unsafe_allow_html=True
        )


        try:

            odds = (
                database.get_odds_by_match(
                    lookup_id
                )
                or []
            )

        except Exception as e:

            odds = []

            st.error(
                f"배당 조회 오류: {e}"
            )


        if not odds:

            st.warning(
                "저장된 최종배당이 없습니다."
            )

        else:

            st.success(
                f"저장된 최종배당 {len(odds):,}개"
            )


            st.dataframe(
                [
                    {
                        "업체": row.get(
                            "bookmaker",
                            ""
                        ),

                        "업체ID": row.get(
                            "bookmaker_id",
                            ""
                        ),

                        "승": row.get(
                            "home_odds"
                        ),

                        "무": row.get(
                            "draw_odds"
                        ),

                        "패": row.get(
                            "away_odds"
                        )
                    }
                    for row in odds
                ],
                use_container_width=True,
                hide_index=True
            )


# =========================================================
# 동일배당 검색 / 분석
# =========================================================

st.divider()

st.subheader(
    "📈 승무패 배당으로 과거 경기 검색"
)


try:

    analysis_companies_list = (
        analysis.get_company_list() or companies
    )

except Exception:

    analysis_companies_list = companies


analysis_companies = st.multiselect(
    "🏢 분석 업체",
    analysis_companies_list,
    key="analysis_companies",
    placeholder="분석할 업체를 선택하세요"
)


if analysis_companies:

    st.markdown(
        "### 배당 입력"
    )


    odds_input = {}


    for company in analysis_companies:

        st.markdown(
            f"#### 🏢 {company}"
        )


        a, b, c = st.columns(3)


        with a:

            home = st.number_input(
                f"{company} 승",
                min_value=0.01,
                value=2.00,
                step=0.01,
                format="%.2f",
                key=f"{company}_home"
            )


        with b:

            draw = st.number_input(
                f"{company} 무",
                min_value=0.01,
                value=3.00,
                step=0.01,
                format="%.2f",
                key=f"{company}_draw"
            )


        with c:

            away = st.number_input(
                f"{company} 패",
                min_value=0.01,
                value=3.00,
                step=0.01,
                format="%.2f",
                key=f"{company}_away"
            )


        odds_input[company] = {
            "home": home,
            "draw": draw,
            "away": away
        }


    tolerance = st.number_input(
        "배당 허용 오차",
        min_value=0.000,
        max_value=0.100,
        value=0.001,
        step=0.001,
        format="%.3f",
        key="analysis_tolerance"
    )


    if st.button(
        "🔎 동일배당 경기 검색",
        use_container_width=True,
        key="search_odds"
    ):

        try:

            result = analysis.run_search(
                analysis_companies,
                odds_input,
                tolerance=tolerance
            )

        except TypeError:

            try:

                result = analysis.run_search(
                    analysis_companies,
                    odds_input
                )

            except Exception as e:

                result = {
                    "success": False,
                    "message": str(e),
                    "results": [],
                    "statistics": None
                }

        except Exception as e:

            result = {
                "success": False,
                "message": str(e),
                "results": [],
                "statistics": None
            }


        st.session_state[
            "analysis_result"
        ] = result


        if not result.get("success", False):

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
            ) or []


            stats = result.get(
                "statistics"
            )


            st.success(
                f"검색 경기: {len(results):,}개"
            )


            # =================================================
            # 통계
            # =================================================

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
                    "### 📊 실제 결과"
                )


                a, b, c = st.columns(3)


                a.metric(
                    "승",
                    f"{actual.get('home', 0):.2f}%"
                )

                b.metric(
                    "무",
                    f"{actual.get('draw', 0):.2f}%"
                )

                c.metric(
                    "패",
                    f"{actual.get('away', 0):.2f}%"
                )


                st.write(
                    "### 🎯 배당 기반 확률"
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


                st.write(
                    "### 📉 실제 결과 - 배당 확률"
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


                try:

                    highest = (
                        analysis.get_highest_shortage(
                            stats
                        )
                    )

                except Exception:

                    highest = None


                if highest:

                    st.success(
                        "🏆 가장 차이가 큰 결과: "
                        + highest
                    )


            # =================================================
            # 검색 결과
            # =================================================

            if results:

                st.write(
                    "### 📋 동일배당 경기 목록"
                )


                display_rows = []


                for row in results:

                    display_rows.append(
                        {
                            "경기 ID":
                                row.get(
                                    "schedule_id",
                                    ""
                                ),

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

                            "스코어":
                                (
                                    f"{row.get('home_score', '')}"
                                    ":"
                                    f"{row.get('away_score', '')}"
                                ),

                            "결과":
                                row.get(
                                    "result",
                                    ""
                                )
                        }
                    )


                st.dataframe(
                    display_rows,
                    use_container_width=True,
                    hide_index=True
                )


            else:

                st.info(
                    "조건에 맞는 경기가 없습니다."
                )


else:

    st.info(
        "🏢 분석할 업체를 하나 이상 선택하세요."
    )


# =========================================================
# 음성 기능
# =========================================================

st.divider()

st.subheader(
    "🎙️ 음성 배당 입력 / 결과 듣기"
)

st.caption(
    "폰에서 🎤 말하기를 누르고 "
    "예: 승 1.80 무 3.40 패 4.20"
)


try:

    from streamlit_mic_recorder import mic_recorder


    audio = mic_recorder(
        start_prompt="🎤 말하기",
        stop_prompt="⏹️ 녹음 중지",
        just_once=True,
        use_container_width=True,
        key="odds_voice"
    )


    if audio:

        st.success(
            "🎤 음성이 입력되었습니다."
        )

        st.audio(
            audio["bytes"],
            format="audio/wav"
        )


except ImportError:

    st.warning(
        "음성 녹음 기능은 "
        "streamlit-mic-recorder 설치 후 사용할 수 있습니다."
    )

except Exception as e:

    st.warning(
        f"마이크 기능 오류: {e}"
    )


# =========================================================
# 분석 결과 음성 듣기
# =========================================================

if st.button(
    "🔊 현재 분석 결과 듣기",
    use_container_width=True,
    key="speak_result"
):

    saved_result = st.session_state.get(
        "analysis_result"
    )


    if not saved_result:

        st.warning(
            "먼저 배당 검색을 실행하세요."
        )

    else:

        stats = saved_result.get(
            "statistics"
        )


        if not stats:

            st.warning(
                "음성으로 읽을 분석 결과가 없습니다."
            )

        else:

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


            try:

                highest = (
                    analysis.get_highest_shortage(
                        stats
                    )
                )

            except Exception:

                highest = None


            speech_text = (
                "배당 분석 결과입니다. "

                f"실제 승률은 "
                f"{actual.get('home', 0):.1f} 퍼센트입니다. "

                f"실제 무승률은 "
                f"{actual.get('draw', 0):.1f} 퍼센트입니다. "

                f"실제 패율은 "
                f"{actual.get('away', 0):.1f} 퍼센트입니다. "

                f"배당 기반 승 확률은 "
                f"{probability.get('home', 0):.1f} 퍼센트입니다. "

                f"배당 기반 무 확률은 "
                f"{probability.get('draw', 0):.1f} 퍼센트입니다. "

                f"배당 기반 패 확률은 "
                f"{probability.get('away', 0):.1f} 퍼센트입니다. "

                f"실제 결과와 배당 확률의 차이는 "

                f"승 {shortage.get('home', 0):+.1f} 퍼센트, "

                f"무 {shortage.get('draw', 0):+.1f} 퍼센트, "

                f"패 {shortage.get('away', 0):+.1f} 퍼센트입니다. "
            )


            if highest:

                speech_text += (
                    f"가장 차이가 큰 결과는 "
                    f"{highest}입니다."
                )


            encoded = base64.b64encode(
                speech_text.encode("utf-8")
            ).decode("ascii")


            st.markdown(
                f"""
                <script>

                (() => {{

                    const binary =
                        atob("{encoded}");

                    const bytes =
                        Uint8Array.from(
                            binary,
                            c => c.charCodeAt(0)
                        );

                    const text =
                        new TextDecoder("utf-8")
                        .decode(bytes);


                    if (
                        "speechSynthesis"
                        in window
                    ) {{

                        window.speechSynthesis.cancel();

                        const msg =
                            new SpeechSynthesisUtterance(
                                text
                            );

                        msg.lang = "ko-KR";
                        msg.rate = 1.0;
                        msg.pitch = 1.0;

                        window.speechSynthesis.speak(
                            msg
                        );

                    }} else {{

                        alert(
                            "이 브라우저는 음성 읽기를 지원하지 않습니다."
                        );

                    }}

                }})();

                </script>
                """,
                unsafe_allow_html=True
            )


# =========================================================
# 화면 새로고침
# =========================================================

st.divider()

if st.button(
    "🔄 화면 새로고침",
    use_container_width=True,
    key="refresh_page"
):

    st.rerun()
