import streamlit as st
import database
import scoreman_crawler
import analysis

import threading
import time
from datetime import datetime


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
# 백그라운드 수집 상태
# =========================================================

if "crawler_state" not in st.session_state:

    st.session_state.crawler_state = {

        "running": False,

        "finished": False,

        "start_id": 0,

        "end_id": 0,

        "current_id": 0,

        "last_saved_id": None,

        "total": 0,

        "processed": 0,

        "success": 0,

        "skipped": 0,

        "failed": 0,

        "odds": 0,

        "message": "",

        "started_at": "",

        "finished_at": "",

        "selected_companies": []

    }


if "crawl_thread" not in st.session_state:

    st.session_state.crawl_thread = None


if "crawl_log" not in st.session_state:

    st.session_state.crawl_log = ""


if "search_result" not in st.session_state:

    st.session_state.search_result = None


# =========================================================
# 전역 백그라운드 상태
#
# Streamlit rerun이 발생해도 작업 상태를 유지하기 위한
# 모듈 전역 상태
# =========================================================

if "background_initialized" not in st.session_state:

    st.session_state.background_initialized = True


if not hasattr(
    scoreman_crawler,
    "_background_job"
):

    scoreman_crawler._background_job = {

        "running": False,

        "finished": False,

        "start_id": 0,

        "end_id": 0,

        "current_id": 0,

        "last_saved_id": None,

        "total": 0,

        "processed": 0,

        "success": 0,

        "skipped": 0,

        "failed": 0,

        "odds": 0,

        "message": "",

        "started_at": "",

        "finished_at": "",

        "selected_companies": [],

        "log": ""

    }


if not hasattr(
    scoreman_crawler,
    "_background_lock"
):

    scoreman_crawler._background_lock = (
        threading.Lock()
    )


# =========================================================
# 공통 함수
# =========================================================

def get_job():

    return scoreman_crawler._background_job


def set_job(**kwargs):

    job = get_job()

    with scoreman_crawler._background_lock:

        for key, value in kwargs.items():

            job[key] = value


def append_job_log(message):

    message = str(message)

    job = get_job()

    with scoreman_crawler._background_lock:

        if job["log"]:

            job["log"] += "\n"

        job["log"] += message

        # 너무 긴 로그 방지
        if len(job["log"]) > 50000:

            job["log"] = job["log"][-50000:]


def get_last_saved_id():

    try:

        rows = database.get_all_matches()

        if not rows:

            return None

        values = []

        for row in rows:

            try:

                values.append(
                    int(
                        row["schedule_id"]
                    )
                )

            except Exception:

                continue

        if not values:

            return None

        return max(values)

    except Exception:

        return None


def normalize_company_name(name):

    return (
        str(name or "")
        .strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )


def company_selected(
    company_name,
    selected_companies
):

    target = normalize_company_name(
        company_name
    )

    for selected in selected_companies:

        if target == normalize_company_name(
            selected
        ):

            return True

    return False


# =========================================================
# 업체 목록
# =========================================================

def get_available_companies():

    try:

        companies = database.get_company_names()

    except Exception:

        companies = []


    preferred = [

        "Bet365",
        "William Hill",
        "10Bet"

    ]


    all_companies = []

    for company in (
        preferred + companies
    ):

        if not company:
            continue

        if company not in all_companies:

            all_companies.append(
                company
            )


    return sorted(

        all_companies,

        key=lambda x:
            str(x).lower()

    )


# =========================================================
# 선택 업체 기준 경기 1건 수집
#
# 기존 scoreman_crawler.py의 기능을 그대로 사용하되
# app에서 업체를 선택하여 저장
# =========================================================

