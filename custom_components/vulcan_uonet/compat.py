"""Warstwa zgodności podpisywania zapytań Vulcan UONET+."""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

_PATCH_APPLIED = False


def _install_pyopenssl_sign_compatibility() -> None:
    """Przywróć crypto.sign usunięte z nowych wersji pyOpenSSL."""

    from OpenSSL import crypto
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    if hasattr(crypto, "sign"):
        _LOGGER.warning(
            "Vulcan UONET+: OpenSSL.crypto.sign jest dostępne — "
            "warstwa zgodności nie jest potrzebna"
        )
        return

    def compatibility_sign(
        private_key: Any,
        data: bytes | str,
        digest: str,
    ) -> bytes:
        """Podpisz dane tak jak dawne OpenSSL.crypto.sign."""

        if isinstance(data, str):
            data = data.encode("utf-8")

        digest_name = str(digest).upper().replace("-", "")

        hash_algorithms = {
            "SHA1": hashes.SHA1,
            "RSASHA1": hashes.SHA1,
            "SHA224": hashes.SHA224,
            "RSASHA224": hashes.SHA224,
            "SHA256": hashes.SHA256,
            "RSASHA256": hashes.SHA256,
            "SHA384": hashes.SHA384,
            "RSASHA384": hashes.SHA384,
            "SHA512": hashes.SHA512,
            "RSASHA512": hashes.SHA512,
        }

        hash_class = hash_algorithms.get(digest_name)

        if hash_class is None:
            raise ValueError(
                f"Nieobsługiwany algorytm podpisu: {digest}"
            )

        private_key_pem = crypto.dump_privatekey(
            crypto.FILETYPE_PEM,
            private_key,
        )

        cryptography_private_key = (
            serialization.load_pem_private_key(
                private_key_pem,
                password=None,
            )
        )

        return cryptography_private_key.sign(
            data,
            padding.PKCS1v15(),
            hash_class(),
        )

    crypto.sign = compatibility_sign

    _LOGGER.warning(
        "Vulcan UONET+: dodano zgodność OpenSSL.crypto.sign "
        "dla pyOpenSSL 26"
    )


def apply_signer_patch() -> None:
    """Podmień signer vulcan-api na uonet-request-signer-hebe."""

    global _PATCH_APPLIED

    if _PATCH_APPLIED:
        return

    try:
        _install_pyopenssl_sign_compatibility()

        import vulcan._api as vulcan_api
        import vulcan._keystore as vulcan_keystore

        from uonet_request_signer_hebe import (
            generate_key_pair,
            get_signature_values,
        )

    except Exception as err:
        _LOGGER.exception(
            "Vulcan UONET+: nie udało się aktywować warstwy "
            "zgodności signera. Typ=%s, treść=%r",
            type(err).__name__,
            err,
        )
        raise

    vulcan_api.get_signature_values = get_signature_values
    vulcan_keystore.generate_key_pair = generate_key_pair

    _PATCH_APPLIED = True

    _LOGGER.warning(
        "Vulcan UONET+: aktywowano signer "
        "uonet_request_signer_hebe"
    )
