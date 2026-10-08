# ============================================================
# analysis.py
# Scoreman 배당 분석
# ============================================================

import math
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
# 배당 -> 확률
# ============================================================

def odds_probability(
    home,
    draw,
    away,
):

    h = safe_float(home)
    d = safe_float(draw)
    a = safe_float(away)

    if not h or not d or not a:
        return None

    if h <= 0 or d <= 0 or a <= 0:
        return None

    raw_h = 1 / h
    raw_d = 1 / d
    raw_a = 1 / a

    total = (
        raw_h
        + raw_d
        + raw_a
    )

    if total <= 0:
        return None

    return {
        "home": raw_h / total * 100,
        "draw": raw_d / total * 100,
        "away": raw_a / total * 100,
    }


# ============================================================
# 배당별 결과
# ============================================================

def analyze_rows(
    rows,
    tolerance=0.01,
):

    total = len(rows)

    win = 0
    draw = 0
    lose = 0

    for row in rows:

        result = row.get(
            "result"
        )

        if result == "승":
            win += 1

        elif result == "무":
            draw += 1

        elif result == "패":
            lose += 1

    def pct(value):

        if total <= 0:
            return 0

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

        stat = analyze_rows(
            items
        )

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
    tolerance=0.01,
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

        if (
            abs(h - target_h)
            <= tolerance
            and
            abs(d - target_d)
            <= tolerance
            and
            abs(a - target_a)
            <= tolerance
        ):

            matched.append(row)

    return {
        "rows": matched,
        "stats": analyze_rows(
            matched
        ),
    }


# ============================================================
# 확률 대비 실제 결과
# ============================================================

def probability_comparison(
    home_odds,
    draw_odds,
    away_odds,
    actual_result,
):

    probability = odds_probability(
        home_odds,
        draw_odds,
        away_odds,
    )

    if probability is None:
        return None

    expected = {
        "승": probability["home"],
        "무": probability["draw"],
        "패": probability["away"],
    }

    actual = expected.get(
        actual_result
    )

    if actual is None:
        return probability

    return {
        "probability": probability,
        "actual_result": actual_result,
        "expected_probability": actual,
        "shortfall": 100 - actual,
    }


# ============================================================
# 결과별 부족확률
# ============================================================

def result_probability_summary(
    rows,
):

    total = len(rows)

    if total == 0:
        return []

    result_counts = {
        "승": 0,
        "무": 0,
        "패": 0,
    }

    for row in rows:

        result = row.get(
            "result"
        )

        if result in result_counts:
            result_counts[result] += 1

    output = []

    for result, count in result_counts.items():

        actual_pct = (
            count / total * 100
        )

        output.append(
            {
                "result": result,
                "count": count,
                "actual_pct": actual_pct,
            }
        )

    return output


# ============================================================
# 수동 배당 분석
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
# 최근 데이터
# ============================================================

def latest_rows(
    rows,
    limit=100,
):

    return rows[:limit]


# ============================================================
# DB에서 전체 분석
# ============================================================

def get_all_analysis(
    bookmaker=None,
):

    rows = database.get_analysis_rows(
        bookmaker
    )

    return rows


# ============================================================
# 종합 분석
# ============================================================

def full_analysis(
    bookmaker=None,
):

    rows = get_all_analysis(
        bookmaker
    )

    return {
        "rows": rows,
        "overall": analyze_rows(
            rows
        ),
        "bookmakers":
            analyze_by_bookmaker(
                rows
            ),
        "result_summary":
            result_probability_summary(
                rows
            ),
    }


# ============================================================
# 배당 범위 검색
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

        if not (
            home_min <= h <= home_max
            and
            draw_min <= d <= draw_max
            and
            away_min <= a <= away_max
        ):
            continue

        result.append(row)

    return result
