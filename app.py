import streamlit as st

import database
import scoreman_crawler
import analysis


# =========================================================
# 페이지 설정
# =========================================================

st.set_page_config(
    page_title="⚽ 전종목 해외배당 분석",
    page_icon="⚽",
    layout="wide"
)


# =========================================================
# DB 초기화
# =========================================================

try:

    database.init_database()

except Exception as e:

    st.error(
        "DATABASE 초기화 오류"
    )

    st.code(
        str(e)
    )

    st.stop()


# =========================================================
# 세션 상태
# =========================================================

if "crawl_log" not in st.session_state:

    st.session_state.crawl_log = ""


if "crawl_result" not in st.session_state:

    st.session_state.crawl_result = None


if "search_result" not in st.session_state:

    st.session_state.search_result = None


# =========================================================
# 제목
# =========================================================

st.title(
    "⚽ 전종목 해외배당 분석"
)

st.caption(
    "스코어맨 자동수집 · 해외업체 · 최종배당 · 실제결과 · 부족확률"
)


# =========================================================
# 상단 DB 현황
# =========================================================

try:

    match_count = database.get_match_count()

except Exception:

    match_count = 0


try:

    odds_count = database.get_odds_count()

except Exception:

    odds_count = 0


try:

    companies_now = database.get_company_names()

except Exception:

    companies_now = []


c1, c2, c3 = st.columns(3)


with c1:

    st.metric(
        "저장 경기",
        f"{match_count:,}건"
    )


with c2:

    st.metric(
        "저장 최종배당",
        f"{odds_count:,}건"
    )


with c3:

    st.metric(
        "실제 저장 업체",
        f"{len(companies_now):,}곳"
    )


st.divider()


# =========================================================
# 1. 스코어맨 자동수집
# =========================================================

st.header(
    "📥 스코어맨 경기 자동수집"
)

st.write(
    "스코어맨 경기 ID를 범위로 지정하면 "
    "완료된 경기와 업체별 **최종배당**을 DB에 저장합니다."
)

st.info(
    "※ 초기배당은 저장하지 않고 최종배당만 저장합니다."
)


# ---------------------------------------------------------
# 종목
# ---------------------------------------------------------

sport = st.selectbox(
    "🏆 종목",
    [
        "축구"
    ],
    index=0
)


# ---------------------------------------------------------
# 스코어맨 URL
# ---------------------------------------------------------

scoreman_url = st.text_input(

    "스코어맨 URL",

    value=(
        "https://football.scoreman123.com/league/25/"
    )
)


# ---------------------------------------------------------
# 업체
# ---------------------------------------------------------

st.subheader(
    "🌍 해외배당 업체"
)

st.caption(
    "실제 DB에 저장된 업체와 주요 업체가 표시됩니다."
)


try:

    available_companies = (
        analysis.get_company_list()
    )

except Exception as e:

    available_companies = []

    st.error(
        f"업체 목록 오류: {e}"
    )


if available_companies:

    selected_collect_companies = st.multiselect(

        "수집/분석 대상 업체",

        options=available_companies,

        default=[],

        placeholder=(
            "업체를 선택하세요"
        )
    )

else:

    selected_collect_companies = []

    st.warning(
        "현재 DB에 저장된 업체가 없습니다."
    )


# ---------------------------------------------------------
# 경기 ID
# ---------------------------------------------------------

st.subheader(
    "📅 수집 범위"
)


c1, c2 = st.columns(2)


with c1:

    start_id = st.number_input(

        "시작 경기 ID",

        min_value=1,

        value=3001118,

        step=1,

        format="%d",

        key="crawl_start_id"

    )


with c2:

    end_id = st.number_input(

        "마지막 경기 ID",

        min_value=1,

        value=3001118,

        step=1,

        format="%d",

        key="crawl_end_id"

    )


if end_id >= start_id:

    total_ids = (
        int(end_id)
        -
        int(start_id)
        +
        1
    )

else:

    total_ids = 0


st.write(
    f"🔢 검색할 경기 ID: **{total_ids:,}개**"
)


# ---------------------------------------------------------
# 요청 간격
# ---------------------------------------------------------

delay = st.number_input(

    "⏱️ 요청 간격(초)",

    min_value=0.20,

    max_value=3.00,

    value=0.50,

    step=0.10,

    format="%.2f"

)


# =========================================================
# 자동수집 버튼
# =========================================================

