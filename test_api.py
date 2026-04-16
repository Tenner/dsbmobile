"""Test the Web API endpoint found in configuration.js."""
import asyncio
import json
import gzip
import base64
import uuid
from datetime import datetime, timezone

import aiohttp
from bs4 import BeautifulSoup
import getpass

LOGIN_URL = "https://www.dsbmobile.de/Login.aspx"
WEB_API_URL = "https://www.dsbmobile.de/jhw-1fd98248-440c-4283-bef6-dc82fe769b61.ashx/GetData"


async def main():
    username = input("Benutzer-ID: ").strip()
    password = getpass.getpass("Passwort: ").strip()

    jar = aiohttp.CookieJar()
    async with aiohttp.ClientSession(cookie_jar=jar) as session:
        # 1. Login first to get session cookies
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
            if "Login" in (await resp.text())[:300]:
                print("Login fehlgeschlagen")
                return
            print("Login OK")

        # 2. Call the Web API (same format as Android API)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload = {
            "UserId": username,
            "UserPw": password,
            "AppVersion": "2.3",
            "Language": "de",
            "OsVersion": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "AppId": str(uuid.uuid4()),
            "Device": "WebApp",
            "BundleId": "de.heinekingmedia.inhouse.dsbmobile.web",
            "Date": now,
            "LastUpdate": now,
            "PushId": "",
        }

        compressed = gzip.compress(json.dumps(payload).encode("utf-8"))
        encoded = base64.b64encode(compressed).decode("utf-8")
        body = {"req": {"Data": encoded, "DataType": 1}}

        async with session.post(
            WEB_API_URL,
            json=body,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Referer": "https://www.dsbmobile.de/default.aspx",
            },
        ) as resp:
            print(f"\nAPI Status: {resp.status}")
            result = await resp.json(content_type=None)

            resp_data = result.get("d", "")
            if resp_data:
                decoded = gzip.decompress(base64.b64decode(resp_data))
                data = json.loads(decoded)
                print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                print("Response:")
                print(json.dumps(result, indent=2, ensure_ascii=False))


asyncio.run(main())
