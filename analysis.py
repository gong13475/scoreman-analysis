# =========================================================
# analysis.py
# =========================================================


# =========================================================
# 숫자 변환
# =========================================================

def to_float(
    value,
    default=0.0
):

    try:

        if value is None:
            return default

        if isinstance(
            value,
            str
        ):

            value = value.replace(
                ",",
                ""
            )

            value = value.replace(
                "%",
                ""
            )

            value = value.strip()

        return float(value)

    except Exception:

        return default


# =========================================================
# 배당 → 확률
# =========================================================

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

    if home_odds <= 1:
        return 0, 0, 0

    if draw_odds <= 1:
        return 0, 0, 0

    if away_odds <= 1:
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

    home_probability = (
        home_raw /
        total *
        100
    )

    draw_probability = (
        draw_raw /
        total *
        100
    )

    away_probability = (
        away_raw /
        total *
        100
    )

    return (

        round(
            home_probability,
            2
        ),

        round(
            draw_probability,
            2
        ),

        round(
            away_probability,
            2
        )
    )


# =========================================================
# 한 경기 분석
# =========================================================

def analyze_match(match):

    home_odds = match.get(
        "home_odds",
        0
    )

    draw_odds = match.get(
        "draw_odds",
        0
    )

    away_odds = match.get(
        "away_odds",
        0
    )

    home_probability, draw_probability, away_probability = (
        odds_to_probability(
            home_odds,
            draw_odds,
            away_odds
        )
    )

    probabilities = {

        "승": home_probability,

        "무": draw_probability,

        "패": away_probability
    }

    prediction = ""

    if max(
        probabilities.values(),
        default=0
    ) > 0:

        prediction = max(
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

        result_probability = (
            probabilities.get(
                result,
                0
            )
        )

    # 실제 결과가 나왔는데
    # 그 결과의 예상확률이 낮을수록
    # 예상에서 벗어난 정도가 커짐
    shortage_probability = 0

    if result:

        shortage_probability = (
            100 -
            result_probability
        )

    return {

        "경기":
            f'{match.get("home_team", "")} '
            f'vs '
            f'{match.get("away_team", "")}',

        "업체":
            match.get(
                "source",
                "Scoreman"
            ),

        "리그":
            match.get(
                "league",
                ""
            ),

        "시간":
            match.get(
                "match_time",
                ""
            ),

        "승배당":
            home_odds,

        "무배당":
            draw_odds,

        "패배당":
            away_odds,

        "승확률":
            home_probability,

        "무확률":
            draw_probability,

        "패확률":
            away_probability,

        "추천":
            prediction,

        "실제결과":
            result,

        "결과확률":
            round(
                result_probability,
                2
            ),

        "부족확률":
            round(
                shortage_probability,
                2
            )
    }


# =========================================================
# 전체 경기 분석
# =========================================================

def analyze_matches(matches):

    results = []

    for match in matches:

        results.append(
            analyze_match(
                match
            )
        )

    return results


# =========================================================
# 전체 통계
# =========================================================

def calculate_statistics(
    analyzed_matches
):

    total = len(
        analyzed_matches
    )

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

    for match in analyzed_matches:

        probability_sum["승"] += (
            to_float(
                match.get(
                    "승확률",
                    0
                )
            )
        )

        probability_sum["무"] += (
            to_float(
                match.get(
                    "무확률",
                    0
                )
            )
        )

        probability_sum["패"] += (
            to_float(
                match.get(
                    "패확률",
                    0
                )
            )
        )

        result = match.get(
            "실제결과",
            ""
        )

        if result in result_count:

            result_count[result] += 1

            result_games += 1

    statistics = {

        "전체경기":
            total,

        "결과확인경기":
            result_games
    }

    for outcome in [
        "승",
        "무",
        "패"
    ]:

        actual_rate = 0

        expected_rate = 0

        difference = 0

        if result_games > 0:

            actual_rate = (
                result_count[outcome]
                /
                result_games
                *
                100
            )

        if total > 0:

            expected_rate = (
                probability_sum[outcome]
                /
                total
            )

        difference = (
            actual_rate -
            expected_rate
        )

        statistics[outcome] = {

            "건수":
                result_count[outcome],

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

    return statistics
