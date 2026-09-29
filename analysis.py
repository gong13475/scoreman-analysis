# =========================================================
# analysis.py
# 스코어맨 배당 분석
# =========================================================

import math


# =========================================================
# 숫자 변환
# =========================================================

def to_float(value, default=0.0):
    try:
        if value is None:
            return default

        if isinstance(value, str):
            value = value.replace(",", "").strip()

        return float(value)

    except Exception:
        return default


# =========================================================
# 배당 -> 정규화 확률
# =========================================================

def odds_to_probability(home_odds, draw_odds, away_odds):
    """
    배당을 확률로 변환한 후
    마진을 제거하여 합계가 100%가 되도록 정규화
    """

    home_odds = to_float(home_odds)
    draw_odds = to_float(draw_odds)
    away_odds = to_float(away_odds)

    if home_odds <= 1.0:
        home_odds = 0

    if draw_odds <= 1.0:
        draw_odds = 0

    if away_odds <= 1.0:
        away_odds = 0

    home_raw = 1 / home_odds if home_odds > 0 else 0
    draw_raw = 1 / draw_odds if draw_odds > 0 else 0
    away_raw = 1 / away_odds if away_odds > 0 else 0

    total = home_raw + draw_raw + away_raw

    if total <= 0:
        return 0.0, 0.0, 0.0

    home_prob = home_raw / total * 100
    draw_prob = draw_raw / total * 100
    away_prob = away_raw / total * 100

    return (
        round(home_prob, 2),
        round(draw_prob, 2),
        round(away_prob, 2)
    )


# =========================================================
# 한 경기 분석
# =========================================================

def analyze_single_game(
    home_odds,
    draw_odds,
    away_odds,
    result=None
):
    """
    한 경기 승/무/패 확률 분석
    """

    home_prob, draw_prob, away_prob = odds_to_probability(
        home_odds,
        draw_odds,
        away_odds
    )

    probabilities = {
        "승": home_prob,
        "무": draw_prob,
        "패": away_prob
    }

    # 가장 확률 높은 결과
    if sum(probabilities.values()) > 0:
        prediction = max(
            probabilities,
            key=probabilities.get
        )
    else:
        prediction = ""

    # 실제 결과가 있는 경우
    actual_probability = 0.0

    if result in probabilities:
        actual_probability = probabilities[result]

    return {
        "승배당": to_float(home_odds),
        "무배당": to_float(draw_odds),
        "패배당": to_float(away_odds),

        "승확률": home_prob,
        "무확률": draw_prob,
        "패확률": away_prob,

        "추천": prediction,

        "실제결과": result if result else "",

        "실제결과확률": actual_probability
    }


# =========================================================
# 전체 경기 통계
# =========================================================

def calculate_overall_statistics(games):
    """
    전체 경기의

    - 경기수
    - 실제 승/무/패 건수
    - 실제 발생률
    - 평균 예상확률
    - 예상확률 대비 차이

    계산
    """

    total_games = len(games)

    if total_games == 0:
        return {
            "전체경기": 0,
            "승": {
                "건수": 0,
                "실제비율": 0.0,
                "예상확률": 0.0,
                "차이": 0.0
            },
            "무": {
                "건수": 0,
                "실제비율": 0.0,
                "예상확률": 0.0,
                "차이": 0.0
            },
            "패": {
                "건수": 0,
                "실제비율": 0.0,
                "예상확률": 0.0,
                "차이": 0.0
            }
        }

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

    valid_result_count = 0

    for game in games:

        # 확률 합계
        probability_sum["승"] += to_float(
            game.get("승확률", 0)
        )

        probability_sum["무"] += to_float(
            game.get("무확률", 0)
        )

        probability_sum["패"] += to_float(
            game.get("패확률", 0)
        )

        # 실제 결과
        result = str(
            game.get("실제결과", "")
        ).strip()

        if result in result_count:
            result_count[result] += 1
            valid_result_count += 1

    # 결과가 있는 경기 기준
    denominator = valid_result_count

    if denominator <= 0:
        denominator = total_games

    result_data = {}

    for outcome in ["승", "무", "패"]:

        actual_rate = (
            result_count[outcome] /
            denominator * 100
            if denominator > 0
            else 0
        )

        expected_rate = (
            probability_sum[outcome] /
            total_games
            if total_games > 0
            else 0
        )

        difference = actual_rate - expected_rate

        result_data[outcome] = {
            "건수": result_count[outcome],
            "실제비율": round(actual_rate, 2),
            "예상확률": round(expected_rate, 2),
            "차이": round(difference, 2)
        }

    return {
        "전체경기": total_games,
        "결과확인경기": valid_result_count,
        "승": result_data["승"],
        "무": result_data["무"],
        "패": result_data["패"]
    }


# =========================================================
# 부족 / 초과 표시
# =========================================================

def get_difference_text(value):

    value = to_float(value)

    if value < 0:
        return f"부족 {abs(value):.2f}%"

    elif value > 0:
        return f"초과 +{value:.2f}%"

    return "일치 0.00%"


# =========================================================
# 경기별 부족확률
# =========================================================

def calculate_game_difference(game):

    result = str(
        game.get("실제결과", "")
    ).strip()

    probabilities = {
        "승": to_float(game.get("승확률", 0)),
        "무": to_float(game.get("무확률", 0)),
        "패": to_float(game.get("패확률", 0))
    }

    if result not in probabilities:
        return {
            "결과확률": 0.0,
            "부족확률": 0.0,
            "차이표시": ""
        }

    actual_probability = probabilities[result]

    # 실제 결과가 발생했으므로
    # 해당 결과의 예상확률이 낮을수록
    # '역배/부족확률'이 커짐
    shortage = 100 - actual_probability

    return {
        "결과확률": round(actual_probability, 2),
        "부족확률": round(shortage, 2),
        "차이표시": (
            f"실제 {result} "
            f"/ 예상 {actual_probability:.2f}% "
            f"/ 부족 {shortage:.2f}%"
        )
    }


# =========================================================
# 전체 분석
# =========================================================

def analyze_all_games(games):

    analyzed_games = []

    for game in games:

        game_copy = dict(game)

        difference = calculate_game_difference(
            game_copy
        )

        game_copy["결과확률"] = difference["결과확률"]
        game_copy["부족확률"] = difference["부족확률"]

        analyzed_games.append(
            game_copy
        )

    statistics = calculate_overall_statistics(
        analyzed_games
    )

    return analyzed_games, statistics
