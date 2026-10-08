# ============================================================
# analysis.py
# Scoreman 배당 분석
#
# 기능
# - 배당 -> 시장확률
# - 전체 경기 확률
# - 부족확률
# - 업체별 분석
# - 동일배당 정확 일치
# ============================================================

from collections import defaultdict

import database


# ============================================================
# 숫자
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

    if (
        h is None
        or d is None
        or a is None
    ):
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
        "home":
            raw_h / total * 100,

        "draw":
            raw_d / total * 100,

        "away":
            raw_a / total * 100,
    }


# ============================================================
# 기본 결과 통계
# ============================================================

def analyze_rows(rows):

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
            return 0.0

        return (
            value
            / total
            * 100
        )

    return {
        "total": total,

        "win": win,
        "draw": draw,
        "lose": lose,

        "win_pct":
            pct(win),

        "draw_pct":
            pct(draw),

        "lose_pct":
            pct(lose),
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

        groups[name].append(
            row
        )

    result = []

    for bookmaker, items in groups.items():

        stat = analyze_rows(
            items
        )

        stat[
            "bookmaker"
        ] = bookmaker

        result.append(stat)

    result.sort(
        key=lambda x: x["total"],
        reverse=True,
    )

    return result


# ============================================================
# 전체 경기
# 배당대비 확률 / 실제비율 / 부족확률
# ============================================================

def overall_probability_analysis(
    rows,
):

    total = len(rows)

    output = {

        "total":
            total,

        "승": {
            "count": 0,
            "actual_pct": 0.0,
            "expected_pct": 0.0,
            "shortfall": 0.0,
            "excess": 0.0,
        },

        "무": {
            "count": 0,
            "actual_pct": 0.0,
            "expected_pct": 0.0,
            "shortfall": 0.0,
            "excess": 0.0,
        },

        "패": {
            "count": 0,
            "actual_pct": 0.0,
            "expected_pct": 0.0,
            "shortfall": 0.0,
            "excess": 0.0,
        },
    }

    if total == 0:
        return output

    expected = {
        "승": 0.0,
        "무": 0.0,
        "패": 0.0,
    }

    probability_count = 0

    # --------------------------------------------------------
    # 실제 결과
    # --------------------------------------------------------

    for row in rows:

        result = row.get(
            "result"
        )

        if result in output:

            output[result][
                "count"
            ] += 1

        probability = (
            odds_probability(
                row.get("final_home"),
                row.get("final_draw"),
                row.get("final_away"),
            )
        )

        if probability is None:
            continue

        expected["승"] += (
            probability["home"]
        )

        expected["무"] += (
            probability["draw"]
        )

        expected["패"] += (
            probability["away"]
        )

        probability_count += 1

    # --------------------------------------------------------
    # 실제비율
    # --------------------------------------------------------

    for outcome in [
        "승",
        "무",
        "패",
    ]:

        count = output[outcome][
            "count"
        ]

        output[outcome][
            "actual_pct"
        ] = (
            count
            / total
            * 100
        )

    # --------------------------------------------------------
    # 평균 배당확률
    # --------------------------------------------------------

    if probability_count > 0:

        for outcome in [
            "승",
            "무",
            "패",
        ]:

            expected_pct = (
                expected[outcome]
                / probability_count
            )

            actual_pct = output[
                outcome
            ]["actual_pct"]

            output[outcome][
                "expected_pct"
            ] = expected_pct

            # 배당확률보다 실제가 낮은 정도

            output[outcome][
                "shortfall"
            ] = max(
                expected_pct
                - actual_pct,
                0,
            )

            # 실제가 배당확률보다 높은 정도

            output[outcome][
                "excess"
            ] = max(
                actual_pct
                - expected_pct,
                0,
            )

    return output


# ============================================================
# 동일배당
#
# 허용오차 없음
# 정확히 동일한 숫자만 검색
# ============================================================

def same_odds_analysis(
    rows,
    home_odds,
    draw_odds,
    away_odds,
):

    target_h = safe_float(
        home_odds
    )

    target_d = safe_float(
        draw_odds
    )

    target_a = safe_float(
        away_odds
    )

    matched = []

    if (
        target_h is None
        or target_d is None
        or target_a is None
    ):

        return {
            "rows": [],
            "stats":
                analyze_rows([]),
            "probability":
                None,
            "summary": {},
        }

    for row in rows:

        h = safe_float(
            row.get(
                "final_home"
            )
        )

        d = safe_float(
            row.get(
                "final_draw"
            )
        )

        a = safe_float(
            row.get(
                "final_away"
            )
        )

        if (
            h is None
            or d is None
            or a is None
        ):
            continue

        # ----------------------------------------------------
        # 허용오차 없음
        # 정확히 같은 배당만
        # ----------------------------------------------------

        if (
            h == target_h
            and d == target_d
            and a == target_a
        ):

            matched.append(
                row
            )

    stats = analyze_rows(
        matched
    )

    probability = odds_probability(
        target_h,
        target_d,
        target_a,
    )

    summary = {}

    if probability:

        expected = {
            "승":
                probability["home"],

            "무":
                probability["draw"],

            "패":
                probability["away"],
        }

        actual = {
            "승":
                stats["win_pct"],

            "무":
                stats["draw_pct"],

            "패":
                stats["lose_pct"],
        }

        counts = {
            "승":
                stats["win"],

            "무":
                stats["draw"],

            "패":
                stats["lose"],
        }

        for outcome in [
            "승",
            "무",
            "패",
        ]:

            shortfall = max(
                expected[outcome]
                - actual[outcome],
                0,
            )

            excess = max(
                actual[outcome]
                - expected[outcome],
                0,
            )

            summary[outcome] = {
                "count":
                    counts[outcome],

                "actual_pct":
                    actual[outcome],

                "expected_pct":
                    expected[outcome],

                "shortfall":
                    shortfall,

                "excess":
                    excess,
            }

    return {
        "rows":
            matched,

        "stats":
            stats,

        "probability":
            probability,

        "summary":
            summary,
    }


# ============================================================
# 결과별 요약
# ============================================================

def result_probability_summary(
    rows,
):

    total = len(rows)

    if total == 0:
        return []

    counts = {
        "승": 0,
        "무": 0,
        "패": 0,
    }

    for row in rows:

        result = row.get(
            "result"
        )

        if result in counts:

            counts[result] += 1

    output = []

    for result in [
        "승",
        "무",
        "패",
    ]:

        count = counts[result]

        actual_pct = (
            count
            / total
            * 100
        )

        output.append(
            {
                "결과":
                    result,

                "수":
                    count,

                "실제비율":
                    actual_pct,
            }
        )

    return output


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
        "승":
            probability["home"],

        "무":
            probability["draw"],

        "패":
            probability["away"],
    }


# ============================================================
# 최근
# ============================================================

def latest_rows(
    rows,
    limit=100,
):

    return rows[:limit]


# ============================================================
# 전체 분석
# ============================================================

def get_all_analysis(
    bookmaker=None,
):

    return database.get_analysis_rows(
        bookmaker
    )


def full_analysis(
    bookmaker=None,
):

    rows = get_all_analysis(
        bookmaker
    )

    return {
        "rows":
            rows,

        "overall":
            analyze_rows(rows),

        "bookmakers":
            analyze_by_bookmaker(
                rows
            ),

        "result_summary":
            result_probability_summary(
                rows
            ),

        "probability":
            overall_probability_analysis(
                rows
            ),
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