def collect_selected_one(
    schedule_id,
    selected_companies
):

    schedule_id = str(
        schedule_id
    )


    # -----------------------------------------------------
    # 핵심:
    # 이미 저장된 경기면 웹사이트에 다시 요청하지 않음
    # -----------------------------------------------------

    if database.match_exists(
        schedule_id
    ):

        return {

            "status":
                "exists",

            "odds":
                0,

            "saved":
                False

        }


    # -----------------------------------------------------
    # 경기 페이지
    # -----------------------------------------------------

    html = scoreman_crawler.get_match_page(
        schedule_id
    )

    if not html:

        return {

            "status":
                "skip",

            "odds":
                0,

            "saved":
                False

        }


    # -----------------------------------------------------
    # 경기 정보
    # -----------------------------------------------------

    match = scoreman_crawler.parse_match_info(

        html,

        schedule_id

    )


    if not match:

        return {

            "status":
                "skip",

            "odds":
                0,

            "saved":
                False

        }


    # -----------------------------------------------------
    # 완료된 경기만 저장
    # -----------------------------------------------------

    if match.get(
        "result"
    ) not in [

        "승",
        "무",
        "패"

    ]:

        return {

            "status":
                "skip",

            "odds":
                0,

            "saved":
                False

        }


    # -----------------------------------------------------
    # 전체 업체 최종배당 가져오기
    # -----------------------------------------------------

    odds_list = scoreman_crawler.get_odds(

        schedule_id

    )


    if not odds_list:

        return {

            "status":
                "skip",

            "odds":
                0,

            "saved":
                False

        }


    # -----------------------------------------------------
    # 선택 업체만 필터
    # -----------------------------------------------------

    selected_odds = []


    for odds in odds_list:

        company_name = odds.get(
            "company_name",
            ""
        )


        if company_selected(

            company_name,

            selected_companies

        ):

            selected_odds.append(
                odds
            )


    # 선택한 업체 배당이 없으면 저장하지 않음

    if not selected_odds:

        return {

            "status":
                "skip",

            "odds":
                0,

            "saved":
                False

        }


    # -----------------------------------------------------
    # 경기 저장
    # -----------------------------------------------------

    database.save_match(

        schedule_id=
            match["schedule_id"],

        match_date=
            match["match_date"],

        home_team=
            match["home_team"],

        away_team=
            match["away_team"],

        home_score=
            match["home_score"],

        away_score=
            match["away_score"],

        result=
            match["result"],

        source=
            "Scoreman"

    )


    # -----------------------------------------------------
    # 선택 업체 최종배당만 저장
    # -----------------------------------------------------

    saved_odds = 0


    for odds in selected_odds:

        ok = database.save_odds(

            schedule_id=
                match["schedule_id"],

            company_id=
                odds.get(
                    "company_id",
                    ""
                ),

            company_name=
                odds.get(
                    "company_name",
                    ""
                ),

            final_home=
                odds.get(
                    "final_home"
                ),

            final_draw=
                odds.get(
                    "final_draw"
                ),

            final_away=
                odds.get(
                    "final_away"
                )

        )


        if ok:

            saved_odds += 1


    return {

        "status":
            "success",

        "odds":
            saved_odds,

        "saved":
            True,

        "home":
            match.get(
                "home_team",
                ""
            ),

        "away":
            match.get(
                "away_team",
                ""
            ),

        "result":
            match.get(
                "result",
                ""
            )

    }


# =========================================================
# 백그라운드 수집 함수
# =========================================================

