"""Sensor platform for DSBmobile Vertretungsplan."""
from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_CLASS, DEFAULT_SCAN_INTERVAL
from .dsb_api import DSBMobileAPI, SubstitutionEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DSBmobile sensors from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    class_input = entry.data.get(CONF_CLASS, "")

    jar = aiohttp.CookieJar()
    web_session = aiohttp.ClientSession(cookie_jar=jar)
    api = DSBMobileAPI(username, password, web_session)

    # Store session for cleanup on unload
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"session": web_session}

    # Fetch ALL entries (no filter) — each sensor filters locally
    coordinator = DSBDataUpdateCoordinator(hass, api)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        _LOGGER.warning("First data fetch failed, will retry in %s seconds", DEFAULT_SCAN_INTERVAL)
        coordinator.data = []

    # Parse comma-separated classes, create one sensor per class
    classes = [c.strip() for c in class_input.split(",") if c.strip()]

    sensors: list[DSBVertretungsplanSensor] = []
    if classes:
        for cls in classes:
            sensors.append(DSBVertretungsplanSensor(coordinator, entry, cls))
    else:
        # No filter — one sensor for all entries
        sensors.append(DSBVertretungsplanSensor(coordinator, entry, ""))

    async_add_entities(sensors)


class DSBDataUpdateCoordinator(DataUpdateCoordinator[list[SubstitutionEntry]]):
    """Coordinator to fetch ALL DSBmobile entries (unfiltered)."""

    def __init__(self, hass: HomeAssistant, api: DSBMobileAPI) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api

    async def _async_update_data(self) -> list[SubstitutionEntry]:
        """Fetch all substitution data without class filter."""
        try:
            entries = await self.api.get_substitutions("")
            _LOGGER.debug("Fetched %d total substitution entries", len(entries))
            return entries
        except Exception as err:
            _LOGGER.error("Error fetching DSBmobile data: %s", err)
            if self.data is not None:
                return self.data
            return []


class DSBVertretungsplanSensor(CoordinatorEntity[DSBDataUpdateCoordinator], SensorEntity):
    """Sensor showing substitution entries, optionally filtered by class."""

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
        self._attr_unique_id = f"{entry.entry_id}_vertretungsplan_{class_filter or 'all'}"

    def _filtered_entries(self) -> list[SubstitutionEntry]:
        """Return entries filtered by this sensor's class."""
        if not self.coordinator.data:
            return []
        if not self._class_filter:
            return self.coordinator.data
        return [
            e for e in self.coordinator.data
            if self._class_filter.lower() in e.raw_text.lower()
        ]

    @property
    def native_value(self) -> int:
        """Return the number of substitution entries."""
        return len(self._filtered_entries())

    @property
    def extra_state_attributes(self) -> dict:
        """Return detailed substitution entries as attributes."""
        filtered = self._filtered_entries()
        entries = [
            {
                "day": e.day,
                "art": e.art,
                "class": e.class_name,
                "lesson": e.lesson,
                "subject": e.subject,
                "room": e.room,
                "vertr_von": e.vertr_von,
                "nach": e.nach,
                "text": e.text,
            }
            for e in filtered
        ]

        other_plans = [
            {"title": p.title, "date": p.date, "url": p.url}
            for p in self.coordinator.api.last_plans
            if not p.is_html
        ]

        return {
            "class_filter": self._class_filter,
            "count": len(entries),
            "entries": entries,
            "other_plans": other_plans,
        }
