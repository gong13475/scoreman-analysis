import database


# =========================================================
# 업체명 정규화
# =========================================================

def normalize_company_name(name):

    if name is None:
        return ""

    value = str(name).strip().lower()

    value = value.replace(" ", "")
    value = value.replace("_", "")
    value = value.replace("-", "")
    value = value.replace(".", "")

    return value


# =========================================================
# 업체 목록
# =========================================================

def get_company_list():

    database.init_database()

    companies = database.get_company_names()

    result = list(companies)

    # 주요 해외 업체
    preferred_companies = [
        "Bet365",
        "William Hill",
        "10Bet",
        "Betway",
        "1xBet",
        "Pinnacle",
        "188Bet",
        "Marathon",
        "Unibet",
        "Bwin"
    ]

    existing_normalized = set()

    for company in result:

        existing_normalized.add(
            normalize_company_name(company)
        )

    for company in preferred_companies:

        normalized = normalize_company_name(
            company
        )

        if normalized not in existing_normalized:

            result.append(company)

            existing_normalized.add(
                normalized
            )

    return sorted(
        result,
        key=lambda x: str(x).lower()
    )


# =========================================================
# 배당 입력값 검증
# =========================================================

def validate_company_odds(
    selected_companies,
    input_odds
):

    if not selected_companies:

        return (
            False,
            "업체를 하나 이상 선택하세요."
        )

    if not input_odds:

        return (
            False,
            "배당값을 입력하세요."
        )

    for company in selected_companies:

        if company not in input_odds:

            return (
                False,
                f"{company} 배당값이 없습니다."
            )

        odds = input_odds[company]

        for key in [
            "home",
            "draw",
            "away"
        ]:

            if key not in odds:

                return (
                    False,
                    f"{company}의 {key} 배당값이 없습니다."
                )

            try:

                value = float(
                    odds[key]
                )

                if value <= 0:

                    return (
                        False,
                        f"{company} 배당값은 0보다 커야 합니다."
                    )

            except Exception:

                return (
                    False,
                    f"{company} 배당값이 올바르지 않습니다."
                )

    return True, ""


# =========================================================
# 배당 → 기본 확률
#
# 단순 역수 확률
# =========================================================

def odds_to_probability(
    home,
    draw,
    away
):

    try:

        home = float(home)
        draw = float(draw)
        away = float(away)

        if (
            home <= 0
            or draw <= 0
            or away <= 0
        ):
            return None

        inv_home = 1.0 / home
        inv_draw = 1.0 / draw
        inv_away = 1.0 / away

        total = (
            inv_home
            + inv_draw
            + inv_away
        )

        if total <= 0:
            return None

        return {

            "home":
                inv_home / total * 100,

            "draw":
                inv_draw / total * 100,

            "away":
                inv_away / total * 100
        }

    except Exception:

        return None


# =========================================================
# 결과별 통계
# =========================================================

def calculate_result_statistics(
    results
):

    total = len(results)

    win_count = 0
    draw_count = 0
    loss_count = 0

    for row in results:

        result = str(
            row.get(
                "result",
                ""
            )
        ).strip()

        if result == "승":
            win_count += 1

        elif result == "무":
            draw_count += 1

        elif result == "패":
            loss_count += 1

    if total > 0:

        win_percent = (
            win_count /
            total *
            100
        )

        draw_percent = (
            draw_count /
            total *
            100
        )

        loss_percent = (
            loss_count /
            total *
            100
        )

    else:

        win_percent = 0
        draw_percent = 0
        loss_percent = 0

    return {

        "total":
            total,

        "win":
            win_count,

        "draw":
            draw_count,

        "loss":
            loss_count,

        "win_percent":
            win_percent,

        "draw_percent":
            draw_percent,

        "loss_percent":
            loss_percent
    }


# =========================================================
# 배당 확률 + 실제 결과 비교
#
# 사용자가 요청한 핵심 기능
#
# 예:
# 배당 확률
# 승 55%
# 무 25%
# 패 20%
#
# 실제 결과
# 승 40%
# 무 35%
# 패 25%
#
# 부족확률
# 승 -15%
# 무 +10%
# 패 +5%
#
# 즉 예상확률보다 실제 결과가 얼마나
# 부족하거나 많은지 표시
# =========================================================

