# ============================================================
# analysis.py
# ⚽ Scoreman 해외배당 분석 엔진 - 최종 교체본
#
# 기능
# - 저장된 경기 분석
# - 업체별 분석
# - 수동 최종배당 입력
# - 동일배당 과거 결과 검색
# - 승 / 무 / 패 실제 확률
# - 배당 자체의 암시확률
# - 실제확률 - 암시확률
# - 부족확률
# - 표본수
# - 소수점 2자리 배당 지원
# - 최근 5년 / 전체 기간 분석
# ============================================================

from datetime import datetime, timedelta

import database


# ============================================================
# 기본값
# ============================================================

DEFAULT_TOLERANCE = 0.0001


# ============================================================
# 숫자 변환
# ============================================================

def to_float(value, default=None):

    try:

        if value is None:
            return default

        if isinstance(value, str):

            value = value.strip()
            value = value.replace(",", "")

        return float(value)

    except Exception:

        return default


# ============================================================
# 배당 표시
# ============================================================

def format_odds(value):

    number = to_float(value)

    if number is None:
        return "-"

    return f"{number:.2f}"


# ============================================================
# 배당 → 암시확률
# ============================================================

def odds_to_probability(odds):

    odds = to_float(odds)

    if odds is None or odds <= 0:
        return 0.0

    return 1.0 / odds * 100.0


# ============================================================
# 3개 배당 암시확률
#
# 정규화 전 확률도 별도로 제공
# ============================================================

def calculate_implied_probabilities(
    home_odds,
    draw_odds,
    away_odds,
):

    home_odds = to_float(home_odds)
    draw_odds = to_float(draw_odds)
    away_odds = to_float(away_odds)

    if (
        home_odds is None
        or draw_odds is None
        or away_odds is None
        or home_odds <= 0
        or draw_odds <= 0
        or away_odds <= 0
    ):

        return {

            "home": 0.0,
            "draw": 0.0,
            "away": 0.0,

            "home_raw": 0.0,
            "draw_raw": 0.0,
            "away_raw": 0.0,

            "total_raw": 0.0,

        }

    home_raw = (
        1.0 / home_odds * 100.0
    )

    draw_raw = (
        1.0 / draw_odds * 100.0
    )

    away_raw = (
        1.0 / away_odds * 100.0
    )

    total_raw = (
        home_raw
        + draw_raw
        + away_raw
    )

    if total_raw <= 0:

        return {

            "home": 0.0,
            "draw": 0.0,
            "away": 0.0,

            "home_raw": home_raw,
            "draw_raw": draw_raw,
            "away_raw": away_raw,

            "total_raw": total_raw,

        }

    return {

        "home":
            home_raw / total_raw * 100.0,

        "draw":
            draw_raw / total_raw * 100.0,

        "away":
            away_raw / total_raw * 100.0,

        "home_raw": home_raw,

        "draw_raw": draw_raw,

        "away_raw": away_raw,

        "total_raw": total_raw,

    }


# ============================================================
# 실제 결과 개수
# ============================================================

def count_results(rows):

    home = 0
    draw = 0
    away = 0

    for row in rows:

        result = str(
            row.get(
                "result",
                ""
            )
            or ""
        ).strip()

        if result == "승":

            home += 1

        elif result == "무":

            draw += 1

        elif result == "패":

            away += 1

    return {

        "home": home,
        "draw": draw,
        "away": away,

        "win": home,

        "loss": away,

        "total":
            home + draw + away,

    }


# ============================================================
# 실제 확률
# ============================================================

def calculate_result_probabilities(rows):

    counts = count_results(rows)

    total = counts["total"]

    if total <= 0:

        return {

            "home": 0.0,
            "draw": 0.0,
            "away": 0.0,

            "win": 0.0,
            "loss": 0.0,

            "total": 0,

        }

    return {

        "home":
            counts["home"]
            / total
            * 100.0,

        "draw":
            counts["draw"]
            / total
            * 100.0,

        "away":
            counts["away"]
            / total
            * 100.0,

        "win":
            counts["home"]
            / total
            * 100.0,

        "loss":
            counts["away"]
            / total
            * 100.0,

        "total": total,

    }


# ============================================================
# 실제확률 - 배당암시확률
#
# 양수:
# 실제 결과 빈도가 배당이 암시하는 확률보다 높음
#
# 음수:
# 실제 결과 빈도가 배당이 암시하는 확률보다 낮음
# ============================================================

def calculate_probability_gap(
    actual_probability,
    implied_probability,
):

    return (
        float(actual_probability or 0)
        - float(implied_probability or 0)
    )


