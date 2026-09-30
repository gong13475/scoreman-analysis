import re
import streamlit as st
import database
import scoreman_crawler
import analysis


# =========================================================
# 설정
# =========================================================

st.set_page_config(
    page_title="스코어맨 배당 분석",
    page_icon="⚽",
    layout="wide"
)

database.init_database()


# =========================================================
# 세션 상태
# =========================================================

if "search_result" not in st.session_state:
    st.session_state.search_result = None


# =========================================================
# 제목
# =========================================================

st.title("⚽ 전종목 해외배당 분석")

st.caption(
    "스코어맨 자동수집 · 전체 해외업체 · "
    "최종배당 · 실제결과 · 확률분석"
)


# =========================================================
# DB 현황
# =========================================================

c1, c2, c3 = st.columns(3)

with c1:
    st.metric(
        "저장 경기",
        f"{database.get_match_count():,}"
    )

with c2:
    st.metric(
        "저장 최종배당",
        f"{database.get_odds_count():,}"
    )

with c3:
    st.metric(
        "실제 저장 업체",
        f"{len(database.get_company_names()):,}"
    )


st.divider()


# =========================================================
# 백그라운드 수집
# =========================================================

st.header("📥 스코어맨 경기 자동수집")

st.info(
    "수집은 백그라운드에서 실행됩니다. "
    "휴대폰 화면을 끄거나 다른 앱으로 이동해도 "
    "서버가 계속 실행 중이면 수집 작업은 계속됩니다."
)


# =========================================================
# 경기 ID
# =========================================================

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


total_ids = (
    int(end_id) - int(start_id) + 1
    if end_id >= start_id
    else 0
)

st.write(
    f"검색 대상: **{total_ids:,}개 경기 ID**"
)


# =========================================================
# 업체 선택
# =========================================================

st.subheader("🏢 수집할 해외업체 선택")

companies = analysis.get_company_list()


crawl_mode = st.radio(
    "수집 방식",
    [
        "전체 업체 자동수집",
        "특정 업체만 수집"
    ],
    horizontal=True,
    key="crawl_mode"
)


selected_crawl_companies = None


# =========================================================
# 전체 업체
# =========================================================

if crawl_mode == "전체 업체 자동수집":

    st.success(
        "✅ 전체 업체 자동수집"
    )

    st.caption(
        "업체를 따로 선택하지 않습니다. "
        "Scoreman이 해당 경기에서 제공하는 모든 업체의 "
        "최종배당을 자동으로 DB에 저장합니다."
    )

    selected_crawl_companies = None


# =========================================================
# 특정 업체
# =========================================================

else:

    selected_crawl_companies = st.multiselect(
        "수집 업체",
        options=companies,
        default=[],
        placeholder="원하는 업체를 여러 개 선택하세요",
        key="crawl_companies"
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
            "특정 업체 수집을 선택했다면 "
            "업체를 1개 이상 선택하세요."
        )


# =========================================================
# 요청 간격
# =========================================================

delay = st.number_input(
    "요청 간격(초)",
    min_value=0.20,
    max_value=2.00,
    value=0.50,
    step=0.10,
    format="%.2f"
)


# =========================================================
# 수집 시작
# =========================================================

status = scoreman_crawler.get_job_status()


if not status["running"]:

    if st.button(
        "🚀 백그라운드 수집 시작",
        type="primary",
        use_container_width=True
    ):

        if end_id < start_id:

            st.error(
                "마지막 ID가 시작 ID보다 작습니다."
            )

        elif (
            crawl_mode == "특정 업체만 수집"
            and not selected_crawl_companies
        ):

            st.error(
                "수집할 업체를 1개 이상 선택하세요."
            )

        else:

            started = (
                scoreman_crawler
                .start_background_collection(
                    int(start_id),
                    int(end_id),
                    selected_crawl_companies,
                    float(delay)
                )
            )

            if started:

                if selected_crawl_companies:

                    company_text = " / ".join(
                        selected_crawl_companies
                    )

                else:

                    company_text = "전체 업체"

                st.success(
                    "백그라운드 수집을 시작했습니다.\n\n"
                    f"수집 업체: {company_text}"
                )

                st.rerun()

            else:

                st.warning(
                    "이미 수집 작업이 실행 중입니다."
                )


# =========================================================
# 수집 상태
# =========================================================

status = scoreman_crawler.get_job_status()


