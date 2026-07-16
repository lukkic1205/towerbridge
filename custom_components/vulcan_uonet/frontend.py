from __future__ import annotations

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

DOMAIN = "vulcan_uonet"

FRONTEND_DIR = Path(__file__).parent / "frontend"
FRONTEND_URL = "/vulcan_uonet"
FRONTEND_VERSION = "1.0.0"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Udostępnij pliki frontendowe integracji Vulcan UONET+."""

    registration_key = f"{DOMAIN}_frontend_registered"

    if hass.data.get(registration_key):
        return

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                FRONTEND_URL,
                str(FRONTEND_DIR),
                cache_headers=False,
            )
        ]
    )

    hass.data[registration_key] = True
