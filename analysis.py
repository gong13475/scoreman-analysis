# ============================================================
# analysis.py
# ⚽ Scoreman 배당 분석
#
# 주요 기능
# 1. 배당 → 정규화 확률
# 2. 전체 경기 배당 기대확률
# 3. 전체 경기 실제 발생확률
# 4. 부족확률 = 실제 발생확률 - 배당 기대확률
# 5. 업체별 분석
# 6. 동일배당 분석
#    → 허용오차 없음 / 완전 동일한 배당만 검색
# 7. 배당 범위 검색
# 8. 기존 함수 호환
# ============================================================

from collections import defaultdict

import database


# ============================================================
# 숫자 변환
# ============================================================

def safe_float(value):

    try:
        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        number = float(value)

        if number != number:
            return None

        return number

    except Exception:
        return None


# ============================================================
# 결과 정규화
# ============================================================

def normalize_result(value):

    if value is None:
        return None

    value = str(value).strip()

    mapping = {
        "승": "승",
        "홈승": "승",
        "home": "승",
        "H": "승",
        "1": "승",

        "무": "무",
        "무승부": "무",
        "draw": "무",
        "D": "무",
        "X": "무",

        "패": "패",
        "원정승": "패",
        "away": "패",
        "A": "패",
        "2": "패",
    }

    return mapping.get(value, value)


# ============================================================
# 배당 → 확률
#
# 마진을 제거한 정규화 확률
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

    if h <= 0 or d <= 0 or a <= 0:
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
# 행 1개의 배당 확률
# ============================================================

def row_probability(row):

    return odds_probability(
        row.get("final_home"),
        row.get("final_draw"),
        row.get("final_away"),
    )


# ============================================================
# 기본 결과 통계
# ============================================================