# ============================================================
# 부족확률
#
# 실제확률이 암시확률보다 낮을 경우
# 그 차이를 부족확률로 표시
#
# 실제확률 >= 암시확률이면 0
# ============================================================

def calculate_shortage_probability(
    actual_probability,
    implied_probability,
):

    gap = (
        float(actual_probability or 0)
        - float(implied_probability or 0)
    )

    if gap >= 0:

        return 0.0

    return abs(gap)


# ============================================================
# 결과 문자열
# ============================================================

def result_name(result):

    result = str(
        result or ""
    ).strip()

    if result == "승":
        return "승"

    if result == "무":
        return "무"

    if result == "패":
        return "패"

    return "-"


# ============================================================
# 날짜 파싱
# ============================================================

def parse_date(value):

    if not value:
        return None

    text = str(value).strip()

    formats = [

        "%Y-%m-%d %H:%M",

        "%Y-%m-%d",

        "%Y/%m/%d %H:%M",

        "%Y/%m/%d",

        "%Y.%m.%d %H:%M",

        "%Y.%m.%d",

    ]

    for fmt in formats:

        try:

            return datetime.strptime(
                text,
                fmt
            )

        except Exception:
            pass

    return None


# ============================================================
# 최근 5년 필터
# ============================================================

def filter_recent_years(
    rows,
    years=5,
):

    cutoff = (
        datetime.now()
        - timedelta(
            days=365 * years
        )
    )

    result = []

    for row in rows:

        date_value = parse_date(
            row.get(
                "match_date"
            )
        )

        if date_value is None:

            # 날짜가 없으면 분석에서 제외하지 않고
            # 데이터 자체는 유지
            result.append(row)

            continue

        if date_value >= cutoff:

            result.append(row)

    return result


# ============================================================
# 같은 배당 검색
# ============================================================

def search_same_odds(
    company_name,
    home_odds,
    draw_odds,
    away_odds,
    tolerance=DEFAULT_TOLERANCE,
):

    home_odds = to_float(home_odds)
    draw_odds = to_float(draw_odds)
    away_odds = to_float(away_odds)

    if (
        home_odds is None
        or draw_odds is None
        or away_odds is None
    ):

        return []

    try:

        return database.search_same_odds(

            company_name,

            home_odds,

            draw_odds,

            away_odds,

            tolerance,

        )

    except Exception:

        return []


# ============================================================
# 같은 배당 분석
# ============================================================

def analyze_same_odds(
    rows,
    home_odds,
    draw_odds,
    away_odds,
):

    actual = (
        calculate_result_probabilities(
            rows
        )
    )

    implied = (
        calculate_implied_probabilities(

            home_odds,

            draw_odds,

            away_odds,

        )
    )

    home_gap = calculate_probability_gap(

        actual["home"],

        implied["home"],

    )

    draw_gap = calculate_probability_gap(

        actual["draw"],

        implied["draw"],

    )

    away_gap = calculate_probability_gap(

        actual["away"],

        implied["away"],

    )

    return {

        "total":
            actual["total"],

        "home_count":
            count_results(rows)["home"],

        "draw_count":
            count_results(rows)["draw"],

        "away_count":
            count_results(rows)["away"],

        "win_count":
            count_results(rows)["win"],

        "loss_count":
            count_results(rows)["loss"],

        "actual_home":
            actual["home"],

        "actual_draw":
            actual["draw"],

        "actual_away":
            actual["away"],

        "implied_home":
            implied["home"],

        "implied_draw":
            implied["draw"],

        "implied_away":
            implied["away"],

        "home_gap":
            home_gap,

        "draw_gap":
            draw_gap,

        "away_gap":
            away_gap,

        "home_shortage":
            calculate_shortage_probability(

                actual["home"],

                implied["home"],

            ),

        "draw_shortage":
            calculate_shortage_probability(

                actual["draw"],

                implied["draw"],

            ),

        "away_shortage":
            calculate_shortage_probability(

                actual["away"],

                implied["away"],

            ),

        "home_odds":
            float(home_odds),

        "draw_odds":
            float(draw_odds),

        "away_odds":
            float(away_odds),

    }


# ============================================================
# 업체별 전체 경기 분석
# ============================================================

