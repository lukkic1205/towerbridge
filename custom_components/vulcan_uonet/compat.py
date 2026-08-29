"""Warstwa zgodności podpisywania zapytań Vulcan UONET+."""

from __future__ import annotations

from datetime import datetime, timezone
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


def _legacy_datetime_payload(value: str) -> dict[str, Any]:
    """Zamień datę ISO na dawny obiekt DateTime vulcan-api."""

    normalized = str(value).strip()

    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    parsed = datetime.fromisoformat(normalized)

    if parsed.tzinfo is None:
        timestamp_value = parsed.replace(tzinfo=timezone.utc)
    else:
        timestamp_value = parsed.astimezone(timezone.utc)

    return {
        "Timestamp": int(timestamp_value.timestamp() * 1000),
        "Date": parsed.date().isoformat(),
        "Time": parsed.time().replace(
            tzinfo=None
        ).isoformat(timespec="seconds"),
    }


def _legacy_datetime_value(value: Any) -> Any:
    """Zachowaj stary słownik daty albo przekonwertuj wartość ISO."""

    if isinstance(value, dict):
        return value

    if isinstance(value, str) and value.strip():
        return _legacy_datetime_payload(value)

    return value


def _install_period_fields_compatibility() -> None:
    """Obsłuż nowe pola StartAt/EndAt zwracane przez Vulcan."""

    from vulcan._endpoints import STUDENT_LIST
    from vulcan.model import Student

    current_get = getattr(Student, "get")
    current_func = getattr(current_get, "__func__", current_get)

    if getattr(current_func, "_towerbridge_period_compat", False):
        return

    async def compatibility_get(cls, api, state, **kwargs):
        data = await api.get(STUDENT_LIST, **kwargs)
        fixed_fields = 0

        for student in data:
            for period in student.get("Periods") or []:
                if "Start" not in period and period.get("StartAt"):
                    period["Start"] = _legacy_datetime_payload(
                        period["StartAt"]
                    )
                    fixed_fields += 1

                if "End" not in period and period.get("EndAt"):
                    period["End"] = _legacy_datetime_payload(
                        period["EndAt"]
                    )
                    fixed_fields += 1

        if fixed_fields:
            _LOGGER.warning(
                "Vulcan UONET+: zgodność Period: "
                "przetłumaczono %s pól StartAt/EndAt",
                fixed_fields,
            )

        return [
            cls.load(student)
            for student in data
            if student.get("State") == state.value
        ]

    compatibility_get._towerbridge_period_compat = True
    Student.get = classmethod(compatibility_get)

    _LOGGER.warning(
        "Vulcan UONET+: aktywowano zgodność Period StartAt/EndAt"
    )


def _install_data_datetime_fields_compatibility() -> None:
    """Obsłuż nowe pola *At w sprawdzianach, ocenach i zadaniach."""

    from vulcan.data import Exam, Grade, Homework

    mappings = (
        (
            Exam,
            "Exam",
            {
                "DateCreated": ("CreatedAt",),
                "DateModify": ("DateModified", "ModifiedAt"),
                "Deadline": ("DeadlineAt",),
            },
        ),
        (
            Grade,
            "Grade",
            {
                "DateCreated": ("CreatedAt",),
                "DateModify": ("DateModified", "ModifiedAt"),
            },
        ),
        (
            Homework,
            "Homework",
            {
                "DateCreated": ("CreatedAt",),
                "Deadline": ("DeadlineAt", "DateAt", "Date"),
                "AnswerDeadline": ("AnswerDeadlineAt",),
                "AnswerDate": ("AnswerAt",),
            },
        ),
    )

    for model_cls, label, field_mapping in mappings:
        current_load = getattr(model_cls, "load")
        current_func = getattr(
            current_load,
            "__func__",
            current_load,
        )

        marker = f"_towerbridge_{label.lower()}_datetime_compat"

        if getattr(current_func, marker, False):
            continue

        def compatibility_load(
            cls,
            data,
            *,
            _original=current_func,
            _field_mapping=field_mapping,
            _label=label,
        ):
            fixed_fields = 0

            if isinstance(data, dict):
                data = dict(data)

                for target, sources in _field_mapping.items():
                    if data.get(target) is not None:
                        continue

                    for source in sources:
                        source_value = data.get(source)

                        if source_value is None:
                            continue

                        data[target] = _legacy_datetime_value(
                            source_value
                        )
                        fixed_fields += 1
                        break

            if fixed_fields:
                _LOGGER.debug(
                    "Vulcan UONET+: zgodność %s: "
                    "przetłumaczono %s pól daty",
                    _label,
                    fixed_fields,
                )

            return _original(cls, data)

        setattr(compatibility_load, marker, True)
        model_cls.load = classmethod(compatibility_load)

    _LOGGER.warning(
        "Vulcan UONET+: aktywowano zgodność pól daty "
        "Exam/Grade/Homework"
    )


def apply_signer_patch() -> None:
    """Podmień signer vulcan-api na uonet-request-signer-hebe."""

    global _PATCH_APPLIED

    if _PATCH_APPLIED:
        return

    try:
        _install_pyopenssl_sign_compatibility()
        _install_period_fields_compatibility()
        _install_data_datetime_fields_compatibility()

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
