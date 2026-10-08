# ============================================================
# analysis.py
# Scoreman 배당 분석
#
# 기능
# - 배당 -> 시장확률
# - 전체 경기 확률 분석
# - 실제 결과 발생률
# - 확률 대비 부족확률
# - 업체별 분석
# - 동일배당 완전 동일값 검색
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
# 퍼센트
# ============================================================

def pct(value, total):

    if total <= 0:
        return 0.0

    return value / total * 100.0


# ============================================================
# 배당 -> 시장확률
# ============================================================

def odds_probability(
    home,
    draw,
    away,
):

    h = safe_float(home)
    d = safe_float(draw)
    a = safe_float(away)

    if h is None or d is None or a is None:
        return None

    raw_h = 1.0 / h
    raw_d = 1.0 / d
    raw_a = 1.0 / a

    total = raw_h + raw_d + raw_a

    if total <= 0:
        return None

    return {
        "home": raw_h / total * 100.0,
        "draw": raw_d / total * 100.0,
        "away": raw_a / total * 100.0,
    }


# ============================================================
# 한 행에 시장확률 추가
# ============================================================

def add_probability_to_row(row):

    result = dict(row)

    probability = odds_probability(
        row.get("final_home"),
        row.get("final_draw"),
        row.get("final_away"),
    )

    if probability is None:

        result["win_probability"] = None
        result["draw_probability"] = None
        result["lose_probability"] = None
        result["actual_probability"] = None

        return result

    result["win_probability"] = probability["home"]
    result["draw_probability"] = probability["draw"]
    result["lose_probability"] = probability["away"]

    actual_result = row.get("result")

    if actual_result == "승":

        result["actual_probability"] = (
            probability["home"]
        )

    elif actual_result == "무":

        result["actual_probability"] = (
            probability["draw"]
        )

    elif actual_result == "패":

        result["actual_probability"] = (
            probability["away"]
        )

    else:

        result["actual_probability"] = None

    return result


# ============================================================
# 전체 행에 시장확률 추가
# ============================================================

def add_probabilities(rows):

    return [
        add_probability_to_row(row)
        for row in rows
    ]


# ============================================================
# 기본 결과 통계
# ============================================================

def analyze_rows(rows):

    total = len(rows)

    win = 0
    draw = 0
    lose = 0

    for row in rows:

        result = row.get("result")

        if result == "승":
            win += 1

        elif result == "무":
            draw += 1

        elif result == "패":
            lose += 1

    return {
        "total": total,

        "win": win,
        "draw": draw,
        "lose": lose,

        "win_pct": pct(win, total),
        "draw_pct": pct(draw, total),
        "lose_pct": pct(lose, total),
    }


# ============================================================
# 전체 경기
# 배당대비 시장확률 + 실제발생률 + 부족확률
#
# 부족확률:
# 시장확률이 실제 발생률보다 높은 만큼
# ============================================================

def probability_summary(rows):

    total = len(rows)

    if total == 0:
        return []

    probability_rows = []

    for row in rows:

        probability = odds_probability(
            row.get("final_home"),
            row.get("final_draw"),
            row.get("final_away"),
        )

        if probability is None:
            continue

        result = row.get("result")

        probability_rows.append(
            {
                "probability": probability,
                "result": result,
            }
        )

    count = len(probability_rows)

    if count == 0:
        return []

    expected_home = sum(
        x["probability"]["home"]
        for x in probability_rows
    ) / count

    expected_draw = sum(
        x["probability"]["draw"]
        for x in probability_rows
    ) / count

    expected_away = sum(
        x["probability"]["away"]
        for x in probability_rows
    ) / count

    actual_home = sum(
        1
        for x in probability_rows
        if x["result"] == "승"
    ) / count * 100

    actual_draw = sum(
        1
        for x in probability_rows
        if x["result"] == "무"
    ) / count * 100

    actual_away = sum(
        1
        for x in probability_rows
        if x["result"] == "패"
    ) / count * 100

    rows_out = []

    values = [
        (
            "승",
            expected_home,
            actual_home,
        ),
        (
            "무",
            expected_draw,
            actual_draw,
        ),
        (
            "패",
            expected_away,
            actual_away,
        ),
    ]

    for result, expected, actual in values:

        difference = actual - expected

        shortage = max(
            expected - actual,
            0,
        )

        rows_out.append(
            {
                "결과": result,
                "경기수": count,
                "배당기준 평균확률":
                    round(expected, 2),
                "실제발생률":
                    round(actual, 2),
                "확률차이":
                    round(difference, 2),
                "부족확률":
                    round(shortage, 2),
            }
        )

    return rows_out


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
# 업체별 확률 분석
# ============================================================

def probability_summary_by_bookmaker(rows):

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

        summary = probability_summary(items)

        for item in summary:

            result.append(
                {
                    "업체": bookmaker,
                    **item,
                }
            )

    return result


# ============================================================
# 동일배당
#
# 허용오차 없음
# 승/무/패 배당이 완전히 같은 경우만 검색
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

        if h is None or d is None or a is None:
            continue

        # ====================================================
        # 허용오차 없음
        # 완전히 동일한 값만 인정
        # ====================================================

        if (
            h == target_h
            and
            d == target_d
            and
            a == target_a
        ):

            matched.append(row)

    return {
        "rows": matched,
        "stats": analyze_rows(matched),
        "probability_summary":
            probability_summary(matched),
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
        return {
            "probability": probability,
            "actual_result": actual_result,
        }

    return {
        "probability": probability,
        "actual_result": actual_result,
        "expected_probability": actual,
    }


# ============================================================
# 결과별 실제 비율
# ============================================================

def result_probability_summary(rows):

    total = len(rows)

    if total == 0:
        return []

    result_counts = {
        "승": 0,
        "무": 0,
        "패": 0,
    }

    for row in rows:

        result = row.get("result")

        if result in result_counts:
            result_counts[result] += 1

    output = []

    for result, count in result_counts.items():

        actual_pct = pct(
            count,
            total,
        )

        output.append(
            {
                "결과": result,
                "경기수": count,
                "실제발생률":
                    round(actual_pct, 2),
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
# DB 전체 분석
# ============================================================

def get_all_analysis(
    bookmaker=None,
):

    return database.get_analysis_rows(
        bookmaker
    )


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

        "overall":
            analyze_rows(rows),

        "bookmakers":
            analyze_by_bookmaker(rows),

        "result_summary":
            result_probability_summary(
                rows
            ),

        "probability_summary":
            probability_summary(rows),
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

        if h is None or d is None or a is None:
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