def analyze_company(
    company_name,
):

    try:

        matches = database.get_all_matches()

    except Exception:

        matches = []

    rows = []

    for match in matches:

        schedule_id = match.get(
            "schedule_id"
        )

        try:

            odds_rows = (
                database.get_odds_by_match(
                    schedule_id
                )
            )

        except Exception:

            continue

        for odds in odds_rows:

            name = str(
                odds.get(
                    "company_name",
                    odds.get(
                        "bookmaker",
                        ""
                    )
                )
                or ""
            ).strip()

            if name.lower() != str(
                company_name
            ).strip().lower():

                continue

            row = dict(match)

            row.update({

                "company_name":
                    name,

                "bookmaker":
                    name,

                "home_odds":
                    odds.get(
                        "home_odds",
                        odds.get(
                            "final_home"
                        )
                    ),

                "draw_odds":
                    odds.get(
                        "draw_odds",
                        odds.get(
                            "final_draw"
                        )
                    ),

                "away_odds":
                    odds.get(
                        "away_odds",
                        odds.get(
                            "final_away"
                        )
                    ),

            })

            rows.append(row)

    return rows


# ============================================================
# 업체 전체 승무패 통계
# ============================================================

def get_company_statistics(
    company_name,
):

    rows = analyze_company(
        company_name
    )

    probabilities = (
        calculate_result_probabilities(
            rows
        )
    )

    counts = count_results(
        rows
    )

    return {

        "company_name":
            company_name,

        "total":
            probabilities["total"],

        "win":
            counts["win"],

        "draw":
            counts["draw"],

        "loss":
            counts["loss"],

        "win_percent":
            probabilities["win"],

        "draw_percent":
            probabilities["draw"],

        "loss_percent":
            probabilities["loss"],

        "rows":
            rows,

    }


# ============================================================
# 모든 업체 통계
# ============================================================

def get_all_company_statistics():

    try:

        companies = (
            database.get_company_list()
        )

    except Exception:

        companies = []

    result = []

    for company in companies:

        result.append(
            get_company_statistics(
                company
            )
        )

    return result


# ============================================================
# 특정 배당과 가장 가까운 과거 경기
# ============================================================

def find_near_odds(
    company_name,
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.01,
):

    try:

        rows = (
            analyze_company(
                company_name
            )
        )

    except Exception:

        return []

    home_odds = to_float(
        home_odds
    )

    draw_odds = to_float(
        draw_odds
    )

    away_odds = to_float(
        away_odds
    )

    if (
        home_odds is None
        or draw_odds is None
        or away_odds is None
    ):

        return []

    result = []

    for row in rows:

        h = to_float(
            row.get(
                "home_odds"
            )
        )

        d = to_float(
            row.get(
                "draw_odds"
            )
        )

        a = to_float(
            row.get(
                "away_odds"
            )
        )

        if (
            h is None
            or d is None
            or a is None
        ):

            continue

        if (
            abs(h - home_odds)
            <= tolerance
            and
            abs(d - draw_odds)
            <= tolerance
            and
            abs(a - away_odds)
            <= tolerance
        ):

            result.append(row)

    return result


# ============================================================
# 수동 배당 분석
#
# 사용자가
# 회사 + 최종 승/무/패 배당을 입력하면
# 과거 동일배당 결과와 비교
# ============================================================

def analyze_manual_odds(
    company_name,
    home_odds,
    draw_odds,
    away_odds,
    tolerance=DEFAULT_TOLERANCE,
    recent_years=None,
):

    home_odds = to_float(
        home_odds
    )

    draw_odds = to_float(
        draw_odds
    )

    away_odds = to_float(
        away_odds
    )

    if (
        home_odds is None
        or draw_odds is None
        or away_odds is None
        or home_odds <= 0
        or draw_odds <= 0
        or away_odds <= 0
    ):

        return {

            "success": False,

            "error":
                "배당값을 정확히 입력하세요.",

            "rows": [],

        }

    rows = search_same_odds(

        company_name,

        home_odds,

        draw_odds,

        away_odds,

        tolerance,

    )

    if recent_years:

        rows = filter_recent_years(
            rows,
            int(recent_years)
        )

    analysis = analyze_same_odds(

        rows,

        home_odds,

        draw_odds,

        away_odds,

    )

    analysis.update({

        "success":
            True,

        "company_name":
            company_name,

        "tolerance":
            tolerance,

        "rows":
            rows,

        "home_odds_display":
            format_odds(home_odds),

        "draw_odds_display":
            format_odds(draw_odds),

        "away_odds_display":
            format_odds(away_odds),

    })

    return analysis


# ============================================================
# 추천 결과
#
# 실제확률이 가장 높은 결과
# ============================================================