if st.button(

    "🚀 스코어맨 DB 자동수집 시작",

    type="primary",

    use_container_width=True,

    key="start_crawler"

):

    if end_id < start_id:

        st.error(
            "마지막 경기 ID가 시작 경기 ID보다 작습니다."
        )

    else:

        st.session_state.crawl_log = ""

        st.session_state.crawl_result = None

        st.subheader(
            "📡 수집 진행상황"
        )

        progress_bar = st.progress(
            0
        )

        log_box = st.empty()


        # -------------------------------------------------
        # 로그
        # -------------------------------------------------

        def add_log(message):

            message = str(
                message
            )

            if st.session_state.crawl_log:

                st.session_state.crawl_log += "\n"

            st.session_state.crawl_log += (
                message
            )

            log_box.code(
                st.session_state.crawl_log,
                language="text"
            )


        # -------------------------------------------------
        # 진행률
        # -------------------------------------------------

        def update_progress(value):

            try:

                value = float(
                    value
                )

                value = min(
                    max(
                        value,
                        0.0
                    ),
                    1.0
                )

                progress_bar.progress(
                    value
                )

            except Exception:

                pass


        add_log(
            "========================================"
        )

        add_log(
            "⚽ Scoreman DB 자동수집 시작"
        )

        add_log(
            f"종목: {sport}"
        )

        add_log(
            f"URL: {scoreman_url}"
        )

        add_log(
            f"범위: {int(start_id):,} ~ "
            f"{int(end_id):,}"
        )

        add_log(
            f"총 검색: {total_ids:,}건"
        )

        add_log(
            "초기배당: 사용하지 않음"
        )

        add_log(
            "최종배당: 저장"
        )

        add_log(
            "========================================"
        )


        # -------------------------------------------------
        # 실제 수집
        # -------------------------------------------------

        try:

            result = (
                scoreman_crawler.build_database_progress(

                    start_id=int(
                        start_id
                    ),

                    end_id=int(
                        end_id
                    ),

                    progress_callback=
                        update_progress,

                    log_callback=
                        add_log,

                    delay=float(
                        delay
                    )

                )
            )


            st.session_state.crawl_result = (
                result
            )


            add_log(
                "========================================"
            )

            add_log(
                "✅ DB 수집 완료"
            )

            add_log(
                f"전체 검색: "
                f"{result.get('total', 0):,}"
            )

            add_log(
                f"신규 저장: "
                f"{result.get('success', 0):,}"
            )

            add_log(
                f"기존 경기: "
                f"{result.get('exists', 0):,}"
            )

            add_log(
                f"실패/건너뜀: "
                f"{result.get('failed', 0):,}"
            )

            add_log(
                f"저장 최종배당: "
                f"{result.get('odds', 0):,}"
            )

            add_log(
                "========================================"
            )


            progress_bar.progress(
                1.0
            )


            st.success(
                "✅ 스코어맨 DB 수집 완료"
            )


            r1, r2, r3, r4 = st.columns(4)


            with r1:

                st.metric(
                    "전체 검색",
                    f"{result.get('total', 0):,}"
                )


            with r2:

                st.metric(
                    "신규 저장",
                    f"{result.get('success', 0):,}"
                )


            with r3:

                st.metric(
                    "기존 경기",
                    f"{result.get('exists', 0):,}"
                )


            with r4:

                st.metric(
                    "최종배당",
                    f"{result.get('odds', 0):,}"
                )


        except Exception as e:

            add_log(
                "========================================"
            )

            add_log(
                f"❌ 수집 오류: {e}"
            )

            add_log(
                "========================================"
            )

            st.error(
                f"크롤링 오류: {e}"
            )


elif st.session_state.crawl_log:

    st.subheader(
        "📡 최근 수집 로그"
    )

    st.code(
        st.session_state.crawl_log,
        language="text"
    )


# =========================================================
# 2. 배당 입력 분석
# =========================================================

st.divider()

st.header(
    "🎯 해외배당 입력 → 과거경기 분석"
)

st.write(
    "해외업체의 승 / 무 / 패 최종배당을 입력하면 "
    "DB에서 동일한 배당의 과거경기를 찾아 분석합니다."
)


st.info(
    "여러 업체를 선택하면 **선택한 모든 업체의 배당이 "
    "동시에 일치하는 경기**만 검색합니다."
)


# =========================================================
# 업체 선택
# =========================================================

st.subheader(
    "🌍 해외배당 업체 선택"
)


