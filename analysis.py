# ============================================================
# analysis.py
# ⚽ Scoreman 배당 분석
#
# 기능
# - 업체 목록
# - 수동 승/무/패 배당 입력
# - 완전 동일배당 검색
# - 실제 승/무/패 결과
# - 실제 결과 확률
# - 배당 기반 확률
# - 실제확률 - 배당확률
# - 부족/초과 확률
# - 업체별 분석
# ============================================================

import database


# ============================================================
# 업체 목록
# ============================================================

def get_company_list():

    try:
        companies = database.get_company_list() or []

        return sorted(
            list(set(
                str(x).strip()
                for x in companies
                if str(x).strip()
            )),
            key=lambda x: x.lower()
        )

    except Exception:

        return []


# ============================================================
# 숫자
# ============================================================

def _to_float(value):

    try:

        value = float(value)

        if value <= 0:
            return None

        return value

    except Exception:

        return None


# ============================================================
# 배당 → 확률
#
# 1 / 배당값을 정규화하여 100%로 환산
# ============================================================

def odds_to_probability(
    home,
    draw,
    away
):

    home = _to_float(home)
    draw = _to_float(draw)
    away = _to_float(away)

    if (
        home is None
        or draw is None
        or away is None
    ):

        return {

            "home": 0.0,
            "draw": 0.0,
            "away": 0.0

        }

    ih = 1.0 / home
    id_ = 1.0 / draw
    ia = 1.0 / away

    total = ih + id_ + ia

    if total <= 0:

        return {

            "home": 0.0,
            "draw": 0.0,
            "away": 0.0

        }

    return {

        "home":
            ih / total * 100.0,

        "draw":
            id_ / total * 100.0,

        "away":
            ia / total * 100.0

    }


# ============================================================
# 결과 정규화
# ============================================================

def _normalize_result(value):

    if value is None:
        return ""

    value = str(value).strip()

    if value in ("승", "W", "win", "WIN"):
        return "승"

    if value in ("무", "D", "draw", "DRAW"):
        return "무"

    if value in ("패", "L", "loss", "LOSS"):
        return "패"

    return value


# ============================================================
# 실제 결과 통계
# ============================================================

def calculate_actual_probability(
    results
):

    total = len(results)

    if total <= 0:

        return {

            "count": 0,

            "home_count": 0,
            "draw_count": 0,
            "away_count": 0,

            "home": 0.0,
            "draw": 0.0,
            "away": 0.0

        }

    home_count = 0
    draw_count = 0
    away_count = 0

    for row in results:

        result = _normalize_result(
            row.get("result", "")
        )

        if result == "승":

            home_count += 1

        elif result == "무":

            draw_count += 1

        elif result == "패":

            away_count += 1

    return {

        "count":
            total,

        "home_count":
            home_count,

        "draw_count":
            draw_count,

        "away_count":
            away_count,

        "home":
            home_count / total * 100.0,

        "draw":
            draw_count / total * 100.0,

        "away":
            away_count / total * 100.0

    }


# ============================================================
# 부족 / 초과 확률
#
# 실제확률 - 배당확률
#
# + : 실제 결과가 배당확률보다 많이 발생
# - : 실제 결과가 배당확률보다 적게 발생
# ============================================================

def calculate_shortage(
    actual,
    probability
):

    return {

        "home":
            actual.get("home", 0.0)
            - probability.get("home", 0.0),

        "draw":
            actual.get("draw", 0.0)
            - probability.get("draw", 0.0),

        "away":
            actual.get("away", 0.0)
            - probability.get("away", 0.0)

    }


# ============================================================
# 가장 큰 부족/초과
# ============================================================

def get_highest_shortage(
    stats
):

    if not stats:
        return ""

    shortage = stats.get(
        "shortage",
        {}
    )

    values = {

        "승":
            float(
                shortage.get(
                    "home",
                    0
                )
            ),

        "무":
            float(
                shortage.get(
                    "draw",
                    0
                )
            ),

        "패":
            float(
                shortage.get(
                    "away",
                    0
                )
            )

    }

    if not values:
        return ""

    return max(
        values,
        key=lambda x:
            abs(values[x])
    )


# ============================================================
# 단일 업체 분석
# ============================================================

def analyze_company(
    company,
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.0001
):

    home_odds = _to_float(home_odds)
    draw_odds = _to_float(draw_odds)
    away_odds = _to_float(away_odds)

    if (
        home_odds is None
        or draw_odds is None
        or away_odds is None
    ):

        return {

            "success": False,

            "message":
                "승/무/패 배당을 모두 입력하세요.",

            "results": [],

            "statistics": None

        }

    # --------------------------------------------------------
    # 동일배당 검색
    # --------------------------------------------------------

    results = database.search_same_odds(

        company_name=company,

        home_odds=home_odds,

        draw_odds=draw_odds,

        away_odds=away_odds,

        tolerance=tolerance

    )

    # --------------------------------------------------------
    # 실제 결과
    # --------------------------------------------------------

    actual = calculate_actual_probability(
        results
    )

    # --------------------------------------------------------
    # 배당 기반 확률
    # --------------------------------------------------------

    probability = odds_to_probability(

        home_odds,

        draw_odds,

        away_odds

    )

    # --------------------------------------------------------
    # 부족 / 초과
    # --------------------------------------------------------

    shortage = calculate_shortage(

        actual,

        probability

    )

    statistics = {

        "count":
            len(results),

        "actual":
            actual,

        "probability":
            probability,

        "shortage":
            shortage,

        "input_odds": {

            "home":
                home_odds,

            "draw":
                draw_odds,

            "away":
                away_odds

        }

    }

    return {

        "success": True,

        "message":
            f"{len(results):,}개 경기 검색 완료",

        "company":
            company,

        "results":
            results,

        "statistics":
            statistics

    }


