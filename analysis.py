import re
import math

import database


# =========================================================
# 업체 목록
# =========================================================

def get_company_list():

    return database.get_company_names()


# =========================================================
# 배당 → 확률
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

        inv_home = 1 / home
        inv_draw = 1 / draw
        inv_away = 1 / away

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
# 숫자 정규화
# =========================================================

def normalize_odds(value):

    if value is None:
        return None

    text = str(
        value
    ).strip().lower()

    text = text.replace(
        ",",
        "."
    )

    text = text.replace(
        "점",
        "."
    )

    text = text.replace(
        " ",
        ""
    )

    match = re.search(
        r"\d+(?:\.\d+)?",
        text
    )

    if not match:
        return None

    try:
        value = float(
            match.group(0)
        )

        if value <= 0:
            return None

        return value

    except Exception:

        return None


# =========================================================
# 음성 숫자 → 배당 3개
# =========================================================

def parse_voice_odds(text):

    if not text:
        return None

    text = str(
        text
    ).lower()

    text = text.replace(
        "배당",
        " "
    )

    text = text.replace(
        "홈",
        " "
    )

    text = text.replace(
        "무",
        " "
    )

    text = text.replace(
        "원정",
        " "
    )

    # 점 → .
    text = text.replace(
        "점",
        "."
    )

    # 한국어 숫자
    korean_numbers = {

        "영": "0",
        "공": "0",

        "일": "1",
        "이": "2",
        "삼": "3",
        "사": "4",
        "오": "5",
        "육": "6",
        "칠": "7",
        "팔": "8",
        "구": "9"
    }

    for word, number in korean_numbers.items():

        text = text.replace(
            word,
            number
        )

    # 숫자 추출
    numbers = re.findall(
        r"\d+(?:\.\d+)?",
        text
    )

    values = []

    for value in numbers:

        try:

            number = float(value)

            if number > 0:
                values.append(number)

        except Exception:
            pass

    # 정확히 3개
    if len(values) < 3:
        return None

    return {

        "home":
            values[0],

        "draw":
            values[1],

        "away":
            values[2]
    }


# =========================================================
# 배당 검색
# =========================================================

def search_by_odds(
    home,
    draw,
    away,
    tolerance=0.02
):

    home = float(home)
    draw = float(draw)
    away = float(away)

    rows = database.get_all_odds()

    results = []

    seen = set()

    for row in rows:

        try:

            rh = float(
                row["home_odds"]
            )

            rd = float(
                row["draw_odds"]
            )

            ra = float(
                row["away_odds"]
            )

        except Exception:

            continue

        if (
            abs(rh - home) <= tolerance
            and abs(rd - draw) <= tolerance
            and abs(ra - away) <= tolerance
        ):

            schedule_id = str(
                row["schedule_id"]
            )

            key = (
                schedule_id,
                row.get(
                    "bookmaker",
                    ""
                )
            )

            if key in seen:
                continue

            seen.add(key)

            match = database.get_match(
                schedule_id
            )

            if not match:
                continue

            results.append({

                "schedule_id":
                    schedule_id,

                "match_date":
                    match.get(
                        "match_date",
                        ""
                    ),

                "home_team":
                    match.get(
                        "home_team",
                        ""
                    ),

                "away_team":
                    match.get(
                        "away_team",
                        ""
                    ),

                "result":
                    match.get(
                        "result",
                        ""
                    ),

                "bookmaker":
                    row.get(
                        "bookmaker",
                        ""
                    ),

                "home_odds":
                    rh,

                "draw_odds":
                    rd,

                "away_odds":
                    ra
            })

    return results


# =========================================================
# 통계
# =========================================================

def calculate_statistics(
    results
):

    if not results:
        return None

    home_count = 0
    draw_count = 0
    away_count = 0

    prob_home = []
    prob_draw = []
    prob_away = []

    for row in results:

        result = row.get(
            "result"
        )

        if result == "승":
            home_count += 1

        elif result == "무":
            draw_count += 1

        elif result == "패":
            away_count += 1

        probability = odds_to_probability(

            row.get("home_odds"),
            row.get("draw_odds"),
            row.get("away_odds")
        )

        if probability:

            prob_home.append(
                probability["home"]
            )

            prob_draw.append(
                probability["draw"]
            )

            prob_away.append(
                probability["away"]
            )

    total = (
        home_count
        + draw_count
        + away_count
    )

    if total <= 0:
        return None

    actual = {

        "home":
            home_count / total * 100,

        "draw":
            draw_count / total * 100,

        "away":
            away_count / total * 100
    }

    probability = {

        "home":
            (
                sum(prob_home)
                / len(prob_home)
                if prob_home
                else 0
            ),

        "draw":
            (
                sum(prob_draw)
                / len(prob_draw)
                if prob_draw
                else 0
            ),

        "away":
            (
                sum(prob_away)
                / len(prob_away)
                if prob_away
                else 0
            )
    }

    shortage = {

        "home":
            actual["home"]
            - probability["home"],

        "draw":
            actual["draw"]
            - probability["draw"],

        "away":
            actual["away"]
            - probability["away"]
    }

    return {

        "count":
            total,

        "actual":
            actual,

        "probability":
            probability,

        "shortage":
            shortage
    }