def analyze_rows(
    rows,
    tolerance=0.0,
):

    total = len(rows)

    win = 0
    draw = 0
    lose = 0

    for row in rows:

        result = normalize_result(
            row.get("result")
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

        return value / total * 100.0

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
# 전체 경기
# 배당 기대확률 + 실제 발생확률 + 부족확률
#
# 부족확률:
#     실제 발생확률 - 배당 기대확률
#
# + : 실제 발생률이 배당 예상보다 높음
# - : 실제 발생률이 배당 예상보다 낮음
# ============================================================

def overall_probability_analysis(rows):

    total = len(rows)

    if total <= 0:

        return {
            "total": 0,

            "win": {
                "count": 0,
                "actual_pct": 0.0,
                "expected_pct": 0.0,
                "shortfall_pct": 0.0,
            },

            "draw": {
                "count": 0,
                "actual_pct": 0.0,
                "expected_pct": 0.0,
                "shortfall_pct": 0.0,
            },

            "lose": {
                "count": 0,
                "actual_pct": 0.0,
                "expected_pct": 0.0,
                "shortfall_pct": 0.0,
            },

            "valid_odds_games": 0,
        }


    # 실제 결과
    result_counts = {
        "승": 0,
        "무": 0,
        "패": 0,
    }


    # 경기별 기대확률 합계
    expected_sum = {
        "승": 0.0,
        "무": 0.0,
        "패": 0.0,
    }

    valid_odds_games = 0


    for row in rows:

        result = normalize_result(
            row.get("result")
        )

        if result in result_counts:
            result_counts[result] += 1


        probability = row_probability(row)

        if probability is None:
            continue


        valid_odds_games += 1

        expected_sum["승"] += probability["home"]
        expected_sum["무"] += probability["draw"]
        expected_sum["패"] += probability["away"]


    # 실제 발생률
    actual_pct = {
        "승": result_counts["승"] / total * 100.0,
        "무": result_counts["무"] / total * 100.0,
        "패": result_counts["패"] / total * 100.0,
    }


    # 배당 기대확률
    if valid_odds_games > 0:

        expected_pct = {
            "승":
                expected_sum["승"] / valid_odds_games,

            "무":
                expected_sum["무"] / valid_odds_games,

            "패":
                expected_sum["패"] / valid_odds_games,
        }

    else:

        expected_pct = {
            "승": 0.0,
            "무": 0.0,
            "패": 0.0,
        }


    # 부족확률
    shortfall_pct = {
        "승":
            actual_pct["승"]
            - expected_pct["승"],

        "무":
            actual_pct["무"]
            - expected_pct["무"],

        "패":
            actual_pct["패"]
            - expected_pct["패"],
    }


    return {

        "total": total,

        "valid_odds_games":
            valid_odds_games,

        "win": {
            "count": result_counts["승"],
            "actual_pct": actual_pct["승"],
            "expected_pct": expected_pct["승"],
            "shortfall_pct": shortfall_pct["승"],
        },

        "draw": {
            "count": result_counts["무"],
            "actual_pct": actual_pct["무"],
            "expected_pct": expected_pct["무"],
            "shortfall_pct": shortfall_pct["무"],
        },

        "lose": {
            "count": result_counts["패"],
            "actual_pct": actual_pct["패"],
            "expected_pct": expected_pct["패"],
            "shortfall_pct": shortfall_pct["패"],
        },
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

        stat = analyze_rows(items)

        probability = overall_probability_analysis(
            items
        )

        stat["bookmaker"] = bookmaker

        # 배당 기대확률
        stat["win_expected_pct"] = (
            probability["win"]["expected_pct"]
        )

        stat["draw_expected_pct"] = (
            probability["draw"]["expected_pct"]
        )

        stat["lose_expected_pct"] = (
            probability["lose"]["expected_pct"]
        )

        # 실제 발생확률
        stat["win_actual_pct"] = (
            probability["win"]["actual_pct"]
        )

        stat["draw_actual_pct"] = (
            probability["draw"]["actual_pct"]
        )

        stat["lose_actual_pct"] = (
            probability["lose"]["actual_pct"]
        )

        # 부족확률
        stat["win_shortfall_pct"] = (
            probability["win"]["shortfall_pct"]
        )

        stat["draw_shortfall_pct"] = (
            probability["draw"]["shortfall_pct"]
        )

        stat["lose_shortfall_pct"] = (
            probability["lose"]["shortfall_pct"]
        )

        stat["valid_odds_games"] = (
            probability["valid_odds_games"]
        )

        result.append(stat)


    result.sort(
        key=lambda x: x["total"],
        reverse=True,
    )

    return result


# ============================================================
# 동일배당
#
# 중요:
# 허용오차 없음
#
# 예:
# 2.10 / 3.20 / 3.50
#
# 정확히 같은 경우만 동일배당
#
# 2.11 / 3.20 / 3.50
# → 다른 배당
# ============================================================

def same_odds_analysis(
    rows,
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.0,
):

    target_h = safe_float(home_odds)
    target_d = safe_float(draw_odds)
    target_a = safe_float(away_odds)

    if (
        target_h is None
        or target_d is None
        or target_a is None
    ):

        return {
            "rows": [],
            "stats": analyze_rows([]),
            "probability": overall_probability_analysis([]),
        }


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


        # ====================================================
        # 허용오차 제거
        # 완전 동일한 숫자만 인정
        # ====================================================

        if (
            h == target_h
            and d == target_d
            and a == target_a
        ):

            matched.append(row)


    stats = analyze_rows(
        matched,
        tolerance=0.0,
    )

    probability = overall_probability_analysis(
        matched
    )


    return {
        "rows": matched,
        "stats": stats,
        "probability": probability,
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


    actual_result = normalize_result(
        actual_result
    )


    actual_probability = expected.get(
        actual_result
    )


    if actual_probability is None:

        return {
            "probability": probability,
            "actual_result": actual_result,
            "expected_probability": None,
            "shortfall": None,
        }


    return {

        "probability":
            probability,

        "actual_result":
            actual_result,

        "expected_probability":
            actual_probability,

        # 기존 100 - 확률 방식이 아니라
        # 실제 결과가 나온 결과의 배당확률
        "shortfall":
            actual_probability,
    }


# ============================================================
# 결과별 부족확률
#
# 전체 경기 기준
# ============================================================

def result_probability_summary(
    rows,
):

    probability = overall_probability_analysis(
        rows
    )

    return [

        {
            "result": "승",
            "count":
                probability["win"]["count"],
            "actual_pct":
                probability["win"]["actual_pct"],
            "expected_pct":
                probability["win"]["expected_pct"],
            "shortfall_pct":
                probability["win"]["shortfall_pct"],
        },

        {
            "result": "무",
            "count":
                probability["draw"]["count"],
            "actual_pct":
                probability["draw"]["actual_pct"],
            "expected_pct":
                probability["draw"]["expected_pct"],
            "shortfall_pct":
                probability["draw"]["shortfall_pct"],
        },

        {
            "result": "패",
            "count":
                probability["lose"]["count"],
            "actual_pct":
                probability["lose"]["actual_pct"],
            "expected_pct":
                probability["lose"]["expected_pct"],
            "shortfall_pct":
                probability["lose"]["shortfall_pct"],
        },
    ]


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
# 수동 배당 상세 분석
# ============================================================

def analyze_manual_odds_detail(
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
        "home_odds": safe_float(home),
        "draw_odds": safe_float(draw),
        "away_odds": safe_float(away),

        "win_probability":
            probability["home"],

        "draw_probability":
            probability["draw"],

        "lose_probability":
            probability["away"],
    }


# ============================================================
# 최근 데이터
# ============================================================

def latest_rows(
    rows,
    limit=100,
):

    try:
        limit = int(limit)
    except Exception:
        limit = 100

    if limit <= 0:
        return []

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


    overall = analyze_rows(
        rows
    )


    probability = overall_probability_analysis(
        rows
    )


    return {

        "rows":
            rows,

        "overall":
            overall,

        "probability":
            probability,

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
# 전체 경기 확률 분석
# 별도 호출용
# ============================================================

def get_overall_probability_analysis(
    bookmaker=None,
):

    rows = get_all_analysis(
        bookmaker
    )

    return overall_probability_analysis(
        rows
    )


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


    home_min = safe_float(home_min)
    home_max = safe_float(home_max)
    draw_min = safe_float(draw_min)
    draw_max = safe_float(draw_max)
    away_min = safe_float(away_min)
    away_max = safe_float(away_max)


    if any(
        value is None
        for value in [
            home_min,
            home_max,
            draw_min,
            draw_max,
            away_min,
            away_max,
        ]
    ):

        return result


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
