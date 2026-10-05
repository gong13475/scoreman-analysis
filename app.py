import re
import streamlit as st

import database
import scoreman_crawler
import analysis


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="스코어맨 배당 분석",
    page_icon="⚽",
    layout="wide"
)


# =========================================================
# Turso 초기화
# =========================================================

try:

    db_ok = database.init_database()

except Exception as e:

    db_ok = False

    st.error("❌ Turso DB 연결 오류")
    st.code(str(e))


# =========================================================
# 세션 상태
# =========================================================

if "search_result" not in st.session_state:
    st.session_state.search_result = None

if "show_collection_log" not in st.session_state:
    st.session_state.show_collection_log = False


# =========================================================
# 제목
# =========================================================

st.title(
    "⚽ 전종목 해외배당 분석"
)

st.caption(
    "스코어맨 자동수집 · 해외업체 최종배당 · "
    "실제결과 · 확률분석 · Turso 영구저장"
)


# =========================================================
# DB 상태
# =========================================================

if db_ok:

    try:

        db_status = database.get_database_status()

        st.success(
            "🟢 Turso 영구 DB 연결됨"
        )

    except Exception as e:

        db_status = {
            "matches": 0,
            "odds": 0,
            "bookmakers": 0
        }

        st.error(
            "❌ Turso DB 조회 오류"
        )

        st.code(str(e))

else:

    db_status = {
        "matches": 0,
        "odds": 0,
        "bookmakers": 0
    }


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
# Turso DB 상세
# =========================================================

with st.expander(
    "🗄️ Turso DB 상태",
    expanded=False
):

    st.write(
        "현재 스코어맨 데이터는 "
        "**Turso Cloud SQLite**에 영구 저장됩니다."
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "저장 경기",
            f"{match_count:,}개"
        )

    with c2:
        st.metric(
            "저장 최종배당",
            f"{odds_count:,}개"
        )

    with c3:
        st.metric(
            "실제 저장 업체",
            f"{company_count:,}개"
        )

    st.markdown("---")

    st.subheader(
        "💾 Turso 저장용량"
    )

    try:

        storage = database.get_storage_usage()

    except Exception as e:

        storage = {
            "success": False,
            "size_mb": 0,
            "size_gb": 0,
            "message": str(e)
        }

    if storage.get("success"):

        size_mb = float(
            storage.get(
                "size_mb",
                0
            )
        )

        size_gb = float(
            storage.get(
                "size_gb",
                0
            )
        )

        c1, c2 = st.columns(2)

        with c1:

            if size_gb >= 1:

                st.metric(
                    "현재 DB 사용량",
                    f"{size_gb:.3f} GB"
                )

            else:

                st.metric(
                    "현재 DB 사용량",
                    f"{size_mb:.2f} MB"
                )

        with c2:

            st.metric(
                "저장 방식",
                "Turso Cloud SQLite"
            )

    else:

        st.warning(
            "⚠️ Turso 저장용량을 조회할 수 없습니다."
        )

        if storage.get("message"):

            st.caption(
                storage["message"]
            )

    st.markdown("---")

    if st.button(
        "🔄 DB 상태 및 저장용량 새로고침",
        use_container_width=True,
        key="refresh_database"
    ):

        st.rerun()


st.divider()


# =========================================================
# 자동수집
# =========================================================

st.header(
    "📥 스코어맨 경기 자동수집"
)

st.info(
    "시작 ID와 마지막 ID를 입력한 뒤 "
    "수집 시작 버튼을 누르면 백그라운드에서 수집합니다."
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
        format="%d",
        key="start_id"
    )


with c2:

    end_id = st.number_input(
        "마지막 경기 ID",
        min_value=1,
        value=3001118,
        step=1,
        format="%d",
        key="end_id"
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
# 수집 업체
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
    horizontal=True,
    key="crawl_mode"
)


selected_crawl_companies = []


if crawl_mode == "전체 업체 자동수집":

    st.success(
        "✅ Scoreman에서 제공하는 업체의 "
        "최종배당을 자동으로 수집합니다."
    )

else:

    try:

        companies = analysis.get_company_list()

    except Exception:

        companies = []

    selected_crawl_companies = st.multiselect(
        "수집 업체",
        options=companies,
        default=[],
        placeholder="여러 업체 선택 가능",
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
    format="%.2f",
    key="crawl_delay"
)


# =========================================================
# 현재 작업 상태
# =========================================================

try:

    status = scoreman_crawler.get_job_status()

except Exception as e:

    status = {
        "running": False,
        "finished": False,
        "error": str(e),
        "current": 0,
        "total": 0,
        "success": 0,
        "exists": 0,
        "failed": 0,
        "odds": 0,
        "log": ""
    }


# =========================================================
# 수집 버튼
# =========================================================

if status.get("running"):

    st.error(
        "🔴 현재 수집중입니다."
    )

    if st.button(
        "🛑 수집 중지",
        type="secondary",
        use_container_width=True,
        key="stop_collection"
    ):

        if hasattr(
            scoreman_crawler,
            "stop_background_collection"
        ):

            try:

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

            except Exception as e:

                st.error(
                    "수집 중지 오류"
                )

                st.code(str(e))

        else:

            st.error(
                "scoreman_crawler.py에 "
                "수집 중지 함수가 없습니다."
            )

