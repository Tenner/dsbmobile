"""Quick test script to check DSBmobile API responses."""
import asyncio
import aiohttp

DSB_AUTH_URL = "https://mobileapi.dsbcontrol.de/authid"
DSB_TIMETABLES_URL = "https://mobileapi.dsbcontrol.de/dsbtimetables"


async def main():
    username = input("Benutzer-ID: ")
    password = input("Passwort: ")

    async with aiohttp.ClientSession() as session:
        # 1. Auth
        params = {
            "bundleid": "de.heinekingmedia.dsbmobile",
            "appversion": "36",
            "osversion": "30",
            "pushid": "",
            "user": username,
            "password": password,
        }
        async with session.get(DSB_AUTH_URL, params=params) as resp:
            token_raw = await resp.text()
            print(f"\n[AUTH] Status: {resp.status}")
            print(f"[AUTH] Token raw: {token_raw[:100]}")
            token = token_raw.strip().strip('"')
            if not token:
                print("[AUTH] FEHLER: Leerer Token!")
                return
            print(f"[AUTH] Token: {token[:20]}...")

        # 2. Timetables
        async with session.get(DSB_TIMETABLES_URL, params={"authid": token}) as resp:
            print(f"\n[PLANS] Status: {resp.status}")
            data = await resp.json(content_type=None)
            print(f"[PLANS] Anzahl Items: {len(data) if data else 0}")

            if not data:
                print("[PLANS] FEHLER: Keine Daten!")
                return

            for i, item in enumerate(data):
                print(f"\n[PLAN {i}] Title: {item.get('Title')}")
                print(f"[PLAN {i}] Date: {item.get('Date')}")
                print(f"[PLAN {i}] ConType: {item.get('ConType')}")
                childs = item.get("Childs", [])
                print(f"[PLAN {i}] Childs: {len(childs)}")
                for j, child in enumerate(childs):
                    detail = child.get("Detail", "")
                    print(f"  [CHILD {j}] ConType: {child.get('ConType')}, Detail: {detail[:120]}")

                    # 3. Fetch HTML
                    if detail and detail.startswith("http"):
                        async with session.get(detail) as html_resp:
                            html = await html_resp.text()
                            print(f"  [HTML] Status: {html_resp.status}, Length: {len(html)} chars")
                            # Show first 500 chars
                            print(f"  [HTML] Preview:\n{html[:500]}")
                            print("  ...")


asyncio.run(main())
