"""Konfiguracja integracji Vulcan UONET+."""

from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol
from vulcan import Account, Keystore

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
            token = user_input[CONF_TOKEN].strip()
            symbol = user_input[CONF_SYMBOL].strip().lower()
            pin = user_input[CONF_PIN].strip()
            device_model = user_input[CONF_DEVICE_MODEL].strip()

            try:
                keystore = await Keystore.create(
                    device_model=device_model,
                )

                account = await Account.register(
                    keystore=keystore,
                    token=token,
                    symbol=symbol,
                    pin=pin,
                )

            except asyncio.TimeoutError:
                errors["base"] = "cannot_connect"

            except Exception:
                errors["base"] = "invalid_auth"

            else:
                await self.async_set_unique_id(
                    f"{symbol}_{keystore.fingerprint}"
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Vulcan UONET+ – {symbol}",
                    data={
                        CONF_SYMBOL: symbol,
                        CONF_DEVICE_MODEL: device_model,
                        "account": account.as_dict,
                        "keystore": keystore.as_dict,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_TOKEN): str,
                vol.Required(
                    CONF_SYMBOL,
                    default=DEFAULT_SYMBOL,
                ): str,
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
