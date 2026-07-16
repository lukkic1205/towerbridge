"""Konfiguracja integracji Vulcan UONET+."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DEVICE_MODEL,
    CONF_PIN,
    CONF_SYMBOL,
    CONF_TOKEN,
    DEFAULT_DEVICE_MODEL,
    DEFAULT_SYMBOL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class VulcanUonetConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Obsługa konfiguracji Vulcan UONET+."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Wyświetl formularz i zarejestruj urządzenie."""

        errors: dict[str, str] = {}

        if user_input is not None:
            token = str(user_input.get(CONF_TOKEN, "")).strip()
            symbol = str(user_input.get(CONF_SYMBOL, "")).strip().lower()
            pin = str(user_input.get(CONF_PIN, "")).strip()
            device_model = str(
                user_input.get(
                    CONF_DEVICE_MODEL,
                    DEFAULT_DEVICE_MODEL,
                )
            ).strip()

            if not token:
                errors[CONF_TOKEN] = "required"

            if not symbol:
                errors[CONF_SYMBOL] = "required"

            if not pin:
                errors[CONF_PIN] = "required"

            if not device_model:
                errors[CONF_DEVICE_MODEL] = "required"

            if not errors:
                try:
                    # Importy są celowo tutaj, a nie na początku pliku.
                    # Dzięki temu formularz może się otworzyć nawet wtedy,
                    # gdy któraś biblioteka zewnętrzna ma problem.
                    from vulcan import Account, Keystore, Vulcan

                    from .compat import apply_signer_patch

                    _LOGGER.warning(
                        "Vulcan UONET+: rozpoczynam rejestrację dla symbolu %s",
                        symbol,
                    )

                    apply_signer_patch()

                    keystore = await Keystore.create(
                        device_model=device_model,
                    )

                    _LOGGER.warning(
                        "Vulcan UONET+: utworzono keystore, fingerprint=%s",
                        keystore.fingerprint,
                    )

                    account = await Account.register(
                        keystore=keystore,
                        token=token,
                        symbol=symbol,
                        pin=pin,
                    )

                    _LOGGER.warning(
                        "Vulcan UONET+: rejestracja zakończona, RestURL=%s",
                        account.rest_url,
                    )

                    session = async_get_clientsession(self.hass)

                    client = Vulcan(
                        keystore=keystore,
                        account=account,
                        session=session,
                    )

                    students = await client.get_students()

                    if not students:
                        errors["base"] = "no_students"
                    else:
                        _LOGGER.warning(
                            "Vulcan UONET+: test API poprawny, uczniowie=%s",
                            len(students),
                        )

                except Exception as err:
                    error_name = type(err).__name__

                    _LOGGER.exception(
                        "Vulcan UONET+: błąd konfiguracji. Typ=%s, treść=%r",
                        error_name,
                        err,
                    )

                    error_map = {
                        "InvalidTokenException": "invalid_token",
                        "InvalidPINException": "invalid_pin",
                        "ExpiredTokenException": "expired_token",
                        "InvalidSymbolException": "invalid_symbol",
                        "UnauthorizedCertificateException": (
                            "invalid_certificate"
                        ),
                        "ClientConnectionError": "cannot_connect",
                        "ClientConnectorError": "cannot_connect",
                        "TimeoutError": "cannot_connect",
                    }

                    errors["base"] = error_map.get(
                        error_name,
                        "unknown",
                    )

                else:
                    if not errors:
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

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TOKEN,
                    default=(
                        user_input.get(CONF_TOKEN, "")
                        if user_input
                        else ""
                    ),
                ): str,
                vol.Required(
                    CONF_SYMBOL,
                    default=(
                        user_input.get(
                            CONF_SYMBOL,
                            DEFAULT_SYMBOL,
                        )
                        if user_input
                        else DEFAULT_SYMBOL
                    ),
                ): str,
                vol.Required(
                    CONF_PIN,
                    default=(
                        user_input.get(CONF_PIN, "")
                        if user_input
                        else ""
                    ),
                ): str,
                vol.Optional(
                    CONF_DEVICE_MODEL,
                    default=(
                        user_input.get(
                            CONF_DEVICE_MODEL,
                            DEFAULT_DEVICE_MODEL,
                        )
                        if user_input
                        else DEFAULT_DEVICE_MODEL
                    ),
                ): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
