import streamlit as st
import time
import database
import crawler
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
# 세션 상태
# =========================================================

if "crawl_log" not in st.session_state:
    st.session_state.crawl_log = ""

if "crawl_result" not in st.session_state:
    st.session_state.crawl_result = None

if "crawl_running" not in st.session_state:
    st.session_state.crawl_running = False


# =========================================================
# 로그 함수
# =========================================================

def add_log(message):

    message = str(message)

    if st.session_state.crawl_log:

        st.session_state.crawl_log += "\n"

    st.session_state.crawl_log += message

    log_box.code(
        st.session_state.crawl_log,
        language="text"
    )


# =========================================================
# 진행률
# =========================================================

def update_progress(value):

    try:

        value = float(value)

        progress_bar.progress(
            min(
                max(value, 0.0),
                1.0
            )
        )

    except Exception:

        pass


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

try:

    match_count = database.get_match_count()

except Exception:

    match_count = 0


try:

    odds_count = database.get_odds_count()

except Exception:

    odds_count = 0


col1, col2 = st.columns(2)

with col1:

    st.metric(
        "저장 경기",
        f"{match_count:,}"
    )

with col2:

    st.metric(
        "저장 배당",
        f"{odds_count:,}"
    )


st.divider()


# =========================================================
# 경기 DB 자동 수집
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
        step=1,
        format="%d"
    )


with col2:

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
    f"검색할 ID: **{total_ids:,}개**"
)


delay = st.number_input(
    "요청 간격",
    min_value=0.20,
    max_value=2.00,
    value=0.50,
    step=0.10,
    format="%.2f"
)


# =========================================================
# 크롤링 시작
# =========================================================

start_button = st.button(
    "🚀 DB 수집 시작",
    type="primary",
    use_container_width=True
)


if start_button:

    if end_id < start_id:

        st.error(
            "마지막 경기 ID가 시작 경기 ID보다 작습니다."
        )

    else:

        st.session_state.crawl_running = True
        st.session_state.crawl_log = ""
        st.session_state.crawl_result = None

        st.subheader(
            "📡 크롤링 로그"
        )

        log_box = st.empty()

        progress_bar = st.progress(
            0
        )

        # -------------------------------------------------
        # 시작 로그
        # -------------------------------------------------

        add_log(
            "========================================"
        )

        add_log(
            "Scoreman DB 수집 시작"
        )

        add_log(
            f"범위: {int(start_id):,} ~ "
            f"{int(end_id):,}"
        )

        add_log(
            f"총 검색: {total_ids:,}건"
        )

        add_log(
            "========================================"
        )

        # -------------------------------------------------
        # 실제 수집
        # -------------------------------------------------

        try:

            result = crawler.build_database_progress(

                start_id=int(start_id),

                end_id=int(end_id),

                progress_callback=
                    update_progress,

                log_callback=
                    add_log,

                delay=float(delay)
            )

            st.session_state.crawl_result = (
                result
            )

            st.session_state.crawl_running = False

            # -------------------------------------------------
            # 완료 로그
            # -------------------------------------------------

            add_log(
                "========================================"
            )

            add_log(
                "DB 수집 완료"
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
                f"저장 배당: "
                f"{result.get('odds', 0):,}"
            )

            add_log(
                "========================================"
            )

            progress_bar.progress(
                1.0
            )

            st.success(
                "✅ DB 수집 완료"
            )

            # -------------------------------------------------
            # 결과 요약
            # -------------------------------------------------

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
                    "저장 배당",
                    f"{result.get('odds', 0):,}"
                )

        except Exception as e:

            st.session_state.crawl_running = False

            add_log(
                "========================================"
            )

            add_log(
                f"[치명적 오류] {e}"
            )

            add_log(
                "========================================"
            )

            st.error(
                f"크롤링 오류: {e}"
            )


# =========================================================
# 이전 크롤링 로그 표시
# =========================================================

elif st.session_state.crawl_log:

    st.subheader(
        "📡 수집 완료 로그"
    )

    st.code(
        st.session_state.crawl_log,
        language="text"
    )


