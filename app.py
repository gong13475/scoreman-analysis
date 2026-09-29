import streamlit as st
import pandas as pd

import database
import analysis
import scoreman_crawler


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(

    page_title="전종목 해외배당 분석",

    page_icon="⚽",

    layout="wide"
)


database.create_database()


# =========================================================
# 제목
# =========================================================

st.title(
    "⚽ 전종목 해외배당 분석"
)

st.caption(
    "자동수집 · 해외업체 · 배당확률 · 실제결과 · 부족확률"
)


# =========================================================
# 사이드바
# =========================================================

st.sidebar.header(
    "⚙️ 분석 설정"
)


menu = st.sidebar.radio(

    "메뉴",

    [
        "자동수집",

        "배당 직접입력",

        "전체 경기분석",

        "DB 조회"
    ]
)


# =========================================================
# 해외업체 선택
# =========================================================

st.sidebar.subheader(
    "🌎 해외업체 선택"
)


selected_bookmakers = st.sidebar.multiselect(

    "업체",

    scoreman_crawler.BOOKMAKERS,

    default=[
        "마카오"
    ]
)


# =========================================================
# 자동수집
# =========================================================

if menu == "자동수집":

    st.header(
        "📥 경기 자동수집"
    )

    st.write(
        "스코어맨에서 경기 데이터를 가져와 DB에 저장합니다."
    )

    st.write(
        "선택 업체:"
    )

    if selected_bookmakers:

        st.write(
            ", ".join(
                selected_bookmakers
            )
        )

    else:

        st.warning(
            "해외업체를 하나 이상 선택하세요."
        )


    st.subheader(
        "🏆 종목"
    )

    sport = st.selectbox(

        "종목 선택",

        [
            "축구"
        ]
    )


    st.subheader(
        "📅 수집 범위"
    )

    period = st.selectbox(

        "기간",

        [
            "현재 페이지",

            "오늘",

            "내일",

            "최근 7일"
        ]
    )


    url = st.text_input(

        "스코어맨 URL",

        value=scoreman_crawler.SCOREMAN_URL
    )


    if st.button(

        "🚀 자동수집 시작",

        use_container_width=True
    ):

        if not selected_bookmakers:

            st.error(
                "해외업체를 하나 이상 선택하세요."
            )

        else:

            with st.spinner(
                "경기 데이터를 수집하는 중..."
            ):

                try:

                    result = (
                        scoreman_crawler
                        .auto_collect(
                            url=url,
                            selected_bookmakers=
                                selected_bookmakers
                        )
                    )

                    st.success(
                        f'수집 경기 '
                        f'{result["found"]:,}개'
                    )

                    st.success(
                        f'새로 저장된 경기 '
                        f'{result["saved"]:,}개'
                    )

                    if result["found"] == 0:

                        st.warning(
                            "경기를 찾지 못했습니다. "
                            "스코어맨 HTML 구조를 확인해야 합니다."
                        )

                except Exception as e:

                    st.error(
                        "자동수집 오류"
                    )

                    st.code(
                        str(e)
                    )


    status = (
        database.get_database_status()
    )


    st.divider()


    c1, c2 = st.columns(2)


    with c1:

        st.metric(
            "DB 전체 경기",
            f'{status["matches"]:,}'
        )


    with c2:

        st.metric(
            "저장 업체 수",
            f'{status["bookmakers"]:,}'
        )


# =========================================================
# 배당 직접입력
# =========================================================

elif menu == "배당 직접입력":

    st.header(
        "🎯 배당 직접입력"
    )

    c1, c2, c3 = st.columns(3)


    with c1:

        home = st.text_input(
            "홈팀"
        )

        home_odds = st.number_input(
            "승 배당",
            min_value=1.01,
            value=2.00,
            step=0.01
        )


    with c2:

        away = st.text_input(
            "원정팀"
        )

        draw_odds = st.number_input(
            "무 배당",
            min_value=1.01,
            value=3.20,
            step=0.01
        )


    with c3:

        st.write("")

        away_odds = st.number_input(
            "패 배당",
            min_value=1.01,
            value=3.00,
            step=0.01
        )


    result = st.selectbox(

        "실제 결과",

        [
            "",
            "승",
            "무",
            "패"
        ]
    )


    if st.button(

        "🔎 분석",

        use_container_width=True
    ):

        match = {

            "bookmaker":
                "직접입력",

            "home_team":
                home,

            "away_team":
                away,

            "home_odds":
                home_odds,

            "draw_odds":
                draw_odds,

            "away_odds":
                away_odds,

            "result":
                result
        }


        data = (
            analysis.analyze_match(
                match
            )
        )


        c1, c2, c3 = st.columns(3)


        with c1:

            st.metric(
                "승확률",
                f'{data["승확률"]:.2f}%'
            )


        with c2:

            st.metric(
                "무확률",
                f'{data["무확률"]:.2f}%'
            )


        with c3:

            st.metric(
                "패확률",
                f'{data["패확률"]:.2f}%'
            )


        st.success(
            f'추천 : **{data["추천"]}**'
        )


        if result:

            st.info(
                f'실제 결과 : **{result}**'
            )

            st.warning(
                f'결과 예상확률 : '
                f'{data["결과확률"]:.2f}%'
            )

            st.warning(
                f'부족확률 : '
                f'{data["부족확률"]:.2f}%'
            )


