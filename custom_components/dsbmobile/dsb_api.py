"""API client for DSBmobile using the Mobile API."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import aiohttp
from bs4 import BeautifulSoup

from .const import (
    DSB_AUTH_URL,
    DSB_TIMETABLES_URL,
    DSB_BUNDLE_ID,
    DSB_APP_VERSION,
    DSB_OS_VERSION,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class SubstitutionEntry:
    """A single substitution plan entry."""

    day: str
    class_name: str
    lesson: str
    subject: str
    substitute: str
    room: str
    info: str
    raw_text: str


class DSBMobileAPI:
    """Client for the DSBmobile Mobile API."""

    def __init__(self, username: str, password: str, session: aiohttp.ClientSession) -> None:
        self._username = username
        self._password = password
        self._session = session
        self._token: str | None = None

    async def authenticate(self) -> bool:
        """Authenticate and get a session token."""
        params = {
            "bundleid": DSB_BUNDLE_ID,
            "appversion": DSB_APP_VERSION,
            "osversion": DSB_OS_VERSION,
            "pushid": "",
            "user": self._username,
            "password": self._password,
        }
        try:
            async with self._session.get(DSB_AUTH_URL, params=params) as resp:
                if resp.status != 200:
                    return False
                token = await resp.text()
                token = token.strip().strip('"')
                if not token:
                    return False
                self._token = token
                return True
        except aiohttp.ClientError as err:
            _LOGGER.error("Authentication failed: %s", err)
            return False

    async def get_plans(self) -> list[dict]:
        """Fetch timetable plan URLs and metadata."""
        if not self._token:
            if not await self.authenticate():
                return []

        params = {"authid": self._token}
        try:
            async with self._session.get(DSB_TIMETABLES_URL, params=params) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, ValueError) as err:
            _LOGGER.error("Failed to fetch plans: %s", err)
            return []

        plans = []
        for item in data or []:
            for child in item.get("Childs", []):
                detail = child.get("Detail", "")
                if detail:
                    plans.append({
                        "title": item.get("Title", ""),
                        "date": item.get("Date", ""),
                        "url": detail,
                    })
        return plans

    async def get_substitutions(self, class_filter: str = "") -> list[SubstitutionEntry]:
        """Fetch and parse substitution entries, optionally filtered by class."""
        plans = await self.get_plans()
        entries: list[SubstitutionEntry] = []

        for plan in plans:
            url = plan["url"]
            try:
                async with self._session.get(url) as resp:
                    if resp.status != 200:
                        continue
                    html = await resp.text()
            except aiohttp.ClientError as err:
                _LOGGER.warning("Failed to fetch plan HTML from %s: %s", url, err)
                continue

            entries.extend(self._parse_plan_html(html, class_filter))

        return entries

    @staticmethod
    def _parse_plan_html(html: str, class_filter: str) -> list[SubstitutionEntry]:
        """Parse the substitution plan HTML (Untis format)."""
        soup = BeautifulSoup(html, "html.parser")
        results: list[SubstitutionEntry] = []
        current_day = ""

        for el in soup.find_all(["div", "tr"]):
            # Day headers
            if el.name == "div" and "dayHeader" in (el.get("class") or []):
                current_day = el.get_text(" ", strip=True)
                continue

            if el.name != "tr":
                continue

            cells = el.find_all("td")
            if not cells:
                continue

            raw = el.get_text(" ", strip=True)
            if not raw:
                continue

            # Apply class filter
            if class_filter and class_filter.lower() not in raw.lower():
                continue

            # Parse cells: typical Untis columns are
            # Klasse | Stunde | Fach | Vertreter | Raum | Hinweis
            cell_texts = [c.get_text(strip=True) for c in cells]
            entry = SubstitutionEntry(
                day=current_day,
                class_name=cell_texts[0] if len(cell_texts) > 0 else "",
                lesson=cell_texts[1] if len(cell_texts) > 1 else "",
                subject=cell_texts[2] if len(cell_texts) > 2 else "",
                substitute=cell_texts[3] if len(cell_texts) > 3 else "",
                room=cell_texts[4] if len(cell_texts) > 4 else "",
                info=cell_texts[5] if len(cell_texts) > 5 else "",
                raw_text=raw,
            )
            results.append(entry)

        return results
