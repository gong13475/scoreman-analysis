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
    'Scoreman 자동수집 · 해외업체 최종배당 · '
    '실제결과 · 확률분석 · Turso 영구저장'
    '</div>',
    unsafe_allow_html=True
)


# =========================================================
# DB 상태
# =========================================================

try:

    status = (
        database.get_database_status()
    )

except Exception as e:

    st.error(
        f"DB 상태 오류: {e}"
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

if (
    database.TURSO_DATABASE_URL
    and database.TURSO_AUTH_TOKEN
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
# DB 상태
# =========================================================

st.subheader(
    "🗄️ 데이터베이스 상태"
)

if (
    database.TURSO_DATABASE_URL
    and database.TURSO_AUTH_TOKEN
):

    st.success(
        "🟢 Turso DB 연결 정상"
    )

else:

    st.warning(
        "🟡 로컬 SQLite fallback 모드"
    )

    st.caption(
        "TURSO_DATABASE_URL / "
        "TURSO_AUTH_TOKEN 환경변수를 설정하면 "
        "Turso를 사용합니다."
    )


# =========================================================
# DB 저장 용량
# =========================================================

st.subheader(
    "💾 DB 저장 용량"
)

try:

    usage = (
        database.get_storage_usage()
    )

    if usage.get("success"):

        size_mb = float(
            usage.get(
                "size_mb",
                0
            )
        )

        size_gb = float(
            usage.get(
                "size_gb",
                0
            )
        )

        storage_type = usage.get(
            "storage",
            "Unknown"
        )

        st.metric(
            "현재 DB 저장 크기",
            f"{size_mb:.2f} MB"
        )

        st.caption(
            f"저장 방식: {storage_type}"
        )

        if storage_type == "Turso":

            st.info(
                "ℹ️ 위 크기는 현재 DB에서 "
                "확인 가능한 저장 데이터 크기입니다. "
                "Turso 무료 플랜의 실제 사용량 및 "
                "남은 한도는 Turso 콘솔에서 "
                "확인하는 것이 정확합니다."
            )

        else:

            st.caption(
                f"현재 SQLite DB 저장 크기: "
                f"{size_gb:.4f} GB"
            )

    else:

        st.warning(
            "DB 저장 용량을 확인할 수 없습니다."
        )

except Exception as e:

    st.warning(
        f"DB 저장 용량 확인 오류: {e}"
    )


# =========================================================
# 업체별 저장량
# =========================================================

st.subheader(
    "🏢 업체별 저장 경기 수"
)

try:

    company_counts = (
        database.get_company_counts()
        or {}
    )

except Exception:

    company_counts = {}


if company_counts:

    st.dataframe(
        [
            {
                "업체": company,
                "저장 경기 수": int(
                    count
                )
            }
            for company, count
            in company_counts.items()
        ],
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "저장된 업체별 데이터가 없습니다."
    )


# =========================================================
# 현재 저장 상태
# =========================================================

state = (
    database.get_collection_state()
)

last_id = state.get(
    "last_completed_id"
)

try:

    last_id = (
        int(last_id)
        if last_id is not None
        else 0
    )

except Exception:

    last_id = 0


saved_start = state.get(
    "start_id"
)

saved_end = state.get(
    "end_id"
)


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
# 수집
# =========================================================

st.subheader(
    "📥 Scoreman 경기 ID 구간 자동수집"
)

col1, col2 = st.columns(2)


with col1:

    default_start = (
        saved_start
        if saved_start
        and saved_start > 0
        else 3001118
    )

    start_id = st.number_input(
        "시작 ID",
        min_value=1,
        value=default_start,
        step=1
    )


with col2:

    default_end = (
        saved_end
        if saved_end
        and saved_end >= start_id
        else start_id
    )

    end_id = st.number_input(
        "마지막 ID",
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
# 마지막 성공
# =========================================================

if last_id > 0:

    st.info(
        f"📌 마지막 성공 완료 ID: "
        f"{last_id:,}"
    )

    st.caption(
        f"다음 자동 시작 ID: "
        f"{last_id + 1:,}"
    )

else:

    st.caption(
        "아직 성공적으로 저장된 완료 ID가 없습니다."
    )


# =========================================================
# 업체
# =========================================================

st.subheader(
    "🏢 수집 업체"
)

try:

    companies = (
        analysis.get_company_list()
        or []
    )

except Exception:

    companies = []


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


st.success(
    "전체 업체 선택 시 Scoreman에서 확인되는 "
    "해외업체 최종배당을 자동 저장합니다."
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
# 자동 이어받기
# =========================================================

if last_id > 0:

    if st.button(
        f"🔄 마지막 성공 지점부터 자동 이어받기 "
        f"({last_id + 1:,} → {end_id:,})",
        use_container_width=True
    ):

        if end_id < last_id + 1:

            st.warning(
                "이어받을 경기 ID가 없습니다."
            )

        else:

            ok = (
                collector.start_background_collection(
                    last_id + 1,
                    end_id,
                    selected,
                    float(delay),
                    resume=False
                )
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

            ok = (
                collector.start_background_collection(
                    int(start_id),
                    int(end_id),
                    selected,
                    float(delay),
                    resume=True
                )
            )

            if ok:

                st.success(
                    "백그라운드 수집을 시작했습니다."
                )

            else:

                st.warning(
                    "이미 수집 중이거나 "
                    "수집할 ID가 없습니다."
                )


with b2:

    if st.button(
        "🛑 수집 중지",
        use_container_width=True
    ):

        if (
            collector.stop_background_collection()
        ):

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

    job = (
        collector.get_job_status()
    )

except Exception:

    job = {
        "running": False,
        "finished": False
    }


if job.get("running"):

    st.subheader(
        "🟢 현재 수집 중"
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

    st.caption(
        f"{progress * 100:.1f}%"
    )

    a, b, c, d, e = (
        st.columns(5)
    )

    a.metric(
        "현재",
        f"{current:,} / {total:,}"
    )

    b.metric(
        "신규",
        f"{int(job.get('success', 0) or 0):,}"
    )

    c.metric(
        "실패",
        f"{int(job.get('failed', 0) or 0):,}"
    )

    d.metric(
        "배당 없음",
        f"{int(job.get('no_odds', 0) or 0):,}"
    )

    e.metric(
        "최종배당",
        f"{int(job.get('odds', 0) or 0):,}"
    )

    current_last = job.get(
        "last_completed_id"
    )

    if current_last:

        st.info(
            f"📌 마지막 완료 ID: "
            f"{int(current_last):,}"
        )

    if (
        "show_collection_log"
        not in st.session_state
    ):

        st.session_state[
            "show_collection_log"
        ] = False


    if st.button(
        (
            "📝 로그 보기"
            if not st.session_state[
                "show_collection_log"
            ]
            else
            "🙈 로그 숨기기"
        ),
        key="running_log"
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

        a, b, c, d, e = (
            st.columns(5)
        )

        a.metric(
            "전체",
            f"{int(result.get('total', 0)):,}"
        )

        b.metric(
            "신규",
            f"{int(result.get('success', 0)):,}"
        )

        c.metric(
            "기존",
            f"{int(result.get('exists', 0)):,}"
        )

        d.metric(
            "실패",
            f"{int(result.get('failed', 0)):,}"
        )

        e.metric(
            "배당 없음",
            f"{int(result.get('no_odds', 0)):,}"
        )

        st.metric(
            "최종배당",
            f"{int(result.get('odds', 0)):,}"
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

    if (
        "show_finished_log"
        not in st.session_state
    ):

        st.session_state[
            "show_finished_log"
        ] = False


    if st.button(
        (
            "📝 로그 보기"
            if not st.session_state[
                "show_finished_log"
            ]
            else
            "🙈 로그 숨기기"
        ),
        key="finished_log"
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
            "수집 로그",
            job.get(
                "log",
                ""
            ),
            height=300
        )


# =========================================================
# 저장된 경기
# =========================================================

st.divider()

st.subheader(
    "📋 저장된 경기 전체 조회"
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
        "저장된 경기가 없습니다."
    )


# =========================================================
# 경기별 최종배당
# =========================================================

st.subheader(
    "🔎 경기별 최종배당 조회"
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

        odds = (
            database.get_odds_by_match(
                lookup_id
            )
            or []
        )

        if not odds:

            st.warning(
                "저장된 최종배당이 없습니다."
            )

        else:

            st.success(
                f"저장된 최종배당 "
                f"{len(odds)}개"
            )

            st.dataframe(
                [
                    {
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
                    }
                    for row in odds
                ],
                use_container_width=True,
                hide_index=True
            )


# =========================================================
# 수동 배당 검색 / 분석
# =========================================================

st.subheader(
    "📈 승무패 배당으로 경기 검색"
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
            "home": h,
            "draw": d,
            "away": aw
        }


    if st.button(
        "🔎 검색",
        use_container_width=True,
        key="odds_search"
    ):

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


        st.session_state[
            "analysis_result"
        ] = result


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
                f"검색 경기: "
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
                    "### 실제 결과 확률"
                )

                a, b, c = (
                    st.columns(3)
                )

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
                    "### 배당 기반 확률"
                )

                a, b, c = (
                    st.columns(3)
                )

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
                    "### 실제 결과 - 배당 확률"
                )

                a, b, c = (
                    st.columns(3)
                )

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

                    st.success(
                        "🏆 가장 차이가 큰 결과: "
                        + highest
                    )


            if results:

                st.write(
                    "### 📋 검색 결과"
                )

                st.dataframe(
                    [
                        {
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
                        }
                        for row in results
                    ],
                    use_container_width=True,
                    hide_index=True
                )

            else:

                st.info(
                    "조건에 맞는 경기가 없습니다."
                )


# =========================================================
# 음성 입력
# =========================================================

st.divider()

st.subheader(
    "🎙️ 음성 배당 입력 / 결과 듣기"
)

st.caption(
    "📱 휴대폰에서는 🎤 말하기 버튼을 누르고 "
    "마이크 권한을 허용하세요."
)


try:

    from streamlit_mic_recorder import (
        mic_recorder
    )

    audio = mic_recorder(
        start_prompt="🎤 말하기",
        stop_prompt="⏹️ 녹음 중지",
        just_once=True,
        use_container_width=True,
        key="odds_voice"
    )

    if audio:

        st.success(
            "🎤 음성 녹음 완료"
        )

        st.audio(
            audio["bytes"],
            format="audio/wav"
        )

        st.info(
            "음성이 녹음되었습니다. "
            "아래 배당 입력값을 확인하고 "
            "분석 버튼을 누르세요."
        )

except ImportError:

    st.error(
        "마이크 기능을 사용하려면 "
        "streamlit-mic-recorder를 설치하세요."
    )

    st.code(
        "pip install streamlit-mic-recorder",
        language="bash"
    )


# =========================================================
# 음성 배당값
# =========================================================

st.markdown(
    "### 🎤 배당 입력"
)

voice_col1, voice_col2, voice_col3 = (
    st.columns(3)
)


with voice_col1:

    voice_home = st.number_input(
        "승 배당",
        min_value=0.01,
        value=1.80,
        step=0.01,
        key="voice_home_odds"
    )


with voice_col2:

    voice_draw = st.number_input(
        "무 배당",
        min_value=0.01,
        value=3.40,
        step=0.01,
        key="voice_draw_odds"
    )


with voice_col3:

    voice_away = st.number_input(
        "패 배당",
        min_value=0.01,
        value=4.20,
        step=0.01,
        key="voice_away_odds"
    )


# =========================================================
# 음성 입력값 분석
# =========================================================

if st.button(
    "📊 입력한 배당 분석",
    use_container_width=True,
    key="voice_analyze"
):

    selected_voice_companies = (
        analysis_companies
        if analysis_companies
        else companies[:1]
    )

    if not selected_voice_companies:

        st.warning(
            "분석할 업체가 없습니다."
        )

    else:

        voice_odds = {}

        for company in (
            selected_voice_companies
        ):

            voice_odds[company] = {
                "home": float(
                    voice_home
                ),
                "draw": float(
                    voice_draw
                ),
                "away": float(
                    voice_away
                )
            }

        try:

            voice_result = (
                analysis.run_search(
                    selected_voice_companies,
                    voice_odds
                )
            )

            st.session_state[
                "analysis_result"
            ] = voice_result


            if voice_result.get(
                "success",
                False
            ):

                st.success(
                    f"검색 경기: "
                    f"{len(voice_result.get('results', [])):,}개"
                )

                voice_stats = (
                    voice_result.get(
                        "statistics"
                    )
                )

                if voice_stats:

                    actual = (
                        voice_stats.get(
                            "actual",
                            {}
                        )
                    )

                    probability = (
                        voice_stats.get(
                            "probability",
                            {}
                        )
                    )

                    shortage = (
                        voice_stats.get(
                            "shortage",
                            {}
                        )
                    )


                    st.markdown(
                        "### 📈 분석 결과"
                    )

                    a, b, c = (
                        st.columns(3)
                    )

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


                    a, b, c = (
                        st.columns(3)
                    )

                    a.metric(
                        "배당 승 확률",
                        f"{probability.get('home', 0):.2f}%"
                    )

                    b.metric(
                        "배당 무 확률",
                        f"{probability.get('draw', 0):.2f}%"
                    )

                    c.metric(
                        "배당 패 확률",
                        f"{probability.get('away', 0):.2f}%"
                    )


                    a, b, c = (
                        st.columns(3)
                    )

                    a.metric(
                        "승 차이",
                        f"{shortage.get('home', 0):+.2f}%"
                    )

                    b.metric(
                        "무 차이",
                        f"{shortage.get('draw', 0):+.2f}%"
                    )

                    c.metric(
                        "패 차이",
                        f"{shortage.get('away', 0):+.2f}%"
                    )


                    highest = (
                        analysis.get_highest_shortage(
                            voice_stats
                        )
                    )

                    if highest:

                        st.success(
                            "🏆 가장 차이가 큰 결과: "
                            + highest
                        )

            else:

                st.error(
                    voice_result.get(
                        "message",
                        "분석 결과가 없습니다."
                    )
                )

        except Exception as e:

            st.error(
                f"배당 분석 오류: {e}"
            )


# =========================================================
# 결과 듣기
# =========================================================

st.markdown(
    "### 🔊 결과 듣기"
)

if st.button(
    "🔊 현재 분석 결과 듣기",
    use_container_width=True,
    key="speak_result"
):

    saved_result = (
        st.session_state.get(
            "analysis_result"
        )
    )

    if not saved_result:

        st.warning(
            "먼저 배당 검색 또는 "
            "음성 배당 분석을 실행하세요."
        )

    else:

        stats = (
            saved_result.get(
                "statistics"
            )
        )

        if not stats:

            st.warning(
                "읽어줄 분석 결과가 없습니다."
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

            highest = (
                analysis.get_highest_shortage(
                    stats
                )
            )

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
                f"승 차이는 "
                f"{shortage.get('home', 0):+.1f} 퍼센트입니다. "
                f"무 차이는 "
                f"{shortage.get('draw', 0):+.1f} 퍼센트입니다. "
                f"패 차이는 "
                f"{shortage.get('away', 0):+.1f} 퍼센트입니다. "
                f"가장 차이가 큰 결과는 "
                f"{highest}입니다."
            )

            st.markdown(
                f"""
                <script>
                (() => {{

                    const text =
                        {speech_text!r};

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
                    }}

                }})();
                </script>
                """,
                unsafe_allow_html=True
            )

            st.success(
                "🔊 분석 결과를 읽었습니다."
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
