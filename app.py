import streamlit as st
import database
import scoreman_crawler
import analysis
import threading
import time


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

defaults = {

    "crawl_log": "",

    "crawl_result": None,

    "search_result": None,

    "crawl_running": False,

    "crawl_data": {

        "current": 0,

        "total": 0,

        "success": 0,

        "exists": 0,

        "failed": 0,

        "odds": 0,

        "finished": False

    }

}


for key, value in defaults.items():

    if key not in st.session_state:

        st.session_state[key] = value


# =========================================================
# 제목
# =========================================================

st.title(
    "⚽ 전종목 해외배당 분석"
)

st.caption(
    "스코어맨 자동수집 · 여러 해외업체 선택 · "
    "최종배당 · 실제결과 · 배당확률"
)


# =========================================================
# DB 현황
# =========================================================

try:

    match_count = (
        database.get_match_count()
    )

except Exception:

    match_count = 0


try:

    odds_count = (
        database.get_odds_count()
    )

except Exception:

    odds_count = 0


try:

    company_names = (
        database.get_company_names()
    )

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
    "경기 ID 범위를 검색하여 완료된 경기정보와 "
    "선택한 해외업체의 최종배당을 저장합니다."
)

st.info(
    "여러 업체를 동시에 선택할 수 있습니다.\n\n"
    "예: Bet365 + William Hill + 10Bet + 기타 업체"
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


# =========================================================
# 수집 업체
# =========================================================

st.subheader(
    "🏢 수집할 해외업체 선택"
)


try:

    all_companies = (
        analysis.get_company_list()
    )

except Exception:

    all_companies = []


preferred = [

    "Bet365",
    "William Hill",
    "10Bet"

]


for company in preferred:

    if company not in all_companies:

        all_companies.append(
            company
        )


all_companies = sorted(

    list(
        dict.fromkeys(
            all_companies
        )
    ),

    key=lambda x: str(x).lower()

)


selected_crawl_companies = st.multiselect(

    "수집 업체",

    options=all_companies,

    default=[],

    placeholder=(
        "여러 업체를 선택하세요"
    ),

    key="crawl_companies"

)


if selected_crawl_companies:

    st.success(
        "선택 업체: "
        +
        " / ".join(
            selected_crawl_companies
        )
    )

else:

    st.warning(
        "수집 업체를 1개 이상 선택하세요."
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

if st.button(

    "🚀 여러 업체 동시 수집 시작",

    type="primary",

    use_container_width=True,

    disabled=st.session_state.crawl_running

):

    if end_id < start_id:

        st.error(
            "마지막 ID가 시작 ID보다 작습니다."
        )

    elif not selected_crawl_companies:

        st.error(
            "수집 업체를 1개 이상 선택하세요."
        )

    else:

        st.session_state.crawl_log = ""

        st.session_state.crawl_result = None

        st.session_state.crawl_running = True

        st.session_state.crawl_data = {

            "current": 0,

            "total": total_ids,

            "success": 0,

            "exists": 0,

            "failed": 0,

            "odds": 0,

            "finished": False

        }


        st.session_state.crawl_log = (

            "========================================\n"

            "⚽ Scoreman DB 자동수집 시작\n"

            f"범위: {int(start_id):,} ~ "
            f"{int(end_id):,}\n"

            f"전체 ID: {total_ids:,}\n"

            "----------------------------------------\n"

            "수집 업체:\n"

            +

            "\n".join(

                f"- {company}"

                for company in
                selected_crawl_companies

            )

            +

            "\n----------------------------------------\n"

            "초기배당: 저장하지 않음\n"

            "최종배당: 저장\n"

            "========================================"

        )


        st.rerun()


# =========================================================
# 진행 표시
# =========================================================

if st.session_state.crawl_running:

    st.subheader(
        "📡 수집 진행상황"
    )


    data = st.session_state.crawl_data


    current = int(
        data.get(
            "current",
            0
        )
    )


    total = int(
        data.get(
            "total",
            total_ids
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


    c1, c2, c3, c4, c5 = st.columns(5)


    with c1:

        st.metric(
            "진행",
            f"{current:,}/{total:,}"
        )


    with c2:

        st.metric(
            "신규",
            f"{data.get('success', 0):,}"
        )


    with c3:

        st.metric(
            "기존",
            f"{data.get('exists', 0):,}"
        )


    with c4:

        st.metric(
            "실패",
            f"{data.get('failed', 0):,}"
        )


    with c5:

        st.metric(
            "최종배당",
            f"{data.get('odds', 0):,}"
        )


    st.code(
        st.session_state.crawl_log,
        language="text"
    )


    st.info(
        "수집 중입니다. "
        "휴대폰 화면이 꺼지거나 다른 앱을 사용하면 "
        "브라우저 연결이 끊길 수 있으므로, "
        "장시간 수집은 서버에서 계속 실행되는 "
        "환경에서 사용하는 것이 안전합니다."
    )


# =========================================================
# 2. 저장 경기
# =========================================================

st.divider()

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
# 3. 분석 업체 선택
# =========================================================

st.divider()

st.header(
    "🌎 해외배당업체 선택"
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

    selected_companies = st.multiselect(

        "분석할 업체",

        options=companies,

        default=[],

        placeholder="여러 업체 선택 가능"

    )

else:

    selected_companies = []


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

                f"{company} 最종 승",

                min_value=0.01,

                value=1.50,

                step=0.01,

                format="%.2f",

                key=f"home_{safe_key}"

            )


        with c2:

            final_draw = st.number_input(

                f"{company} 최종 무",

                min_value=0.01,

                value=3.50,

                step=0.01,

                format="%.2f",

                key=f"draw_{safe_key}"

            )


        with c3:

            final_away = st.number_input(

                f"{company} 최종 패",

                min_value=0.01,

                value=5.00,

                step=0.01,

                format="%.2f",

                key=f"away_{safe_key}"

            )


        input_odds[company] = {

            "home":
                final_home,

            "draw":
                final_draw,

            "away":
                final_away

        }


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

            st.session_state.search_result = (

                result.get(
                    "results",
                    []
                )

            )


# =========================================================
# 5. 검색 결과
# =========================================================

search_results = (
    st.session_state.search_result
)


if search_results:

    st.divider()

    st.header(
        "📊 배당 확률 대비 실제 결과 분석"
    )


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


    win_pct = (
        win_count
        /
        total_games
        *
        100
        if total_games
        else 0
    )


    draw_pct = (
        draw_count
        /
        total_games
        *
        100
        if total_games
        else 0
    )


    loss_pct = (
        loss_count
        /
        total_games
        *
        100
        if total_games
        else 0
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


    st.subheader(
        "🎯 업체별 부족확률"
    )


    for company in selected_companies:

        company_data = []


        for row in search_results:

            odds = (

                row.get(
                    "company_odds",
                    {}
                )

                .get(
                    company
                )

            )


            if not odds:

                continue


            try:

                home = float(
                    odds["home"]
                )

                draw = float(
                    odds["draw"]
                )

                away = float(
                    odds["away"]
                )


                raw_home = 1 / home

                raw_draw = 1 / draw

                raw_away = 1 / away


                total_raw = (

                    raw_home
                    +
                    raw_draw
                    +
                    raw_away

                )


                company_data.append({

                    "home":
                        raw_home
                        /
                        total_raw
                        *
                        100,

                    "draw":
                        raw_draw
                        /
                        total_raw
                        *
                        100,

                    "away":
                        raw_away
                        /
                        total_raw
                        *
                        100,

                    "result":
                        row.get(
                            "result",
                            ""
                        )

                })


            except Exception:

                continue


        if not company_data:

            continue


        count = len(
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


        win_actual = (
            actual_win
            /
            count
            *
            100
        )


        draw_actual = (
            actual_draw
            /
            count
            *
            100
        )


        loss_actual = (
            actual_loss
            /
            count
            *
            100
        )


        avg_home = (
            sum(
                x["home"]
                for x in company_data
            )
            /
            count
        )


        avg_draw = (
            sum(
                x["draw"]
                for x in company_data
            )
            /
            count
        )


        avg_away = (
            sum(
                x["away"]
                for x in company_data
            )
            /
            count
        )


        win_gap = (
            win_actual
            -
            avg_home
        )


        draw_gap = (
            draw_actual
            -
            avg_draw
        )


        loss_gap = (
            loss_actual
            -
            avg_away
        )


        st.markdown(
            f"### 🏢 {company}"
        )


        st.write(
            f"분석 경기: **{count:,}건**"
        )


        table = [

            {

                "구분":
                    "승",

                "배당확률":
                    f"{avg_home:.2f}%",

                "실제결과":
                    f"{win_actual:.2f}%",

                "실제건수":
                    f"{actual_win:,}건",

                "차이":
                    f"{win_gap:+.2f}%",

                "부족확률":
                    f"{max(0, -win_gap):.2f}%"

            },

            {

                "구분":
                    "무",

                "배당확률":
                    f"{avg_draw:.2f}%",

                "실제결과":
                    f"{draw_actual:.2f}%",

                "실제건수":
                    f"{actual_draw:,}건",

                "차이":
                    f"{draw_gap:+.2f}%",

                "부족확률":
                    f"{max(0, -draw_gap):.2f}%"

            },

            {

                "구분":
                    "패",

                "배당확률":
                    f"{avg_away:.2f}%",

                "실제결과":
                    f"{loss_actual:.2f}%",

                "실제건수":
                    f"{actual_loss:,}건",

                "차이":
                    f"{loss_gap:+.2f}%",

                "부족확률":
                    f"{max(0, -loss_gap):.2f}%"

            }

        ]


        st.dataframe(

            table,

            use_container_width=True,

            hide_index=True

        )


    # =====================================================
    # 경기 목록
    # =====================================================

    st.divider()

    st.subheader(
        "📋 검색된 경기"
    )


    for index, row in enumerate(

        search_results,

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
                "**스코어**"
            )

            st.write(

                f"{row.get('home_score', '-')}"
                f" - "
                f"{row.get('away_score', '-')}"

            )


        with c3:

            st.write(
                "**실제 결과**"
            )

            st.write(
                row.get(
                    "result",
                    "-"
                )
            )


        with c4:

            st.write(
                "**경기일**"
            )

            st.write(
                row.get(
                    "match_date",
                    "-"
                )
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

                    f"🏢 **{company}** "
                    f"승 `{odds.get('home')}` / "
                    f"무 `{odds.get('draw')}` / "
                    f"패 `{odds.get('away')}`"

                )


        st.divider()


# =========================================================
# 6. DB 최종배당
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
    "💡 수집할 때 업체를 1개만 선택할 필요가 없습니다. "
    "Bet365 / William Hill / 10Bet 및 DB에 등록된 "
    "다른 업체도 여러 개 선택할 수 있습니다."
)

st.success(
    "✅ 프로그램 정상 작동"
)
