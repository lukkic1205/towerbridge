"""Integracja Vulcan UONET+ dla Home Assistant."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from vulcan import Account, Keystore, Vulcan

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .calendar_sync import async_sync_exam_calendar
from .compat import apply_signer_patch
from .coordinator import VulcanUonetCoordinator
from .exam_compat import apply_exam_fetch_patch
from .frontend import async_register_frontend

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


@dataclass
class VulcanUonetRuntimeData:
    """Dane integracji przechowywane podczas działania."""

    account: Account
    keystore: Keystore
    client: Vulcan
    coordinator: VulcanUonetCoordinator


type VulcanUonetConfigEntry = ConfigEntry[VulcanUonetRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VulcanUonetConfigEntry,
) -> bool:
    """Uruchom integrację z wpisu konfiguracji."""

    _LOGGER.warning(
        "Vulcan UONET+: rozpoczynam uruchamianie wpisu %s",
        entry.title,
    )

    apply_signer_patch()
    apply_exam_fetch_patch()

    # Udostępnienie plików frontendowych integracji.
    await async_register_frontend(hass)

    account_data = entry.data["account"]
    keystore_data = entry.data["keystore"]

    account = Account.load(account_data)
    keystore = Keystore.load(keystore_data)

    _LOGGER.warning(
        "Vulcan UONET+: RestURL konta: %s",
        account.rest_url,
    )

    session = async_get_clientsession(hass)

    client = Vulcan(
        keystore=keystore,
        account=account,
        session=session,
    )

    coordinator = VulcanUonetCoordinator(
        hass=hass,
        client=client,
    )

    try:
        await coordinator.async_config_entry_first_refresh()

    except Exception:
        _LOGGER.exception(
            "Vulcan UONET+: pierwsze pobranie danych nie powiodło się"
        )
        raise

    entry.runtime_data = VulcanUonetRuntimeData(
        account=account,
        keystore=keystore,
        client=client,
        coordinator=coordinator,
    )

    await async_sync_exam_calendar(
        hass,
        coordinator.data,
    )

    def _schedule_calendar_sync() -> None:
        hass.async_create_task(
            async_sync_exam_calendar(
                hass,
                coordinator.data,
            )
        )

    entry.async_on_unload(
        coordinator.async_add_listener(
            _schedule_calendar_sync
        )
    )

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    _LOGGER.warning(
        "Vulcan UONET+: integracja została uruchomiona poprawnie"
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: VulcanUonetConfigEntry,
) -> bool:
    """Wyładuj integrację."""

    return await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )
