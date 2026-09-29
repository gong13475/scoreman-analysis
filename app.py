import streamlit as st
import pandas as pd

import database
import scoreman_crawler as crawler
import analysis


# =========================================================
# 페이지 설정
# =========================================================

st.set_page_config(
    page_title="⚽ 스코어맨 해외배당 분석",
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
    company_count = len(
        database.get_company_names()
    )
except Exception:
    company_count = 0


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
        f"{company_count:,}"
    )


st.divider()


# =========================================================
# 1. 스코어맨 자동수집
# =========================================================

st.header(
    "📥 1. 스코어맨 경기 자동수집"
)

st.write(
    "스코어맨 경기 ID를 기준으로 완료된 경기와 "
    "해외업체 최종배당을 DB에 저장합니다."
)

st.info(
    "초기배당은 저장하지 않고 "
    "**최종배당만 저장**합니다."
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
    f"수집 대상: **{total_ids:,}개 ID**"
)


delay = st.number_input(
    "요청 간격(초)",
    min_value=0.20,
    max_value=3.00,
    value=0.50,
    step=0.10,
    format="%.2f"
)


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

        def add_log(message):

            message = str(message)

            if st.session_state.crawl_log:

                st.session_state.crawl_log += "\n"

            st.session_state.crawl_log += message

            log_box.code(
                st.session_state.crawl_log,
                language="text"
            )

        def update_progress(value):

            try:

                value = float(value)

                value = min(
                    max(value, 0.0),
                    1.0
                )

                progress_bar.progress(
                    value
                )

            except Exception:

                pass

        try:

            result = (
                crawler.build_database_progress(

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
                    "저장 최종배당",
                    f"{result.get('odds', 0):,}"
                )

        except Exception as e:

            add_log(
                f"[치명적 오류] {e}"
            )

            st.error(
                f"크롤링 오류: {e}"
            )


if st.session_state.crawl_log:

    with st.expander(
        "📜 수집 로그 보기",
        expanded=False
    ):

        st.code(
            st.session_state.crawl_log,
            language="text"
        )


# =========================================================
# 2. 해외배당 업체 선택
# =========================================================

st.divider()

st.header(
    "🏢 2. 해외배당 업체 선택"
)

st.write(
    "스코어맨 DB에 저장된 업체를 선택하고 "
    "입력한 최종배당과 완전히 일치하는 과거 경기를 검색합니다."
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
        f"선택 가능한 업체: {len(companies)}개"
    )

    selected_companies = st.multiselect(

        "해외배당 업체",

        options=companies,

        default=[],

        placeholder=
            "분석할 업체를 선택하세요"
    )

else:

    selected_companies = []

    st.warning(
        "DB에 저장된 해외배당 업체가 없습니다."
    )


# =========================================================
# 3. 배당 입력
# =========================================================

if selected_companies:

    st.divider()

    st.header(
        "💰 3. 최종배당 입력"
    )

    st.caption(
        "승 / 무 / 패 배당을 입력하면 "
        "과거 동일배당 경기를 검색합니다."
    )

    input_odds = {}

    for index, company in enumerate(
        selected_companies,
        start=1
    ):

        st.markdown(
            f"### {index}. 🏢 {company}"
        )

        safe_key = (
            str(company)
            .replace(" ", "_")
            .replace(".", "_")
            .replace("/", "_")
            .replace("-", "_")
            .replace("(", "_")
            .replace(")", "_")
        )

        c1, c2, c3 = st.columns(3)

        with c1:

            final_home = st.number_input(

                f"{company} 승",

                min_value=0.01,

                value=1.50,

                step=0.01,

                format="%.2f",

                key=
                    f"home_{safe_key}"
            )

        with c2:

            final_draw = st.number_input(

                f"{company} 무",

                min_value=0.01,

                value=3.50,

                step=0.01,

                format="%.2f",

                key=
                    f"draw_{safe_key}"
            )

        with c3:

            final_away = st.number_input(

                f"{company} 패",

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


    # =====================================================
    # 4. 검색
    # =====================================================

    st.divider()

    if st.button(
        "🔎 배당 입력 → 과거 전체경기 분석",
        type="primary",
        use_container_width=True
    ):

        with st.spinner(
            "과거 경기 데이터를 분석하고 있습니다..."
        ):

            result = analysis.run_search(

                selected_companies,

                input_odds
            )

        st.session_state.search_result = result


# =========================================================
# 5. 분석 결과
# =========================================================

result = st.session_state.search_result


if result:

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

        st.divider()

        st.header(
            "📊 5. 전체 경기 분석 결과"
        )

        # =================================================
        # 전체 경기 수
        # =================================================

        total_games = result.get(
            "total_games",
            len(results)
        )

        win_count = result.get(
            "win_count",
            0
        )

        draw_count = result.get(
            "draw_count",
            0
        )

        loss_count = result.get(
            "loss_count",
            0
        )

        win_percent = result.get(
            "win_percent",
            0
        )

        draw_percent = result.get(
            "draw_percent",
            0
        )

        loss_percent = result.get(
            "loss_percent",
            0
        )


        # =================================================
        # 전체 경기 / 승무패 건수
        # =================================================

        st.subheader(
            "🎯 전체 경기수 및 실제 결과"
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
                f"{win_percent:.1f}%"
            )

        with c3:

            st.metric(
                "무",
                f"{draw_count:,}건",
                f"{draw_percent:.1f}%"
            )

        with c4:

            st.metric(
                "패",
                f"{loss_count:,}건",
                f"{loss_percent:.1f}%"
            )


        # =================================================
        # 배당확률
        # =================================================

        probability = result.get(
            "average_probability"
        )

        gap = result.get(
            "average_gap"
        )


        if probability:

            st.subheader(
                "📈 배당확률 대비 실제 결과"
            )

            p1, p2, p3 = st.columns(3)

            with p1:

                st.markdown(
                    "### 🟢 승"
                )

                st.metric(
                    "배당확률",
                    f"{probability['home']:.1f}%"
                )

                st.write(
                    f"실제 결과: "
                    f"**{win_percent:.1f}% "
                    f"({win_count:,}건)**"
                )

                if gap:

                    value = gap["home"]

                    if value < 0:

                        st.error(
                            f"⚠️ 부족확률 "
                            f"{abs(value):.1f}%"
                        )

                    elif value > 0:

                        st.success(
                            f"▲ 초과 "
                            f"{value:.1f}%"
                        )

                    else:

                        st.info(
                            "배당확률과 실제결과 일치"
                        )


            with p2:

                st.markdown(
                    "### 🟡 무"
                )

                st.metric(
                    "배당확률",
                    f"{probability['draw']:.1f}%"
                )

                st.write(
                    f"실제 결과: "
                    f"**{draw_percent:.1f}% "
                    f"({draw_count:,}건)**"
                )

                if gap:

                    value = gap["draw"]

                    if value < 0:

                        st.error(
                            f"⚠️ 부족확률 "
                            f"{abs(value):.1f}%"
                        )

                    elif value > 0:

                        st.success(
                            f"▲ 초과 "
                            f"{value:.1f}%"
                        )

                    else:

                        st.info(
                            "배당확률과 실제결과 일치"
                        )


            with p3:

                st.markdown(
                    "### 🔴 패"
                )

                st.metric(
                    "배당확률",
                    f"{probability['away']:.1f}%"
                )

                st.write(
                    f"실제 결과: "
                    f"**{loss_percent:.1f}% "
                    f"({loss_count:,}건)**"
                )

                if gap:

                    value = gap["away"]

                    if value < 0:

                        st.error(
                            f"⚠️ 부족확률 "
                            f"{abs(value):.1f}%"
                        )

                    elif value > 0:

                        st.success(
                            f"▲ 초과 "
                            f"{value:.1f}%"
                        )

                    else:

                        st.info(
                            "배당확률과 실제결과 일치"
                        )


        # =================================================
        # 결과표
        # =================================================

        if results:

            st.divider()

            st.subheader(
                "📋 검색된 전체 경기"
            )

            table_data = []

            for row in results:

                table_data.append({

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
                        f"{row.get('home_score', '-')}"
                        f"-"
                        f"{row.get('away_score', '-')}",

                    "실제결과":
                        row.get(
                            "result",
                            ""
                        ),

                    "경기ID":
                        row.get(
                            "schedule_id",
                            ""
                        )

                })

            df = pd.DataFrame(
                table_data
            )

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )


            # =================================================
            # 개별 경기 상세
            # =================================================

            st.subheader(
                "🔍 경기별 상세 배당"
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

                with st.expander(
                    f"{index}. "
                    f"{home_team} vs {away_team} "
                    f"→ {result_value}"
                ):

                    c1, c2, c3, c4 = (
                        st.columns(4)
                    )

                    with c1:

                        st.write(
                            "**경기일**"
                        )

                        st.write(
                            row.get(
                                "match_date",
                                "-"
                            )
                        )

                    with c2:

                        st.write(
                            "**스코어**"
                        )

                        st.write(
                            f"{row.get('home_score', '-')}"
                            f"-"
                            f"{row.get('away_score', '-')}"
                        )

                    with c3:

                        st.write(
                            "**실제결과**"
                        )

                        st.write(
                            result_value
                        )

                    with c4:

                        st.write(
                            "**경기 ID**"
                        )

                        st.write(
                            row.get(
                                "schedule_id",
                                "-"
                            )
                        )


                    st.markdown(
                        "#### 🏢 업체별 최종배당"
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
                                f"**{company}**  "
                                f"승 {odds.get('home')} / "
                                f"무 {odds.get('draw')} / "
                                f"패 {odds.get('away')}"
                            )


        else:

            st.warning(
                "입력한 업체와 최종배당이 "
                "모두 일치하는 과거 경기가 없습니다."
            )


# =========================================================
# 6. 저장된 전체 경기
# =========================================================

st.divider()

st.header(
    "📋 6. 저장된 전체 경기"
)


try:

    matches = database.get_all_matches()

except Exception as e:

    matches = []

    st.error(
        f"경기 DB 조회 오류: {e}"
    )


if matches:

    st.write(
        f"총 **{len(matches):,}경기**"
    )

    match_table = []

    for row in matches:

        match_table.append({

            "경기 ID":
                row["schedule_id"],

            "경기일":
                row["match_date"],

            "홈팀":
                row["home_team"],

            "원정팀":
                row["away_team"],

            "스코어":
                f"{row['home_score']}"
                f"-"
                f"{row['away_score']}",

            "결과":
                row["result"],

            "출처":
                row["source"]

        })

    st.dataframe(
        pd.DataFrame(match_table),
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "저장된 경기가 없습니다."
    )


# =========================================================
# 7. 저장된 최종배당
# =========================================================

st.divider()

st.header(
    "🗃️ 7. 저장된 해외업체 최종배당"
)

show_odds = st.checkbox(
    "최종배당 DB 보기",
    value=False
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

    if odds_rows:

        odds_table = []

        for row in odds_rows:

            odds_table.append({

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
            pd.DataFrame(odds_table),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "저장된 최종배당이 없습니다."
        )


# =========================================================
# 8. DB 업체 목록
# =========================================================

st.divider()

st.header(
    "🏢 8. DB 해외업체 목록"
)


try:

    final_companies = (
        database.get_company_names()
    )

except Exception:

    final_companies = []


if final_companies:

    with st.expander(
        f"실제 저장된 업체 {len(final_companies):,}개"
    ):

        for index, company in enumerate(
            final_companies,
            start=1
        ):

            st.write(
                f"{index}. {company}"
            )

else:

    st.info(
        "현재 DB에 실제 저장된 업체가 없습니다."
    )


# =========================================================
# 9. 최종 DB 현황
# =========================================================

st.divider()

st.header(
    "📊 9. 최종 DB 현황"
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

    final_company_count = len(
        database.get_company_names()
    )

except Exception:

    final_company_count = 0


c1, c2, c3 = st.columns(3)

with c1:

    st.metric(
        "전체 경기",
        f"{final_match_count:,}"
    )

with c2:

    st.metric(
        "전체 최종배당",
        f"{final_odds_count:,}"
    )

with c3:

    st.metric(
        "실제 업체 수",
        f"{final_company_count:,}"
    )


# =========================================================
# 안내
# =========================================================

st.divider()

st.caption(
    "※ 스코어맨에서 수집한 완료 경기와 "
    "최종배당을 기준으로 분석합니다."
)

st.caption(
    "※ 배당확률은 승/무/패 배당의 역수를 "
    "정규화한 값입니다."
)

st.caption(
    "※ 부족확률 = 실제 결과 비율 - "
    "배당에서 계산된 확률입니다."
)

st.success(
    "✅ 프로그램 정상 작동"
                )
