"""Konfiguracja integracji Vulcan UONET+."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries

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
            token = str(
                user_input.get(CONF_TOKEN, "")
            ).strip()

            symbol = str(
                user_input.get(CONF_SYMBOL, "")
            ).strip().lower()

            pin = str(
                user_input.get(CONF_PIN, "")
            ).strip()

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
                    # Importy celowo wewnątrz kroku.
                    from vulcan import Account, Keystore, Vulcan

                    from .compat import apply_signer_patch

                    _LOGGER.warning(
                        "Vulcan UONET+: rozpoczynam rejestrację. "
                        "Symbol=%s, urządzenie=%s",
                        symbol,
                        device_model,
                    )

                    apply_signer_patch()

                    _LOGGER.warning(
                        "Vulcan UONET+: tworzę keystore X.509"
                    )

                    keystore = await Keystore.create(
                        device_model=device_model,
                    )

                    fingerprint = getattr(
                        keystore,
                        "fingerprint",
                        None,
                    )

                    _LOGGER.warning(
                        "Vulcan UONET+: keystore został utworzony. "
                        "Fingerprint=%s",
                        fingerprint,
                    )

                    _LOGGER.warning(
                        "Vulcan UONET+: wysyłam rejestrację urządzenia"
                    )

                    account = await Account.register(
                        keystore,
                        token,
                        symbol,
                        pin,
                    )

                    rest_url = getattr(
                        account,
                        "rest_url",
                        None,
                    )

                    _LOGGER.warning(
                        "Vulcan UONET+: urządzenie zarejestrowane. "
                        "RestURL=%s",
                        rest_url,
                    )

                    _LOGGER.warning(
                        "Vulcan UONET+: rozpoczynam test get_students()"
                    )

                    # Dokładnie tak jak w działającym skrypcie:
                    # klient ma własną sesję i zostaje zamknięty
                    # przez async with.
                    client = Vulcan(
                        keystore,
                        account,
                    )

                    async with client:
                        students = await client.get_students()

                    _LOGGER.warning(
                        "Vulcan UONET+: klient testowy został zamknięty"
                    )

                    if not students:
                        _LOGGER.error(
                            "Vulcan UONET+: konto działa, "
                            "ale nie znaleziono uczniów"
                        )
                        errors["base"] = "no_students"

                    else:
                        _LOGGER.warning(
                            "Vulcan UONET+: test API zakończony "
                            "poprawnie. Liczba uczniów=%s",
                            len(students),
                        )

                except Exception as err:
                    error_name = type(err).__name__

                    _LOGGER.exception(
                        "Vulcan UONET+: konfiguracja zakończona błędem. "
                        "Typ=%s, treść=%r",
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
                        "ClientResponseError": "cannot_connect",
                        "ServerDisconnectedError": "cannot_connect",
                        "TimeoutError": "cannot_connect",
                        "ConnectionError": "cannot_connect",
                        "RuntimeError": "runtime_error",
                    }

                    errors["base"] = error_map.get(
                        error_name,
                        "unknown",
                    )

                else:
                    if not errors:
                        account_data = getattr(
                            account,
                            "as_dict",
                            None,
                        )

                        if callable(account_data):
                            account_data = account_data()

                        keystore_data = getattr(
                            keystore,
                            "as_dict",
                            None,
                        )

                        if callable(keystore_data):
                            keystore_data = keystore_data()

                        if not isinstance(account_data, dict):
                            raise ValueError(
                                "Account.as_dict nie zwrócił słownika"
                            )

                        if not isinstance(keystore_data, dict):
                            raise ValueError(
                                "Keystore.as_dict nie zwrócił słownika"
                            )

                        login_id = account_data.get(
                            "LoginId",
                            "",
                        )

                        unique_id = (
                            f"{symbol}_{login_id}_{fingerprint}"
                        )

                        await self.async_set_unique_id(
                            unique_id
                        )

                        self._abort_if_unique_id_configured()

                        return self.async_create_entry(
                            title=f"Vulcan UONET+ – {symbol}",
                            data={
                                CONF_SYMBOL: symbol,
                                CONF_DEVICE_MODEL: device_model,
                                "account": account_data,
                                "keystore": keystore_data,
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
