# ============================================================
# analysis.py
# ⚽ Scoreman 배당 분석
#
# 기능
# - 회사별 분석
# - 완전 동일배당
# - 최근 5년
# - 전체 기간
# - 승/무/패 실제확률
# ============================================================

from datetime import datetime

import database


# ============================================================
# 날짜 필터
# ============================================================

def _recent_date_filter(
    recent_years
):

    if not recent_years:
        return None

    try:

        now = datetime.now()

        year = (
            now.year
            - int(recent_years)
        )

        return (
            f"{year:04d}-"
            f"{now.month:02d}-"
            f"{now.day:02d}"
        )

    except Exception:

        return None


# ============================================================
# 완전 동일배당 분석
# ============================================================

def analyze_manual_odds(
    company_name,
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0,
    recent_years=None
):

    try:

        company_name = str(
            company_name
        ).strip()

        if not company_name:

            return {
                "success": False,
                "error": "업체를 선택하세요."
            }

        home_odds = float(
            home_odds
        )

        draw_odds = float(
            draw_odds
        )

        away_odds = float(
            away_odds
        )

    except Exception:

        return {
            "success": False,
            "error": "배당값을 확인하세요."
        }

    if (

        home_odds <= 1

        or draw_odds <= 1

        or away_odds <= 1

    ):

        return {

            "success": False,

            "error":
                "배당은 1.01 이상이어야 합니다."

        }

    # --------------------------------------------------------
    # 완전 동일배당
    # --------------------------------------------------------

    rows = database.search_same_odds(

        company_name,

        home_odds,

        draw_odds,

        away_odds,

        tolerance=0

    )

    # --------------------------------------------------------
    # 최근 5년
    # --------------------------------------------------------

    if recent_years:

        cutoff = _recent_date_filter(
            recent_years
        )

        if cutoff:

            filtered = []

            for row in rows:

                date_text = str(

                    row.get(
                        "match_date",
                        ""
                    )
                    or ""

                )

                if not date_text:
                    continue

                if date_text[:10] >= cutoff:

                    filtered.append(
                        row
                    )

            rows = filtered

    # --------------------------------------------------------
    # 결과 계산
    # --------------------------------------------------------

    total = len(rows)

    home_count = 0
    draw_count = 0
    away_count = 0

    unknown_count = 0

    for row in rows:

        result = str(

            row.get(
                "result",
                ""
            )
            or ""

        ).strip()

        if result == "승":

            home_count += 1

        elif result == "무":

            draw_count += 1

        elif result == "패":

            away_count += 1

        else:

            unknown_count += 1

    if total > 0:

        actual_home = (
            home_count
            / total
            * 100
        )

        actual_draw = (
            draw_count
            / total
            * 100
        )

        actual_away = (
            away_count
            / total
            * 100
        )

    else:

        actual_home = 0.0
        actual_draw = 0.0
        actual_away = 0.0

    return {

        "success": True,

        "company_name":
            company_name,

        "home_odds":
            home_odds,

        "draw_odds":
            draw_odds,

        "away_odds":
            away_odds,

        "total":
            total,

        "home_count":
            home_count,

        "draw_count":
            draw_count,

        "away_count":
            away_count,

        "unknown_count":
            unknown_count,

        "actual_home":
            actual_home,

        "actual_draw":
            actual_draw,

        "actual_away":
            actual_away,

        "rows":
            rows

    }
