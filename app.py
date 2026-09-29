import streamlit as st
import pandas as pd

import database
import analysis
import scoreman_crawler


# =========================================================
# 페이지 설정
# =========================================================

st.set_page_config(

    page_title="스코어맨 배당 분석",

    page_icon="⚽",

    layout="wide"
)


# =========================================================
# DB 생성
# =========================================================

database.create_database()


# =========================================================
# 제목
# =========================================================

st.title(
    "⚽ 스코어맨 배당 분석"
)

st.caption(
    "배당 → 확률 → 실제 결과 → 전체 승무패 통계"
)


# =========================================================
# 사이드바
# =========================================================

menu = st.sidebar.radio(

    "메뉴",

    [
        "배당 직접입력",

        "스코어맨 경기수집",

        "전체 경기분석",

        "DB 조회"
    ]
)


# =========================================================
# 1. 배당 직접 입력
# =========================================================

if menu == "배당 직접입력":

    st.header(
        "🎯 배당 직접 입력"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        home_team = st.text_input(
            "홈팀"
        )

        home_odds = st.number_input(
            "승 배당",
            min_value=1.01,
            value=2.00,
            step=0.01
        )

    with col2:

        away_team = st.text_input(
            "원정팀"
        )

        draw_odds = st.number_input(
            "무 배당",
            min_value=1.01,
            value=3.20,
            step=0.01
        )

    with col3:

        st.write("")

        away_odds = st.number_input(
            "패 배당",
            min_value=1.01,
            value=3.00,
            step=0.01
        )

    result = st.selectbox(

        "실제 경기 결과",

        [
            "",
            "승",
            "무",
            "패"
        ]
    )


    if st.button(
        "🔎 분석하기",
        use_container_width=True
    ):

        match = {

            "source":
                "직접입력",

            "sport":
                "축구",

            "league":
                "",

            "match_date":
                "",

            "match_time":
                "",

            "home_team":
                home_team,

            "away_team":
                away_team,

            "home_odds":
                home_odds,

            "draw_odds":
                draw_odds,

            "away_odds":
                away_odds,

            "result":
                result
        }

        result_data = (
            analysis.analyze_match(
                match
            )
        )


        st.subheader(
            "📊 분석 결과"
        )


        c1, c2, c3 = st.columns(3)


        with c1:

            st.metric(
                "승",
                f'{result_data["승확률"]:.2f}%'
            )


        with c2:

            st.metric(
                "무",
                f'{result_data["무확률"]:.2f}%'
            )


        with c3:

            st.metric(
                "패",
                f'{result_data["패확률"]:.2f}%'
            )


        st.success(
            f'추천 : **{result_data["추천"]}**'
        )


        if result:

            st.info(
                f'실제 결과 : **{result}**'
            )

            st.warning(
                f'실제 결과 예상확률 : '
                f'**{result_data["결과확률"]:.2f}%**'
            )

            st.warning(
                f'부족확률 : '
                f'**{result_data["부족확률"]:.2f}%**'
            )


# =========================================================
# 2. 스코어맨 경기 수집
# =========================================================

elif menu == "스코어맨 경기수집":

    st.header(
        "🌐 스코어맨 경기 수집"
    )

    st.write(
        "현재 설정된 스코어맨 리그 페이지에서 "
        "경기와 배당을 가져옵니다."
    )

    if st.button(
        "📥 경기 수집 시작",
        use_container_width=True
    ):

        with st.spinner(
            "스코어맨에서 경기 데이터를 가져오는 중..."
        ):

            try:

                matches = (
                    scoreman_crawler
                    .crawl_scoreman()
                )

                if matches:

                    st.success(
                        f"{len(matches)}개 경기 확인"
                    )

                else:

                    st.warning(
                        "경기를 찾지 못했습니다."
                    )

            except Exception as e:

                st.error(
                    "수집 중 오류가 발생했습니다."
                )

                st.code(
                    str(e)
                )


# =========================================================
# 3. 전체 경기 분석
# =========================================================

elif menu == "전체 경기분석":

    st.header(
        "📊 전체 경기 분석"
    )

    matches = database.get_matches(
        limit=10000
    )

    if not matches:

        st.warning(
            "DB에 저장된 경기가 없습니다."
        )

        st.stop()


    analyzed = (
        analysis.analyze_matches(
            matches
        )
    )


    statistics = (
        analysis.calculate_statistics(
            analyzed
        )
    )


    # -----------------------------------------------------
    # 전체 경기
    # -----------------------------------------------------

    st.subheader(
        "📌 전체 경기 결과"
    )


    c1, c2, c3, c4 = st.columns(4)


    with c1:

        st.metric(
            "전체 경기",
            f'{statistics["전체경기"]:,}경기'
        )


    with c2:

        st.metric(
            "승",
            f'{statistics["승"]["건수"]:,}건'
        )


    with c3:

        st.metric(
            "무",
            f'{statistics["무"]["건수"]:,}건'
        )


    with c4:

        st.metric(
            "패",
            f'{statistics["패"]["건수"]:,}건'
        )


    # -----------------------------------------------------
    # 결과 확인 경기
    # -----------------------------------------------------

    st.write(
        f'실제 결과 확인 경기 : '
        f'**{statistics["결과확인경기"]:,}경기**'
    )


    # -----------------------------------------------------
    # 전체 통계표
    # -----------------------------------------------------

    st.subheader(
        "📈 배당 예상확률 대비 실제 결과"
    )


    summary_df = pd.DataFrame({

        "구분": [
            "승",
            "무",
            "패"
        ],

        "실제 경기수": [

            statistics[
                "승"
            ][
                "건수"
            ],

            statistics[
                "무"
            ][
                "건수"
            ],

            statistics[
                "패"
            ][
                "건수"
            ]
        ],

        "실제 발생률": [

            f'{statistics["승"]["실제비율"]:.2f}%',

            f'{statistics["무"]["실제비율"]:.2f}%',

            f'{statistics["패"]["실제비율"]:.2f}%'
        ],

        "배당 예상확률": [

            f'{statistics["승"]["예상확률"]:.2f}%',

            f'{statistics["무"]["예상확률"]:.2f}%',

            f'{statistics["패"]["예상확률"]:.2f}%'
        ],

        "부족/초과": [

            f'{statistics["승"]["차이"]:+.2f}%',

            f'{statistics["무"]["차이"]:+.2f}%',

            f'{statistics["패"]["차이"]:+.2f}%'
        ]
    })


    st.dataframe(

        summary_df,

        use_container_width=True,

        hide_index=True
    )


    # -----------------------------------------------------
    # 부족 / 초과
    # -----------------------------------------------------

    st.subheader(
        "⚠️ 부족 / 초과 결과"
    )


    for outcome in [
        "승",
        "무",
        "패"
    ]:

        data = statistics[
            outcome
        ]

        difference = data[
            "차이"
        ]


        if difference < 0:

            st.error(

                f'🔴 {outcome} : '
                f'예상 {data["예상확률"]:.2f}% → '
                f'실제 {data["실제비율"]:.2f}% → '
                f'**{abs(difference):.2f}% 부족**'
            )


        elif difference > 0:

            st.success(

                f'🟢 {outcome} : '
                f'예상 {data["예상확률"]:.2f}% → '
                f'실제 {data["실제비율"]:.2f}% → '
                f'**+{difference:.2f}% 초과**'
            )


        else:

            st.info(
                f'⚪ {outcome} : 차이 없음'
            )


    # -----------------------------------------------------
    # 경기별
    # -----------------------------------------------------

    st.subheader(
        "⚽ 경기별 분석"
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


    display_df = pd.DataFrame(
        display
    )


    st.dataframe(

        display_df,

        use_container_width=True,

        hide_index=True
    )


# =========================================================
# 4. DB 조회
# =========================================================

elif menu == "DB 조회":

    st.header(
        "🗄️ DB 경기 데이터"
    )


    status = (
        database.get_database_status()
    )


    st.metric(

        "저장 경기",

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
            "DB에 데이터가 없습니다."
        )
