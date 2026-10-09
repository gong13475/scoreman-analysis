# ============================================================
# analysis.py
# Scoreman 해외배당 분석
#
# 1. 승무패 통계
# 2. 업체별 통계
# 3. 시장 예상확률
# 4. 배당 마진
# 5. 완전 동일 배당 분석
# 6. 예상확률 대비 실제 발생 확률
# 7. 부족 확률
# 8. 가상 ROI
# ============================================================

import math

from collections import Counter, defaultdict


# ============================================================
# 숫자 변환
# ============================================================

def _safe_float(value):

    try:

        if value is None:
            return None

        number = float(value)

        if not math.isfinite(number):
            return None

        return number

    except Exception:

        return None


# ============================================================
# 중복 경기 제거
# ============================================================

def _unique_matches(rows):

    output = []

    seen = set()

    for index, row in enumerate(rows):

        sid = row.get("schedule_id")

        key = (
            str(sid)
            if sid is not None
            else f"row_{index}"
        )

        if key in seen:
            continue

        seen.add(key)

        output.append(row)

    return output


# ============================================================
# 승무패 통계
# ============================================================

def result_counts(rows):

    rows = _unique_matches(rows)

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


# ============================================================
# 배당 마진
# ============================================================

def odds_overround(home, draw, away):

    h = _safe_float(home)
    d = _safe_float(draw)
    a = _safe_float(away)

    if (
        h is None
        or d is None
        or a is None
        or min(h, d, a) <= 0
    ):

        return None

    return (
        1 / h
        + 1 / d
        + 1 / a
        - 1
    ) * 100


# ============================================================
# 배당 기준 시장 예상확률
#
# 역수로 계산한 확률을 합계 100%로 정규화한다.
# ============================================================

def odds_probability(home, draw, away):

    h = _safe_float(home)
    d = _safe_float(draw)
    a = _safe_float(away)

    if (
        h is None
        or d is None
        or a is None
        or min(h, d, a) <= 0
    ):

        return None

    implied = {

        "승": 1 / h,

        "무": 1 / d,

        "패": 1 / a,
    }

    total = sum(implied.values())

    if total <= 0:
        return None

    return {

        key: value / total * 100

        for key, value in implied.items()
    }


# ============================================================
# 업체별 통계
# ============================================================

def bookmaker_stats(rows):

    grouped = defaultdict(list)

    for row in rows:

        bookmaker = (
            row.get("bookmaker")
            or "미상"
        )

        grouped[bookmaker].append(row)

    output = []

    for bookmaker, items in grouped.items():

        items = _unique_matches(items)

        stat = result_counts(items)

        margins = []

        profits = {

            "승": 0.0,
            "무": 0.0,
            "패": 0.0,
        }

        valid_bets = 0

        for row in items:

            margin = odds_overround(

                row.get("final_home"),

                row.get("final_draw"),

                row.get("final_away"),
            )

            if margin is not None:
                margins.append(margin)

            result = row.get("result")

            if result not in profits:
                continue

            prices = {

                "승": _safe_float(
                    row.get("final_home")
                ),

                "무": _safe_float(
                    row.get("final_draw")
                ),

                "패": _safe_float(
                    row.get("final_away")
                ),
            }

            if any(
                value is None
                for value in prices.values()
            ):

                continue

            valid_bets += 1

            for key in profits:

                if result == key:

                    profits[key] += prices[key] - 1

                else:

                    profits[key] -= 1

        roi = {

            key: (
                profits[key] / valid_bets * 100
                if valid_bets else 0
            )

            for key in profits
        }

        output.append({

            "bookmaker": bookmaker,

            **stat,

            "평균마진": (
                sum(margins) / len(margins)
                if margins else 0
            ),

            "승 베팅 ROI": roi["승"],

            "무 베팅 ROI": roi["무"],

            "패 베팅 ROI": roi["패"],
        })

    output.sort(

        key=lambda item: item["total"],

        reverse=True,
    )

    return output


# ============================================================
# 완전 동일 배당 분석
#
# 기본값 tolerance=0
# 소수점 둘째 자리까지 세 배당이 일치해야 한다.
# ============================================================

