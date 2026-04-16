"""Sensor platform for DSBmobile Vertretungsplan."""
from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_CLASS, DEFAULT_SCAN_INTERVAL
from .dsb_api import DSBMobileAPI, SubstitutionEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DSBmobile sensor from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    class_filter = entry.data.get(CONF_CLASS, "")

    session = async_get_clientsession(hass)
    # Web API needs cookie jar for session management
    jar = aiohttp.CookieJar()
    web_session = aiohttp.ClientSession(cookie_jar=jar)
    api = DSBMobileAPI(username, password, web_session)

    coordinator = DSBDataUpdateCoordinator(hass, api, class_filter)

    # Don't fail setup if first fetch fails — sensor will show "unavailable"
    # and retry on next update cycle
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        _LOGGER.warning("First data fetch failed, sensor will retry in %s seconds", DEFAULT_SCAN_INTERVAL)
        coordinator.data = []

    async_add_entities([DSBVertretungsplanSensor(coordinator, entry, class_filter)])


class DSBDataUpdateCoordinator(DataUpdateCoordinator[list[SubstitutionEntry]]):
    """Coordinator to fetch DSBmobile data."""

    def __init__(
        self, hass: HomeAssistant, api: DSBMobileAPI, class_filter: str
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        self.class_filter = class_filter

    async def _async_update_data(self) -> list[SubstitutionEntry]:
        """Fetch data from DSBmobile."""
        try:
            entries = await self.api.get_substitutions(self.class_filter)
            _LOGGER.debug("Fetched %d substitution entries", len(entries))
            return entries
        except Exception as err:
            _LOGGER.error("Error fetching DSBmobile data: %s", err)
            # Return previous data if available, otherwise empty list
            if self.data is not None:
                return self.data
            return []


class DSBVertretungsplanSensor(CoordinatorEntity[DSBDataUpdateCoordinator], SensorEntity):
    """Sensor showing the number of substitution entries."""

    _attr_icon = "mdi:school"

    def __init__(
        self,
        coordinator: DSBDataUpdateCoordinator,
        entry: ConfigEntry,
        class_filter: str,
    ) -> None:
        super().__init__(coordinator)
        self._class_filter = class_filter
        suffix = f" {class_filter}" if class_filter else ""
        self._attr_name = f"Vertretungsplan{suffix}"
        self._attr_unique_id = f"{entry.entry_id}_vertretungsplan"

    @property
    def native_value(self) -> int:
        """Return the number of substitution entries."""
        if self.coordinator.data is None:
            return 0
        return len(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict:
        """Return detailed substitution entries as attributes."""
        entries = []
        if self.coordinator.data:
            for e in self.coordinator.data:
                entries.append({
                    "day": e.day,
                    "class": e.class_name,
                    "lesson": e.lesson,
                    "subject": e.subject,
                    "substitute": e.substitute,
                    "room": e.room,
                    "info": e.info,
                })

        # Collect non-HTML plan URLs (images, documents)
        other_plans = []
        for plan in self.coordinator.api.last_plans:
            if not plan.is_html:
                other_plans.append({
                    "title": plan.title,
                    "date": plan.date,
                    "url": plan.url,
                })

        return {
            "class_filter": self._class_filter,
            "count": len(entries),
            "entries": entries,
            "other_plans": other_plans,
        }