if status["running"] or status["finished"]:

    st.subheader("📡 수집 진행상황")

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
        if total
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
            "실패",
            f"{status.get('failed', 0):,}"
        )

    with c5:

        st.metric(
            "최종배당",
            f"{status.get('odds', 0):,}"
        )


    selected_status_companies = status.get(
        "selected_companies"
    )


    if selected_status_companies:

        st.write(
            "**수집 업체:** "
            + " / ".join(
                selected_status_companies
            )
        )

    else:

        st.write(
            "**수집 업체:** 전체 업체"
        )


    st.code(
        status.get(
            "log",
            ""
        ),
        language="text"
    )


    if status["running"]:

        st.info(
            "수집 중입니다. "
            "이 화면을 닫거나 휴대폰 화면을 꺼도 "
            "서버의 백그라운드 작업은 계속 실행됩니다."
        )

    elif status["finished"]:

        if status.get("error"):

            st.error(
                "수집 작업 오류: "
                + str(
                    status["error"]
                )
            )

        else:

            st.success(
                "수집 작업이 완료되었습니다."
            )


st.divider()


# =========================================================
# 저장 경기
# =========================================================

st.header("📋 저장된 전체 경기")

matches = database.get_all_matches()


if not matches:

    st.info(
        "저장된 경기가 없습니다."
    )

