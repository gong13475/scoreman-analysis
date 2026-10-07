# ============================================================
# analysis.py
# ⚽ 해외배당 확률 분석
# ============================================================

import database


# ============================================================
# 배당 → 정규화 내재확률
# ============================================================

def odds_to_probabilities(
    home_odds,
    draw_odds,
    away_odds
):

    home_odds = float(home_odds)
    draw_odds = float(draw_odds)
    away_odds = float(away_odds)

    ih = 1.0 / home_odds
    idraw = 1.0 / draw_odds
    ia = 1.0 / away_odds

    total = ih + idraw + ia

    if total <= 0:
        return {
            "home": 0,
            "draw": 0,
            "away": 0
        }

    return {
        "home": ih / total * 100,
        "draw": idraw / total * 100,
        "away": ia / total * 100
    }


# ============================================================
# 동일배당 결과 통계
# ============================================================

def calculate_result_stats(rows):

    total = len(rows)

    if total == 0:

        return {
            "sample_count": 0,
            "home": 0,
            "draw": 0,
            "away": 0,
            "win_count": 0,
            "draw_count": 0,
            "loss_count": 0
        }

    win_count = sum(
        1
        for r in rows
        if r.get("result") == "승"
    )

    draw_count = sum(
        1
        for r in rows
        if r.get("result") == "무"
    )

    loss_count = sum(
        1
        for r in rows
        if r.get("result") == "패"
    )

    return {
        "sample_count": total,

        "home":
            win_count / total * 100,

        "draw":
            draw_count / total * 100,

        "away":
            loss_count / total * 100,

        "win_count":
            win_count,

        "draw_count":
            draw_count,

        "loss_count":
            loss_count
    }


# ============================================================
# 수동 배당 분석
# ============================================================

def analyze_manual_odds(
    company_name,
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.0001
):

    try:

        home_odds = float(home_odds)
        draw_odds = float(draw_odds)
        away_odds = float(away_odds)

        if (
            home_odds <= 1
            or draw_odds <= 1
            or away_odds <= 1
        ):
            return None

    except Exception:

        return None


    # --------------------------------------------------------
    # 내재확률
    # --------------------------------------------------------

    implied = odds_to_probabilities(
        home_odds,
        draw_odds,
        away_odds
    )


    # --------------------------------------------------------
    # 동일배당 검색
    # --------------------------------------------------------

    rows = database.search_same_odds(
        company_name=company_name,
        home_odds=home_odds,
        draw_odds=draw_odds,
        away_odds=away_odds,
        tolerance=tolerance
    )


    # --------------------------------------------------------
    # 실제 결과
    # --------------------------------------------------------

    stats = calculate_result_stats(
        rows
    )


    # --------------------------------------------------------
    # 부족확률
    #
    # 과거 실제확률 - 현재 내재확률
    #
    # 양수 = 과거 실제확률이 더 높음
    # 음수 = 현재 배당 내재확률이 더 높음
    # --------------------------------------------------------

    shortage_home = (
        stats["home"]
        - implied["home"]
    )

    shortage_draw = (
        stats["draw"]
        - implied["draw"]
    )

    shortage_away = (
        stats["away"]
        - implied["away"]
    )


    return {

        "company_name":
            company_name,

        "home_odds":
            home_odds,

        "draw_odds":
            draw_odds,

        "away_odds":
            away_odds,

        "implied_home":
            implied["home"],

        "implied_draw":
            implied["draw"],

        "implied_away":
            implied["away"],

        "historical_home":
            stats["home"],

        "historical_draw":
            stats["draw"],

        "historical_away":
            stats["away"],

        "shortage_home":
            shortage_home,

        "shortage_draw":
            shortage_draw,

        "shortage_away":
            shortage_away,

        "sample_count":
            stats["sample_count"],

        "win_count":
            stats["win_count"],

        "draw_count":
            stats["draw_count"],

        "loss_count":
            stats["loss_count"],

        "matches":
            rows

    }


# ============================================================
# 업체별 전체 통계
# ============================================================

def company_statistics():

    result = []

    companies = database.get_company_list()

    for company in companies:

        rows = database.search_same_odds(
            company,
            1.01,
            99.99,
            99.99,
            tolerance=98.99
        )

        stats = calculate_result_stats(rows)

        result.append({
            "company": company,
            **stats
        })

    return result


# ============================================================
# 결과 한글 변환
# ============================================================

def result_text(result):

    mapping = {
        "승": "승",
        "무": "무",
        "패": "패"
    }

    return mapping.get(
        result,
        result or ""
    )
