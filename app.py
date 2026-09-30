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
    "스코어맨 자동수집 · 전체 해외업체 · "
    "최종배당 · 실제결과 · 동일배당 확률분석"
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
# 수집
# =========================================================

st.header(
    "📥 스코어맨 경기 자동수집"
)

st.info(
    "경기별로 정상 저장된 데이터는 서버가 중단되어도 "
    "DB에 남습니다. 다시 시작하면 기존 데이터는 중복되지 않고 "
    "업데이트됩니다."
)


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
    int(end_id)
    - int(start_id)
    + 1
    if end_id >= start_id
    else 0
)

st.write(
    f"검색 대상: **{total_ids:,}개 경기 ID**"
)


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


all_companies = (
    crawl_mode
    == "전체 업체 자동수집"
)


companies = analysis.get_company_list()


if all_companies:

    selected_crawl_companies = []

    st.success(
        "✅ 전체 업체 자동수집\n\n"
        "업체를 따로 선택하지 않습니다. "
        "Scoreman이 해당 경기에서 제공하는 "
        "모든 업체의 최종배당을 자동으로 저장합니다."
    )

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


delay = st.number_input(
    "요청 간격(초)",
    min_value=0.20,
    max_value=2.00,
    value=0.50,
    step=0.10,
    format="%.2f"
)


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
            not all_companies
            and not selected_crawl_companies
        ):

            st.error(
                "수집 업체를 1개 이상 선택하세요."
            )

        else:

            started = (
                scoreman_crawler
                .start_background_collection(
                    int(start_id),
                    int(end_id),
                    selected_crawl_companies,
                    float(delay),
                    all_companies
                )
            )

            if started:

                st.success(
                    "백그라운드 수집을 시작했습니다."
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


if (
    status["running"]
    or status["finished"]
):

    st.subheader(
        "📡 수집 진행상황"
    )

    total = int(
        status["total"]
    )

    current = int(
        status["current"]
    )

    progress = (
        current / total
        if total
        else 0
    )

    st.progress(
        min(
            max(progress, 0),
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
            f"{status['success']:,}"
        )

    with c3:

        st.metric(
            "기존",
            f"{status['exists']:,}"
        )

    with c4:

        st.metric(
            "실패",
            f"{status['failed']:,}"
        )

    with c5:

        st.metric(
            "최종배당",
            f"{status['odds']:,}"
        )


    if status["all_companies"]:

        st.write(
            "**수집 업체:** 전체 업체"
        )

    elif status["selected_companies"]:

        st.write(
            "**수집 업체:** "
            + " / ".join(
                status["selected_companies"]
            )
        )


    if status["last_saved_id"]:

        c1, c2 = st.columns(2)

        with c1:

            st.metric(
                "마지막 정상 저장 ID",
                f"{status['last_saved_id']:,}"
            )

        with c2:

            st.metric(
                "다음 시작 권장 ID",
                f"{status['next_start_id']:,}"
            )


    if status["failed_ids"]:

        st.warning(
            "실패 ID: "
            + ", ".join(
                str(x)
                for x in status["failed_ids"]
            )
        )


    st.code(
        status["log"],
        language="text"
    )


    if status["running"]:

        st.info(
            "수집 중입니다. 정상 저장된 경기 데이터는 "
            "DB에 즉시 보존됩니다."
        )

    elif status["finished"]:

        if status["error"]:

            st.error(
                "수집 작업 오류: "
                + status["error"]
            )

        else:

            st.success(
                "수집 작업이 완료되었습니다."
            )


st.divider()


# =========================================================
# 저장 경기
# =========================================================

st.header(
    "📋 저장된 전체 경기"
)

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

st.header(
    "🌎 해외배당업체 선택"
)

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
        "💰 업체별 최종배당 입력"
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
            "home": home,
            "draw": draw,
            "away": away
        }


    if st.button(
        "🔎 동일배당 전체경기 분석",
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
# 분석 결과
# =========================================================

search = st.session_state.search_result


if search and search.get("success"):

    st.divider()

    st.header(
        "📊 동일배당 전체경기 분석"
    )

    same_odds = search.get(
        "same_odds",
        {}
    )


    for company in selected_companies:

        statistics = same_odds.get(
            company
        )

        if not statistics:
            continue

        total = statistics["total"]

        counts = statistics["counts"]

        expected = statistics["expected"]

        actual = statistics["actual"]

        difference = statistics["difference"]


        st.subheader(
            f"🏢 {company}"
        )


        st.write(
            f"현재 입력 배당: "
            f"승 **{statistics['odds']['home']:.2f}** / "
            f"무 **{statistics['odds']['draw']:.2f}** / "
            f"패 **{statistics['odds']['away']:.2f}**"
        )


        if total == 0:

            st.warning(
                "DB에 동일한 배당 조합의 "
                "과거 경기가 없습니다."
            )

        elif total < 10:

            st.warning(
                f"동일배당 경기 {total:,}건 "
                "⚠️ 표본이 적습니다."
            )

        elif total < 50:

            st.info(
                f"동일배당 경기 {total:,}건 "
                "🟡 참고용 표본입니다."
            )

        else:

            st.success(
                f"동일배당 경기 {total:,}건 "
                "🟢 충분한 표본입니다."
            )


        table = [

            {
                "구분": "승",

                "경기수":
                    counts["home"],

                "기대값 확률":
                    f"{expected['home']:.2f}%",

                "실제결과":
                    f"{actual['home']:.2f}%",

                "실제-기대":
                    f"{difference['home']:+.2f}%p"
            },

            {
                "구분": "무",

                "경기수":
                    counts["draw"],

                "기대값 확률":
                    f"{expected['draw']:.2f}%",

                "실제결과":
                    f"{actual['draw']:.2f}%",

                "실제-기대":
                    f"{difference['draw']:+.2f}%p"
            },

            {
                "구분": "패",

                "경기수":
                    counts["away"],

                "기대값 확률":
                    f"{expected['away']:.2f}%",

                "실제결과":
                    f"{actual['away']:.2f}%",

                "실제-기대":
                    f"{difference['away']:+.2f}%p"
            }
        ]


        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True
        )


        st.caption(
            "실제-기대 = 실제 결과 확률 − "
            "배당에서 계산된 기대확률. "
            "음수도 그대로 표시합니다."
        )


# =========================================================
# 검색된 경기
# =========================================================

if search and search.get("success"):

    results = search.get(
        "results",
        []
    )

    st.divider()

    st.header(
        "📋 입력 배당과 동일한 검색 경기"
    )

    if not results:

        st.info(
            "입력한 업체/배당과 정확히 일치하는 "
            "경기가 없습니다."
        )

    else:

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
                    row.get(
                        "company_odds",
                        {}
                    ).get(company)
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
                "업체": company,
                "저장 배당 수": count
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
