import streamlit as st
import crawler
import database
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

database.init_database()


# =========================================================
# 제목
# =========================================================

st.title(
    "⚽ 스코어맨 배당 분석"
)

st.caption(
    "스코어맨 전체 경기 DB + 업체별 최종배당 완전일치 검색"
)


# =========================================================
# DB 현황
# =========================================================

status = (
    analysis.get_database_status()
)

c1, c2, c3 = st.columns(3)

with c1:

    st.metric(
        "저장 경기",
        status["matches"]
    )

with c2:

    st.metric(
        "저장 배당",
        status["odds"]
    )

with c3:

    st.metric(
        "저장 업체",
        status["company_count"]
    )


st.divider()


# =========================================================
# 크롤링
# =========================================================

st.header(
    "🚀 스코어맨 전체 경기 DB 자동 수집"
)

st.write(
    "지정한 경기 ID 범위의 완료된 경기를 수집하고 "
    "경기정보와 업체별 최종배당을 DB에 저장합니다."
)


col1, col2 = st.columns(2)

with col1:

    start_id = st.number_input(
        "시작 경기 ID",
        min_value=1,
        value=3001118,
        step=1
    )

with col2:

    end_id = st.number_input(
        "마지막 경기 ID",
        min_value=1,
        value=3001118,
        step=1
    )


if end_id >= start_id:

    total_ids = (
        end_id -
        start_id +
        1
    )

else:

    total_ids = 0


st.info(
    f"검색할 ID: {total_ids:,}개"
)


delay = st.slider(
    "요청 간격",
    min_value=0.20,
    max_value=2.00,
    value=0.50,
    step=0.10
)


# =========================================================
# 크롤링 로그
# =========================================================

if "crawl_logs" not in st.session_state:

    st.session_state.crawl_logs = []


if "crawl_result" not in st.session_state:

    st.session_state.crawl_result = None


log_box = st.empty()


def add_log(message):

    message = str(
        message
    )

    st.session_state.crawl_logs.append(
        message
    )

    # 너무 오래된 로그를 무한히 쌓지 않음
    if len(
        st.session_state.crawl_logs
    ) > 1000:

        st.session_state.crawl_logs = (
            st.session_state.crawl_logs[-1000:]
        )

    log_box.text(
        "\n".join(
            st.session_state.crawl_logs
        )
    )


progress_box = st.empty()


def update_progress(value):

    try:

        progress_box.progress(
            float(value)
        )

    except Exception:

        pass


# =========================================================
# 수집 버튼
# =========================================================

if st.button(
    "🚀 DB 수집 시작",
    type="primary",
    use_container_width=True
):

    if end_id < start_id:

        st.error(
            "마지막 경기 ID가 시작 경기 ID보다 작습니다."
        )

    else:

        # 이전 로그 삭제
        st.session_state.crawl_logs = []

        st.session_state.crawl_result = None

        log_box.text("")

        progress_box.progress(
            0
        )

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

            st.session_state.crawl_result = (
                result
            )

            progress_box.progress(
                1.0
            )

            st.success(
                "✅ DB 수집 완료"
            )

            st.rerun()

        except Exception as e:

            add_log(
                f"[치명적 오류] {e}"
            )

            st.error(
                f"수집 중 오류가 발생했습니다: {e}"
            )


# =========================================================
# 수집 결과
# =========================================================

result = (
    st.session_state.crawl_result
)

if result:

    r1, r2, r3, r4 = st.columns(4)

    with r1:

        st.metric(
            "전체 검색",
            result.get(
                "total",
                0
            )
        )

    with r2:

        st.metric(
            "신규 저장",
            result.get(
                "success",
                0
            )
        )

    with r3:

        st.metric(
            "기존 경기",
            result.get(
                "exists",
                0
            )
        )

    with r4:

        st.metric(
            "저장 배당",
            result.get(
                "odds",
                0
            )
        )


# =========================================================
# 로그
# =========================================================

if st.session_state.crawl_logs:

    with st.expander(
        "📡 수집 로그",
        expanded=True
    ):

        st.text(
            "\n".join(
                st.session_state.crawl_logs
            )
        )


st.divider()


# =========================================================
# 저장된 전체 경기
# =========================================================

st.header(
    "📋 저장된 전체 경기"
)


matches = (
    analysis.get_all_matches()
)


if not matches:

    st.info(
        "저장된 경기가 없습니다."
    )

else:

    match_data = []

    for row in matches:

        match_data.append({

            "경기 ID":
                row["schedule_id"],

            "날짜":
                row["match_date"],

            "홈팀":
                row["home_team"],

            "원정팀":
                row["away_team"],

            "스코어":
                (
                    f"{row['home_score']}-"
                    f"{row['away_score']}"
                ),

            "결과":
                row["result"]
        })

    st.dataframe(
        match_data,
        use_container_width=True,
        hide_index=True
    )


st.divider()


# =========================================================
# 업체별 최종배당 검색
# =========================================================

st.header(
    "🎯 업체별 최종배당 완전일치 검색"
)

st.write(
    "여러 업체를 선택한 뒤 각 업체의 "
    "최종 승/무/패 배당을 입력하세요. "
    "선택한 모든 업체의 최종배당이 "
    "같은 경기에서 일치하는 경우만 검색합니다."
)


