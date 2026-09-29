# =========================================================
# 배당 분석
# =========================================================


def to_float(value):

    try:

        if value is None:
            return 0.0

        if isinstance(value, str):

            value = value.replace(
                ",",
                ""
            )

            value = value.replace(
                "%",
                ""
            )

        return float(value)

    except Exception:

        return 0.0


def odds_to_probability(
    home_odds,
    draw_odds,
    away_odds
):

    home_odds = to_float(
        home_odds
    )

    draw_odds = to_float(
        draw_odds
    )

    away_odds = to_float(
        away_odds
    )

    if (
        home_odds <= 1
        or draw_odds <= 1
        or away_odds <= 1
    ):

        return 0, 0, 0

    home_raw = 1 / home_odds
    draw_raw = 1 / draw_odds
    away_raw = 1 / away_odds

    total = (
        home_raw +
        draw_raw +
        away_raw
    )

    if total <= 0:

        return 0, 0, 0

    return (

        round(
            home_raw / total * 100,
            2
        ),

        round(
            draw_raw / total * 100,
            2
        ),

        round(
            away_raw / total * 100,
            2
        )
    )


def analyze_match(match):

    hp, dp, ap = odds_to_probability(

        match.get(
            "home_odds",
            0
        ),

        match.get(
            "draw_odds",
            0
        ),

        match.get(
            "away_odds",
            0
        )
    )

    probabilities = {

        "승": hp,
        "무": dp,
        "패": ap
    }

    recommendation = ""

    if max(
        probabilities.values(),
        default=0
    ) > 0:

        recommendation = max(
            probabilities,
            key=probabilities.get
        )

    result = str(
        match.get(
            "result",
            ""
        )
    ).strip()

    if result not in [
        "승",
        "무",
        "패"
    ]:

        result = ""

    result_probability = 0

    if result:

        result_probability = probabilities[
            result
        ]

    shortage = 0

    if result:

        shortage = (
            100 -
            result_probability
        )

    return {

        "업체": match.get(
            "bookmaker",
            ""
        ),

        "리그": match.get(
            "league",
            ""
        ),

        "경기":
            f'{match.get("home_team", "")} '
            f'vs '
            f'{match.get("away_team", "")}',

        "승배당": to_float(
            match.get(
                "home_odds",
                0
            )
        ),

        "무배당": to_float(
            match.get(
                "draw_odds",
                0
            )
        ),

        "패배당": to_float(
            match.get(
                "away_odds",
                0
            )
        ),

        "승확률": hp,
        "무확률": dp,
        "패확률": ap,

        "추천": recommendation,

        "실제결과": result,

        "결과확률":
            round(
                result_probability,
                2
            ),

        "부족확률":
            round(
                shortage,
                2
            )
    }


def analyze_matches(matches):

    return [
        analyze_match(match)
        for match in matches
    ]


def calculate_statistics(
    analyzed
):

    total = len(analyzed)

    result_count = {
        "승": 0,
        "무": 0,
        "패": 0
    }

    probability_sum = {
        "승": 0,
        "무": 0,
        "패": 0
    }

    result_games = 0

    for game in analyzed:

        probability_sum["승"] += (
            to_float(
                game["승확률"]
            )
        )

        probability_sum["무"] += (
            to_float(
                game["무확률"]
            )
        )

        probability_sum["패"] += (
            to_float(
                game["패확률"]
            )
        )

        result = game[
            "실제결과"
        ]

        if result in result_count:

            result_count[result] += 1

            result_games += 1

    output = {

        "전체경기": total,

        "결과확인경기":
            result_games
    }

    for result in [
        "승",
        "무",
        "패"
    ]:

        actual_rate = 0
        expected_rate = 0

        if result_games:

            actual_rate = (
                result_count[result]
                /
                result_games
                *
                100
            )

        if total:

            expected_rate = (
                probability_sum[result]
                /
                total
            )

        difference = (
            actual_rate -
            expected_rate
        )

        output[result] = {

            "건수":
                result_count[result],

            "실제비율":
                round(
                    actual_rate,
                    2
                ),

            "예상확률":
                round(
                    expected_rate,
                    2
                ),

            "차이":
                round(
                    difference,
                    2
                )
        }

    return output
