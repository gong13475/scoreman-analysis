import requests
import re


URL = (
    "https://www.scoreman123.com/"
    "match/data-2929675"
)


HEADERS = {

    "User-Agent": (
        "Mozilla/5.0 "
        "(Linux; Android 10) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 "
        "Mobile Safari/537.36"
    )
}


def main():

    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=30
    )

    print(
        "HTTP:",
        response.status_code
    )

    html = response.text


    # ======================================
    # callOddsDetailWin 함수 찾기
    # ======================================

    keyword = "callOddsDetailWin"

    positions = [
        m.start()
        for m in re.finditer(
            keyword,
            html
        )
    ]


    print(
        "callOddsDetailWin 발견:",
        len(positions)
    )


    for position in positions[:10]:

        start = max(
            0,
            position - 1000
        )

        end = min(
            len(html),
            position + 5000
        )

        print(
            "\n"
            + "=" * 80
        )

        print(
            html[start:end]
        )


    # ======================================
    # odds 관련 JavaScript 파일 찾기
    # ======================================

    scripts = re.findall(
        r'<script[^>]+src=["\']([^"\']+)',
        html,
        re.I
    )


    print(
        "\n\nJavaScript 파일:",
        len(scripts)
    )


    for script in scripts:

        if (
            "odds" in script.lower()
            or
            "match" in script.lower()
            or
            "data" in script.lower()
        ):

            print(
                script
            )


if __name__ == "__main__":

    main()