else:

    table = []

    for row in matches:

        table.append({

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
        table,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# 분석 업체
# =========================================================

st.divider()

st.header("🌎 해외배당업체 선택")

analysis_companies = (
    analysis.get_company_list()
)


if not analysis_companies:

    st.warning(
        "현재 DB에 저장된 해외업체가 없습니다."
    )

    st.info(
        "먼저 위의 '전체 업체 자동수집'으로 "
        "경기를 수집하세요."
    )

    selected_companies = []

else:

    selected_companies = st.multiselect(
        "분석할 업체",
        options=analysis_companies,
        default=[],
        placeholder="여러 업체 선택 가능",
        key="analysis_companies"
    )


# =========================================================
# 배당 입력
# =========================================================

input_odds = {}


if selected_companies:

    st.subheader("💰 업체별 최종배당 입력")

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
                key=f"analysis_home_{safe}"
            )

        with c2:

            draw = st.number_input(
                f"{company} 최종 무",
                min_value=0.01,
                value=3.50,
                step=0.01,
                format="%.2f",
                key=f"analysis_draw_{safe}"
            )

        with c3:

            away = st.number_input(
                f"{company} 최종 패",
                min_value=0.01,
                value=5.00,
                step=0.01,
                format="%.2f",
                key=f"analysis_away_{safe}"
            )


        input_odds[company] = {

            "home":
                home,

            "draw":
                draw,

            "away":
                away

        }


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

        if result["success"]:

            st.session_state.search_result = result

        else:

            st.error(
                result["message"]
            )


# =========================================================
# 검색 결과
# =========================================================

search = (
    st.session_state.search_result
)


if search and search.get("success"):

    results = search["results"]

    st.divider()

    st.header(
        "📊 배당 확률 대비 실제 결과"
    )


    total = len(results)


    wins = sum(
        1
        for x in results
        if x.get("result") == "승"
    )


    draws = sum(
        1
        for x in results
        if x.get("result") == "무"
    )


    losses = sum(
        1
        for x in results
        if x.get("result") == "패"
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
            f"{wins:,}",
            (
                f"{wins / total * 100:.2f}%"
                if total
                else "0%"
            )
        )


    with c3:

        st.metric(
            "무",
            f"{draws:,}",
            (
                f"{draws / total * 100:.2f}%"
                if total
                else "0%"
            )
        )


    with c4:

        st.metric(
            "패",
            f"{losses:,}",
            (
                f"{losses / total * 100:.2f}%"
                if total
                else "0%"
            )
        )


    # =====================================================
    # 업체별 부족확률
    # =====================================================

    st.subheader(
        "🎯 업체별 부족확률"
    )


    for company in selected_companies:

        data = []


        for row in results:

            odds = (
                row
                .get(
                    "company_odds",
                    {}
                )
                .get(
                    company
                )
            )


            if not odds:

                continue


            # ---------------------------------------------
            # 배당 → 정규화 확률
            # ---------------------------------------------

            home_odd = float(
                odds["home"]
            )

            draw_odd = float(
                odds["draw"]
            )

            away_odd = float(
                odds["away"]
            )


            if (
                home_odd <= 0
                or draw_odd <= 0
                or away_odd <= 0
            ):

                continue


            inv_home = (
                1.0 / home_odd
            )

            inv_draw = (
                1.0 / draw_odd
            )

            inv_away = (
                1.0 / away_odd
            )


            probability_total = (
                inv_home
                + inv_draw
                + inv_away
            )


            if probability_total <= 0:

                continue


            p_home = (
                inv_home
                / probability_total
                * 100
            )

            p_draw = (
                inv_draw
                / probability_total
                * 100
            )

            p_away = (
                inv_away
                / probability_total
                * 100
            )


            data.append({

                "home":
                    p_home,

                "draw":
                    p_draw,

                "away":
                    p_away,

                "result":
                    row.get(
                        "result",
                        ""
                    )

            })


        if not data:

            st.warning(
                f"{company}: "
                "분석할 데이터가 없습니다."
            )

            continue


        n = len(data)


        # =================================================
        # 실제 결과
        # =================================================

        actual_win = (
            sum(
                x["result"] == "승"
                for x in data
            )
            / n
            * 100
        )


        actual_draw = (
            sum(
                x["result"] == "무"
                for x in data
            )
            / n
            * 100
        )


        actual_loss = (
            sum(
                x["result"] == "패"
                for x in data
            )
            / n
            * 100
        )


        # =================================================
        # 평균 배당확률
        # =================================================

        avg_home = (
            sum(
                x["home"]
                for x in data
            )
            / n
        )


        avg_draw = (
            sum(
                x["draw"]
                for x in data
            )
            / n
        )


        avg_away = (
            sum(
                x["away"]
                for x in data
            )
            / n
        )


        # =================================================
        # 부족확률
        # =================================================

        shortage_home = max(
            0,
            avg_home - actual_win
        )


        shortage_draw = max(
            0,
            avg_draw - actual_draw
        )


        shortage_away = max(
            0,
            avg_away - actual_loss
        )


        # =================================================
        # 차이
        # =================================================

        difference_home = (
            actual_win
            - avg_home
        )


        difference_draw = (
            actual_draw
            - avg_draw
        )


        difference_away = (
            actual_loss
            - avg_away
        )


        table = [

            {
                "구분":
                    "승",

                "배당확률":
                    f"{avg_home:.2f}%",

                "실제결과":
                    f"{actual_win:.2f}%",

                "차이":
                    f"{difference_home:+.2f}%",

                "부족확률":
                    f"{shortage_home:.2f}%"
            },

            {
                "구분":
                    "무",

                "배당확률":
                    f"{avg_draw:.2f}%",

                "실제결과":
                    f"{actual_draw:.2f}%",

                "차이":
                    f"{difference_draw:+.2f}%",

                "부족확률":
                    f"{shortage_draw:.2f}%"
            },

            {
                "구분":
                    "패",

                "배당확률":
                    f"{avg_away:.2f}%",

                "실제결과":
                    f"{actual_loss:.2f}%",

                "차이":
                    f"{difference_away:+.2f}%",

                "부족확률":
                    f"{shortage_away:.2f}%"
            }

        ]


        st.markdown(
            f"### 🏢 {company}"
        )


        st.write(
            f"분석 경기: **{n:,}건**"
        )


        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True
        )


    # =====================================================
    # 검색된 경기
    # =====================================================

    st.subheader(
        "📋 검색된 경기"
    )


    for index, row in enumerate(
        results,
        start=1
    ):

        st.markdown(
            f"### {index}. "
            f"{row.get('home_team', '')} "
            f"vs "
            f"{row.get('away_team', '')}"
        )


        c1, c2, c3, c4 = st.columns(4)


        with c1:

            st.write(
                f"**경기 ID:** "
                f"{row.get('schedule_id', '-')}"
            )


        with c2:

            st.write(
                f"**스코어:** "
                f"{row.get('home_score', '-')} - "
                f"{row.get('away_score', '-')}"
            )


        with c3:

            st.write(
                f"**결과:** "
                f"{row.get('result', '-')}"
            )


        with c4:

            st.write(
                f"**경기일:** "
                f"{row.get('match_date', '-')}"
            )


        for company in selected_companies:

            odds = (
                row
                .get(
                    "company_odds",
                    {}
                )
                .get(
                    company
                )
            )


            if odds:

                st.write(
                    f"🏢 **{company}** "
                    f"승 `{odds['home']}` / "
                    f"무 `{odds['draw']}` / "
                    f"패 `{odds['away']}`"
                )


        st.divider()


# =========================================================
# DB 배당
# =========================================================

st.header(
    "🗃️ 저장된 업체별 최종배당"
)


if st.checkbox(
    "DB 최종배당 데이터 보기"
):

    odds_rows = database.get_all_odds()

    table = []


    for row in odds_rows:

        table.append({

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
        table,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# 업체별 저장량
# =========================================================

st.divider()

st.header(
    "🏢 해외업체별 저장 데이터"
)


counts = database.get_company_counts()


if counts:

    st.dataframe(

        [

            {
                "업체":
                    company,

                "저장 배당 수":
                    count
            }

            for company, count
            in counts.items()

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

status = scoreman_crawler.get_job_status()


if status["running"]:

    st.markdown(
        """
        <script>
        setTimeout(function() {
            window.parent.location.reload();
        }, 3000);
        </script>
        """,
        unsafe_allow_html=True
            )
