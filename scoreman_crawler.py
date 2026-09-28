import requests
from bs4 import BeautifulSoup
from datetime import datetime


SCOREMAN_URL = "https://www.scoreman123.com/football/results"


def get_scoreman_page():

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Linux; Android 10) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0 Mobile Safari/537.36"
        )
    }

    response = requests.get(
        SCOREMAN_URL,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    return response.text


def check_scoreman():

    try:

        html = get_scoreman_page()

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        title = soup.title

        if title:

            print(
                "페이지 제목:",
                title.get_text(strip=True)
            )

        print(
            "페이지 접속 성공"
        )

        print(
            "HTML 크기:",
            len(html)
        )

        return True

    except Exception as e:

        print(
            "스코어맨 접속 오류:",
            e
        )

        return False


if __name__ == "__main__":

    print(
        "스코어맨 접속 테스트"
    )

    check_scoreman()