try:

    companies = (
        analysis.get_company_list()
    )

except Exception as e:

    companies = []

    st.error(
        f"업체 목록 오류: {e}"
    )


if companies:

    st.caption(
        f"선택 가능한 업체: {len(companies):,}개"
    )

    selected_companies = st.multiselect(

        "분석할 업체",

        options=companies,

        default=[],

        placeholder=(
            "해외배당 업체를 선택하세요"
        ),

        key="analysis_companies"

    )

else:

    selected_companies = []

    st.warning(
        "DB에 저장된 업체가 없습니다."
    )


# =========================================================
# 배당 입력
# =========================================================

input_odds = {}


if selected_companies:

    st.subheader(
        "💰 최종배당 입력"
    )


    for index, company in enumerate(

        selected_companies,

        start=1

    ):

        st.markdown(
            f"### {index}. 🏢 {company}"
        )


        c1, c2, c3 = st.columns(3)


        safe_key = (

            str(company)

            .replace(
                " ",
                "_"
            )

            .replace(
                ".",
                "_"
            )

            .replace(
                "/",
                "_"
            )

            .replace(
                "-",
                "_"
            )

            .replace(
                "(",
                "_"
            )

            .replace(
                ")",
                "_"
            )

        )


        with c1:

            final_home = st.number_input(

                f"{company} 승",

                min_value=0.01,

                value=1.50,

                step=0.01,

                format="%.2f",

                key=(
                    f"analysis_home_"
                    f"{safe_key}"
                )

            )


        with c2:

            final_draw = st.number_input(

                f"{company} 무",

                min_value=0.01,

                value=3.50,

                step=0.01,

                format="%.2f",

                key=(
                    f"analysis_draw_"
                    f"{safe_key}"
                )

            )


        with c3:

            final_away = st.number_input(

                f"{company} 패",

                min_value=0.01,

                value=5.00,

                step=0.01,

                format="%.2f",

                key=(
                    f"analysis_away_"
                    f"{safe_key}"
                )

            )


        input_odds[company] = {

            "home":
                final_home,

            "draw":
                final_draw,

            "away":
                final_away

        }


        st.divider()


    # =====================================================
    # 검색 버튼
    # =====================================================

    if st.button(

        "🔎 배당 분석 시작",

        type="primary",

        use_container_width=True,

        key="search_odds"

    ):

        result = analysis.run_search(

            selected_companies,

            input_odds

        )


        st.session_state.search_result = (
            result
        )


# =========================================================
# 검색 결과
# =========================================================

search_result = (
    st.session_state.search_result
)


