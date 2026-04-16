"""API client for DSBmobile using the Mobile API."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

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

# ConType values from DSBmobile API
CONTYPE_CHILDS = 2   # Contains child items
CONTYPE_HTML = 4     # Detail is a link to an HTML page
CONTYPE_TEXT = 5     # Detail is plain text
CONTYPE_IMAGE = 6    # Detail is a link to a PNG/GIF image


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


@dataclass
class PlanInfo:
    """Metadata about a substitution plan."""

    title: str
    date: str
    url: str
    con_type: int
    image_urls: list[str] = field(default_factory=list)


class DSBMobileAPI:
    """Client for the DSBmobile Mobile API."""

    def __init__(self, username: str, password: str, session: aiohttp.ClientSession) -> None:
        self._username = username
        self._password = password
        self._session = session
        self._token: str | None = None
        self.last_plans: list[PlanInfo] = []

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
                    _LOGGER.error("Auth returned status %s", resp.status)
                    return False
                token = await resp.text()
                _LOGGER.debug("Auth response: %s", token[:50] if token else "(empty)")
                token = token.strip().strip('"')
                if not token:
                    _LOGGER.error("Auth returned empty token")
                    return False
                self._token = token
                _LOGGER.debug("Authenticated successfully, token: %s...", token[:8])
                return True
        except aiohttp.ClientError as err:
            _LOGGER.error("Authentication failed: %s", err)
            return False

    async def get_plans(self) -> list[PlanInfo]:
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

        _LOGGER.debug("Timetables response: %d items", len(data) if data else 0)
        plans: list[PlanInfo] = []

        for item in data or []:
            parent_type = item.get("ConType", 0)
            title = item.get("Title", "")
            date = item.get("Date", "")
            childs = item.get("Childs", [])

            _LOGGER.debug(
                "Plan item: title=%s, ConType=%s, childs=%d",
                title, parent_type, len(childs),
            )

            if parent_type == CONTYPE_CHILDS:
                # Parent with children — collect all child URLs
                image_urls = []
                html_url = ""
                child_type = 0

                for child in childs:
                    detail = child.get("Detail", "")
                    ct = child.get("ConType", 0)
                    _LOGGER.debug("  Child: ConType=%s, Detail=%s", ct, detail[:80] if detail else "")

                    if not detail:
                        continue

                    child_type = ct
                    if ct == CONTYPE_IMAGE:
                        image_urls.append(detail)
                    elif ct == CONTYPE_HTML:
                        html_url = detail

                if html_url:
                    plans.append(PlanInfo(
                        title=title, date=date, url=html_url,
                        con_type=CONTYPE_HTML,
                    ))
                elif image_urls:
                    plans.append(PlanInfo(
                        title=title, date=date, url=image_urls[0],
                        con_type=CONTYPE_IMAGE, image_urls=image_urls,
                    ))
            else:
                # Direct item
                detail = item.get("Detail", "")
                if detail:
                    plans.append(PlanInfo(
                        title=title, date=date, url=detail,
                        con_type=parent_type,
                    ))

        _LOGGER.debug("Found %d plans", len(plans))
        self.last_plans = plans
        return plans

    async def get_substitutions(self, class_filter: str = "") -> list[SubstitutionEntry]:
        """Fetch and parse substitution entries, optionally filtered by class."""
        plans = await self.get_plans()
        entries: list[SubstitutionEntry] = []

        for plan in plans:
            if plan.con_type == CONTYPE_IMAGE:
                _LOGGER.debug(
                    "Plan '%s' is image-based (%d images), skipping HTML parse",
                    plan.title, len(plan.image_urls),
                )
                continue

            # Also skip if URL looks like an image regardless of ConType
            url_lower = plan.url.lower()
            if url_lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp")):
                _LOGGER.debug("Plan '%s' URL ends with image extension, skipping: %s", plan.title, plan.url)
                # Reclassify as image plan so it shows up in attributes
                plan.con_type = CONTYPE_IMAGE
                plan.image_urls = [plan.url]
                continue

            try:
                async with self._session.get(plan.url) as resp:
                    if resp.status != 200:
                        continue

                    # Check Content-Type before reading as text
                    content_type = resp.headers.get("Content-Type", "")
                    _LOGGER.debug("Plan '%s' Content-Type: %s", plan.title, content_type)

                    if "image" in content_type:
                        _LOGGER.debug("Plan '%s' is an image (Content-Type), skipping", plan.title)
                        plan.con_type = CONTYPE_IMAGE
                        plan.image_urls = [plan.url]
                        continue

                    if "text/html" not in content_type and "text/plain" not in content_type:
                        _LOGGER.debug("Plan '%s' has unexpected Content-Type: %s, skipping", plan.title, content_type)
                        continue

                    html = await resp.text()
            except aiohttp.ClientError as err:
                _LOGGER.warning("Failed to fetch plan from %s: %s", plan.url, err)
                continue
            except UnicodeDecodeError as err:
                _LOGGER.warning("Plan '%s' is not text (decode error), treating as image: %s", plan.title, err)
                plan.con_type = CONTYPE_IMAGE
                plan.image_urls = [plan.url]
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

            if class_filter and class_filter.lower() not in raw.lower():
                continue

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
