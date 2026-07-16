"""Warstwa zgodności podpisywania zapytań Vulcan UONET+."""

from __future__ import annotations

import logging

import vulcan._api as vulcan_api
import vulcan._keystore as vulcan_keystore
from uonet_request_signer_hebe import (
    generate_key_pair,
    get_signature_values,
)

_LOGGER = logging.getLogger(__name__)

_PATCH_APPLIED = False


def apply_signer_patch() -> None:
    """Podmień signer w vulcan-api na uonet-request-signer-hebe."""

    global _PATCH_APPLIED

    if _PATCH_APPLIED:
        return

    vulcan_api.get_signature_values = get_signature_values
    vulcan_keystore.generate_key_pair = generate_key_pair

    _PATCH_APPLIED = True

    _LOGGER.warning(
        "Vulcan UONET+: aktywowano signer uonet_request_signer_hebe"
    )
