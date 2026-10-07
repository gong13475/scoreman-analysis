# ============================================================
# analysis.py
# ⚽ 최종배당 분석
# ============================================================

import database


def implied_probabilities(
    home_odds,
    draw_odds,
    away_odds
):

    h = 1.0 / float(home_odds)
    d = 1.0 / float(draw_odds)
    a = 1.0 / float(away_odds)

    total = h + d + a

    return {
        "home": h / total * 100.0,
        "draw": d / total * 100.0,
        "away": a / total * 100.0
    }


def raw_implied_probabilities(
    home_odds,
    draw_odds,
    away_odds
):

    return {
        "home":
            100.0 / float(home_odds),

        "draw":
            100.0 / float(draw_odds),

        "away":
            100.0 / float(away_odds)
    }


def _history_statistics(matches):

    total = len(matches)

    home_count = sum(
        1
        for x in matches
        if x.get("result") == "승"
    )

    draw_count = sum(
        1
        for x in matches
        if x.get("result") == "무"
    )

    away_count = sum(
        1
        for x in matches
        if x.get("result") == "패"
    )

    def pct(n):

        if total == 0:
            return 0.0

        return n / total * 100.0

    return {
        "total": total,

        "home_count":
            home_count,

        "draw_count":
            draw_count,

        "away_count":
            away_count,

        "home_pct":
            pct(home_count),

        "draw_pct":
            pct(draw_count),

        "away_pct":
            pct(away_count),

        "matches":
            matches
    }


def analyze_manual_odds(
    company_name,
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.0001
):

    home_odds = round(
        float(home_odds),
        2
    )

    draw_odds = round(
        float(draw_odds),
        2
    )

    away_odds = round(
        float(away_odds),
        2
    )

    probabilities = implied_probabilities(
        home_odds,
        draw_odds,
        away_odds
    )

    matches = database.search_same_odds(
        company_name,
        home_odds,
        draw_odds,
        away_odds,
        tolerance
    )

    history = _history_statistics(
        matches
    )

    expected = {
        "home":
            history["home_pct"],

        "draw":
            history["draw_pct"],

        "away":
            history["away_pct"]
    }

    shortage = {
        "home":
            expected["home"]
            - probabilities["home"],

        "draw":
            expected["draw"]
            - probabilities["draw"],

        "away":
            expected["away"]
            - probabilities["away"]
    }

    return {
        "company_name":
            company_name,

        "odds": {
            "home": home_odds,
            "draw": draw_odds,
            "away": away_odds
        },

        "implied_probability":
            probabilities,

        "expected_probability":
            expected,

        "shortage_probability":
            shortage,

        "historical":
            history
    }


def analyze_matches(
    matches
):

    return _history_statistics(
        matches
    )


def result_probability(
    matches
):

    stats = _history_statistics(
        matches
    )

    return {
        "승":
            stats["home_pct"],

        "무":
            stats["draw_pct"],

        "패":
            stats["away_pct"]
    }