else:

    if st.button(
        "🚀 백그라운드 수집 시작",
        type="primary",
        use_container_width=True,
        key="start_collection"
    ):

        if not db_ok:

            st.error(
                "❌ Turso DB 연결이 되어 있지 않습니다."
            )

        elif end_id < start_id:

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
                        "🚀 백그라운드 수집을 시작했습니다."
                    )

                    st.rerun()

                else:

                    st.warning(
                        "이미 수집 작업이 실행 중입니다."
                    )

            except Exception as e:

                st.error(
                    "수집 시작 오류"
                )

                st.code(str(e))


# =========================================================
# 수집 상태
# =========================================================

try:

    status = scoreman_crawler.get_job_status()

except Exception:

    status = {
        "running": False,
        "finished": False
    }


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

        st.error("🔴 수집중")

    elif status.get("stopped"):

        st.warning("🛑 수집 중지됨")

    elif status.get("finished"):

        st.success("🟢 수집 완료")

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

    last_id = status.get(
        "last_completed_id"
    )

    if last_id:

        st.info(
            f"✅ 마지막 완료 경기 ID: **{last_id}**"
        )

    status_companies = status.get(
        "selected_companies",
        []
    )

    if status_companies:

        st.write(
            "**수집 업체:** "
            + " / ".join(status_companies)
        )

    show_log = st.checkbox(
        "📜 수집 로그 보기",
        value=st.session_state.show_collection_log,
        key="show_collection_log"
    )

    if show_log:

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
                "아직 수집 로그가 없습니다."
            )

    if status.get("error"):

        st.error(
            "수집 작업 오류: "
            + str(status["error"])
        )

    if status.get("finished"):

        if status.get("stopped"):

            st.warning(
                "🛑 사용자가 수집을 중지했습니다."
            )

        elif not status.get("error"):

            st.success(
                "✅ 수집 작업이 완료되었습니다."
            )


st.divider()


# =========================================================
# 저장 경기
# =========================================================

st.header(
    "📋 저장된 전체 경기"
)


try:

    matches = database.get_all_matches()

except Exception as e:

    matches = []

    st.error(
        "경기 데이터 조회 오류"
    )

    st.code(str(e))


if not matches:

    st.info(
        "저장된 경기가 없습니다."
    )

else:

    table = []

    for row in matches:

        table.append({

            "경기 ID":
                row.get("schedule_id"),

            "경기일":
                row.get("match_date"),

            "홈팀":
                row.get("home_team"),

            "원정팀":
                row.get("away_team"),

            "홈 점수":
                row.get("home_score"),

            "원정 점수":
                row.get("away_score"),

            "실제 결과":
                row.get("result"),

            "출처":
                row.get("source")
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
        "입력한 승/무/패 배당과 동일한 "
        "DB의 과거 경기를 검색합니다."
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
        "🔎 동일 배당 경기 검색 및 확률 분석",
        type="primary",
        use_container_width=True,
        key="search_odds"
    ):

        try:

            result = analysis.run_search(
                selected_companies,
                input_odds
            )

            if result.get("success"):

                st.session_state.search_result = result

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

            st.code(str(e))


# =========================================================
# 검색 결과
# =========================================================

search = st.session_state.search_result


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

    st.subheader(
        "🎯 업체별 확률 / 실제결과 / 부족확률"
    )

    st.caption(
        "부족확률 = 실제 결과율 - 기대값확률"
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

            st.code(str(e))

            continue

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

            expected = company_stats[
                "expected"
            ][key]

            actual = company_stats[
                "actual"
            ][key]

            difference = actual - expected

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
            [
                "home",
                "draw",
                "away"
            ],
            key=lambda x:
                company_stats["actual"][x]
        )

        best_label = {
            "home": "승",
            "draw": "무",
            "away": "패"
        }[best_key]

        st.success(
            f"실제 발생률이 가장 높은 결과: "
            f"**{best_label} "
            f"{company_stats['actual'][best_key]:.2f}%**"
        )

    # =====================================================
    # 검색 경기
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
                .get(company)
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
# 저장된 최종배당
# =========================================================

st.header(
    "🗃️ 저장된 업체별 최종배당"
)


if st.checkbox(
    "DB 최종배당 데이터 보기",
    key="show_db_odds"
):

    try:

        odds_rows = database.get_all_odds()

    except Exception as e:

        odds_rows = []

        st.error(
            "최종배당 조회 오류"
        )

        st.code(str(e))

    table = []

    for row in odds_rows:

        table.append({

            "경기 ID":
                row.get("schedule_id"),

            "업체":
                row.get("bookmaker"),

            "최종 승":
                row.get("home_odds"),

            "최종 무":
                row.get("draw_odds"),

            "최종 패":
                row.get("away_odds")
        })

    if table:

        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "저장된 최종배당 데이터가 없습니다."
        )


# =========================================================
# 업체별 저장량
# =========================================================

st.divider()

st.header(
    "🏢 해외업체별 저장 데이터"
)


try:

    company_counts = (
        database.get_company_counts()
    )

except Exception as e:

    company_counts = {}

    st.error(
        "업체별 데이터 조회 오류"
    )

    st.code(str(e))


if company_counts:

    st.dataframe(
        [
            {
                "업체": company,
                "저장 배당 수": count
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

try:

    current_status = (
        scoreman_crawler.get_job_status()
    )

except Exception:

    current_status = {
        "running": False
    }


if current_status.get("running"):

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