# =========================================================
# 업체별 검색
# =========================================================

def run_search(
    companies,
    odds_input
):

    if not companies:

        return {

            "success":
                False,

            "message":
                "업체를 선택하세요.",

            "results":
                [],

            "statistics":
                None
        }

    rows = database.get_all_odds()

    results = []

    selected = {

        str(x).strip().lower()

        for x in companies
    }

    wanted = {}

    for company in companies:

        item = odds_input.get(
            company
        )

        if not item:
            continue

        wanted[
            str(company)
            .strip()
            .lower()
        ] = {

            "home":
                float(item["home"]),

            "draw":
                float(item["draw"]),

            "away":
                float(item["away"])
        }

    for row in rows:

        company = str(
            row.get(
                "bookmaker",
                ""
            )
        ).strip().lower()

        if company not in selected:
            continue

        if company not in wanted:
            continue

        target = wanted[company]

        try:

            rh = float(
                row["home_odds"]
            )

            rd = float(
                row["draw_odds"]
            )

            ra = float(
                row["away_odds"]
            )

        except Exception:
            continue

        if not (
            math.isclose(
                rh,
                target["home"],
                abs_tol=0.02
            )
            and
            math.isclose(
                rd,
                target["draw"],
                abs_tol=0.02
            )
            and
            math.isclose(
                ra,
                target["away"],
                abs_tol=0.02
            )
        ):
            continue

        match = database.get_match(
            row["schedule_id"]
        )

        if not match:
            continue

        results.append({

            "schedule_id":
                row["schedule_id"],

            "match_date":
                match.get(
                    "match_date",
                    ""
                ),

            "home_team":
                match.get(
                    "home_team",
                    ""
                ),

            "away_team":
                match.get(
                    "away_team",
                    ""
                ),

            "result":
                match.get(
                    "result",
                    ""
                ),

            "bookmaker":
                row.get(
                    "bookmaker",
                    ""
                ),

            "home_odds":
                rh,

            "draw_odds":
                rd,

            "away_odds":
                ra
        })

    stats = calculate_statistics(
        results
    )

    return {

        "success":
            True,

        "message":
            "",

        "results":
            results,

        "statistics":
            stats
    }


# =========================================================
# 부족한 결과
# =========================================================

def get_highest_shortage(stats):

    if not stats:
        return ""

    values = stats.get(
        "shortage",
        {}
    )

    if not values:
        return ""

    key = max(
        values,
        key=values.get
    )

    names = {

        "home":
            "홈승",

        "draw":
            "무승부",

        "away":
            "원정승"
    }

    return (
        names.get(
            key,
            key
        )
        + " "
        + f"{values[key]:+.2f}%"
    )


# =========================================================
# 음성 분석 문장
# =========================================================

def make_voice_summary(
    odds,
    results,
    stats
):

    if not stats:

        return (
            "해당 배당과 일치하는 "
            "저장 경기를 찾지 못했습니다."
        )

    actual = stats["actual"]
    probability = stats["probability"]
    shortage = stats["shortage"]

    strongest = max(
        actual,
        key=actual.get
    )

    names = {

        "home":
            "홈승",

        "draw":
            "무승부",

        "away":
            "원정승"
    }

    return (

        f"배당은 "
        f"{odds['home']:.2f}, "
        f"{odds['draw']:.2f}, "
        f"{odds['away']:.2f}입니다. "

        f"검색된 경기는 "
        f"{len(results)}경기입니다. "

        f"실제 결과는 "
        f"홈승 {actual['home']:.1f}퍼센트, "
        f"무승부 {actual['draw']:.1f}퍼센트, "
        f"원정승 {actual['away']:.1f}퍼센트입니다. "

        f"배당 기준 확률은 "
        f"홈승 {probability['home']:.1f}퍼센트, "
        f"무승부 {probability['draw']:.1f}퍼센트, "
        f"원정승 {probability['away']:.1f}퍼센트입니다. "

        f"배당 대비 실제 결과 차이는 "
        f"홈승 {shortage['home']:+.1f}퍼센트, "
        f"무승부 {shortage['draw']:+.1f}퍼센트, "
        f"원정승 {shortage['away']:+.1f}퍼센트입니다. "

        f"실제 결과 비율이 가장 높은 것은 "
        f"{names[strongest]}입니다."
            )
