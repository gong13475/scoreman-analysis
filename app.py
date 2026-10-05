import re

import streamlit as st

import database
import scoreman_crawler
import analysis


# =========================================================
# 페이지 설정
# =========================================================

st.set_page_config(

    page_title=
        "스코어맨 배당 분석",

    page_icon=
        "⚽",

    layout=
        "wide"
)


# =========================================================
# CSS
# =========================================================

st.markdown(
    """
    <style>

    .main .block-container {

        padding-left: 1rem;
        padding-right: 1rem;
        max-width: 1400px;
    }

    @media (max-width: 768px) {

        .main .block-container {

            padding-left: 0.7rem;
            padding-right: 0.7rem;
        }

        h1 {
            font-size: 1.65rem !important;
        }

        h2 {
            font-size: 1.35rem !important;
        }

        h3 {
            font-size: 1.15rem !important;
        }

        .stButton button {

            min-height: 48px;
            font-size: 16px;
        }

        .stNumberInput input {

            font-size: 16px;
        }
    }


    .odds-card {

        border: 1px solid #dddddd;
        border-radius: 14px;
        padding: 14px;
        margin-bottom: 10px;
        background: #ffffff;
        box-shadow:
            0 1px 4px rgba(0,0,0,0.05);
    }


    .odds-company {

        font-size: 18px;
        font-weight: 700;
        margin-bottom: 12px;
    }


    .odds-row {

        display: flex;
        justify-content: space-between;
        gap: 8px;
        text-align: center;
    }


    .odds-item {

        flex: 1;
        border-radius: 10px;
        padding: 10px 4px;
        background: #f5f6f8;
    }


    .odds-label {

        display: block;
        font-size: 13px;
        color: #666666;
        margin-bottom: 4px;
    }


    .odds-value {

        display: block;
        font-size: 20px;
        font-weight: 700;
        color: #111111;
    }


    .match-card {

        border: 1px solid #dddddd;
        border-radius: 14px;
        padding: 16px;
        margin-bottom: 14px;
        background: #ffffff;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# DB
# =========================================================

try:

    database.init_database()

    db_ok = True

except Exception as e:

    db_ok = False

    st.error(
        "❌ DB 연결 오류"
    )

    st.code(
        str(e)
    )


# =========================================================
# 세션
# =========================================================

if "search_result" not in st.session_state:

    st.session_state.search_result = None


# =========================================================
# 제목
# =========================================================

st.title(
    "⚽ 전종목 해외배당 분석"
)


st.caption(
    "스코어맨 자동수집 · "
    "해외업체 최종배당 · "
    "실제결과 · "
    "확률분석 · "
    "Turso 영구저장"
)


# =========================================================
# DB 상태
# =========================================================

if db_ok:

    try:

        match_count = (
            database.get_match_count()
        )

        odds_count = (
            database.get_odds_count()
        )

        company_count = len(
            database.get_company_names()
        )

        st.success(
            "🟢 Turso 영구 DB 연결됨"
        )

    except Exception as e:

        match_count = 0
        odds_count = 0
        company_count = 0

        st.error(
            "DB 조회 오류"
        )

        st.code(
            str(e)
        )

else:

    match_count = 0
    odds_count = 0
    company_count = 0


# =========================================================
# DB Metric
# =========================================================

c1, c2, c3, c4 = st.columns(4)


with c1:

    st.metric(
        "저장 경기",
        f"{match_count:,}"
    )


with c2:

    st.metric(
        "저장 최종배당",
        f"{odds_count:,}"
    )


with c3:

    st.metric(
        "실제 저장 업체",
        f"{company_count:,}"
    )


with c4:

    st.metric(
        "DB",
        "Turso"
    )


# =========================================================
# DB 상세
# =========================================================

with st.expander(
    "🗄️ Turso DB 상태"
):

    storage = (
        database.get_storage_usage()
    )

    c1, c2, c3 = st.columns(3)


    with c1:

        st.metric(
            "저장 경기",
            f"{match_count:,}"
        )


    with c2:

        st.metric(
            "저장 최종배당",
            f"{odds_count:,}"
        )


    with c3:

        st.metric(
            "저장 업체",
            f"{company_count:,}"
        )


    if storage.get("success"):

        st.metric(
            "DB 사용량",
            f"{storage.get('size_mb', 0):.2f} MB"
        )

    else:

        st.warning(
            storage.get(
                "message",
                "용량 조회 실패"
            )
        )


st.divider()


# =========================================================
# 자동수집
# =========================================================

st.header(
    "📥 스코어맨 경기 자동수집"
)


st.info(
    "경기 ID 범위를 입력하면 "
    "경기정보와 완료 경기의 최종배당을 "
    "자동으로 저장합니다."
)


# =========================================================
# ID
# =========================================================

c1, c2 = st.columns(2)


with c1:

    start_id = st.number_input(

        "시작 경기 ID",

        min_value=1,

        value=2005000,

        step=1,

        format="%d"
    )


with c2:

    end_id = st.number_input(

        "마지막 경기 ID",

        min_value=1,

        value=3001118,

        step=1,

        format="%d"
    )


if end_id >= start_id:

    total_ids = (
        int(end_id)
        - int(start_id)
        + 1
    )

else:

    total_ids = 0


st.write(
    f"검색 대상: **{total_ids:,}개 경기 ID**"
)


# =========================================================
# 업체
# =========================================================

st.subheader(
    "🏢 수집할 해외업체 선택"
)


crawl_mode = st.radio(

    "수집 방식",

    [
        "전체 업체 자동수집",
        "특정 업체만 수집"
    ],

    horizontal=True
)


selected_crawl_companies = []


if crawl_mode == "전체 업체 자동수집":

    st.success(
        "✅ Scoreman에서 제공하는 "
        "최종배당 업체를 자동수집합니다."
    )

else:

    try:

        companies = (
            analysis.get_company_list()
        )

    except Exception:

        companies = []


    selected_crawl_companies = st.multiselect(

        "수집 업체",

        options=companies,

        default=[]
    )


    if selected_crawl_companies:

        st.success(
            "선택 업체: "
            + " / ".join(
                selected_crawl_companies
            )
        )

    else:

        st.warning(
            "업체를 1개 이상 선택하세요."
        )


# =========================================================
# Delay
# =========================================================

delay = st.number_input(

    "요청 간격(초)",

    min_value=0.10,

    max_value=5.00,

    value=0.50,

    step=0.10,

    format="%.2f"
)


# =========================================================
# 현재 상태
# =========================================================

status = (
    scoreman_crawler.get_job_status()
)


# =========================================================
# 수집 버튼
# =========================================================

if status.get("running"):

    st.error(
        "🔴 현재 수집중입니다."
    )


    if st.button(
        "🛑 수집 중지",
        use_container_width=True
    ):

        if (
            scoreman_crawler
            .stop_background_collection()
        ):

            st.warning(
                "🛑 중지 요청을 보냈습니다."
            )

        st.rerun()


else:

    if st.button(

        "🚀 백그라운드 수집 시작",

        type="primary",

        use_container_width=True
    ):

        if not db_ok:

            st.error(
                "DB 연결을 확인하세요."
            )

        elif end_id < start_id:

            st.error(
                "마지막 ID가 시작 ID보다 작습니다."
            )

        elif (

            crawl_mode ==
            "특정 업체만 수집"

            and

            not selected_crawl_companies
        ):

            st.error(
                "수집 업체를 선택하세요."
            )

        else:

            companies_for_crawler = (

                selected_crawl_companies

                if crawl_mode ==
                "특정 업체만 수집"

                else None
            )


            try:

                started = (
                    scoreman_crawler
                    .start_background_collection(

                        int(start_id),

                        int(end_id),

                        companies_for_crawler,

                        float(delay)
                    )
                )


                if started:

                    st.success(
                        "🚀 수집을 시작했습니다."
                    )

                    st.rerun()

                else:

                    st.warning(
                        "이미 수집중입니다."
                    )

            except Exception as e:

                st.error(
                    "수집 시작 오류"
                )

                st.code(
                    str(e)
                )


# =========================================================
# 진행상황
# =========================================================

status = (
    scoreman_crawler.get_job_status()
)


if (
    status.get("running")
    or status.get("finished")
):

    st.divider()

    st.subheader(
        "📡 수집 진행상황"
    )


    total = int(
        status.get(
            "total",
            0
        )
    )


    current = int(
        status.get(
            "current",
            0
        )
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


    if status.get("running"):

        st.error(
            "🔴 수집중"
        )

    elif status.get("stopped"):

        st.warning(
            "🛑 수집 중지됨"
        )

    else:

        st.success(
            "🟢 수집 완료"
        )


    c1, c2, c3, c4, c5 = st.columns(5)


    with c1:

        st.metric(
            "진행",
            f"{current:,}/{total:,}"
        )


    with c2:

        st.metric(
            "신규",
            f"{status.get('success', 0):,}"
        )


    with c3:

        st.metric(
            "기존",
            f"{status.get('exists', 0):,}"
        )


    with c4:

        st.metric(
            "실패/배당없음",
            f"{status.get('failed', 0):,}"
        )


    with c5:

        st.metric(
            "최종배당",
            f"{status.get('odds', 0):,}"
        )


    last_id = status.get(
        "last_completed_id"
    )


    if last_id:

        st.info(
            f"✅ 마지막 완료 ID: "
            f"**{last_id:,}**"
        )


    with st.expander(
        "📜 수집 로그",
        expanded=True
    ):

        log_text = status.get(
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
                "아직 로그가 없습니다."
            )


    if status.get("error"):

        st.error(
            status["error"]
        )


st.divider()


# =========================================================
# 저장 경기
# =========================================================

st.header(
    "📋 저장된 전체 경기"
)


try:

    matches = (
        database.get_all_matches()
    )

except Exception as e:

    matches = []

    st.error(
        "경기 데이터 조회 오류"
    )

    st.code(
        str(e)
    )


if matches:

    table = []


    for row in matches:

        table.append({

            "경기 ID":
                row.get(
                    "schedule_id"
                ),

            "경기일":
                row.get(
                    "match_date"
                ),

            "홈팀":
                row.get(
                    "home_team"
                ),

            "원정팀":
                row.get(
                    "away_team"
                ),

            "홈 점수":
                row.get(
                    "home_score"
                ),

            "원정 점수":
                row.get(
                    "away_score"
                ),

            "실제 결과":
                row.get(
                    "result"
                )
        })


    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "저장된 경기가 없습니다."
    )


# =========================================================
# 경기별 배당
# =========================================================

st.divider()

st.header(
    "📱 경기별 최종배당 확인"
)


odds_match_id = st.number_input(

    "경기 ID",

    min_value=1,

    value=3001118,

    step=1,

    format="%d"
)


if st.button(

    "🔎 이 경기 배당 확인",

    type="primary",

    use_container_width=True
):

    target_id = int(
        odds_match_id
    )


    match = database.get_match(
        target_id
    )


    if match:

        home_team = (
            match.get(
                "home_team"
            )
            or "-"
        )


        away_team = (
            match.get(
                "away_team"
            )
            or "-"
        )


        st.markdown(

            f"""
            <div class="match-card">

                <div style="
                    text-align:center;
                    font-size:22px;
                    font-weight:700;
                ">

                    {home_team}

                    <br>

                    <span style="
                        font-size:15px;
                        color:#777;
                    ">
                        VS
                    </span>

                    <br>

                    {away_team}

                </div>

                <div style="
                    text-align:center;
                    color:#555;
                    margin-top:12px;
                ">

                    경기 ID:
                    <b>{target_id:,}</b>

                    <br>

                    경기일:
                    <b>
                    {match.get('match_date') or '-'}
                    </b>

                    <br>

                    실제 결과:
                    <b>
                    {match.get('result') or '-'}
                    </b>

                </div>

            </div>
            """,

            unsafe_allow_html=True
        )


    else:

        st.warning(
            "경기 정보가 없습니다."
        )


    match_odds = (
        database.get_odds_by_match(
            target_id
        )
    )


    st.markdown("---")


    if match_odds:

        st.success(
            f"💰 저장된 최종배당 "
            f"**{len(match_odds)}개 업체**"
        )


        for row in match_odds:

            bookmaker = (
                row.get(
                    "bookmaker"
                )
                or "-"
            )


            def odds_text(value):

                try:

                    return f"{float(value):.2f}"

                except Exception:

                    return "-"


            home = odds_text(
                row.get(
                    "home_odds"
                )
            )

            draw = odds_text(
                row.get(
                    "draw_odds"
                )
            )

            away = odds_text(
                row.get(
                    "away_odds"
                )
            )


            st.markdown(

                f"""
                <div class="odds-card">

                    <div class="odds-company">
                        🏢 {bookmaker}
                    </div>

                    <div class="odds-row">

                        <div class="odds-item">

                            <span class="odds-label">
                                승
                            </span>

                            <span class="odds-value">
                                {home}
                            </span>

                        </div>


                        <div class="odds-item">

                            <span class="odds-label">
                                무
                            </span>

                            <span class="odds-value">
                                {draw}
                            </span>

                        </div>


                        <div class="odds-item">

                            <span class="odds-label">
                                패
                            </span>

                            <span class="odds-value">
                                {away}
                            </span>

                        </div>

                    </div>

                </div>
                """,

                unsafe_allow_html=True
            )


    else:

        st.error(
            "❌ 저장된 최종배당이 없습니다."
        )


# =========================================================
# 분석 업체
# =========================================================

st.divider()

st.header(
    "🌎 해외배당업체 선택"
)


try:

    analysis_companies = (
        analysis.get_company_list()
    )

except Exception:

    analysis_companies = []


try:

    db_companies = (
        database.get_company_names()
    )

except Exception:

    db_companies = []


all_companies = sorted(
    set(
        analysis_companies
        + db_companies
    )
)


selected_companies = st.multiselect(

    "분석할 업체",

    options=all_companies,

    default=[]
)


# =========================================================
# 배당 입력
# =========================================================

input_odds = {}


if selected_companies:

    st.subheader(
        "💰 동일 배당 기준 입력"
    )


    st.info(
        "입력한 승/무/패 배당과 동일한 "
        "과거 경기를 검색합니다."
    )


    for company in selected_companies:

        st.markdown(
            f"### 🏢 {company}"
        )


        c1, c2, c3 = st.columns(3)


        safe = re.sub(
            r"[^a-zA-Z0-9가-힣_]",
            "_",
            company
        )


        with c1:

            home = st.number_input(

                f"{company} 최종 승",

                min_value=0.01,

                value=1.50,

                step=0.01,

                format="%.2f",

                key=
                    f"analysis_home_{safe}"
            )


        with c2:

            draw = st.number_input(

                f"{company} 최종 무",

                min_value=0.01,

                value=3.50,

                step=0.01,

                format="%.2f",

                key=
                    f"analysis_draw_{safe}"
            )


        with c3:

            away = st.number_input(

                f"{company} 최종 패",

                min_value=0.01,

                value=5.00,

                step=0.01,

                format="%.2f",

                key=
                    f"analysis_away_{safe}"
            )


        input_odds[company] = {

            "home":
                home,

            "draw":
                draw,

            "away":
                away
        }


    if st.button(

        "🔎 동일 배당 경기 검색 및 확률 분석",

        type="primary",

        use_container_width=True
    ):

        try:

            result = analysis.run_search(

                selected_companies,

                input_odds
            )


            if result.get("success"):

                st.session_state.search_result = (
                    result
                )

            else:

                st.error(
                    result.get(
                        "message",
                        "검색 결과가 없습니다."
                    )
                )


        except Exception as e:

            st.error(
                "분석 실행 오류"
            )

            st.code(
                str(e)
            )


# =========================================================
# 검색 결과
# =========================================================

search = (
    st.session_state.search_result
)


if (
    search
    and search.get("success")
):

    results = search.get(
        "results",
        []
    )


    statistics = search.get(
        "statistics",
        {}
    )


    st.divider()

    st.header(
        "📊 동일 배당 기준 전체 경기 분석"
    )


    counts = statistics.get(
        "counts",
        {}
    )


    total = counts.get(
        "total",
        len(results)
    )


    wins = counts.get(
        "home",
        0
    )


    draws = counts.get(
        "draw",
        0
    )


    losses = counts.get(
        "away",
        0
    )


    c1, c2, c3, c4 = st.columns(4)


    with c1:

        st.metric(
            "전체 경기",
            f"{total:,}"
        )


    with c2:

        st.metric(
            "승",
            f"{wins:,}"
        )


    with c3:

        st.metric(
            "무",
            f"{draws:,}"
        )


    with c4:

        st.metric(
            "패",
            f"{losses:,}"
        )


    st.subheader(
        "🎯 업체별 확률 / 실제결과 / 부족확률"
    )


    for company in selected_companies:

        try:

            company_stats = (
                analysis
                .calculate_company_analysis(

                    results,

                    company
                )
            )

        except Exception as e:

            st.error(
                f"{company} 분석 오류"
            )

            continue


        if not company_stats:

            st.warning(
                f"{company}: 데이터 없음"
            )

            continue


        n = company_stats["total"]


        table = []


        for key, label in [

            ("home", "승"),

            ("draw", "무"),

            ("away", "패")

        ]:

            expected = (
                company_stats
                ["expected"]
                [key]
            )


            actual = (
                company_stats
                ["actual"]
                [key]
            )


            difference = (
                actual
                - expected
            )


            table.append({

                "구분":
                    label,

                "기대값 확률":
                    f"{expected:.2f}%",

                "실제 결과":
                    f"{actual:.2f}%",

                "부족확률":
                    f"{difference:+.2f}%",

                "발생 건수":
                    company_stats
                    ["counts"]
                    [key],

                "전체 건수":
                    n
            })


        st.markdown(
            f"### 🏢 {company}"
        )


        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# 전체 배당
# =========================================================

st.divider()

st.header(
    "🗃️ 저장된 업체별 최종배당"
)


if st.checkbox(
    "DB 전체 최종배당 데이터 보기"
):

    odds_rows = (
        database.get_all_odds()
    )


    table = []


    for row in odds_rows:

        table.append({

            "경기 ID":
                row.get(
                    "schedule_id"
                ),

            "업체":
                row.get(
                    "bookmaker"
                ),

            "최종 승":
                row.get(
                    "home_odds"
                ),

            "최종 무":
                row.get(
                    "draw_odds"
                ),

            "최종 패":
                row.get(
                    "away_odds"
                )
        })


    if table:

        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "저장된 최종배당이 없습니다."
        )


# =========================================================
# 업체별 저장량
# =========================================================

st.divider()

st.header(
    "🏢 해외업체별 저장 데이터"
)


company_counts = (
    database.get_company_counts()
)


if company_counts:

    st.dataframe(

        [

            {
                "업체":
                    company,

                "저장 배당 수":
                    count
            }

            for company, count
            in company_counts.items()

        ],

        use_container_width=True,

        hide_index=True
    )

else:

    st.info(
        "아직 업체별 배당 데이터가 없습니다."
    )


# =========================================================
# 자동 새로고침
# =========================================================

current_status = (
    scoreman_crawler.get_job_status()
)


if current_status.get("running"):

    st.markdown(
        """
        <script>

        setTimeout(
            function() {

                window.parent.location.reload();

            },
            3000
        );

        </script>
        """,
        unsafe_allow_html=True
                )
