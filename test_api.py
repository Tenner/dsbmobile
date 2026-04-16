"""Test fetching the actual subst_*.htm files."""
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import getpass

LOGIN_URL = "https://www.dsbmobile.de/Login.aspx"

PLAN_URLS = [
    "https://dsbmobile.de/data/d96553e1-c205-46d6-998e-cc9676bd6046/2b487ea6-ccbc-42ba-a9c8-1ede780c815d/subst_001.htm",
    "https://dsbmobile.de/data/d96553e1-c205-46d6-998e-cc9676bd6046/2b487ea6-ccbc-42ba-a9c8-1ede780c815d/subst_002.htm",
    "https://dsbmobile.de/data/d96553e1-c205-46d6-998e-cc9676bd6046/2b487ea6-ccbc-42ba-a9c8-1ede780c815d/subst_003.htm",
]


async def main():
    username = input("Benutzer-ID: ").strip()
    password = getpass.getpass("Passwort: ").strip()

    jar = aiohttp.CookieJar()
    async with aiohttp.ClientSession(cookie_jar=jar) as session:
        # Login first
        async with session.get(LOGIN_URL) as resp:
            html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")
        form = {
            "__VIEWSTATE": soup.find("input", {"name": "__VIEWSTATE"})["value"],
            "__VIEWSTATEGENERATOR": soup.find("input", {"name": "__VIEWSTATEGENERATOR"})["value"],
            "__EVENTVALIDATION": soup.find("input", {"name": "__EVENTVALIDATION"})["value"],
            "txtUser": username,
            "txtPass": password,
            "ctl03": "Anmelden",
        }
        async with session.post(LOGIN_URL, data=form, allow_redirects=True) as resp:
            print("Login OK\n")

        # Fetch each plan URL
        for url in PLAN_URLS:
            print(f"=== {url.split('/')[-1]} ===")
            try:
                async with session.get(url) as resp:
                    print(f"Status: {resp.status}")
                    print(f"Content-Type: {resp.headers.get('Content-Type', '?')}")
                    if resp.status == 200:
                        html = await resp.text()
                        print(f"Length: {len(html)} chars")
                        print(f"Preview: {html[:500]}")

                        # Check for 08b
                        if "08b" in html.lower():
                            print(">>> CONTAINS 08b <<<")
                        else:
                            print("(does not contain 08b)")
                    print()
            except Exception as e:
                print(f"Error: {e}\n")


asyncio.run(main())
