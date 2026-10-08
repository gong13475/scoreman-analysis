# ============================================================
# analysis.py
# Scoreman 배당 분석
#
# 기능
# - 배당 -> 시장확률
# - 전체 경기 승/무/패
# - 배당대비 실제 결과
# - 부족확률
# - 동일배당 정확 일치
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

    if (
        h <= 0
        or d <= 0
        or a <= 0
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
# 전체 결과 통계
# ============================================================

def analyze_rows(
    rows,
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

def analyze_by_bookmaker(
    rows,
):

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

    for bookmaker, items in (
        groups.items()
    ):

        stat = analyze_rows(
            items
        )

        stat[
            "bookmaker"
        ] = bookmaker

        result.append(stat)

    result.sort(
        key=lambda x:
            x["total"],
        reverse=True,
    )

    return result


# ============================================================
# 배당에서 기대확률
# ============================================================

def probability_from_row(
    row,
):

    return odds_probability(
        row.get("final_home"),
        row.get("final_draw"),
        row.get("final_away"),
    )


# ============================================================
# 동일배당
# ============================================================

def same_odds_analysis(
    rows,
    home_odds,
    draw_odds,
    away_odds,
):

    target_h = float(
        home_odds
    )

    target_d = float(
        draw_odds
    )

    target_a = float(
        away_odds
    )

    matched = []

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
        # 소수 둘째자리 기준 정확 일치
        # ----------------------------------------------------

        if (
            round(h, 2)
            == round(target_h, 2)

            and
            round(d, 2)
            == round(target_d, 2)

            and
            round(a, 2)
            == round(target_a, 2)
        ):

            matched.append(row)

    stat = analyze_rows(
        matched
    )

    probability = odds_probability(
        target_h,
        target_d,
        target_a,
    )

    # --------------------------------------------------------
    # 실제 비율 - 기대확률
    #
    # 양수 = 실제가 기대보다 높음
    # 음수 = 실제가 기대보다 낮음
    #
    # 부족확률 = 기대확률 - 실제비율
    # --------------------------------------------------------

    if probability:

        expected_win = (
            probability["home"]
        )

        expected_draw = (
            probability["draw"]
        )

        expected_lose = (
            probability["away"]
        )

    else:

        expected_win = 0.0
        expected_draw = 0.0
        expected_lose = 0.0

    actual_win = stat[
        "win_pct"
    ]

    actual_draw = stat[
        "draw_pct"
    ]

    actual_lose = stat[
        "lose_pct"
    ]

    summary = {

        "승": {
            "수":
                stat["win"],

            "실제비율":
                actual_win,

            "배당확률":
                expected_win,

            "부족확률":
                max(
                    expected_win
                    - actual_win,
                    0,
                ),

            "차이":
                actual_win
                - expected_win,
        },

        "무": {
            "수":
                stat["draw"],

            "실제비율":
                actual_draw,

            "배당확률":
                expected_draw,

            "부족확률":
                max(
                    expected_draw
                    - actual_draw,
                    0,
                ),

            "차이":
                actual_draw
                - expected_draw,
        },

        "패": {
            "수":
                stat["lose"],

            "실제비율":
                actual_lose,

            "배당확률":
                expected_lose,

            "부족확률":
                max(
                    expected_lose
                    - actual_lose,
                    0,
                ),

            "차이":
                actual_lose
                - expected_lose,
        },
    }

    return {

        "rows":
            matched,

        "stats":
            stat,

        "probability":
            probability,

        "summary":
            summary,
    }


# ============================================================
# 전체 경기 배당 대비 확률
# ============================================================

def overall_probability_analysis(
    rows,
):

    total = len(rows)

    valid = 0

    actual = {
        "승": 0,
        "무": 0,
        "패": 0,
    }

    expected_sum = {
        "승": 0.0,
        "무": 0.0,
        "패": 0.0,
    }

    for row in rows:

        result = row.get(
            "result"
        )

        if result in actual:

            actual[result] += 1

        probability = (
            probability_from_row(
                row
            )
        )

        if probability is None:
            continue

        valid += 1

        expected_sum["승"] += (
            probability["home"]
        )

        expected_sum["무"] += (
            probability["draw"]
        )

        expected_sum["패"] += (
            probability["away"]
        )

    if valid <= 0:

        return []

    output = []

    mapping = {

        "승": (
            "승",
            "home",
        ),

        "무": (
            "무",
            "draw",
        ),

        "패": (
            "패",
            "away",
        ),
    }

    for result, key in [
        ("승", "home"),
        ("무", "draw"),
        ("패", "away"),
    ]:

        actual_count = actual[
            result
        ]

        actual_pct = (
            actual_count
            / total
            * 100
            if total
            else 0
        )

        expected_pct = (
            expected_sum[result]
            / valid
        )

        shortfall = max(
            expected_pct
            - actual_pct,
            0,
        )

        difference = (
            actual_pct
            - expected_pct
        )

        output.append(
            {
                "결과":
                    result,

                "전체경기":
                    total,

                "확률계산가능":
                    valid,

                "실제수":
                    actual_count,

                "실제비율":
                    actual_pct,

                "배당대비확률":
                    expected_pct,

                "부족확률":
                    shortfall,

                "실제-확률차이":
                    difference,
            }
        )

    return output


# ============================================================
# 결과별 요약
# ============================================================

def result_probability_summary(
    rows,
):

    total = len(rows)

    if total <= 0:
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

    for result in (
        "승",
        "무",
        "패",
    ):

        count = counts[
            result
        ]

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
# 최근 데이터
# ============================================================

def latest_rows(
    rows,
    limit=100,
):

    return rows[:limit]


# ============================================================
# DB 전체
# ============================================================

def get_all_analysis(
    bookmaker=None,
):

    return database.get_analysis_rows(
        bookmaker
    )


# ============================================================
# 종합
# ============================================================

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
            analyze_rows(
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

        "probability_analysis":
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