# ============================================================
# 여러 업체 분석
# ============================================================

def run_search(
    companies,
    odds_input,
    tolerance=0.0001
):

    if not companies:

        return {

            "success": False,

            "message":
                "분석할 업체를 선택하세요.",

            "results": [],

            "statistics": None,

            "company_statistics": {}

        }

    all_results = []

    company_statistics = {}

    total_actual = {

        "home": 0.0,
        "draw": 0.0,
        "away": 0.0

    }

    total_probability = {

        "home": 0.0,
        "draw": 0.0,
        "away": 0.0

    }

    total_count = 0

    # --------------------------------------------------------
    # 업체별 검색
    # --------------------------------------------------------

    for company in companies:

        data = odds_input.get(
            company,
            {}
        )

        result = analyze_company(

            company,

            data.get("home"),

            data.get("draw"),

            data.get("away"),

            tolerance

        )

        if not result.get("success"):

            continue

        results = result.get(
            "results",
            []
        )

        stats = result.get(
            "statistics"
        )

        company_statistics[
            company
        ] = stats

        all_results.extend(
            results
        )

        count = len(results)

        total_count += count

        if count > 0:

            actual = stats.get(
                "actual",
                {}
            )

            probability = stats.get(
                "probability",
                {}
            )

            total_actual["home"] += (
                actual.get("home", 0)
                * count
                / 100.0
            )

            total_actual["draw"] += (
                actual.get("draw", 0)
                * count
                / 100.0
            )

            total_actual["away"] += (
                actual.get("away", 0)
                * count
                / 100.0
            )

            total_probability["home"] += (
                probability.get("home", 0)
                * count
                / 100.0
            )

            total_probability["draw"] += (
                probability.get("draw", 0)
                * count
                / 100.0
            )

            total_probability["away"] += (
                probability.get("away", 0)
                * count
                / 100.0
            )

    # --------------------------------------------------------
    # 전체 통계
    # --------------------------------------------------------

    if total_count > 0:

        actual = {

            "home":
                total_actual["home"]
                / total_count
                * 100.0,

            "draw":
                total_actual["draw"]
                / total_count
                * 100.0,

            "away":
                total_actual["away"]
                / total_count
                * 100.0

        }

        probability = {

            "home":
                total_probability["home"]
                / total_count
                * 100.0,

            "draw":
                total_probability["draw"]
                / total_count
                * 100.0,

            "away":
                total_probability["away"]
                / total_count
                * 100.0

        }

    else:

        actual = {

            "home": 0.0,
            "draw": 0.0,
            "away": 0.0

        }

        probability = {

            "home": 0.0,
            "draw": 0.0,
            "away": 0.0

        }

    shortage = calculate_shortage(

        actual,

        probability

    )

    statistics = {

        "count":
            total_count,

        "actual":
            actual,

        "probability":
            probability,

        "shortage":
            shortage

    }

    return {

        "success": True,

        "message":
            f"{total_count:,}개 경기 분석 완료",

        "results":
            all_results,

        "statistics":
            statistics,

        "company_statistics":
            company_statistics

    }


# ============================================================
# 업체별 결과 요약
# ============================================================

def get_company_summary(
    company_statistics
):

    rows = []

    for company, stats in (
        company_statistics or {}
    ).items():

        if not stats:
            continue

        actual = stats.get(
            "actual",
            {}
        )

        probability = stats.get(
            "probability",
            {}
        )

        shortage = stats.get(
            "shortage",
            {}
        )

        rows.append({

            "업체":
                company,

            "경기수":
                stats.get(
                    "count",
                    0
                ),

            "실제 승률":
                actual.get(
                    "home",
                    0
                ),

            "실제 무승률":
                actual.get(
                    "draw",
                    0
                ),

            "실제 패율":
                actual.get(
                    "away",
                    0
                ),

            "배당 승확률":
                probability.get(
                    "home",
                    0
                ),

            "배당 무확률":
                probability.get(
                    "draw",
                    0
                ),

            "배당 패확률":
                probability.get(
                    "away",
                    0
                ),

            "승 부족/초과":
                shortage.get(
                    "home",
                    0
                ),

            "무 부족/초과":
                shortage.get(
                    "draw",
                    0
                ),

            "패 부족/초과":
                shortage.get(
                    "away",
                    0
                )

        })

    return rows
