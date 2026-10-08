# ============================================================
# analysis.py
# Scoreman 배당 분석
# ============================================================

from collections import Counter, defaultdict


def _safe_float(v):

    try:
        return float(v)
    except Exception:
        return None


def result_counts(rows):

    counter = Counter()

    for row in rows:

        result = row.get("result")

        if result in ("승", "무", "패"):
            counter[result] += 1

    total = sum(counter.values())

    return {
        "total": total,
        "승": counter["승"],
        "무": counter["무"],
        "패": counter["패"],
        "승률": (
            counter["승"] / total * 100
            if total else 0
        ),
        "무율": (
            counter["무"] / total * 100
            if total else 0
        ),
        "패율": (
            counter["패"] / total * 100
            if total else 0
        ),
    }


def bookmaker_stats(rows):

    grouped = defaultdict(list)

    for row in rows:

        bookmaker = (
            row.get("bookmaker")
            or "미상"
        )

        grouped[bookmaker].append(row)

    result = []

    for bookmaker, items in grouped.items():

        stat = result_counts(items)

        result.append({
            "bookmaker": bookmaker,
            **stat,
        })

    result.sort(
        key=lambda x: x["total"],
        reverse=True,
    )

    return result


def odds_probability(home, draw, away):

    h = _safe_float(home)
    d = _safe_float(draw)
    a = _safe_float(away)

    if not h or not d or not a:
        return None

    try:

        ih = 1 / h
        id_ = 1 / d
        ia = 1 / a

        total = ih + id_ + ia

        if total <= 0:
            return None

        return {
            "승": ih / total * 100,
            "무": id_ / total * 100,
            "패": ia / total * 100,
        }

    except Exception:
        return None


def same_odds_analysis(
    rows,
    target_home,
    target_draw,
    target_away,
    tolerance=0.01,
):

    result = []

    th = _safe_float(target_home)
    td = _safe_float(target_draw)
    ta = _safe_float(target_away)

    if th is None or td is None or ta is None:
        return result

    for row in rows:

        h = _safe_float(row.get("final_home"))
        d = _safe_float(row.get("final_draw"))
        a = _safe_float(row.get("final_away"))

        if h is None or d is None or a is None:
            continue

        if (
            abs(h - th) <= tolerance
            and abs(d - td) <= tolerance
            and abs(a - ta) <= tolerance
        ):

            result.append(row)

    return result


def expected_vs_actual(rows):

    total = 0
    expected = {
        "승": 0,
        "무": 0,
        "패": 0,
    }

    actual = {
        "승": 0,
        "무": 0,
        "패": 0,
    }

    for row in rows:

        result = row.get("result")

        probs = odds_probability(
            row.get("final_home"),
            row.get("final_draw"),
            row.get("final_away"),
        )

        if not probs:
            continue

        if result not in actual:
            continue

        total += 1

        for key in expected:
            expected[key] += probs[key]

        actual[result] += 1

    if total == 0:
        return []

    output = []

    for key in ("승", "무", "패"):

        expected_rate = (
            expected[key] / total
        )

        actual_rate = (
            actual[key] / total * 100
        )

        output.append({
            "결과": key,
            "실제": actual[key],
            "실제확률": actual_rate,
            "예상확률": expected_rate,
            "차이": actual_rate - expected_rate,
        })

    return output
