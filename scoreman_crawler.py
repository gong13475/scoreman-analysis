import re
import requests

from bs4 import BeautifulSoup

from database import (
    create_database,
    save_matches,
    get_database_status
)


# =========================================================
# 스코어맨
# =========================================================

SCOREMAN_URL = (
    "https://football.scoreman123.com/league/25/"
)


HEADERS = {

    "User-Agent": (
        "Mozilla/5.0 "
        "(Linux; Android 10; K) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 "
        "Mobile Safari/537.36"
    ),

    "Accept-Language":
        "ko-KR,ko;q=0.9,en-US;q=0.8"
}


# =========================================================
# 해외업체 목록
# =========================================================

BOOKMAKERS = [

    "마카오",

    "Bet365",

    "Pinnacle",

    "SBOBET",

    "188BET",

    "William Hill",

    "10BET",

    "12BET",

    "1XBET",

    "기타"
]


# =========================================================
# 페이지 요청
# =========================================================

def get_page(
    url=SCOREMAN_URL
):

    response = requests.get(

        url,

        headers=HEADERS,

        timeout=30
    )

    response.raise_for_status()

    response.encoding = (
        response.apparent_encoding
    )

    return response.text


# =========================================================
# 배당 추출
# =========================================================

def find_odds(text):

    if not text:

        return []

    values = re.findall(
        r"\b\d+\.\d{2}\b",
        text
    )

    return [
        float(x)
        for x in values
    ]


# =========================================================
# 결과 계산
# =========================================================

def score_to_result(
    text
):

    match = re.search(
        r"(\d+)\s*[-:]\s*(\d+)",
        text
    )

    if not match:

        return ""

    home = int(
        match.group(1)
    )

    away = int(
        match.group(2)
    )

    if home > away:

        return "승"

    if home < away:

        return "패"

    return "무"


# =========================================================
# 경기 파싱
# =========================================================

def parse_matches(
    html,
    bookmaker=""
):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    matches = []

    rows = soup.find_all(
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

        teams = []

        for link in links:

            name = link.get_text(
                " ",
                strip=True
            )

            if name:

                teams.append(
                    name
                )

        if len(teams) < 2:

            continue

        odds = find_odds(
            text
        )

        if len(odds) < 3:

            continue

        home_team = teams[0]
        away_team = teams[1]

        home_odds = odds[0]
        draw_odds = odds[1]
        away_odds = odds[2]

        result = score_to_result(
            text
        )

        matches.append({

            "source":
                "Scoreman",

            "bookmaker":
                bookmaker,

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
# 자동수집
# =========================================================

def auto_collect(
    url=SCOREMAN_URL,
    selected_bookmakers=None
):

    create_database()

    if selected_bookmakers is None:

        selected_bookmakers = [
            "마카오"
        ]

    html = get_page(
        url
    )

    all_matches = []

    # 현재 페이지에서 읽은 배당을
    # 선택한 업체에 연결
    for bookmaker in selected_bookmakers:

        parsed = parse_matches(
            html,
            bookmaker
        )

        all_matches.extend(
            parsed
        )

    saved = save_matches(
        all_matches
    )

    return {
        "found":
            len(all_matches),

        "saved":
            saved,

        "matches":
            all_matches
    }


# =========================================================
# 페이지 검사
# =========================================================

def inspect_page():

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

    return html


if __name__ == "__main__":

    result = auto_collect()

    print(
        "수집 경기:",
        result["found"]
    )

    print(
        "저장 경기:",
        result["saved"]
    )

    print(
        get_database_status()
    )