if search_result:

    if not search_result.get(
        "success",
        False
    ):

        st.error(
            search_result.get(
                "message",
                "검색 오류"
            )
        )

    else:

        results = search_result.get(
            "results",
            []
        )

        statistics = search_result.get(
            "statistics"
        )


        # =================================================
        # 전체 통계
        # =================================================

        st.divider()

        st.header(
            "📊 전체 분석 결과"
        )


        if not results:

            st.warning(
                "입력한 모든 업체의 최종배당과 "
                "완전히 일치하는 과거경기가 없습니다."
            )

        else:

            counts = statistics.get(
                "counts",
                {}
            )

            probability = statistics.get(
                "probability",
                {}
            )

            actual = statistics.get(
                "actual",
                {}
            )

            shortage = statistics.get(
                "shortage",
                {}
            )


            # ---------------------------------------------
            # 경기수
            # ---------------------------------------------

            st.subheader(
                "🏆 실제 경기 결과 건수"
            )


            c1, c2, c3, c4 = st.columns(4)


            with c1:

                st.metric(
                    "전체 경기",
                    f"{counts.get('total', 0):,}건"
                )


            with c2:

                st.metric(
                    "승",
                    f"{counts.get('home', 0):,}건"
                )


            with c3:

                st.metric(
                    "무",
                    f"{counts.get('draw', 0):,}건"
                )


            with c4:

                st.metric(
                    "패",
                    f"{counts.get('away', 0):,}건"
                )


            # ---------------------------------------------
            # 확률 비교
            # ---------------------------------------------

            st.subheader(
                "📈 배당확률 vs 실제결과"
            )


            table_data = [

                {

                    "구분":
                        "승",

                    "배당확률":
                        f"{probability.get('home', 0):.2f}%",

                    "실제 승률":
                        f"{actual.get('home', 0):.2f}%",

                    "결과 건수":
                        f"{counts.get('home', 0):,}건",

                    "부족확률":
                        f"{shortage.get('home', 0):.2f}%p"

                },

                {

                    "구분":
                        "무",

                    "배당확률":
                        f"{probability.get('draw', 0):.2f}%",

                    "실제 무승률":
                        f"{actual.get('draw', 0):.2f}%",

                    "결과 건수":
                        f"{counts.get('draw', 0):,}건",

                    "부족확률":
                        f"{shortage.get('draw', 0):.2f}%p"

                },

                {

                    "구분":
                        "패",

                    "배당확률":
                        f"{probability.get('away', 0):.2f}%",

                    "실제 패율":
                        f"{actual.get('away', 0):.2f}%",

                    "결과 건수":
                        f"{counts.get('away', 0):,}건",

                    "부족확률":
                        f"{shortage.get('away', 0):.2f}%p"

                }

            ]


            st.dataframe(

                table_data,

                use_container_width=True,

                hide_index=True

            )


            # ---------------------------------------------
            # 핵심 결과
            # ---------------------------------------------

            highest = (
                analysis.get_highest_shortage(
                    statistics
                )
            )


            st.subheader(
                "⚠️ 확률 대비 부족한 결과"
            )


            if highest:

                if highest == "승":

                    highest_value = shortage.get(
                        "home",
                        0
                    )

                elif highest == "무":

                    highest_value = shortage.get(
                        "draw",
                        0
                    )

                else:

                    highest_value = shortage.get(
                        "away",
                        0
                    )


                st.warning(

                    f"가장 부족한 결과: "
                    f"**{highest}**  "
                    f"부족확률 **{highest_value:.2f}%p**"

                )


            # =================================================
            # 평균 배당
            # =================================================

            average_odds = statistics.get(
                "average_odds",
                {}
            )


            st.subheader(
                "💰 입력 배당 평균"
            )


            c1, c2, c3 = st.columns(3)


            with c1:

                st.metric(

                    "승 평균배당",

                    f"{average_odds.get('home', 0):.2f}"

                )


            with c2:

                st.metric(

                    "무 평균배당",

                    f"{average_odds.get('draw', 0):.2f}"

                )


            with c3:

                st.metric(

                    "패 평균배당",

                    f"{average_odds.get('away', 0):.2f}"

                )


            # =================================================
            # 실제 검색 경기
            # =================================================

            st.divider()

            st.header(
                "📋 검색된 전체 경기"
            )


            st.success(
                f"총 **{len(results):,}경기**"
            )


            # -------------------------------------------------
            # 전체 경기 테이블
            # -------------------------------------------------

            result_table = []


            for row in results:

                result_table.append({

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

                    "홈팀":
                        row.get(
                            "home_team",
                            ""
                        ),

                    "원정팀":
                        row.get(
                            "away_team",
                            ""
                        ),

                    "스코어":
                        (
                            f"{row.get('home_score', '-')}"
                            f"-"
                            f"{row.get('away_score', '-')}"
                        ),

                    "실제결과":
                        row.get(
                            "result",
                            "-"
                        )

                })


            st.dataframe(

                result_table,

                use_container_width=True,

                hide_index=True

            )


            # =================================================
            # 경기별 상세
            # =================================================

            st.subheader(
                "🔎 경기별 상세"
            )


            for index, row in enumerate(

                results,

                start=1

            ):

                home_team = row.get(
                    "home_team",
                    ""
                )

                away_team = row.get(
                    "away_team",
                    ""
                )

                result_value = row.get(
                    "result",
                    "-"
                )

                score = (

                    f"{row.get('home_score', '-')}"
                    f"-"
                    f"{row.get('away_score', '-')}"

                )


                with st.expander(

                    f"{index}. "
                    f"{home_team} vs {away_team} "
                    f"| 결과: {result_value} "
                    f"| {score}"

                ):

                    c1, c2, c3, c4 = st.columns(4)


                    with c1:

                        st.write(
                            "**경기 ID**"
                        )

                        st.write(
                            row.get(
                                "schedule_id",
                                "-"
                            )
                        )


                    with c2:

                        st.write(
                            "**경기일**"
                        )

                        st.write(
                            row.get(
                                "match_date",
                                "-"
                            )
                        )


                    with c3:

                        st.write(
                            "**스코어**"
                        )

                        st.write(
                            score
                        )


                    with c4:

                        st.write(
                            "**실제 결과**"
                        )

                        st.write(
                            result_value
                        )


                    st.write(
                        "**업체별 최종배당**"
                    )


                    company_odds = row.get(
                        "company_odds",
                        {}
                    )


                    odds_table = []


                    for company in selected_companies:

                        odds = company_odds.get(
                            company
                        )


                        if odds:

                            odds_table.append({

                                "업체":
                                    company,

                                "승":
                                    odds.get(
                                        "home"
                                    ),

                                "무":
                                    odds.get(
                                        "draw"
                                    ),

                                "패":
                                    odds.get(
                                        "away"
                                    )

                            })


                    if odds_table:

                        st.dataframe(

                            odds_table,

                            use_container_width=True,

                            hide_index=True

                        )

                    else:

                        st.write(
                            "업체 배당 데이터 없음"
                        )