def same_odds_analysis(
    rows,
    target_home,
    target_draw,
    target_away,
    tolerance=0.0,
):

    th = _safe_float(target_home)
    td = _safe_float(target_draw)
    ta = _safe_float(target_away)

    tolerance = _safe_float(tolerance)

    if (
        th is None
        or td is None
        or ta is None
        or tolerance is None
        or tolerance < 0
    ):

        return []

    output = []

    seen = set()

    for index, row in enumerate(rows):

        h = _safe_float(
            row.get("final_home")
        )

        d = _safe_float(
            row.get("final_draw")
        )

        a = _safe_float(
            row.get("final_away")
        )

        if h is None or d is None or a is None:
            continue

        if tolerance == 0:

            matched = (

                round(h, 2) == round(th, 2)

                and round(d, 2) == round(td, 2)

                and round(a, 2) == round(ta, 2)
            )

        else:

            matched = (

                abs(h - th) <= tolerance

                and abs(d - td) <= tolerance

                and abs(a - ta) <= tolerance
            )

        if not matched:
            continue

        sid = row.get("schedule_id")

        key = (
            str(sid)
            if sid is not None
            else f"row_{index}"
        )

        if key in seen:
            continue

        seen.add(key)

        output.append(row)

    return output


# ============================================================
# 예상확률 대비 실제 발생 확률
#
# 부족확률 = 예상확률 - 실제 발생 확률
#
# 양수: 예상보다 실제 발생률이 낮음
# 음수: 예상보다 실제 발생률이 높음
# ============================================================

def expected_vs_actual(rows):

    grouped = defaultdict(list)

    for index, row in enumerate(rows):

        sid = row.get("schedule_id")

        if sid is None:
            sid = f"row_{index}"

        grouped[str(sid)].append(row)

    expected = {

        "승": 0.0,
        "무": 0.0,
        "패": 0.0,
    }

    actual = {

        "승": 0,
        "무": 0,
        "패": 0,
    }

    total = 0

    for items in grouped.values():

        valid_probs = []

        result = None

        for row in items:

            current_result = row.get("result")

            if current_result in actual:

                result = current_result

            probs = odds_probability(

                row.get("final_home"),

                row.get("final_draw"),

                row.get("final_away"),
            )

            if probs:

                valid_probs.append(probs)

        if result not in actual or not valid_probs:
            continue

        avg_probs = {

            key: sum(
                item[key]
                for item in valid_probs
            ) / len(valid_probs)

            for key in ("승", "무", "패")
        }

        total += 1

        actual[result] += 1

        for key in expected:

            expected[key] += avg_probs[key]

    if total == 0:
        return []

    output = []

    for key in ("승", "무", "패"):

        actual_rate = actual[key] / total * 100

        expected_rate = expected[key] / total

        shortage = expected_rate - actual_rate

        output.append({

            "결과": key,

            "경기수": total,

            "실제횟수": actual[key],

            "예상확률": round(expected_rate, 2),

            "실제확률": round(actual_rate, 2),

            "부족확률(%p)": round(shortage, 2),

            "차이(%p)": round(
                actual_rate - expected_rate,
                2,
            ),
        })

    return output


# ============================================================
# 시장 마진 요약
#
# 전체 업체 조회 시 같은 경기를 한 번만 계산하고,
# 해당 경기의 업체별 마진을 평균한다.
# ============================================================

def market_summary(rows):

    grouped = defaultdict(list)

    for index, row in enumerate(rows):

        sid = row.get("schedule_id")

        if sid is None:
            sid = f"row_{index}"

        grouped[str(sid)].append(row)

    margins = []

    for items in grouped.values():

        match_margins = []

        for row in items:

            value = odds_overround(

                row.get("final_home"),

                row.get("final_draw"),

                row.get("final_away"),
            )

            if value is not None:

                match_margins.append(value)

        if match_margins:

            margins.append(
                sum(match_margins) / len(match_margins)
            )

    if not margins:

        return {

            "경기수": len(grouped),

            "평균마진": 0,

            "최저마진": 0,

            "최고마진": 0,
        }

    return {

        "경기수": len(margins),

        "평균마진": sum(margins) / len(margins),

        "최저마진": min(margins),

        "최고마진": max(margins),
    }
