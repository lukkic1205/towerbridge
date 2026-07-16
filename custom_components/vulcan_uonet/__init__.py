"""Integracja Vulcan UONET+ dla Home Assistant."""

from __future__ import annotations

import json
from dataclasses import dataclass

from vulcan import Account, Keystore, Vulcan

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import VulcanUonetCoordinator

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

    account_data = entry.data["account"]
    keystore_data = entry.data["keystore"]

    account = Account.load(
        json.dumps(
            account_data,
            ensure_ascii=False,
        )
    )

    keystore = Keystore.load(
        json.dumps(
            keystore_data,
            ensure_ascii=False,
        )
    )

    client = Vulcan(
        keystore=keystore,
        account=account,
    )

    coordinator = VulcanUonetCoordinator(
        hass=hass,
        client=client,
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = VulcanUonetRuntimeData(
        account=account,
        keystore=keystore,
        client=client,
        coordinator=coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: VulcanUonetConfigEntry,
) -> bool:
    """Wyładuj integrację."""

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )

    if unload_ok:
        await entry.runtime_data.client.close()

    return unload_ok
