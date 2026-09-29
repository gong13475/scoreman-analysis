import streamlit as st
import database
import scoreman_crawler
import analysis


# =========================================================
# 페이지 설정
# =========================================================

st.set_page_config(
    page_title="스코어맨 배당 분석",
    page_icon="⚽",
    layout="wide"
)


# =========================================================
# DB 초기화
# =========================================================

try:

    database.init_database()

except Exception as e:

    st.error("DATABASE 초기화 오류")
    st.code(str(e))
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
    "스코어맨 자동수집 · 해외업체 · 최종배당 · "
    "배당확률 · 실제결과 · 부족확률"
)


# =========================================================
# DB 현황
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

    company_names = database.get_company_names()

except Exception:

    company_names = []


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
        "실제 저장 업체",
        f"{len(company_names):,}"
    )


st.divider()


# =========================================================
# 1. 스코어맨 자동수집
# =========================================================

st.header(
    "📥 스코어맨 경기 자동수집"
)

st.write(
    "스코어맨 경기 ID 범위를 검색하여 "
    "완료된 경기와 해외업체 최종배당을 DB에 저장합니다."
)

st.info(
    "초기배당은 저장하지 않고 "
    "**최종배당만 저장**합니다."
)


# ---------------------------------------------------------
# 경기 ID
# ---------------------------------------------------------

c1, c2 = st.columns(2)


with c1:

    start_id = st.number_input(
        "시작 경기 ID",
        min_value=1,
        value=3001118,
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
        -
        int(start_id)
        +
        1
    )

else:

    total_ids = 0


st.write(
    f"검색 대상: **{total_ids:,}개 경기 ID**"
)


# ---------------------------------------------------------
# 요청 간격
# ---------------------------------------------------------

delay = st.number_input(

    "요청 간격(초)",

    min_value=0.20,

    max_value=2.00,

    value=0.50,

    step=0.10,

    format="%.2f"
)


# =========================================================
# 수집 버튼
# =========================================================

if st.button(
    "🚀 스코어맨 DB 자동수집 시작",
    type="primary",
    use_container_width=True
):

    if end_id < start_id:

        st.error(
            "마지막 ID가 시작 ID보다 작습니다."
        )

    else:

        st.session_state.crawl_log = ""

        st.subheader(
            "📡 수집 진행상황"
        )

        log_box = st.empty()

        progress_bar = st.progress(
            0
        )


        # -------------------------------------------------
        # 로그
        # -------------------------------------------------

        def add_log(message):

            message = str(
                message
            )

            if st.session_state.crawl_log:

                st.session_state.crawl_log += "\n"

            st.session_state.crawl_log += message

            log_box.code(
                st.session_state.crawl_log,
                language="text"
            )


        # -------------------------------------------------
        # 진행률
        # -------------------------------------------------

        def update_progress(value):

            try:

                value = float(value)

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
            f"범위: {int(start_id):,} ~ "
            f"{int(end_id):,}"
        )

        add_log(
            f"전체 ID: {total_ids:,}"
        )

        add_log(
            "초기배당: 저장하지 않음"
        )

        add_log(
            "최종배당: 저장"
        )

        add_log(
            "========================================"
        )


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


            st.session_state.crawl_result = result


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
                f"최종배당: "
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
                f"스코어맨 수집 오류: {e}"
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
# 2. 저장된 전체 경기
# =========================================================

st.divider()

st.header(
    "📋 저장된 전체 경기"
)


try:

    matches = database.get_all_matches()

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
        f"현재 DB에 총 "
        f"{len(matches):,}경기가 있습니다."
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

            "홈 점수":
                row["home_score"],

            "원정 점수":
                row["away_score"],

            "실제 결과":
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
# 3. 해외업체 선택
# =========================================================

st.divider()

st.header(
    "🌎 해외배당업체 선택"
)


st.write(
    "검색할 해외업체를 선택하고 "
    "최종 승 / 무 / 패 배당을 입력합니다."
)


try:

    companies = analysis.get_company_list()

except Exception as e:

    companies = []

    st.error(
        f"업체 목록 오류: {e}"
    )


# ---------------------------------------------------------
# 주요 업체가 반드시 표시되도록 보완
# ---------------------------------------------------------

preferred_companies = [

    "Bet365",
    "William Hill",
    "10Bet"

]


for company in preferred_companies:

    if company not in companies:

        companies.append(
            company
        )


