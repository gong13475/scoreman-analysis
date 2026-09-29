# =========================================================
# analysis.py
# =========================================================


# =========================================================
# 숫자 변환
# =========================================================

def to_float(value, default=0.0):

    try:

        if value is None:
            return default

        if isinstance(value, str):
            value = value.replace(",", "")
            value = value.replace("%", "")
            value = value.strip()

        return float(value)

    except Exception:

        return default


# =========================================================
# 배당 -> 확률
# =========================================================

def odds_to_probability(
    home_odds,
    draw_odds,
    away_odds
):

    home_odds = to_float(home_odds)
    draw_odds = to_float(draw_odds)
    away_odds = to_float(away_odds)

    if home_odds <= 1:
        home_odds = 0

    if draw_odds <= 1:
        draw_odds = 0

    if away_odds <= 1:
        away_odds = 0

    home_raw = (
        1 / home_odds
        if home_odds > 0
        else 0
    )

    draw_raw = (
        1 / draw_odds
        if draw_odds > 0
        else 0
    )

    away_raw = (
        1 / away_odds
        if away_odds > 0
        else 0
    )

    total = (
        home_raw +
        draw_raw +
        away_raw
    )

    if total <= 0:

        return 0.0, 0.0, 0.0

    home_probability = (
        home_raw / total * 100
    )

    draw_probability = (
        draw_raw / total * 100
    )

    away_probability = (
        away_raw / total * 100
    )

    return (
        round(home_probability, 2),
        round(draw_probability, 2),
        round(away_probability, 2)
    )


# =========================================================
# 한 경기 분석
# =========================================================

def analyze_game(game):

    home_odds = to_float(
        game.get("home_odds", 0)
    )

    draw_odds = to_float(
        game.get("draw_odds", 0)
    )

    away_odds = to_float(
        game.get("away_odds", 0)
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

    if max(probabilities.values(), default=0) > 0:

        prediction = max(
            probabilities,
            key=probabilities.get
        )

    result = str(
        game.get("result", "")
    ).strip()

    if result not in ["승", "무", "패"]:

        result = ""

    result_probability = 0

    if result:

        result_probability = probabilities.get(
            result,
            0
        )

    # 실제 결과가 예상확률에서 얼마나 벗어났는지
    shortage = 0

    if result:

        shortage = 100 - result_probability

    return {

        "경기": (
            f'{game.get("home_team", "")} '
            f'vs '
            f'{game.get("away_team", "")}'
        ),

        "시간": game.get(
            "game_time",
            ""
        ),

        "업체": game.get(
            "source",
            "Scoreman"
        ),

        "리그": game.get(
            "league",
            ""
        ),

        "승배당": home_odds,

        "무배당": draw_odds,

        "패배당": away_odds,

        "승확률": home_probability,

        "무확률": draw_probability,

        "패확률": away_probability,

        "추천": prediction,

        "실제결과": result,

        "결과확률": round(
            result_probability,
            2
        ),

        "부족확률": round(
            shortage,
            2
        )
    }


# =========================================================
# 전체 경기 분석
# =========================================================

def analyze_all_games(games):

    analyzed = []

    for game in games:

        analyzed.append(
            analyze_game(game)
        )

    return analyzed


# =========================================================
# 전체 통계
# =========================================================

def calculate_overall_statistics(
    analyzed_games
):

    total_games = len(
        analyzed_games
    )

    result_games = 0

    result_count = {
        "승": 0,
        "무": 0,
        "패": 0
    }

    probability_sum = {
        "승": 0.0,
        "무": 0.0,
        "패": 0.0
    }

    for game in analyzed_games:

        probability_sum["승"] += to_float(
            game.get("승확률")
        )

        probability_sum["무"] += to_float(
            game.get("무확률")
        )

        probability_sum["패"] += to_float(
            game.get("패확률")
        )

        result = game.get(
            "실제결과",
            ""
        )

        if result in result_count:

            result_count[result] += 1

            result_games += 1

    statistics = {}

    for outcome in ["승", "무", "패"]:

        actual_rate = 0

        expected_rate = 0

        difference = 0

        if result_games > 0:

            actual_rate = (
                result_count[outcome]
                / result_games
                * 100
            )

        if total_games > 0:

            expected_rate = (
                probability_sum[outcome]
                / total_games
            )

        difference = (
            actual_rate -
            expected_rate
        )

        statistics[outcome] = {

            "건수": result_count[outcome],

            "실제비율": round(
                actual_rate,
                2
            ),

            "예상확률": round(
                expected_rate,
                2
            ),

            "차이": round(
                difference,
                2
            )
        }

    return {

        "전체경기": total_games,

        "결과확인경기": result_games,

        "승": statistics["승"],

        "무": statistics["무"],

        "패": statistics["패"]
    }


# =========================================================
# 부족 / 초과 문구
# =========================================================

def difference_text(value):

    value = to_float(value)

    if value < 0:

        return (
            f"부족 {abs(value):.2f}%"
        )

    if value > 0:

        return (
            f"초과 +{value:.2f}%"
        )

    return "일치 0.00%"