def background_collect(

    start_id,

    end_id,

    selected_companies,

    delay

):

    start_id = int(
        start_id
    )

    end_id = int(
        end_id
    )

    total = (
        end_id
        -
        start_id
        +
        1
    )


    set_job(

        running=True,

        finished=False,

        start_id=start_id,

        end_id=end_id,

        current_id=start_id,

        last_saved_id=
            get_last_saved_id(),

        total=total,

        processed=0,

        success=0,

        skipped=0,

        failed=0,

        odds=0,

        message="수집 시작",

        started_at=
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

        finished_at="",

        selected_companies=
            list(selected_companies),

        log=""

    )


    append_job_log(
        "========================================"
    )

    append_job_log(
        "⚽ Scoreman 백그라운드 수집 시작"
    )

    append_job_log(
        f"범위: {start_id:,} ~ {end_id:,}"
    )

    append_job_log(
        f"전체 ID: {total:,}"
    )

    append_job_log(
        "기존 저장 경기: 재수집하지 않음"
    )

    append_job_log(
        "초기배당: 저장하지 않음"
    )

    append_job_log(
        "최종배당: 선택 업체만 저장"
    )

    append_job_log(
        "선택 업체: "
        +
        ", ".join(
            selected_companies
        )
    )

    append_job_log(
        "========================================"
    )


    for index, schedule_id in enumerate(

        range(
            start_id,
            end_id + 1
        ),

        start=1

    ):

        set_job(
            current_id=schedule_id,
            processed=index
        )


        try:

            # -------------------------------------------------
            # 기존 경기 확인
            # 웹 요청보다 먼저 확인
            # -------------------------------------------------

            if database.match_exists(
                str(schedule_id)
            ):

                skipped = (
                    get_job()["skipped"]
                    + 1
                )

                set_job(
                    skipped=skipped
                )

                append_job_log(
                    f"[건너뜀] "
                    f"ID={schedule_id:,} "
                    f"→ 이미 저장된 경기"
                )

            else:

                result = collect_selected_one(

                    schedule_id,

                    selected_companies

                )


                status = result.get(
                    "status",
                    "skip"
                )


                if status == "success":

                    success = (
                        get_job()["success"]
                        + 1
                    )

                    odds = (
                        get_job()["odds"]
                        +
                        int(
                            result.get(
                                "odds",
                                0
                            )
                        )
                    )


                    set_job(

                        success=success,

                        odds=odds,

                        last_saved_id=
                            int(
                                schedule_id
                            )

                    )


                    append_job_log(

                        f"[저장] "
                        f"ID={schedule_id:,} "
                        f"{result.get('home', '')} "
                        f"vs "
                        f"{result.get('away', '')} "
                        f"→ "
                        f"{result.get('result', '')} "
                        f"/ 업체 "
                        f"{result.get('odds', 0)}개"

                    )


                else:

                    skipped = (
                        get_job()["skipped"]
                        + 1
                    )

                    set_job(
                        skipped=skipped
                    )

                    append_job_log(
                        f"[건너뜀] "
                        f"ID={schedule_id:,}"
                    )


        except Exception as e:

            failed = (
                get_job()["failed"]
                + 1
            )

            set_job(
                failed=failed
            )

            append_job_log(
                f"[오류] "
                f"ID={schedule_id:,}: {e}"
            )


        # -----------------------------------------------------
        # 진행률 로그
        # -----------------------------------------------------

        if (
            index == 1
            or index % 10 == 0
            or index == total
        ):

            job = get_job()

            append_job_log(

                f"[진행] "
                f"{index:,}/{total:,} "
                f"({index / total * 100:.1f}%) "
                f"신규={job['success']:,} "
                f"건너뜀={job['skipped']:,} "
                f"실패={job['failed']:,} "
                f"배당={job['odds']:,}"

            )


        if delay:

            time.sleep(
                float(delay)
            )


    # ---------------------------------------------------------
    # 완료
    # ---------------------------------------------------------

    last_id = get_last_saved_id()


    set_job(

        running=False,

        finished=True,

        current_id=end_id,

        last_saved_id=last_id,

        finished_at=
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

        message="수집 완료"

    )


    append_job_log(
        "========================================"
    )

    append_job_log(
        "✅ 백그라운드 수집 완료"
    )

    append_job_log(
        f"전체 검색: {total:,}"
    )

    append_job_log(
        f"신규 저장: "
        f"{get_job()['success']:,}"
    )

    append_job_log(
        f"건너뜀: "
        f"{get_job()['skipped']:,}"
    )

    append_job_log(
        f"실패: "
        f"{get_job()['failed']:,}"
    )

    append_job_log(
        f"최종배당: "
        f"{get_job()['odds']:,}"
    )

    append_job_log(
        f"마지막 저장 경기 ID: "
        f"{last_id if last_id is not None else '-'}"
    )

    append_job_log(
        "========================================"
    )


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
    "이미 DB에 저장된 경기 ID는 다시 요청하지 않고 "
    "새로운 경기만 추가합니다."
)

st.info(
    "📱 휴대폰 화면을 끄거나 다른 앱으로 이동해도 "
    "수집 작업은 서버에서 계속 실행됩니다. "
    "수집 중인 서버 자체가 종료되면 작업도 중단됩니다."
)


# =========================================================
# 수집 업체 선택
# =========================================================

st.subheader(
    "🏢 수집 업체 선택"
)


available_companies = (
    get_available_companies()
)


selected_collect_companies = st.multiselect(

    "수집할 해외업체",

    options=available_companies,

    default=[],

    placeholder=
        "Bet365 / William Hill / 10Bet 및 다른 업체 선택"

)


