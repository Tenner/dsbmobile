"""Fetch and dump the actual HTML structure of subst_001.htm."""
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import getpass

LOGIN_URL = "https://www.dsbmobile.de/Login.aspx"

PLAN_URLS = [
    "https://dsbmobile.de/data/d96553e1-c205-46d6-998e-cc9676bd6046/2b487ea6-ccbc-42ba-a9c8-1ede780c815d/subst_001.htm",
]


async def main():
    username = input("Benutzer-ID: ").strip()
    password = getpass.getpass("Passwort: ").strip()

    jar = aiohttp.CookieJar()
    async with aiohttp.ClientSession(cookie_jar=jar) as session:
        # Login
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

        # Fetch plan with correct encoding
        for url in PLAN_URLS:
            async with session.get(url) as resp:
                raw = await resp.read()
                html = raw.decode("iso-8859-1")

            soup = BeautifulSoup(html, "html.parser")

            # Show the structure
            print("=== TITLE ===")
            print(soup.title.string if soup.title else "?")

            print("\n=== ALL DIVS WITH CLASS ===")
            for div in soup.find_all("div"):
                classes = div.get("class", [])
                if classes:
                    text = div.get_text(" ", strip=True)[:80]
                    print(f"  class={classes}  text={text}")

            print("\n=== ALL TABLES ===")
            tables = soup.find_all("table")
            print(f"  Found {len(tables)} tables")

            for i, table in enumerate(tables):
                print(f"\n--- Table {i} ---")
                classes = table.get("class", [])
                print(f"  class={classes}")
                rows = table.find_all("tr")
                print(f"  rows={len(rows)}")
                for j, row in enumerate(rows[:5]):  # First 5 rows
                    cells = row.find_all(["td", "th"])
                    cell_texts = [c.get_text(strip=True) for c in cells]
                    row_class = row.get("class", [])
                    print(f"  row {j} class={row_class}: {cell_texts}")
                if len(rows) > 5:
                    print(f"  ... ({len(rows)} total rows)")

            print("\n=== FIRST 3000 CHARS OF HTML ===")
            print(html[:3000])


asyncio.run(main())
