"""Config flow for DSBmobile integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_CLASS
from .dsb_api import DSBMobileAPI

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_CLASS, default=""): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input by trying to authenticate."""
    async with aiohttp.ClientSession() as session:
        api = DSBMobileAPI(data[CONF_USERNAME], data[CONF_PASSWORD], session)
        if not await api.authenticate():
            raise InvalidAuth
    return {"title": f"DSBmobile ({data[CONF_USERNAME]})"}


class DSBMobileConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DSBmobile."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class InvalidAuth(Exception):
    """Error to indicate invalid authentication."""
