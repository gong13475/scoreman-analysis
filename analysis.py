# ============================================================
# analysis.py
# Scoreman 배당 분석
# ============================================================

from collections import Counter

import database


# ============================================================
# 안전한 숫자
# ============================================================

def safe_float(value):

    try:

        if value is None:
            return None

        value = float(value)

        if value <= 0:
            return None

        return value

    except Exception:

        return None


# ============================================================
# 배당 → 암시확률
# ============================================================

def odds_probability(
    home,
    draw,
    away,
):

    h = safe_float(home)
    d = safe_float(draw)
    a = safe_float(away)

    if (
        h is None
        or d is None
        or a is None
    ):

        return None

    ih = 1 / h
    idraw = 1 / d
    ia = 1 / a

    total = (
        ih
        + idraw
        + ia
    )

    if total <= 0:
        return None

    return {

        "home":
            ih / total * 100,

        "draw":
            idraw / total * 100,

        "away":
            ia / total * 100,
    }


# ============================================================
# 전체 분석
# ============================================================

def get_summary(
    bookmaker=None
):

    rows = database.get_analysis_rows(
        bookmaker
    )

    total = len(rows)

    wins = sum(
        1
        for r in rows
        if r.get("result") == "승"
    )

    draws = sum(
        1
        for r in rows
        if r.get("result") == "무"
    )

    losses = sum(
        1
        for r in rows
        if r.get("result") == "패"
    )

    def pct(value):

        if total <= 0:
            return 0

        return (
            value
            / total
            * 100
        )

    return {

        "total": total,

        "win": wins,

        "draw": draws,

        "loss": losses,

        "win_pct":
            pct(wins),

        "draw_pct":
            pct(draws),

        "loss_pct":
            pct(losses),
    }


# ============================================================
# 결과 분류
# ============================================================

def result_from_odds(
    row
):

    probs = odds_probability(
        row.get("final_home"),
        row.get("final_draw"),
        row.get("final_away"),
    )

    if not probs:
        return None

    values = {

        "승": probs["home"],

        "무": probs["draw"],

        "패": probs["away"],
    }

    return max(
        values,
        key=values.get
    )


# ============================================================
# 배당별 결과
# ============================================================

def analyze_rows(
    rows
):

    result = []

    for row in rows:

        probs = odds_probability(
            row.get("final_home"),
            row.get("final_draw"),
            row.get("final_away"),
        )

        item = dict(row)

        if probs:

            item["home_probability"] = (
                probs["home"]
            )

            item["draw_probability"] = (
                probs["draw"]
            )

            item["away_probability"] = (
                probs["away"]
            )

            item["predicted_result"] = (
                result_from_odds(
                    row
                )
            )

        else:

            item["home_probability"] = None
            item["draw_probability"] = None
            item["away_probability"] = None
            item["predicted_result"] = None

        item["correct"] = (
            item["predicted_result"]
            == item.get("result")
            if item["predicted_result"]
            else False
        )

        result.append(item)

    return result


# ============================================================
# 예측 적중률
# ============================================================

def get_prediction_summary(
    bookmaker=None
):

    rows = database.get_analysis_rows(
        bookmaker
    )

    analyzed = analyze_rows(
        rows
    )

    valid = [
        r
        for r in analyzed
        if r.get(
            "predicted_result"
        )
    ]

    correct = sum(
        1
        for r in valid
        if r.get("correct")
    )

    total = len(valid)

    accuracy = (
        correct / total * 100
        if total
        else 0
    )

    return {

        "total":
            len(rows),

        "analyzed":
            total,

        "correct":
            correct,

        "accuracy":
            accuracy,
    }


# ============================================================
# 결과별 확률
# ============================================================

def get_result_probability_stats(
    bookmaker=None
):

    rows = database.get_analysis_rows(
        bookmaker
    )

    stats = {

        "승": {
            "count": 0,
            "probability_sum": 0,
        },

        "무": {
            "count": 0,
            "probability_sum": 0,
        },

        "패": {
            "count": 0,
            "probability_sum": 0,
        },
    }

    for row in rows:

        result = row.get(
            "result"
        )

        if result not in stats:
            continue

        probs = odds_probability(
            row.get("final_home"),
            row.get("final_draw"),
            row.get("final_away"),
        )

        if not probs:
            continue

        stats[result]["count"] += 1

        if result == "승":

            stats[result][
                "probability_sum"
            ] += probs["home"]

        elif result == "무":

            stats[result][
                "probability_sum"
            ] += probs["draw"]

        elif result == "패":

            stats[result][
                "probability_sum"
            ] += probs["away"]

    for key in stats:

        count = stats[key]["count"]

        if count:

            stats[key][
                "average_probability"
            ] = (
                stats[key]["probability_sum"]
                / count
            )

        else:

            stats[key][
                "average_probability"
            ] = 0

    return stats


# ============================================================
# 업체별 통계
# ============================================================

def get_bookmaker_summary():

    bookmakers = (
        database.get_bookmakers()
    )

    result = []

    for item in bookmakers:

        name = item[
            "bookmaker"
        ]

        summary = get_summary(
            name
        )

        prediction = (
            get_prediction_summary(
                name
            )
        )

        result.append({

            "bookmaker":
                name,

            "games":
                summary["total"],

            "win":
                summary["win"],

            "draw":
                summary["draw"],

            "loss":
                summary["loss"],

            "win_pct":
                summary["win_pct"],

            "draw_pct":
                summary["draw_pct"],

            "loss_pct":
                summary["loss_pct"],

            "accuracy":
                prediction["accuracy"],
        })

    return result


# ============================================================
# 특정 배당 검색
# ============================================================

def find_same_odds(
    home,
    draw,
    away,
    tolerance=0.01,
    bookmaker=None,
):

    rows = database.get_analysis_rows(
        bookmaker
    )

    result = []

    for row in rows:

        h = safe_float(
            row.get("final_home")
        )

        d = safe_float(
            row.get("final_draw")
        )

        a = safe_float(
            row.get("final_away")
        )

        if (
            h is None
            or d is None
            or a is None
        ):
            continue

        if (
            abs(h - home)
            <= tolerance
            and
            abs(d - draw)
            <= tolerance
            and
            abs(a - away)
            <= tolerance
        ):

            result.append(
                row
            )

    return result


# ============================================================
# 같은 배당 통계
# ============================================================

def same_odds_summary(
    home,
    draw,
    away,
    tolerance=0.01,
    bookmaker=None,
):

    rows = find_same_odds(
        home,
        draw,
        away,
        tolerance,
        bookmaker,
    )

    counter = Counter(
        r.get("result")
        for r in rows
        if r.get("result")
    )

    total = sum(
        counter.values()
    )

    def percentage(value):

        if total == 0:
            return 0

        return (
            value
            / total
            * 100
        )

    return {

        "total":
            total,

        "win":
            counter.get("승", 0),

        "draw":
            counter.get("무", 0),

        "loss":
            counter.get("패", 0),

        "win_pct":
            percentage(
                counter.get("승", 0)
            ),

        "draw_pct":
            percentage(
                counter.get("무", 0)
            ),

        "loss_pct":
            percentage(
                counter.get("패", 0)
            ),

        "rows":
            rows,
    }


# ============================================================
# 미해결 경기
# ============================================================

def get_unresolved():

    return database.get_unresolved_matches()
