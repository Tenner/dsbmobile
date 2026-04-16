"""Config flow for DSBmobile integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback

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
    jar = aiohttp.CookieJar()
    async with aiohttp.ClientSession(cookie_jar=jar) as session:
        api = DSBMobileAPI(data[CONF_USERNAME], data[CONF_PASSWORD], session)
        if not await api.authenticate():
            raise InvalidAuth
    return {"title": f"DSBmobile ({data[CONF_USERNAME]})"}


class DSBMobileConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DSBmobile."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow handler."""
        return DSBMobileOptionsFlow(config_entry)

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


class DSBMobileOptionsFlow(OptionsFlow):
    """Handle options for DSBmobile."""

    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # Update the config entry data with the new class
            new_data = {**self._config_entry.data, CONF_CLASS: user_input[CONF_CLASS]}
            self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            # Reload the integration so the sensor picks up the new class
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        current_class = self._config_entry.data.get(CONF_CLASS, "")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_CLASS, default=current_class): str,
                }
            ),
        )