companies = sorted(
    list(
        dict.fromkeys(
            companies
        )
    ),
    key=lambda x: str(x).lower()
)


if companies:

    st.caption(
        f"선택 가능한 업체: "
        f"{len(companies):,}개"
    )


    selected_companies = st.multiselect(

        "해외업체 선택",

        options=companies,

        default=[],

        placeholder=
            "Bet365 / William Hill / 10Bet 등 선택"

    )

else:

    selected_companies = []

    st.warning(
        "현재 DB에 저장된 업체가 없습니다."
    )


# =========================================================
# 4. 업체별 배당 입력
# =========================================================

input_odds = {}


if selected_companies:

    st.subheader(
        "💰 업체별 최종배당 입력"
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
            .replace(" ", "_")
            .replace(".", "_")
            .replace("/", "_")
            .replace("-", "_")
        )


        with c1:

            final_home = st.number_input(

                f"{company} 최종 승",

                min_value=0.01,

                value=1.50,

                step=0.01,

                format="%.2f",

                key=
                    f"home_{safe_key}"

            )


        with c2:

            final_draw = st.number_input(

                f"{company} 최종 무",

                min_value=0.01,

                value=3.50,

                step=0.01,

                format="%.2f",

                key=
                    f"draw_{safe_key}"

            )


        with c3:

            final_away = st.number_input(

                f"{company} 최종 패",

                min_value=0.01,

                value=5.00,

                step=0.01,

                format="%.2f",

                key=
                    f"away_{safe_key}"

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
    # 검색
    # =====================================================

    if st.button(

        "🔎 배당 검색 및 확률 분석",

        type="primary",

        use_container_width=True

    ):

        result = analysis.run_search(

            selected_companies,

            input_odds

        )


        if not result.get(
            "success",
            False
        ):

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


            st.session_state.search_result = results


            if not results:

                st.warning(
                    "입력한 모든 업체의 "
                    "최종배당과 완전히 일치하는 "
                    "경기가 없습니다."
                )

            else:

                st.success(
                    f"🎯 검색 결과 "
                    f"{len(results):,}경기"
                )


# =========================================================
# 5. 검색 결과 분석
# =========================================================

search_results = (
    st.session_state.search_result
)


if search_results:

    st.divider()

    st.header(
        "📊 배당 확률 대비 실제 결과 분석"
    )


    # -----------------------------------------------------
    # 전체 경기 결과 집계
    # -----------------------------------------------------

    total_games = len(
        search_results
    )

    win_count = 0
    draw_count = 0
    loss_count = 0


    for row in search_results:

        result = str(
            row.get(
                "result",
                ""
            )
        ).strip()


        if result == "승":

            win_count += 1

        elif result == "무":

            draw_count += 1

        elif result == "패":

            loss_count += 1


    # -----------------------------------------------------
    # 실제 결과 퍼센트
    # -----------------------------------------------------

    if total_games > 0:

        win_pct = (
            win_count /
            total_games *
            100
        )

        draw_pct = (
            draw_count /
            total_games *
            100
        )

        loss_pct = (
            loss_count /
            total_games *
            100
        )

    else:

        win_pct = 0
        draw_pct = 0
        loss_pct = 0


    # -----------------------------------------------------
    # 결과 전체 건수
    # -----------------------------------------------------

    st.subheader(
        "🏆 전체 경기 결과"
    )


    c1, c2, c3, c4 = st.columns(4)


    with c1:

        st.metric(
            "전체 경기",
            f"{total_games:,}건"
        )


    with c2:

        st.metric(
            "승",
            f"{win_count:,}건",
            f"{win_pct:.1f}%"
        )


    with c3:

        st.metric(
            "무",
            f"{draw_count:,}건",
            f"{draw_pct:.1f}%"
        )


    with c4:

        st.metric(
            "패",
            f"{loss_count:,}건",
            f"{loss_pct:.1f}%"
        )


    st.divider()


    # =====================================================
    # 배당 확률 계산
    # =====================================================

    st.subheader(
        "🎯 배당 확률 대비 부족확률"
    )


    st.info(
        "부족확률은 해당 배당의 암시확률과 "
        "실제 과거 결과 비율을 비교한 값입니다."
    )


    # -----------------------------------------------------
    # 업체별 분석
    # -----------------------------------------------------

    for company in selected_companies:

        company_data = []


        for row in search_results:

            company_odds = row.get(
                "company_odds",
                {}
            )


            odds = company_odds.get(
                company
            )


            if not odds:

                continue


            try:

                home_odd = float(
                    odds["home"]
                )

                draw_odd = float(
                    odds["draw"]
                )

                away_odd = float(
                    odds["away"]
                )

            except Exception:

                continue


            if (
                home_odd <= 0
                or draw_odd <= 0
                or away_odd <= 0
            ):

                continue


            # ---------------------------------------------
            # 배당 암시확률
            # ---------------------------------------------

            raw_home = (
                1 /
                home_odd
            )

            raw_draw = (
                1 /
                draw_odd
            )

            raw_away = (
                1 /
                away_odd
            )


            total_raw = (
                raw_home
                +
                raw_draw
                +
                raw_away
            )


            if total_raw <= 0:

                continue


            implied_home = (
                raw_home /
                total_raw *
                100
            )


            implied_draw = (
                raw_draw /
                total_raw *
                100
            )


            implied_away = (
                raw_away /
                total_raw *
                100
            )


            company_data.append({

                "home":
                    implied_home,

                "draw":
                    implied_draw,

                "away":
                    implied_away,

                "result":
                    row.get(
                        "result",
                        ""
                    )

            })


        if not company_data:

            continue


        data_count = len(
            company_data
        )


        actual_win = sum(

            1

            for x in company_data

            if x["result"] == "승"

        )


        actual_draw = sum(

            1

            for x in company_data

            if x["result"] == "무"

        )


        actual_loss = sum(

            1

            for x in company_data

            if x["result"] == "패"

        )


        actual_win_pct = (
            actual_win /
            data_count *
            100
        )


        actual_draw_pct = (
            actual_draw /
            data_count *
            100
        )


        actual_loss_pct = (
            actual_loss /
            data_count *
            100
        )


        avg_home_probability = (

            sum(
                x["home"]
                for x in company_data
            )
            /
            data_count

        )


        avg_draw_probability = (

            sum(
                x["draw"]
                for x in company_data
            )
            /
            data_count

        )


        avg_away_probability = (

            sum(
                x["away"]
                for x in company_data
            )
            /
            data_count

        )


        # -------------------------------------------------
        # 부족확률
        #
        # 실제 결과율 - 배당확률
        #
        # 양수 = 실제 결과가 더 많이 발생
        # 음수 = 실제 결과가 부족
        # -------------------------------------------------

        win_gap = (
            actual_win_pct
            -
            avg_home_probability
        )


        draw_gap = (
            actual_draw_pct
            -
            avg_draw_probability
        )


        loss_gap = (
            actual_loss_pct
            -
            avg_away_probability
        )


        # -------------------------------------------------
        # 부족한 정도
        #
        # 실제 확률이 배당확률보다 낮으면
        # 부족확률로 표시
        # -------------------------------------------------

        win_shortage = max(
            0,
            -win_gap
        )


        draw_shortage = max(
            0,
            -draw_gap
        )


        loss_shortage = max(
            0,
            -loss_gap
        )


        st.markdown(
            f"### 🏢 {company}"
        )


        st.write(
            f"분석 경기: **{data_count:,}건**"
        )


        c1, c2, c3 = st.columns(3)


        with c1:

            st.metric(
                "승",
                f"{actual_win_pct:.1f}%",
                f"배당 {avg_home_probability:.1f}%"
            )

            if win_shortage > 0:

                st.warning(
                    f"승 부족확률 "
                    f"{win_shortage:.1f}%"
                )

            else:

                st.success(
                    f"승 초과 "
                    f"{win_gap:.1f}%"
                )


        with c2:

            st.metric(
                "무",
                f"{actual_draw_pct:.1f}%",
                f"배당 {avg_draw_probability:.1f}%"
            )

            if draw_shortage > 0:

                st.warning(
                    f"무 부족확률 "
                    f"{draw_shortage:.1f}%"
                )

            else:

                st.success(
                    f"무 초과 "
                    f"{draw_gap:.1f}%"
                )


        with c3:

            st.metric(
                "패",
                f"{actual_loss_pct:.1f}%",
                f"배당 {avg_away_probability:.1f}%"
            )

            if loss_shortage > 0:

                st.warning(
                    f"패 부족확률 "
                    f"{loss_shortage:.1f}%"
                )

            else:

                st.success(
                    f"패 초과 "
                    f"{loss_gap:.1f}%"
                )


        # -------------------------------------------------
        # 상세표
        # -------------------------------------------------

        analysis_table = [

            {

                "구분":
                    "승",

                "배당확률":
                    f"{avg_home_probability:.2f}%",

                "실제결과":
                    f"{actual_win_pct:.2f}%",

                "실제건수":
                    f"{actual_win:,}건",

                "차이":
                    f"{win_gap:+.2f}%",

                "부족확률":
                    f"{win_shortage:.2f}%"

            },

            {

                "구분":
                    "무",

                "배당확률":
                    f"{avg_draw_probability:.2f}%",

                "실제결과":
                    f"{actual_draw_pct:.2f}%",

                "실제건수":
                    f"{actual_draw:,}건",

                "차이":
                    f"{draw_gap:+.2f}%",

                "부족확률":
                    f"{draw_shortage:.2f}%"

            },

            {

                "구분":
                    "패",

                "배당확률":
                    f"{avg_away_probability:.2f}%",

                "실제결과":
                    f"{actual_loss_pct:.2f}%",

                "실제건수":
                    f"{actual_loss:,}건",

                "차이":
                    f"{loss_gap:+.2f}%",

                "부족확률":
                    f"{loss_shortage:.2f}%"

            }

        ]


        st.dataframe(

            analysis_table,

            use_container_width=True,

            hide_index=True

        )


        st.divider()


    # =====================================================
    # 실제 경기 목록
    # =====================================================

    st.subheader(
        "📋 검색된 전체 경기"
    )


    for index, row in enumerate(

        search_results,

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


        result = row.get(
            "result",
            "-"
        )


        home_score = row.get(
            "home_score",
            "-"
        )


        away_score = row.get(
            "away_score",
            "-"
        )


        match_date = row.get(
            "match_date",
            "-"
        )


        st.markdown(

            f"### {index}. "
            f"{home_team} vs {away_team}"

        )


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
                "**실제 스코어**"
            )

            st.write(
                f"{home_score} - {away_score}"
            )


        with c3:

            st.write(
                "**실제 결과**"
            )

            st.write(
                result
            )


        with c4:

            st.write(
                "**경기일**"
            )

            st.write(
                match_date
            )


        st.markdown(
            "**업체별 최종배당**"
        )


        company_odds = row.get(
            "company_odds",
            {}
        )


        for company in selected_companies:

            odds = company_odds.get(
                company
            )


            if odds:

                st.write(

                    f"🏢 **{company}**  "
                    f"승 `{odds.get('home')}` / "
                    f"무 `{odds.get('draw')}` / "
                    f"패 `{odds.get('away')}`"

                )


        st.divider()


# =========================================================
# 6. DB 최종배당 확인
# =========================================================

st.header(
    "🗃️ 저장된 업체별 최종배당"
)


show_odds = st.checkbox(
    "DB 최종배당 데이터 보기",
    value=False
)


if show_odds:

    try:

        odds_rows = database.get_all_odds()

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
# 7. 업체별 저장 개수
# =========================================================

st.divider()

st.header(
    "🏢 해외업체별 저장 데이터"
)


try:

    company_counts = (
        database.get_company_counts()
    )

except Exception:

    company_counts = {}


if company_counts:

    company_table = []


    for company, count in (
        company_counts.items()
    ):

        company_table.append({

            "업체":
                company,

            "저장 배당 수":
                count

        })


    st.dataframe(

        company_table,

        use_container_width=True,

        hide_index=True

    )

else:

    st.info(
        "아직 업체별 배당 데이터가 없습니다."
    )


# =========================================================
# 8. 최종 DB 현황
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
        f"{len(final_companies):,}개"
    )


# =========================================================
# 업체 목록
# =========================================================

with st.expander(
    "📋 현재 DB 해외업체 전체 목록"
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
            "현재 DB에 실제 저장된 업체가 없습니다."
        )


# =========================================================
# 안내
# =========================================================

st.info(
    "💡 Bet365 / William Hill / 10Bet은 "
    "업체 선택창에 표시됩니다. "
    "단, 실제 검색 결과를 만들려면 "
    "스코어맨에서 해당 업체의 최종배당이 "
    "DB에 저장되어 있어야 합니다."
)


st.success(
    "✅ 프로그램 정상 작동"
    )