if selected_collect_companies:

    st.success(

        "선택 업체: "
        +
        ", ".join(
            selected_collect_companies
        )

    )

else:

    st.warning(
        "수집할 업체를 하나 이상 선택하세요."
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
# 요청 간격
# =========================================================

delay = st.number_input(

    "요청 간격(초)",

    min_value=0.20,

    max_value=5.00,

    value=0.50,

    step=0.10,

    format="%.2f"

)


# =========================================================
# 현재 백그라운드 상태
# =========================================================

job = get_job()


if job["running"]:

    st.subheader(
        "📡 현재 수집 상태"
    )


    total = max(
        int(job["total"]),
        1
    )

    processed = int(
        job["processed"]
    )

    progress = min(

        max(

            processed /
            total,

            0.0

        ),

        1.0

    )


    st.progress(
        progress
    )


    c1, c2, c3, c4 = st.columns(4)


    with c1:

        st.metric(
            "현재 경기 ID",
            f"{job['current_id']:,}"
        )


    with c2:

        st.metric(
            "신규 저장",
            f"{job['success']:,}"
        )


    with c3:

        st.metric(
            "건너뜀",
            f"{job['skipped']:,}"
        )


    with c4:

        st.metric(
            "실패",
            f"{job['failed']:,}"
        )


    st.info(
        f"🔄 현재 ID **{job['current_id']:,}** "
        f"수집 중 / "
        f"진행률 **{progress * 100:.1f}%**"
    )


    if job["last_saved_id"] is not None:

        st.success(
            f"📌 마지막 저장 경기 ID: "
            f"**{job['last_saved_id']:,}**"
        )


# =========================================================
# 수집 시작 버튼
# =========================================================

can_start = (
    not job["running"]
    and
    bool(selected_collect_companies)
    and
    end_id >= start_id
)


if st.button(

    "🚀 백그라운드 경기 수집 시작",

    type="primary",

    use_container_width=True,

    disabled=not can_start

):

    # -----------------------------------------------------
    # 중복 실행 방지
    # -----------------------------------------------------

    if get_job()["running"]:

        st.warning(
            "이미 수집이 진행 중입니다."
        )

    else:

        thread = threading.Thread(

            target=background_collect,

            args=(

                int(start_id),

                int(end_id),

                list(
                    selected_collect_companies
                ),

                float(delay)

            ),

            daemon=True

        )


        thread.start()


        st.session_state.crawl_thread = (
            thread
        )


        st.success(
            "🚀 백그라운드 수집을 시작했습니다."
        )


        st.rerun()


if (
    end_id < start_id
):

    st.error(
        "마지막 경기 ID가 시작 ID보다 작습니다."
    )


if (
    not selected_collect_companies
):

    st.warning(
        "수집 업체를 먼저 선택하세요."
    )


# =========================================================
# 마지막 저장 경기 ID
# =========================================================

last_saved_id = get_last_saved_id()


st.subheader(
    "📌 마지막 저장 경기 ID"
)


if last_saved_id is not None:

    st.success(
        f"**{last_saved_id:,}**"
    )

else:

    st.info(
        "아직 저장된 경기가 없습니다."
    )


# =========================================================
# 최근 수집 로그
# =========================================================

job = get_job()


if job["log"]:

    st.subheader(
        "📜 수집 로그"
    )


    st.code(
        job["log"],
        language="text"
    )


# =========================================================
# 자동 새로고침 안내
# =========================================================

if get_job()["running"]:

    st.info(
        "수집 중입니다. "
        "화면을 다시 열면 현재 진행상태를 확인할 수 있습니다."
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

    key=lambda x:
        str(x).lower()

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


            st.session_state.search_result = (
                results
            )


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


    st.subheader(
        "🎯 배당 확률 대비 부족확률"
    )


    st.info(
        "부족확률 = 배당 암시확률보다 "
        "실제 과거 결과가 적게 발생한 정도입니다."
    )


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

    "💡 Bet365 / William Hill / 10Bet뿐 아니라 "
    "DB에 실제 저장된 다른 해외업체도 선택할 수 있습니다. "
    "수집 시 선택한 업체의 최종배당만 저장합니다."

)


st.success(
    "✅ 프로그램 정상 작동"
    )
