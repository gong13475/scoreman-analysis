# ============================================================
# analysis.py
# ⚽ Scoreman 해외배당 분석 엔진
# ============================================================

from datetime import datetime, timedelta

import database


DEFAULT_TOLERANCE = 0.01


# ============================================================
# 숫자
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


def format_odds(value):

    number = to_float(value)

    if number is None:
        return "-"

    return f"{number:.2f}"


# ============================================================
# 배당 암시확률
# ============================================================

def odds_to_probability(odds):

    odds = to_float(odds)

    if odds is None or odds <= 0:
        return 0.0

    return (
        1.0 / odds * 100.0
    )


# ============================================================
# 정규화 암시확률
# ============================================================

def calculate_implied_probabilities(
    home_odds,
    draw_odds,
    away_odds
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

            "total_raw": 0.0

        }

    home_raw = (
        1.0 / home_odds * 100
    )

    draw_raw = (
        1.0 / draw_odds * 100
    )

    away_raw = (
        1.0 / away_odds * 100
    )

    total_raw = (
        home_raw
        + draw_raw
        + away_raw
    )

    return {

        "home":
            home_raw / total_raw * 100,

        "draw":
            draw_raw / total_raw * 100,

        "away":
            away_raw / total_raw * 100,

        "home_raw":
            home_raw,

        "draw_raw":
            draw_raw,

        "away_raw":
            away_raw,

        "total_raw":
            total_raw

    }


# ============================================================
# 실제 결과
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
            home + draw + away

    }


def calculate_result_probabilities(rows):

    counts = count_results(
        rows
    )

    total = counts["total"]

    if total <= 0:

        return {

            "home": 0.0,
            "draw": 0.0,
            "away": 0.0,

            "win": 0.0,
            "loss": 0.0,

            "total": 0

        }

    return {

        "home":
            counts["home"]
            / total
            * 100,

        "draw":
            counts["draw"]
            / total
            * 100,

        "away":
            counts["away"]
            / total
            * 100,

        "win":
            counts["win"]
            / total
            * 100,

        "loss":
            counts["loss"]
            / total
            * 100,

        "total":
            total

    }


# ============================================================
# 확률 차이
# ============================================================

def calculate_probability_gap(
    actual_probability,
    implied_probability
):

    return (
        float(actual_probability or 0)
        -
        float(implied_probability or 0)
    )


def calculate_shortage_probability(
    actual_probability,
    implied_probability
):

    gap = calculate_probability_gap(
        actual_probability,
        implied_probability
    )

    if gap >= 0:
        return 0.0

    return abs(gap)


# ============================================================
# 날짜
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
        "%Y.%m.%d"

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


def filter_recent_years(
    rows,
    years=5
):

    cutoff = (
        datetime.now()
        -
        timedelta(
            days=365 * int(years)
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

            result.append(row)

        elif date_value >= cutoff:

            result.append(row)

    return result


# ============================================================
# 동일배당
# ============================================================

def search_same_odds(
    company_name,
    home_odds,
    draw_odds,
    away_odds,
    tolerance=DEFAULT_TOLERANCE
):

    try:

        return database.search_same_odds(

            company_name,

            home_odds,

            draw_odds,

            away_odds,

            tolerance

        )

    except Exception:

        return []


def analyze_same_odds(
    rows,
    home_odds,
    draw_odds,
    away_odds
):

    counts = count_results(
        rows
    )

    actual = calculate_result_probabilities(
        rows
    )

    implied = calculate_implied_probabilities(
        home_odds,
        draw_odds,
        away_odds
    )

    home_gap = calculate_probability_gap(
        actual["home"],
        implied["home"]
    )

    draw_gap = calculate_probability_gap(
        actual["draw"],
        implied["draw"]
    )

    away_gap = calculate_probability_gap(
        actual["away"],
        implied["away"]
    )

    return {

        "total":
            actual["total"],

        "home_count":
            counts["home"],

        "draw_count":
            counts["draw"],

        "away_count":
            counts["away"],

        "win_count":
            counts["win"],

        "loss_count":
            counts["loss"],

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
                implied["home"]
            ),

        "draw_shortage":
            calculate_shortage_probability(
                actual["draw"],
                implied["draw"]
            ),

        "away_shortage":
            calculate_shortage_probability(
                actual["away"],
                implied["away"]
            ),

        "home_odds":
            float(home_odds),

        "draw_odds":
            float(draw_odds),

        "away_odds":
            float(away_odds)

    }


# ============================================================
# 업체 전체
# ============================================================

def analyze_company(
    company_name
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
                    ""
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
                        "final_home"
                    ),

                "draw_odds":
                    odds.get(
                        "final_draw"
                    ),

                "away_odds":
                    odds.get(
                        "final_away"
                    )

            })

            rows.append(row)

    return rows


def get_company_statistics(
    company_name
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
            rows

    }


def get_all_company_statistics():

    try:

        companies = (
            database.get_company_list()
        )

    except Exception:

        companies = []

    return [

        get_company_statistics(
            company
        )

        for company in companies

    ]


# ============================================================
# 가까운 배당
# ============================================================

def find_near_odds(
    company_name,
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.01
):

    rows = analyze_company(
        company_name
    )

    h0 = to_float(
        home_odds
    )

    d0 = to_float(
        draw_odds
    )

    a0 = to_float(
        away_odds
    )

    if (
        h0 is None
        or d0 is None
        or a0 is None
    ):

        return []

    result = []

    for row in rows:

        h = to_float(
            row.get("home_odds")
        )

        d = to_float(
            row.get("draw_odds")
        )

        a = to_float(
            row.get("away_odds")
        )

        if (
            h is None
            or d is None
            or a is None
        ):
            continue

        if (
            abs(h - h0) <= tolerance
            and
            abs(d - d0) <= tolerance
            and
            abs(a - a0) <= tolerance
        ):

            result.append(row)

    return result


# ============================================================
# 수동 분석
# ============================================================

def analyze_manual_odds(
    company_name,
    home_odds,
    draw_odds,
    away_odds,
    tolerance=DEFAULT_TOLERANCE,
    recent_years=None
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

            "rows": []

        }

    rows = search_same_odds(

        company_name,

        home_odds,

        draw_odds,

        away_odds,

        tolerance

    )

    if recent_years:

        rows = filter_recent_years(
            rows,
            int(recent_years)
        )

    result = analyze_same_odds(

        rows,

        home_odds,

        draw_odds,

        away_odds

    )

    result.update({

        "success": True,

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
            format_odds(away_odds)

    })

    return result


# ============================================================
# 추천
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
            )

    }

    return max(
        values,
        key=values.get
    )


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
            )

    }

    return max(
        values,
        key=values.get
    )


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
# 상세
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
                )

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
                )

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
                )

        }

    ]


# ============================================================
# 배당 검증
# ============================================================

def validate_odds(
    home_odds,
    draw_odds,
    away_odds
):

    home = to_float(
        home_odds
    )

    draw = to_float(
        draw_odds
    )

    away = to_float(
        away_odds
    )

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
            away

    }


if __name__ == "__main__":

    print(
        calculate_implied_probabilities(
            1.83,
            3.20,
            4.10
        )
    )