# =========================================================
# 업체 목록
# =========================================================

companies = (
    analysis.get_company_list()
)


# ---------------------------------------------------------
# 업체 선택
# ---------------------------------------------------------

selected_companies = st.multiselect(
    "검색할 업체 선택",
    options=companies,
    default=[],
    placeholder="업체를 선택하세요"
)


# =========================================================
# 선택 업체별 최종배당 입력
# =========================================================

input_odds = {}


if selected_companies:

    st.subheader(
        "💰 선택 업체 최종배당 입력"
    )

    for company in selected_companies:

        company = (
            analysis.normalize_company_name(
                company
            )
        )

        st.markdown(
            f"### 🏢 {company}"
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            home = st.text_input(
                f"{company} - 최종 승",
                key=f"final_home_{company}"
            )

        with col2:

            draw = st.text_input(
                f"{company} - 최종 무",
                key=f"final_draw_{company}"
            )

        with col3:

            away = st.text_input(
                f"{company} - 최종 패",
                key=f"final_away_{company}"
            )

        input_odds[
            company
        ] = {

            "home":
                home,

            "draw":
                draw,

            "away":
                away
        }

        st.divider()


else:

    st.info(
        "위에서 검색할 업체를 선택하세요."
    )


# =========================================================
# 검색
# =========================================================

if st.button(
    "🔎 최종배당 검색",
    type="primary",
    use_container_width=True
):

    if not selected_companies:

        st.warning(
            "검색할 업체를 하나 이상 선택하세요."
        )

    else:

        # -------------------------------------------------
        # 빈 값 검사
        # -------------------------------------------------

        invalid_company = None

        for company in selected_companies:

            values = input_odds.get(
                company,
                {}
            )

            for key in [
                "home",
                "draw",
                "away"
            ]:

                if not str(
                    values.get(
                        key,
                        ""
                    )
                ).strip():

                    invalid_company = company

                    break

            if invalid_company:

                break


        if invalid_company:

            st.warning(
                f"{invalid_company}의 "
                "최종 승/무/패 배당을 "
                "모두 입력하세요."
            )

        else:

            with st.spinner(
                "DB 검색 중..."
            ):

                result = analysis.run_search(
                    selected_companies,
                    input_odds
                )


            if not result["success"]:

                st.error(
                    result["message"]
                )

            else:

                rows = (
                    result["results"]
                )

                if not rows:

                    st.warning(
                        "조건과 일치하는 경기가 없습니다."
                    )

                else:

                    st.success(
                        f"🎯 {len(rows)}경기를 찾았습니다."
                    )

                    # -------------------------------------------------
                    # 결과 표시
                    # -------------------------------------------------

                    for index, row in enumerate(
                        rows,
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

                        result_text = row.get(
                            "result",
                            ""
                        )

                        score = (
                            f"{row.get('home_score', '-')}"
                            f"-"
                            f"{row.get('away_score', '-')}"
                        )

                        with st.container(
                            border=True
                        ):

                            st.markdown(
                                f"### {index}. "
                                f"{home_team} "
                                f"vs "
                                f"{away_team}"
                            )

                            c1, c2, c3 = (
                                st.columns(3)
                            )

                            with c1:

                                st.write(
                                    f"**경기 ID:** "
                                    f"{row.get('schedule_id', '')}"
                                )

                            with c2:

                                st.write(
                                    f"**스코어:** {score}"
                                )

                            with c3:

                                st.write(
                                    f"**결과:** {result_text}"
                                )

                            st.caption(
                                f"경기일: "
                                f"{row.get('match_date', '')}"
                            )

                            company_data = (
                                row.get(
                                    "company_odds",
                                    {}
                                )
                            )

                            for company in (
                                selected_companies
                            ):

                                company = (
                                    analysis.normalize_company_name(
                                        company
                                    )
                                )

                                odds = (
                                    company_data.get(
                                        company
                                    )
                                )

                                if not odds:
                                    continue

                                st.write(
                                    f"**{company}**  "
                                    f"승 `{odds.get('home')}`  "
                                    f"무 `{odds.get('draw')}`  "
                                    f"패 `{odds.get('away')}`"
                                )


st.divider()


# =========================================================
# DB 배당 데이터
# =========================================================

st.header(
    "🗃️ 저장된 업체별 최종배당 데이터"
)


with st.expander(
    "DB 최종배당 데이터 보기"
):

    odds_rows = (
        analysis.get_all_odds()
    )

    if not odds_rows:

        st.info(
            "저장된 배당 데이터가 없습니다."
        )

    else:

        odds_data = []

        for row in odds_rows:

            odds_data.append({

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
            odds_data,
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# 최종 현황
# =========================================================

st.divider()

st.header(
    "📊 최종 DB 현황"
)

final_status = (
    analysis.get_database_status()
)

c1, c2 = st.columns(2)

with c1:

    st.metric(
        "전체 경기",
        final_status["matches"]
    )

with c2:

    st.metric(
        "전체 배당",
        final_status["odds"]
    )


st.success(
    "✅ 프로그램 정상 작동"
)