# =========================================================
# 3. 전체 저장 경기
# =========================================================

st.divider()

st.header(
    "📋 DB 저장 전체 경기"
)


try:

    matches = (
        database.get_all_matches()
    )

except Exception as e:

    matches = []

    st.error(
        f"경기 DB 조회 오류: {e}"
    )


if not matches:

    st.info(
        "저장된 경기가 없습니다."
    )

else:

    st.success(
        f"총 **{len(matches):,}경기** 저장"
    )


    table_data = []


    for row in matches:

        table_data.append({

            "경기 ID":
                row["schedule_id"],

            "경기일":
                row["match_date"],

            "홈팀":
                row["home_team"],

            "원정팀":
                row["away_team"],

            "홈":
                row["home_score"],

            "원정":
                row["away_score"],

            "결과":
                row["result"],

            "출처":
                row["source"]

        })


    st.dataframe(

        table_data,

        use_container_width=True,

        hide_index=True

    )


# =========================================================
# 4. 저장된 최종배당
# =========================================================

st.divider()

st.header(
    "🗃️ 저장된 업체별 최종배당"
)


show_odds = st.checkbox(

    "DB 최종배당 데이터 보기",

    value=False,

    key="show_saved_odds"

)


if show_odds:

    try:

        odds_rows = (
            database.get_all_odds()
        )

    except Exception as e:

        odds_rows = []

        st.error(
            f"배당 DB 조회 오류: {e}"
        )


    if not odds_rows:

        st.info(
            "저장된 최종배당이 없습니다."
        )

    else:

        table_data = []


        for row in odds_rows:

            table_data.append({

                "경기 ID":
                    row["schedule_id"],

                "업체":
                    row["company_name"],

                "최종 승":
                    row["final_home"],

                "최종 무":
                    row["final_draw"],

                "최종 패":
                    row["final_away"]

            })


        st.dataframe(

            table_data,

            use_container_width=True,

            hide_index=True

        )


# =========================================================
# 5. 최종 DB 현황
# =========================================================

st.divider()

st.header(
    "📊 최종 DB 현황"
)


try:

    final_match_count = (
        database.get_match_count()
    )

except Exception:

    final_match_count = 0


try:

    final_odds_count = (
        database.get_odds_count()
    )

except Exception:

    final_odds_count = 0


try:

    final_companies = (
        database.get_company_names()
    )

except Exception:

    final_companies = []


c1, c2, c3 = st.columns(3)


with c1:

    st.metric(

        "전체 경기",

        f"{final_match_count:,}건"

    )


with c2:

    st.metric(

        "전체 최종배당",

        f"{final_odds_count:,}건"

    )


with c3:

    st.metric(

        "실제 저장 업체",

        f"{len(final_companies):,}곳"

    )


# =========================================================
# 업체 전체 목록
# =========================================================

with st.expander(
    "📋 현재 DB 업체 전체 목록"
):

    if final_companies:

        for index, company in enumerate(

            final_companies,

            start=1

        ):

            st.write(
                f"{index}. {company}"
            )

    else:

        st.write(
            "현재 DB에 저장된 업체가 없습니다."
        )


# =========================================================
# 안내
# =========================================================

st.divider()

st.caption(
    "※ 스코어맨에서 수집한 실제 업체명과 최종배당을 기준으로 분석합니다."
)

st.caption(
    "※ 입력 배당의 역수 정규화 확률과 과거 실제 승/무/패 비율을 비교합니다."
)

st.caption(
    "※ 부족확률은 배당상 확률보다 실제 결과 비율이 낮은 차이(%p)를 표시합니다."
)

st.success(
    "✅ 프로그램 정상 작동"
)