def calculate_probability_gap(
    results,
    home_odds,
    draw_odds,
    away_odds
):

    probability = odds_to_probability(
        home_odds,
        draw_odds,
        away_odds
    )

    if probability is None:

        return {

            "probability":
                None,

            "actual":
                None,

            "gap":
                None
        }

    statistics = (
        calculate_result_statistics(
            results
        )
    )

    actual = {

        "home":
            statistics["win_percent"],

        "draw":
            statistics["draw_percent"],

        "away":
            statistics["loss_percent"]
    }

    gap = {

        "home":
            actual["home"]
            -
            probability["home"],

        "draw":
            actual["draw"]
            -
            probability["draw"],

        "away":
            actual["away"]
            -
            probability["away"]
    }

    return {

        "probability":
            probability,

        "actual":
            actual,

        "gap":
            gap
    }


# =========================================================
# 부족확률 표시용
#
# 음수 = 실제 결과가 배당확률보다 부족
# 양수 = 실제 결과가 배당확률보다 많음
# =========================================================

def get_gap_text(value):

    try:

        value = float(value)

    except Exception:

        return "-"

    if value < 0:

        return f"부족 {abs(value):.1f}%"

    if value > 0:

        return f"초과 +{value:.1f}%"

    return "일치 0.0%"


# =========================================================
# 결과 전체 분석
# =========================================================

def build_result_analysis(
    results,
    home_odds,
    draw_odds,
    away_odds
):

    total = len(results)

    statistics = (
        calculate_result_statistics(
            results
        )
    )

    probability = odds_to_probability(
        home_odds,
        draw_odds,
        away_odds
    )

    if probability is None:

        return {

            "total":
                total,

            "statistics":
                statistics,

            "probability":
                None,

            "actual":
                None,

            "gap":
                None
        }

    actual = {

        "home":
            statistics["win_percent"],

        "draw":
            statistics["draw_percent"],

        "away":
            statistics["loss_percent"]
    }

    gap = {

        "home":
            actual["home"]
            -
            probability["home"],

        "draw":
            actual["draw"]
            -
            probability["draw"],

        "away":
            actual["away"]
            -
            probability["away"]
    }

    return {

        "total":
            total,

        "statistics":
            statistics,

        "probability":
            probability,

        "actual":
            actual,

        "gap":
            gap
    }


# =========================================================
# 업체별 검색
# =========================================================

def search_company(
    company,
    odds
):

    try:

        rows = database.search_final_odds(

            company_name=company,

            final_home=float(
                odds["home"]
            ),

            final_draw=float(
                odds["draw"]
            ),

            final_away=float(
                odds["away"]
            )
        )

        return list(rows)

    except Exception:

        return []


# =========================================================
# 여러 업체 검색
# =========================================================