# =========================================================
# 저장된 전체 경기
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
        f"총 {len(matches):,}경기가 저장되어 있습니다."
    )

    # -----------------------------------------------------
    # DataFrame용 데이터
    # -----------------------------------------------------

    table_data = []

    for row in matches:

        try:

            schedule_id = row["schedule_id"]

        except Exception:

            schedule_id = ""

        try:

            match_date = row["match_date"]

        except Exception:

            match_date = ""

        try:

            home_team = row["home_team"]

        except Exception:

            home_team = ""

        try:

            away_team = row["away_team"]

        except Exception:

            away_team = ""

        try:

            home_score = row["home_score"]

        except Exception:

            home_score = ""

        try:

            away_score = row["away_score"]

        except Exception:

            away_score = ""

        try:

            result = row["result"]

        except Exception:

            result = ""

        table_data.append({

            "경기 ID":
                schedule_id,

            "경기일":
                match_date,

            "홈팀":
                home_team,

            "원정팀":
                away_team,

            "홈":
                home_score,

            "원정":
                away_score,

            "결과":
                result
        })

    st.dataframe(
        table_data,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# 업체별 최종배당 검색
# =========================================================

st.divider()

st.header(
    "🎯 업체별 최종배당 완전일치 검색"
)

st.write(
    "여러 업체를 선택한 뒤 각 업체의 최종배당을 입력하세요. "
    "입력한 배당이 DB의 같은 업체 데이터와 모두 일치하는 "
    "경기만 검색합니다."
)


# =========================================================
# 업체 목록
# =========================================================

try:

    companies = (
        analysis.get_company_list()
    )

except Exception as e:

    companies = []

    st.error(
        f"업체 목록을 불러오지 못했습니다: {e}"
    )


st.subheader(
    "🔎 검색할 업체 선택"
)


if companies:

    st.caption(
        f"검색 가능 업체: {len(companies)}개"
    )

    selected_companies = st.multiselect(

        "업체 선택",

        options=companies,

        default=[],

        placeholder=
            "여러 업체를 선택하세요"
    )

else:

    selected_companies = []

    st.warning(
        "DB에서 업체 목록을 찾지 못했습니다."
    )


# =========================================================
# 선택 업체 최종배당 입력
# =========================================================

input_odds = {}


if selected_companies:

    st.subheader(
        "💰 선택 업체 최종배당 입력"
    )

    for company in selected_companies:

        st.markdown(
            f"### 🏢 {company}"
        )

        c1, c2, c3 = st.columns(3)

        safe_key = (
            str(company)
            .replace(" ", "_")
            .replace(".", "_")
            .replace("/", "_")
        )

        with c1:

            final_home = st.number_input(

                f"{company} 최종 승",

                min_value=0.01,

                value=1.50,

                step=0.01,

                format="%.2f",

                key=
                    f"final_home_{safe_key}"
            )

        with c2:

            final_draw = st.number_input(

                f"{company} 최종 무",

                min_value=0.01,

                value=3.50,

                step=0.01,

                format="%.2f",

                key=
                    f"final_draw_{safe_key}"
            )

        with c3:

            final_away = st.number_input(

                f"{company} 최종 패",

                min_value=0.01,

                value=5.00,

                step=0.01,

                format="%.2f",

                key=
                    f"final_away_{safe_key}"
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
        "🔎 최종배당 검색",
        type="primary",
        use_container_width=True
    ):

        try:

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

                if not results:

                    st.warning(
                        "입력한 모든 업체의 최종배당과 "
                        "완전히 일치하는 경기가 없습니다."
                    )

                else:

                    st.success(
                        f"🎯 "
                        f"{len(results):,}경기를 찾았습니다."
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

                        st.markdown(
                            f"### {index}. "
                            f"{home_team} "
                            f"vs "
                            f"{away_team}"
                        )

                        c1, c2, c3 = st.columns(3)

                        with c1:

                            st.write(
                                "**경기 ID**"
                            )

                            st.write(
                                row.get(
                                    "schedule_id",
                                    ""
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
                                "**결과**"
                            )

                            st.write(
                                row.get(
                                    "result",
                                    "-"
                                )
                            )

                        # ---------------------------------
                        # 업체별 배당
                        # ---------------------------------

                        company_odds = row.get(
                            "company_odds",
                            {}
                        )

                        for company in selected_companies:

                            odds = (
                                company_odds.get(
                                    company
                                )
                            )

                            if odds:

                                st.write(
                                    f"**{company}**  "
                                    f"승 {odds.get('home')} / "
                                    f"무 {odds.get('draw')} / "
                                    f"패 {odds.get('away')}"
                                )

                        st.divider()

        except Exception as e:

            st.error(
                f"검색 오류: {e}"
            )

else:

    st.info(
        "검색할 업체를 하나 이상 선택하세요."
    )


# =========================================================
# 저장된 업체별 배당
# =========================================================

st.divider()

st.header(
    "🗃️ 저장된 업체별 최종배당 데이터"
)


show_odds = st.checkbox(
    "DB 최종배당 데이터 보기",
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

    if not odds_rows:

        st.info(
            "저장된 배당 데이터가 없습니다."
        )

    else:

        table_data = []

        for row in odds_rows:

            try:
                schedule_id = row[
                    "schedule_id"
                ]
            except Exception:
                schedule_id = ""

            try:
                company_name = row[
                    "company_name"
                ]
            except Exception:
                company_name = ""

            try:
                final_home = row[
                    "final_home"
                ]
            except Exception:
                final_home = ""

            try:
                final_draw = row[
                    "final_draw"
                ]
            except Exception:
                final_draw = ""

            try:
                final_away = row[
                    "final_away"
                ]
            except Exception:
                final_away = ""

            table_data.append({

                "경기 ID":
                    schedule_id,

                "업체":
                    company_name,

                "최종 승":
                    final_home,

                "최종 무":
                    final_draw,

                "최종 패":
                    final_away
            })

        st.dataframe(
            table_data,
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# 최종 DB 현황
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
        analysis.get_company_list()
    )

except Exception:

    final_companies = []


c1, c2, c3 = st.columns(3)

with c1:

    st.metric(
        "전체 경기",
        f"{final_match_count:,}"
    )

with c2:

    st.metric(
        "전체 배당",
        f"{final_odds_count:,}"
    )

with c3:

    st.metric(
        "업체 수",
        f"{len(final_companies):,}"
    )


# =========================================================
# 업체 목록 확인
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
            "업체가 없습니다."
        )


# =========================================================
# 정상 작동
# =========================================================

st.success(
    "✅ 프로그램 정상 작동"
    )