# =========================================================
# 전체 경기분석
# =========================================================

elif menu == "전체 경기분석":

    st.header(
        "📊 전체 경기 승무패 분석"
    )


    matches = database.get_matches(
        limit=10000
    )


    if not matches:

        st.warning(
            "DB에 경기 데이터가 없습니다."
        )

        st.stop()


    analyzed = (
        analysis.analyze_matches(
            matches
        )
    )


    stats = (
        analysis.calculate_statistics(
            analyzed
        )
    )


    # -----------------------------------------------------
    # 전체 경기수
    # -----------------------------------------------------

    st.subheader(
        "📌 전체 경기"
    )


    c1, c2, c3, c4 = st.columns(4)


    with c1:

        st.metric(
            "전체 경기",
            f'{stats["전체경기"]:,}경기'
        )


    with c2:

        st.metric(
            "승",
            f'{stats["승"]["건수"]:,}건'
        )


    with c3:

        st.metric(
            "무",
            f'{stats["무"]["건수"]:,}건'
        )


    with c4:

        st.metric(
            "패",
            f'{stats["패"]["건수"]:,}건'
        )


    st.write(
        f'실제 결과 확인 : '
        f'**{stats["결과확인경기"]:,}경기**'
    )


    # -----------------------------------------------------
    # 전체 통계
    # -----------------------------------------------------

    st.subheader(
        "📈 예상확률 대비 실제 결과"
    )


    summary = pd.DataFrame({

        "구분": [
            "승",
            "무",
            "패"
        ],

        "경기수": [

            stats["승"]["건수"],

            stats["무"]["건수"],

            stats["패"]["건수"]
        ],

        "실제발생률": [

            f'{stats["승"]["실제비율"]:.2f}%',

            f'{stats["무"]["실제비율"]:.2f}%',

            f'{stats["패"]["실제비율"]:.2f}%'
        ],

        "배당예상확률": [

            f'{stats["승"]["예상확률"]:.2f}%',

            f'{stats["무"]["예상확률"]:.2f}%',

            f'{stats["패"]["예상확률"]:.2f}%'
        ],

        "부족/초과": [

            f'{stats["승"]["차이"]:+.2f}%',

            f'{stats["무"]["차이"]:+.2f}%',

            f'{stats["패"]["차이"]:+.2f}%'
        ]
    })


    st.dataframe(

        summary,

        use_container_width=True,

        hide_index=True
    )


    # -----------------------------------------------------
    # 부족/초과
    # -----------------------------------------------------

    st.subheader(
        "⚠️ 부족한 결과"
    )


    for outcome in [
        "승",
        "무",
        "패"
    ]:

        data = stats[
            outcome
        ]

        diff = data[
            "차이"
        ]


        if diff < 0:

            st.error(

                f'🔴 {outcome} '
                f'{abs(diff):.2f}% 부족 '
                f'| 예상 {data["예상확률"]:.2f}% '
                f'| 실제 {data["실제비율"]:.2f}%'
            )


        elif diff > 0:

            st.success(

                f'🟢 {outcome} '
                f'+{diff:.2f}% 초과 '
                f'| 예상 {data["예상확률"]:.2f}% '
                f'| 실제 {data["실제비율"]:.2f}%'
            )


    # -----------------------------------------------------
    # 경기별 결과
    # -----------------------------------------------------

    st.subheader(
        "⚽ 전체 경기 상세"
    )


    display = []


    for game in analyzed:

        display.append({

            "업체":
                game["업체"],

            "리그":
                game["리그"],

            "경기":
                game["경기"],

            "승배당":
                game["승배당"],

            "무배당":
                game["무배당"],

            "패배당":
                game["패배당"],

            "승확률":
                f'{game["승확률"]:.2f}%',

            "무확률":
                f'{game["무확률"]:.2f}%',

            "패확률":
                f'{game["패확률"]:.2f}%',

            "추천":
                game["추천"],

            "실제결과":
                game["실제결과"],

            "결과확률":
                f'{game["결과확률"]:.2f}%',

            "부족확률":
                f'{game["부족확률"]:.2f}%'
        })


    st.dataframe(

        pd.DataFrame(display),

        use_container_width=True,

        hide_index=True
    )


# =========================================================
# DB 조회
# =========================================================

elif menu == "DB 조회":

    st.header(
        "🗄️ 저장된 경기 데이터"
    )


    status = (
        database.get_database_status()
    )


    st.metric(
        "전체 DB 경기",
        f'{status["matches"]:,}경기'
    )


    matches = database.get_matches(
        limit=10000
    )


    if matches:

        df = pd.DataFrame(
            matches
        )

        st.dataframe(

            df,

            use_container_width=True,

            hide_index=True
        )

    else:

        st.info(
            "DB 데이터가 없습니다."
        )
