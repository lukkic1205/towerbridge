"""Konfiguracja integracji Vulcan UONET+."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_DEVICE_MODEL,
    CONF_PIN,
    CONF_SYMBOL,
    CONF_TOKEN,
    DEFAULT_DEVICE_MODEL,
    DEFAULT_SYMBOL,
    DOMAIN,
)


class VulcanUonetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Obsługa konfiguracji Vulcan UONET+."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Obsłuż konfigurację rozpoczętą przez użytkownika."""

        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_SYMBOL].strip().lower()}_"
                f"{user_input[CONF_DEVICE_MODEL].strip().lower()}"
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Vulcan UONET+ – {user_input[CONF_SYMBOL]}",
                data={
                    CONF_TOKEN: user_input[CONF_TOKEN].strip(),
                    CONF_SYMBOL: user_input[CONF_SYMBOL].strip().lower(),
                    CONF_PIN: user_input[CONF_PIN].strip(),
                    CONF_DEVICE_MODEL: user_input[CONF_DEVICE_MODEL].strip(),
                },
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_TOKEN): str,
                vol.Required(CONF_SYMBOL, default=DEFAULT_SYMBOL): str,
                vol.Required(CONF_PIN): str,
                vol.Optional(
                    CONF_DEVICE_MODEL,
                    default=DEFAULT_DEVICE_MODEL,
                ): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
