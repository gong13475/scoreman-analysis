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


# =========================================================
# DB 초기화
# =========================================================

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
# 자동수집
# =========================================================

st.header("📥 스코어맨 경기 자동수집")

st.info(
    "시작 경기 ID와 마지막 경기 ID를 입력한 후 "
    "수집 시작 버튼을 누르면 백그라운드에서 자동수집합니다."
)


# =========================================================
# ID 입력
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


crawl_mode = st.radio(
    "수집 방식",
    [
        "전체 업체 자동수집",
        "특정 업체만 수집"
    ],
    horizontal=True,
    key="crawl_mode"
)


selected_crawl_companies = []


if crawl_mode == "전체 업체 자동수집":

    st.success(
        "✅ 전체 업체 자동수집\n\n"
        "Scoreman에서 제공하는 모든 업체의 "
        "최종배당을 자동으로 저장합니다."
    )

else:

    companies = analysis.get_company_list()


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
            "업체를 1개 이상 선택하세요."
        )


# =========================================================
# 요청 간격
# =========================================================

delay = st.number_input(
    "요청 간격(초)",
    min_value=0.10,
    max_value=2.00,
    value=0.50,
    step=0.10,
    format="%.2f"
)


# =========================================================
# 현재 작업 상태
# =========================================================

status = scoreman_crawler.get_job_status()


# =========================================================
# 수집 시작 / 중지 버튼
# =========================================================

if not status["running"]:

    st.success("🟢 수집 대기중")


    c1, c2 = st.columns(2)


    with c1:

        if st.button(
            "🚀 수집 시작",
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
                    "수집 업체를 1개 이상 선택하세요."
                )

            else:

                if crawl_mode == "전체 업체 자동수집":

                    companies_for_crawler = None

                else:

                    companies_for_crawler = (
                        selected_crawl_companies
                    )


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
                        "🚀 백그라운드 수집을 시작했습니다."
                    )

                    st.rerun()

                else:

                    st.warning(
                        "수집 작업을 시작하지 못했습니다."
                    )


    with c2:

        if st.button(
            "🔄 상태 새로고침",
            use_container_width=True
        ):

            st.rerun()


else:

    st.error("🔴 현재 수집중입니다.")


    if st.button(
        "🛑 수집 중지",
        type="secondary",
        use_container_width=True
    ):

        stopped = (
            scoreman_crawler
            .stop_background_collection()
        )


        if stopped:

            st.warning(
                "🛑 수집 중지 요청을 보냈습니다."
            )

        else:

            st.info(
                "현재 실행 중인 수집 작업이 없습니다."
            )


        st.rerun()


# =========================================================
# 수집 상태
# =========================================================

status = scoreman_crawler.get_job_status()


if status["running"] or status["finished"]:

    st.divider()

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


    if total > 0:

        progress = (
            current / total
        )

    else:

        progress = 0


    st.progress(
        min(
            max(
                progress,
                0
            ),
            1
        )
    )


    # =====================================================
    # 수집 상태 표시
    # =====================================================

    if status["running"]:

        st.error(
            "🔴 수집중"
        )

    elif status.get("stopped"):

        st.warning(
            "🛑 수집 중지됨"
        )

    elif status["finished"]:

        st.success(
            "🟢 수집 완료"
        )


    # =====================================================
    # 숫자 현황
    # =====================================================

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


    # =====================================================
    # 마지막 완료 ID
    # =====================================================

    last_id = status.get(
        "last_completed_id"
    )


    if last_id:

        st.info(
            f"✅ 마지막 완료 경기 ID: "
            f"**{last_id}**"
        )


    # =====================================================
    # 업체
    # =====================================================

    selected_status_companies = (
        status.get(
            "selected_companies",
            []
        )
    )


    if selected_status_companies:

        st.write(
            "**수집 업체:** "
            + " / ".join(
                selected_status_companies
            )
        )


    # =====================================================
    # 로그
    # =====================================================

    st.subheader(
        "📜 수집 로그"
    )


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
            "수집 로그가 없습니다."
        )


    # =====================================================
    # 오류
    # =====================================================

    if status.get("error"):

        st.error(
            "수집 작업 오류: "
            + str(
                status["error"]
            )
        )


    # =====================================================
    # 완료 결과
    # =====================================================

    if (
        status["finished"]
        and status.get("result")
    ):

        result = status["result"]


        if status.get("stopped"):

            st.warning(
                "🛑 사용자가 수집을 중지했습니다."
            )

        else:

            st.success(
                "✅ 수집 작업이 완료되었습니다."
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


selected_companies = st.multiselect(
    "분석할 업체",
    options=analysis.get_company_list(),
    default=[],
    placeholder="여러 업체 선택 가능",
    key="analysis_companies"
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
        "입력한 승/무/패 배당과 동일한 배당을 가진 "
        "DB의 전체 경기를 검색합니다."
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


    if st.button(
        "🔎 동일 배당 경기 검색 및 확률 분석",
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

search = st.session_state.search_result


if search and search.get("success"):

    results = search["results"]


    statistics = search.get(
        "statistics",
        {}
    )


    st.divider()


    st.header(
        "📊 동일 배당 기준 전체 경기 분석"
    )


    # =====================================================
    # 전체 요약
    # =====================================================

    counts = statistics.get(
        "counts",
        {}
    )


    c1, c2, c3, c4 = st.columns(4)


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
    # 업체별 분석
    # =====================================================

    st.subheader(
        "🎯 업체별 확률 / 실제결과 / 부족확률"
    )


    st.caption(
        "부족확률 = 실제결과율 - 기대값확률"
    )


    for company in selected_companies:

        company_stats = (
            analysis.calculate_company_analysis(
                results,
                company
            )
        )


        if not company_stats:

            st.warning(
                f"{company}: 동일 배당 경기 데이터가 없습니다."
            )

            continue


        n = company_stats["total"]


        st.markdown(
            f"### 🏢 {company}"
        )


        st.write(
            f"동일 배당 분석 경기: **{n:,}건**"
        )


        table = []


        for key, label in [

            ("home", "승"),

            ("draw", "무"),

            ("away", "패")

        ]:

            expected = (
                company_stats["expected"][key]
            )


            actual = (
                company_stats["actual"][key]
            )


            difference = (
                actual - expected
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
                    company_stats["counts"][key],

                "전체 건수":
                    n
            })


        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True
        )


        best_key = max(
            ["home", "draw", "away"],
            key=lambda x:
                company_stats["actual"][x]
        )


        best_label = {

            "home":
                "승",

            "draw":
                "무",

            "away":
                "패"

        }[best_key]


        st.success(
            f"실제 발생률이 가장 높은 결과: "
            f"**{best_label} "
            f"{company_stats['actual'][best_key]:.2f}%**"
        )


    # =====================================================
    # 검색된 경기
    # =====================================================

    st.subheader(
        "📋 동일 배당으로 검색된 경기"
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
                f"{row.get('home_score', '-')}"
                f" - "
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
