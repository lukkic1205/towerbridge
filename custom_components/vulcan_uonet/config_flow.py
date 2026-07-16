"""Konfiguracja integracji Vulcan UONET+."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol
from vulcan import Account, Keystore, Vulcan
from vulcan._exceptions import (
    ExpiredTokenException,
    InvalidPINException,
    InvalidSymbolException,
    InvalidTokenException,
    UnauthorizedCertificateException,
    VulcanAPIException,
)

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .compat import apply_signer_patch
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
    ) -> FlowResult:
        """Obsłuż formularz konfiguracji."""

        errors: dict[str, str] = {}

        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            symbol = user_input[CONF_SYMBOL].strip().lower()
            pin = user_input[CONF_PIN].strip()
            device_model = user_input[
                CONF_DEVICE_MODEL
            ].strip()

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
                    _LOGGER.warning(
                        "Vulcan UONET+: aktywuję signer "
                        "uonet_request_signer_hebe"
                    )

                    apply_signer_patch()

                    _LOGGER.warning(
                        "Vulcan UONET+: tworzę keystore X.509 "
                        "dla urządzenia %s",
                        device_model,
                    )

                    keystore = await Keystore.create(
                        device_model=device_model,
                    )

                    _LOGGER.warning(
                        "Vulcan UONET+: rejestruję urządzenie "
                        "dla symbolu %s",
                        symbol,
                    )

                    account = await Account.register(
                        keystore=keystore,
                        token=token,
                        symbol=symbol,
                        pin=pin,
                    )

                    _LOGGER.warning(
                        "Vulcan UONET+: rejestracja zakończona; "
                        "RestURL=%s, fingerprint=%s",
                        account.rest_url,
                        keystore.fingerprint,
                    )

                    # Od razu sprawdzamy, czy nowo utworzone konto
                    # naprawdę pozwala pobrać uczniów.
                    session = async_get_clientsession(self.hass)

                    client = Vulcan(
                        keystore=keystore,
                        account=account,
                        session=session,
                    )

                    students = await client.get_students()

                    if not students:
                        _LOGGER.error(
                            "Vulcan UONET+: rejestracja powiodła się, "
                            "ale konto nie zawiera uczniów"
                        )
                        errors["base"] = "no_students"

                    else:
                        _LOGGER.warning(
                            "Vulcan UONET+: test API zakończony "
                            "poprawnie; liczba uczniów: %s",
                            len(students),
                        )

                except InvalidTokenException:
                    _LOGGER.exception(
                        "Vulcan UONET+: nieprawidłowy token"
                    )
                    errors["base"] = "invalid_token"

                except InvalidPINException:
                    _LOGGER.exception(
                        "Vulcan UONET+: nieprawidłowy PIN"
                    )
                    errors["base"] = "invalid_pin"

                except ExpiredTokenException:
                    _LOGGER.exception(
                        "Vulcan UONET+: token wygasł"
                    )
                    errors["base"] = "expired_token"

                except InvalidSymbolException:
                    _LOGGER.exception(
                        "Vulcan UONET+: nieprawidłowy symbol jednostki"
                    )
                    errors["base"] = "invalid_symbol"

                except UnauthorizedCertificateException:
                    _LOGGER.exception(
                        "Vulcan UONET+: certyfikat urządzenia "
                        "nie został zaakceptowany"
                    )
                    errors["base"] = "invalid_certificate"

                except (
                    asyncio.TimeoutError,
                    aiohttp.ClientError,
                ):
                    _LOGGER.exception(
                        "Vulcan UONET+: błąd połączenia"
                    )
                    errors["base"] = "cannot_connect"

                except VulcanAPIException:
                    _LOGGER.exception(
                        "Vulcan UONET+: błąd API Vulcan"
                    )
                    errors["base"] = "api_error"

                except Exception:
                    _LOGGER.exception(
                        "Vulcan UONET+: nieoczekiwany błąd "
                        "podczas rejestracji"
                    )
                    errors["base"] = "unknown"

                else:
                    if not errors:
                        unique_id = (
                            f"{symbol}_"
                            f"{keystore.fingerprint}"
                        )

                        await self.async_set_unique_id(
                            unique_id
                        )
                        self._abort_if_unique_id_configured()

                        return self.async_create_entry(
                            title=(
                                f"Vulcan UONET+ – {symbol}"
                            ),
                            data={
                                CONF_SYMBOL: symbol,
                                CONF_DEVICE_MODEL: device_model,
                                "account": account.as_dict,
                                "keystore": keystore.as_dict,
                            },
                        )

        data_schema = vol.Schema(
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
            data_schema=data_schema,
            errors=errors,
        )
