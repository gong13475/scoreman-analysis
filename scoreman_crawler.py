import requests
from bs4 import BeautifulSoup

from database import (
    create_database,
    save_match,
    get_database_status
)


# 테스트용 스코어맨 리그
SCOREMAN_URL = (
    "https://football.scoreman123.com/league/25/"
)


def get_page():

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Linux; Android 10) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0 "
            "Mobile Safari/537.36"
        )
    }

    response = requests.get(
        SCOREMAN_URL,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    return response.text


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

    # --------------------------------------
    # 페이지 텍스트
    # --------------------------------------

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

    # --------------------------------------
    # 링크
    # --------------------------------------

    links = soup.find_all("a")

    print(
        "\n링크 수:",
        len(links)
    )

    for link in links[:50]:

        href = link.get("href")

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

    # --------------------------------------
    # 테이블
    # --------------------------------------

    tables = soup.find_all("table")

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


if __name__ == "__main__":

    inspect_page()
