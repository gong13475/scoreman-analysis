import re
import requests

from bs4 import BeautifulSoup

from database import (
    create_database,
    save_match,
    get_database_status
)


# =========================================================
# 스코어맨 URL
# =========================================================

SCOREMAN_URL = (
    "https://football.scoreman123.com/league/25/"
)


# =========================================================
# 헤더
# =========================================================

HEADERS = {

    "User-Agent": (
        "Mozilla/5.0 "
        "(Linux; Android 10) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 "
        "Mobile Safari/537.36"
    ),

    "Accept-Language":
        "ko-KR,ko;q=0.9,en-US;q=0.8"
}


# =========================================================
# 페이지 가져오기
# =========================================================

def get_page():

    response = requests.get(

        SCOREMAN_URL,

        headers=HEADERS,

        timeout=30
    )

    response.raise_for_status()

    return response.text


# =========================================================
# 배당 숫자
# =========================================================

def find_odds(text):

    if not text:
        return []

    values = re.findall(
        r"\b\d+\.\d{2}\b",
        text
    )

    return [
        float(value)
        for value in values
    ]


# =========================================================
# 결과 변환
# =========================================================

def convert_result(
    text
):

    text = str(
        text
    ).strip()

    if text in [
        "胜",
        "홈승",
        "승"
    ]:

        return "승"

    if text in [
        "平",
        "무",
        "무승부"
    ]:

        return "무"

    if text in [
        "负",
        "패",
        "원정승"
    ]:

        return "패"

    return ""


# =========================================================
# 경기 후보 파싱
# =========================================================

def parse_matches(
    html
):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    matches = []

    # -----------------------------------------------------
    # TABLE 방식
    # -----------------------------------------------------

    tables = soup.find_all(
        "table"
    )

    for table in tables:

        rows = table.find_all(
            "tr"
        )

        for row in rows:

            text = row.get_text(
                " ",
                strip=True
            )

            if not text:
                continue

            links = row.find_all(
                "a"
            )

            team_names = []

            for link in links:

                name = link.get_text(
                    " ",
                    strip=True
                )

                if name:

                    team_names.append(
                        name
                    )

            # 팀이 2개 이상 있어야 함
            if len(team_names) < 2:
                continue

            home_team = team_names[0]

            away_team = team_names[1]

            odds = find_odds(
                text
            )

            if len(odds) < 3:
                continue

            home_odds = odds[0]

            draw_odds = odds[1]

            away_odds = odds[2]

            result = ""

            # 점수 찾기
            score_match = re.search(
                r"(\d+)\s*[-:]\s*(\d+)",
                text
            )

            if score_match:

                home_score = int(
                    score_match.group(1)
                )

                away_score = int(
                    score_match.group(2)
                )

                if home_score > away_score:

                    result = "승"

                elif home_score < away_score:

                    result = "패"

                else:

                    result = "무"

            matches.append({

                "source":
                    "Scoreman",

                "sport":
                    "축구",

                "league":
                    "",

                "match_date":
                    "",

                "match_time":
                    "",

                "home_team":
                    home_team,

                "away_team":
                    away_team,

                "home_odds":
                    home_odds,

                "draw_odds":
                    draw_odds,

                "away_odds":
                    away_odds,

                "result":
                    result
            })

    return matches


# =========================================================
# 스코어맨 경기 수집
# =========================================================

def crawl_scoreman():

    create_database()

    html = get_page()

    print(
        "HTTP 페이지 수신 성공"
    )

    print(
        "HTML 크기:",
        len(html)
    )

    matches = parse_matches(
        html
    )

    print(
        "찾은 경기:",
        len(matches)
    )

    saved = 0

    for match in matches:

        saved += save_match(

            source=match[
                "source"
            ],

            sport=match[
                "sport"
            ],

            league=match[
                "league"
            ],

            match_date=match[
                "match_date"
            ],

            match_time=match[
                "match_time"
            ],

            home_team=match[
                "home_team"
            ],

            away_team=match[
                "away_team"
            ],

            home_odds=match[
                "home_odds"
            ],

            draw_odds=match[
                "draw_odds"
            ],

            away_odds=match[
                "away_odds"
            ],

            result=match[
                "result"
            ]
        )

    status = get_database_status()

    print(
        "새로 저장된 경기:",
        saved
    )

    print(
        "DB 전체 경기:",
        status["matches"]
    )

    return matches


# =========================================================
# 페이지 검사
# =========================================================

def inspect_page():

    create_database()

    html = get_page()

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    print(
        "HTTP 페이지 수신 성공"
    )

    print(
        "HTML 크기:",
        len(html)
    )

    text = soup.get_text(
        " ",
        strip=True
    )

    print(
        "\n페이지 텍스트:"
    )

    print(
        text[:5000]
    )

    links = soup.find_all(
        "a"
    )

    print(
        "\n링크 수:",
        len(links)
    )

    for link in links[:50]:

        href = link.get(
            "href"
        )

        name = link.get_text(
            " ",
            strip=True
        )

        if href:

            print(
                name,
                "=>",
                href
            )

    tables = soup.find_all(
        "table"
    )

    print(
        "\n테이블 수:",
        len(tables)
    )

    for index, table in enumerate(
        tables[:10]
    ):

        print(
            f"\n--- TABLE {index + 1} ---"
        )

        print(
            table.get_text(
                " ",
                strip=True
            )[:2000]
        )

    return html


# =========================================================
# 직접 실행
# =========================================================

if __name__ == "__main__":

    crawl_scoreman()
