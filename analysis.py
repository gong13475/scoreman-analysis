# ============================================================
# analysis.py
# Scoreman 배당 분석
# ============================================================

from collections import defaultdict

import database


# ============================================================
# 숫자
# ============================================================

def safe_float(value):

    try:
        return float(value)
    except Exception:
        return None


# ============================================================
# 배당 → 확률
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

    if h <= 0 or d <= 0 or a <= 0:
        return None

    raw_h = 1 / h
    raw_d = 1 / d
    raw_a = 1 / a

    total = raw_h + raw_d + raw_a

    if total <= 0:
        return None

    return {
        "home": raw_h / total * 100,
        "draw": raw_d / total * 100,
        "away": raw_a / total * 100,
    }


# ============================================================
# 전체 결과
# ============================================================

def analyze_rows(rows):

    valid = [
        row for row in rows
        if row.get("result") in ("승", "무", "패")
    ]

    total = len(valid)

    win = sum(
        1 for row in valid
        if row.get("result") == "승"
    )

    draw = sum(
        1 for row in valid
        if row.get("result") == "무"
    )

    lose = sum(
        1 for row in valid
        if row.get("result") == "패"
    )

    def pct(value):

        if total == 0:
            return 0.0

        return value / total * 100

    return {
        "total": total,

        "win": win,
        "draw": draw,
        "lose": lose,

        "win_pct": pct(win),
        "draw_pct": pct(draw),
        "lose_pct": pct(lose),
    }


# ============================================================
# 배당별 예상확률 + 실제확률 + 부족확률
# ============================================================

def probability_result_analysis(rows):

    total = 0

    expected = {
        "승": 0.0,
        "무": 0.0,
        "패": 0.0,
    }

    actual_count = {
        "승": 0,
        "무": 0,
        "패": 0,
    }

    for row in rows:

        result = row.get("result")

        if result not in ("승", "무", "패"):
            continue

        probability = odds_probability(
            row.get("final_home"),
            row.get("final_draw"),
            row.get("final_away"),
        )

        if probability is None:
            continue

        total += 1

        expected["승"] += probability["home"]
        expected["무"] += probability["draw"]
        expected["패"] += probability["away"]

        actual_count[result] += 1

    if total == 0:
        return []

    output = []

    mapping = {
        "승": "home",
        "무": "draw",
        "패": "away",
    }

    for result in ("승", "무", "패"):

        expected_pct = (
            expected[result] / total
        )

        actual_pct = (
            actual_count[result]
            / total
            * 100
        )

        shortfall = (
            actual_pct - expected_pct
        )

        output.append({
            "결과": result,
            "경기수": actual_count[result],
            "배당예상확률": round(
                expected_pct,
                2,
            ),
            "실제확률": round(
                actual_pct,
                2,
            ),
            "부족확률": round(
                shortfall,
                2,
            ),
        })

    return output


# ============================================================
# 업체별
# ============================================================

def analyze_by_bookmaker(rows):

    groups = defaultdict(list)

    for row in rows:

        name = (
            row.get("bookmaker")
            or row.get("company_name")
            or "미상"
        )

        groups[name].append(row)

    result = []

    for bookmaker, items in groups.items():

        stat = analyze_rows(items)

        stat["bookmaker"] = bookmaker

        result.append(stat)

    result.sort(
        key=lambda x: x["total"],
        reverse=True,
    )

    return result


# ============================================================
# 동일배당
# ============================================================

def same_odds_analysis(
    rows,
    home_odds,
    draw_odds,
    away_odds,
):

    target_h = float(home_odds)
    target_d = float(draw_odds)
    target_a = float(away_odds)

    matched = []

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

        # ================================================
        # 허용오차 없음
        # 완전히 같은 배당만
        # ================================================

        if (
            h == target_h
            and d == target_d
            and a == target_a
        ):

            matched.append(row)

    stats = analyze_rows(matched)

    probability = odds_probability(
        target_h,
        target_d,
        target_a,
    )

    actual = {
        "승": stats["win_pct"],
        "무": stats["draw_pct"],
        "패": stats["lose_pct"],
    }

    probability_rows = []

    if probability:

        expected = {
            "승": probability["home"],
            "무": probability["draw"],
            "패": probability["away"],
        }

        for result in ("승", "무", "패"):

            probability_rows.append({
                "결과": result,

                "경기수": (
                    stats["win"]
                    if result == "승"
                    else stats["draw"]
                    if result == "무"
                    else stats["lose"]
                ),

                "배당예상확률": round(
                    expected[result],
                    2,
                ),

                "실제확률": round(
                    actual[result],
                    2,
                ),

                "부족확률": round(
                    actual[result]
                    - expected[result],
                    2,
                ),
            })

    return {
        "rows": matched,
        "stats": stats,
        "probability": probability,
        "probability_rows":
            probability_rows,
    }


# ============================================================
# 전체 결과확률
# ============================================================

def result_probability_summary(rows):

    stats = analyze_rows(rows)

    if stats["total"] == 0:
        return []

    return [
        {
            "결과": "승",
            "경기수": stats["win"],
            "실제확률": round(
                stats["win_pct"],
                2,
            ),
        },
        {
            "결과": "무",
            "경기수": stats["draw"],
            "실제확률": round(
                stats["draw_pct"],
                2,
            ),
        },
        {
            "결과": "패",
            "경기수": stats["lose"],
            "실제확률": round(
                stats["lose_pct"],
                2,
            ),
        },
    ]


# ============================================================
# 수동 배당
# ============================================================

def analyze_manual_odds(
    home,
    draw,
    away,
):

    probability = odds_probability(
        home,
        draw,
        away,
    )

    if probability is None:
        return None

    return {
        "승": probability["home"],
        "무": probability["draw"],
        "패": probability["away"],
    }


# ============================================================
# 전체
# ============================================================

def get_all_analysis(bookmaker=None):

    return database.get_analysis_rows(
        bookmaker
    )


def full_analysis(bookmaker=None):

    rows = get_all_analysis(bookmaker)

    return {
        "rows": rows,

        "overall":
            analyze_rows(rows),

        "bookmakers":
            analyze_by_bookmaker(rows),

        "result_summary":
            result_probability_summary(rows),

        "probability_summary":
            probability_result_analysis(rows),
    }


# ============================================================
# 배당 범위
# ============================================================

def find_odds_range(
    rows,
    home_min,
    home_max,
    draw_min,
    draw_max,
    away_min,
    away_max,
):

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
            home_min <= h <= home_max
            and draw_min <= d <= draw_max
            and away_min <= a <= away_max
        ):

            result.append(row)

    return result