def get_best_result(
    analysis
):

    values = {

        "승":
            float(
                analysis.get(
                    "actual_home",
                    0
                )
                or 0
            ),

        "무":
            float(
                analysis.get(
                    "actual_draw",
                    0
                )
                or 0
            ),

        "패":
            float(
                analysis.get(
                    "actual_away",
                    0
                )
                or 0
            ),

    }

    if not values:
        return ""

    return max(
        values,
        key=values.get
    )


# ============================================================
# 부족확률이 가장 큰 결과
# ============================================================

def get_shortage_result(
    analysis
):

    values = {

        "승":
            float(
                analysis.get(
                    "home_shortage",
                    0
                )
                or 0
            ),

        "무":
            float(
                analysis.get(
                    "draw_shortage",
                    0
                )
                or 0
            ),

        "패":
            float(
                analysis.get(
                    "away_shortage",
                    0
                )
                or 0
            ),

    }

    if not values:
        return ""

    return max(
        values,
        key=values.get
    )


# ============================================================
# 분석 요약 문자열
# ============================================================

def make_summary(
    analysis
):

    if not analysis.get(
        "success",
        True
    ):

        return str(
            analysis.get(
                "error",
                ""
            )
        )

    total = int(
        analysis.get(
            "total",
            0
        )
        or 0
    )

    if total <= 0:

        return (
            "동일배당 과거 경기 데이터가 없습니다."
        )

    best = get_best_result(
        analysis
    )

    return (

        f"표본 {total}경기 / "

        f"승 {analysis.get('actual_home', 0):.2f}% / "

        f"무 {analysis.get('actual_draw', 0):.2f}% / "

        f"패 {analysis.get('actual_away', 0):.2f}% / "

        f"실제확률 최고: {best}"

    )


# ============================================================
# 결과별 상세 데이터
# ============================================================

def get_result_detail(
    analysis
):

    return [

        {

            "result": "승",

            "count":
                int(
                    analysis.get(
                        "home_count",
                        0
                    )
                    or 0
                ),

            "actual_probability":
                float(
                    analysis.get(
                        "actual_home",
                        0
                    )
                    or 0
                ),

            "implied_probability":
                float(
                    analysis.get(
                        "implied_home",
                        0
                    )
                    or 0
                ),

            "gap":
                float(
                    analysis.get(
                        "home_gap",
                        0
                    )
                    or 0
                ),

            "shortage":
                float(
                    analysis.get(
                        "home_shortage",
                        0
                    )
                    or 0
                ),

        },

        {

            "result": "무",

            "count":
                int(
                    analysis.get(
                        "draw_count",
                        0
                    )
                    or 0
                ),

            "actual_probability":
                float(
                    analysis.get(
                        "actual_draw",
                        0
                    )
                    or 0
                ),

            "implied_probability":
                float(
                    analysis.get(
                        "implied_draw",
                        0
                    )
                    or 0
                ),

            "gap":
                float(
                    analysis.get(
                        "draw_gap",
                        0
                    )
                    or 0
                ),

            "shortage":
                float(
                    analysis.get(
                        "draw_shortage",
                        0
                    )
                    or 0
                ),

        },

        {

            "result": "패",

            "count":
                int(
                    analysis.get(
                        "away_count",
                        0
                    )
                    or 0
                ),

            "actual_probability":
                float(
                    analysis.get(
                        "actual_away",
                        0
                    )
                    or 0
                ),

            "implied_probability":
                float(
                    analysis.get(
                        "implied_away",
                        0
                    )
                    or 0
                ),

            "gap":
                float(
                    analysis.get(
                        "away_gap",
                        0
                    )
                    or 0
                ),

            "shortage":
                float(
                    analysis.get(
                        "away_shortage",
                        0
                    )
                    or 0
                ),

        },

    ]


# ============================================================
# 배당값 검증
# ============================================================

def validate_odds(
    home_odds,
    draw_odds,
    away_odds,
):

    home = to_float(home_odds)
    draw = to_float(draw_odds)
    away = to_float(away_odds)

    errors = []

    if home is None or home <= 1:
        errors.append("승 배당")

    if draw is None or draw <= 1:
        errors.append("무 배당")

    if away is None or away <= 1:
        errors.append("패 배당")

    return {

        "valid":
            len(errors) == 0,

        "errors":
            errors,

        "home":
            home,

        "draw":
            draw,

        "away":
            away,

    }


# ============================================================
# 모듈 테스트용
# ============================================================

if __name__ == "__main__":

    test = calculate_implied_probabilities(
        1.83,
        3.20,
        4.10,
    )

    print(test)