def run_search(
    selected_companies,
    input_odds
):

    valid, message = (
        validate_company_odds(
            selected_companies,
            input_odds
        )
    )

    if not valid:

        return {

            "success":
                False,

            "message":
                message,

            "results":
                []
        }

    company_odds = {}

    for company in selected_companies:

        odds = input_odds[company]

        company_odds[company] = {

            "home":
                float(odds["home"]),

            "draw":
                float(odds["draw"]),

            "away":
                float(odds["away"])
        }

    try:

        matches = (
            database.search_multiple_final_odds(
                company_odds
            )
        )

    except Exception as e:

        return {

            "success":
                False,

            "message":
                str(e),

            "results":
                []
        }

    results = []

    normalized_selected = {}

    for company in selected_companies:

        normalized_selected[
            normalize_company_name(
                company
            )
        ] = company

    for match in matches:

        item = dict(match)

        item["company_odds"] = {}

        rows = (
            database.get_match_final_odds(
                match["schedule_id"]
            )
        )

        for row in rows:

            actual_name = row[
                "company_name"
            ]

            normalized = (
                normalize_company_name(
                    actual_name
                )
            )

            selected_name = (
                normalized_selected.get(
                    normalized
                )
            )

            if selected_name:

                item[
                    "company_odds"
                ][selected_name] = {

                    "home":
                        row["final_home"],

                    "draw":
                        row["final_draw"],

                    "away":
                        row["final_away"]
                }

        # ---------------------------------------------
        # 여러 업체의 배당을 이용한 평균 배당
        # ---------------------------------------------

        home_values = []
        draw_values = []
        away_values = []

        for company in selected_companies:

            odds = item[
                "company_odds"
            ].get(company)

            if not odds:
                continue

            try:

                home_values.append(
                    float(odds["home"])
                )

                draw_values.append(
                    float(odds["draw"])
                )

                away_values.append(
                    float(odds["away"])
                )

            except Exception:

                continue

        if home_values:

            avg_home = (
                sum(home_values)
                /
                len(home_values)
            )

        else:

            avg_home = None

        if draw_values:

            avg_draw = (
                sum(draw_values)
                /
                len(draw_values)
            )

        else:

            avg_draw = None

        if away_values:

            avg_away = (
                sum(away_values)
                /
                len(away_values)
            )

        else:

            avg_away = None

        item["average_odds"] = {

            "home":
                avg_home,

            "draw":
                avg_draw,

            "away":
                avg_away
        }

        # ---------------------------------------------
        # 이 경기 자체의 결과
        # ---------------------------------------------

        item["actual_result"] = (
            item.get(
                "result",
                ""
            )
        )

        results.append(item)

    # =====================================================
    # 검색된 전체 경기 기준 통계
    # =====================================================

    overall = calculate_result_statistics(
        results
    )

    # =====================================================
    # 평균배당 기준 확률
    # =====================================================

    valid_average = [

        row["average_odds"]

        for row in results

        if row.get(
            "average_odds",
            {}
        ).get("home") is not None

        and row.get(
            "average_odds",
            {}
        ).get("draw") is not None

        and row.get(
            "average_odds",
            {}
        ).get("away") is not None

    ]

    average_probability = None
    average_gap = None

    if valid_average:

        avg_home = sum(
            x["home"]
            for x in valid_average
        ) / len(valid_average)

        avg_draw = sum(
            x["draw"]
            for x in valid_average
        ) / len(valid_average)

        avg_away = sum(
            x["away"]
            for x in valid_average
        ) / len(valid_average)

        average_probability = (
            odds_to_probability(
                avg_home,
                avg_draw,
                avg_away
            )
        )

        if average_probability:

            actual = {

                "home":
                    overall["win_percent"],

                "draw":
                    overall["draw_percent"],

                "away":
                    overall["loss_percent"]
            }

            average_gap = {

                "home":
                    actual["home"]
                    -
                    average_probability["home"],

                "draw":
                    actual["draw"]
                    -
                    average_probability["draw"],

                "away":
                    actual["away"]
                    -
                    average_probability["away"]
            }

    return {

        "success":
            True,

        "message":
            "",

        "results":
            results,

        # 전체 경기 수
        "total_games":
            overall["total"],

        # 실제 결과 건수
        "win_count":
            overall["win"],

        "draw_count":
            overall["draw"],

        "loss_count":
            overall["loss"],

        # 실제 결과 퍼센트
        "win_percent":
            overall["win_percent"],

        "draw_percent":
            overall["draw_percent"],

        "loss_percent":
            overall["loss_percent"],

        # 평균배당
        "average_probability":
            average_probability,

        # 배당확률 대비 부족/초과
        "average_gap":
            average_gap
    }


# =========================================================
# 검색 결과 요약
# =========================================================

def get_summary(result):

    if not result:

        return {}

    return {

        "전체 경기":
            result.get(
                "total_games",
                0
            ),

        "승":
            result.get(
                "win_count",
                0
            ),

        "무":
            result.get(
                "draw_count",
                0
            ),

        "패":
            result.get(
                "loss_count",
                0
            ),

        "승률":
            result.get(
                "win_percent",
                0
            ),

        "무승부율":
            result.get(
                "draw_percent",
                0
            ),

        "패율":
            result.get(
                "loss_percent",
                0
            )
    }


# =========================================================
# 테스트
# =========================================================

if __name__ == "__main__":

    database.init_database()

    print(
        "========================================"
    )

    print(
        "Scoreman Analysis"
    )

    print(
        "업체:"
    )

    for company in get_company_list():

        print(
            "-",
            company
        )

    print(
        "========================================"
        )
