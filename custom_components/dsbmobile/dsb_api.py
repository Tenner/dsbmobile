"""API client for DSBmobile using the Web API."""
from __future__ import annotations

import logging
import json
import gzip
import base64
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import aiohttp
from bs4 import BeautifulSoup

from .const import CONF_USERNAME, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)

LOGIN_URL = "https://www.dsbmobile.de/Login.aspx"
WEB_API_URL = "https://www.dsbmobile.de/jhw-1fd98248-440c-4283-bef6-dc82fe769b61.ashx/GetData"


@dataclass
class SubstitutionEntry:
    """A single substitution plan entry."""

    day: str
    art: str
    class_name: str
    lesson: str
    subject: str
    room: str
    vertr_von: str
    nach: str
    text: str
    raw_text: str


@dataclass
class PlanInfo:
    """Metadata about a plan."""

    title: str
    date: str
    url: str
    is_html: bool = False


class DSBMobileAPI:
    """Client for DSBmobile using the Web API."""

    def __init__(self, username: str, password: str, session: aiohttp.ClientSession) -> None:
        self._username = username
        self._password = password
        self._session = session
        self._logged_in = False
        self.last_plans: list[PlanInfo] = []

    async def _web_login(self) -> bool:
        """Login via the web form to get session cookies."""
        try:
            async with self._session.get(LOGIN_URL) as resp:
                html = await resp.text()

            soup = BeautifulSoup(html, "html.parser")
            vs = soup.find("input", {"name": "__VIEWSTATE"})
            vsg = soup.find("input", {"name": "__VIEWSTATEGENERATOR"})
            ev = soup.find("input", {"name": "__EVENTVALIDATION"})

            if not vs or not ev:
                _LOGGER.error("Login page missing form fields")
                return False

            form = {
                "__VIEWSTATE": vs["value"],
                "__VIEWSTATEGENERATOR": vsg["value"] if vsg else "",
                "__EVENTVALIDATION": ev["value"],
                "txtUser": self._username,
                "txtPass": self._password,
                "ctl03": "Anmelden",
            }

            async with self._session.post(LOGIN_URL, data=form, allow_redirects=True) as resp:
                text = await resp.text()
                if "default.aspx" in str(resp.url) or "<title>DSBmobile</title>" in text:
                    _LOGGER.debug("Web login successful")
                    self._logged_in = True
                    return True
                _LOGGER.error("Web login failed — still on login page")
                return False

        except aiohttp.ClientError as err:
            _LOGGER.error("Web login error: %s", err)
            return False

    async def authenticate(self) -> bool:
        """Authenticate via web login + Web API call."""
        if not await self._web_login():
            return False

        # Test the API call
        data = await self._call_web_api()
        return data is not None and data.get("Resultcode") == 0

    async def _call_web_api(self) -> dict | None:
        """Call the Web API GetData endpoint."""
        if not self._logged_in:
            if not await self._web_login():
                return None

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload = {
            "UserId": self._username,
            "UserPw": self._password,
            "AppVersion": "2.3",
            "Language": "de",
            "OsVersion": "Mozilla/5.0",
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

        try:
            async with self._session.post(
                WEB_API_URL,
                json=body,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Referer": "https://www.dsbmobile.de/default.aspx",
                },
            ) as resp:
                if resp.status != 200:
                    _LOGGER.error("Web API returned status %s", resp.status)
                    return None

                result = await resp.json(content_type=None)
                resp_data = result.get("d", "")
                if not resp_data:
                    _LOGGER.error("Web API returned no data: %s", result)
                    return None

                decoded = gzip.decompress(base64.b64decode(resp_data))
                data = json.loads(decoded)

                if data.get("Resultcode") != 0:
                    _LOGGER.error("Web API error: %s", data.get("ResultStatusInfo"))
                    return None

                _LOGGER.debug("Web API call successful")
                return data

        except (aiohttp.ClientError, Exception) as err:
            _LOGGER.error("Web API call failed: %s", err)
            return None

    async def get_plans(self) -> list[PlanInfo]:
        """Extract plan URLs from the Web API response."""
        data = await self._call_web_api()
        if not data:
            return []

        plans: list[PlanInfo] = []

        for menu in data.get("ResultMenuItems", []):
            for section in menu.get("Childs", []):
                method = section.get("MethodName", "")
                root = section.get("Root", {})

                _LOGGER.debug("Section: %s (method=%s)", section.get("Title"), method)

                for item in root.get("Childs", []):
                    title = item.get("Title", "")
                    date = item.get("Date", "")

                    for child in item.get("Childs", []):
                        detail = child.get("Detail", "")
                        if not detail:
                            continue

                        is_html = detail.lower().endswith((".htm", ".html"))
                        plans.append(PlanInfo(
                            title=child.get("Title", title),
                            date=date,
                            url=detail,
                            is_html=is_html,
                        ))
                        _LOGGER.debug(
                            "  Found: %s (html=%s) -> %s",
                            child.get("Title", ""), is_html, detail[:80],
                        )

        self.last_plans = plans
        _LOGGER.debug("Total plans found: %d", len(plans))
        return plans

    async def get_substitutions(self, class_filter: str = "") -> list[SubstitutionEntry]:
        """Fetch and parse HTML substitution plans."""
        plans = await self.get_plans()
        entries: list[SubstitutionEntry] = []

        for plan in plans:
            if not plan.is_html:
                _LOGGER.debug("Skipping non-HTML plan: %s -> %s", plan.title, plan.url[:60])
                continue

            try:
                async with self._session.get(plan.url) as resp:
                    if resp.status != 200:
                        _LOGGER.warning("Plan %s returned status %s", plan.url, resp.status)
                        continue

                    content_type = resp.headers.get("Content-Type", "")
                    if "image" in content_type:
                        _LOGGER.debug("Skipping image content: %s", plan.url)
                        plan.is_html = False
                        continue

                    # Read raw bytes and detect encoding
                    raw = await resp.read()
                    # Try iso-8859-1 first (common for Untis), then utf-8
                    html = None
                    for encoding in ("iso-8859-1", "utf-8", "latin-1", "cp1252"):
                        try:
                            html = raw.decode(encoding)
                            break
                        except (UnicodeDecodeError, LookupError):
                            continue

                    if html is None:
                        _LOGGER.warning("Could not decode plan %s with any encoding", plan.title)
                        continue

                    _LOGGER.debug("Fetched HTML plan: %s (%d chars)", plan.title, len(html))

            except aiohttp.ClientError as err:
                _LOGGER.warning("Failed to fetch %s: %s", plan.url, err)
                continue

            entries.extend(self._parse_plan_html(html, class_filter))

        _LOGGER.debug("Total substitution entries: %d (filter='%s')", len(entries), class_filter)
        return entries

    @staticmethod
    def _parse_plan_html(html: str, class_filter: str) -> list[SubstitutionEntry]:
        """Parse Untis substitution plan HTML.

        Untis format:
        - Day header: div.mon_title (e.g. "16.4.2026 Donnerstag")
        - Table: table.mon_list
        - Columns: Art | Klasse(n) | Stunde | (Fach) | Raum | Vertr. von | (Le.) nach | Text
        - Header row uses <th>, data rows use <td>
        - <s> tags indicate old/cancelled values (converted to ~~strikethrough~~)
        """
        soup = BeautifulSoup(html, "html.parser")
        results: list[SubstitutionEntry] = []
        current_day = ""

        # Find day headers: div.mon_title
        day_divs = {id(div): div.get_text(" ", strip=True)
                    for div in soup.find_all("div", class_="mon_title")}

        # Walk through all elements in order
        for el in soup.find_all(["div", "tr"]):
            # Day header
            if el.name == "div" and id(el) in day_divs:
                current_day = day_divs[id(el)]
                continue

            if el.name != "tr":
                continue

            # Skip header rows (th cells)
            if el.find("th"):
                continue

            cells = el.find_all("td")
            if not cells:
                continue

            raw = el.get_text(" ", strip=True)
            if not raw:
                continue

            if class_filter and class_filter.lower() not in raw.lower():
                continue

            # Untis columns: Art | Klasse(n) | Stunde | (Fach) | Raum | Vertr. von | (Le.) nach | Text
            c = [DSBMobileAPI._cell_text(cell) for cell in cells]
            entry = SubstitutionEntry(
                day=current_day,
                art=c[0] if len(c) > 0 else "",
                class_name=c[1] if len(c) > 1 else "",
                lesson=c[2] if len(c) > 2 else "",
                subject=c[3] if len(c) > 3 else "",
                room=c[4] if len(c) > 4 else "",
                vertr_von=c[5] if len(c) > 5 else "",
                nach=c[6] if len(c) > 6 else "",
                text=c[7] if len(c) > 7 else "",
                raw_text=raw,
            )
            results.append(entry)

        return results

    @staticmethod
    def _cell_text(cell) -> str:
        """Extract text from a table cell, converting <s> to ~~strikethrough~~."""
        parts = []
        for child in cell.children:
            if hasattr(child, "name") and child.name == "s":
                text = child.get_text(strip=True)
                if text:
                    parts.append(f"~~{text}~~")
            else:
                text = child.get_text(strip=True) if hasattr(child, "get_text") else str(child).strip()
                if text and text != "\xa0":
                    parts.append(text)
        return " ".join(parts) if parts else ""

