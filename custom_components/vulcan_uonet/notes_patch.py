"""Bezpieczna obsługa uwag i pochwał z mobilnego API Vulcan."""

from __future__ import annotations

from datetime import date, datetime
import logging
import re
from typing import Any

_LOGGER = logging.getLogger(__name__)

NOTES_ENDPOINT = "api/mobile/note/byPupil"
NOTES_PAGE_SIZE = 500
NOTES_LAST_ID = -2147483648
NOTES_LAST_SYNC_DATE = "1970-01-01 00:00:00"

_PATCH_MARKER = "_vulcan_uonet_notes_patch"


def _raw_get(
    obj: Any,
    *keys: str,
    default: Any = None,
) -> Any:
    """Bezpiecznie pobierz wartość ze słownika odpowiedzi API."""

    if not isinstance(obj, dict):
        return default

    for key in keys:
        if key in obj and obj[key] is not None:
            return obj[key]

    return default


def _raw_datetime_to_iso(value: Any) -> str | None:
    """Zamień surowy DateTimeInfo VULCAN na datę ISO."""

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date().isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if not isinstance(value, dict):
        text = str(value).strip()
        return text or None

    # Najbezpieczniejsze pole dla dat z VULCAN-a, np. 03.09.2025.
    display = _raw_get(value, "DateDisplay", "dateDisplay")
    if display:
        try:
            return datetime.strptime(
                str(display).strip(),
                "%d.%m.%Y",
            ).date().isoformat()
        except ValueError:
            pass

    raw_date = _raw_get(value, "Date", "date")
    if raw_date:
        text = str(raw_date).strip()

        try:
            return datetime.fromisoformat(
                text.replace("Z", "+00:00")
            ).date().isoformat()
        except ValueError:
            pass

        # Starsze odpowiedzi Hebe potrafią używać formatu /Date(…)/.
        match = re.search(r"/Date\((-?\d+)", text)
        if match:
            try:
                timestamp = int(match.group(1)) / 1000
                return datetime.fromtimestamp(timestamp).date().isoformat()
            except (OSError, OverflowError, ValueError):
                pass

    timestamp = _raw_get(value, "Timestamp", "timestamp")
    if timestamp is not None:
        try:
            numeric = float(timestamp)
            if abs(numeric) > 10_000_000_000:
                numeric /= 1000
            return datetime.fromtimestamp(numeric).date().isoformat()
        except (OSError, OverflowError, TypeError, ValueError):
            pass

    return None


def _school_year_from_iso(value: str | None) -> str | None:
    """Wylicz rok szkolny z daty ISO, np. 2025/2026."""

    if not value:
        return None

    try:
        parsed = date.fromisoformat(str(value)[:10])
    except ValueError:
        return None

    start_year = parsed.year if parsed.month >= 9 else parsed.year - 1
    return f"{start_year}/{start_year + 1}"


def _teacher_name(creator: Any) -> str | None:
    """Zbuduj czytelną nazwę nauczyciela z surowego rekordu."""

    teacher = _raw_get(
        creator,
        "DisplayName",
        "displayName",
        "FullName",
        "fullName",
    )

    if teacher:
        return str(teacher)

    first_name = _raw_get(
        creator,
        "FirstName",
        "firstName",
        "Name",
        "name",
        default="",
    )
    last_name = _raw_get(
        creator,
        "LastName",
        "lastName",
        "Surname",
        "surname",
        default="",
    )

    result = f"{first_name} {last_name}".strip()
    return result or None


def _note_to_dict(note: dict[str, Any]) -> dict[str, Any]:
    """Zamień surową uwagę/pochwałę na dane integracji."""

    creator = _raw_get(note, "Creator", "creator", default={})
    category = _raw_get(note, "Category", "category", default={})
    positive_raw = _raw_get(note, "Positive", "positive")

    if isinstance(positive_raw, bool):
        positive = positive_raw
    elif isinstance(positive_raw, int):
        positive = bool(positive_raw)
    else:
        positive = None

    note_date = _raw_datetime_to_iso(
        _raw_get(note, "DateValid", "dateValid")
    )
    note_key = _raw_get(note, "Key", "key")

    return {
        "id": _raw_get(note, "Id", "id"),
        "key": str(note_key) if note_key is not None else None,
        "pupil_id": _raw_get(
            note,
            "IdPupil",
            "idPupil",
            "PupilId",
            "pupilId",
        ),
        "positive": positive,
        "type": (
            "pochwala"
            if positive is True
            else "uwaga"
            if positive is False
            else None
        ),
        "date": note_date,
        "date_modified": _raw_datetime_to_iso(
            _raw_get(note, "DateModify", "dateModify")
        ),
        "school_year": _school_year_from_iso(note_date),
        "content": _raw_get(note, "Content", "content"),
        "points": _raw_get(note, "Points", "points"),
        "teacher": _teacher_name(creator),
        "category": _raw_get(category, "Name", "name"),
        "category_type": _raw_get(category, "Type", "type"),
        "category_id": _raw_get(category, "Id", "id"),
        "category_default_points": _raw_get(
            category,
            "DefaultPoints",
            "defaultPoints",
        ),
    }


async def _fetch_notes(
    client: Any,
    student: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Pobierz uwagi po PupilId, bez periodId i bez filtra roku."""

    pupil = getattr(student, "pupil", None)
    pupil_id = getattr(pupil, "id", None)
    first_name = getattr(pupil, "first_name", "Uczeń")

    info: dict[str, Any] = {
        "available": False,
        "endpoint": NOTES_ENDPOINT,
        "count": 0,
        "oldest": None,
        "newest": None,
        "school_years": {},
    }

    if pupil_id is None:
        _LOGGER.warning(
            "Vulcan: TEST note/byPupil/%s pominięty - brak PupilId",
            first_name,
        )
        return [], info

    try:
        # fetch_for_student() ustawia już poprawnego studenta i RestURL.
        response = await client._api.get(  # noqa: SLF001
            NOTES_ENDPOINT,
            {
                "pupilId": pupil_id,
                "lastSyncDate": NOTES_LAST_SYNC_DATE,
                "lastId": NOTES_LAST_ID,
                "pageSize": NOTES_PAGE_SIZE,
            },
        )
    except Exception:
        _LOGGER.exception(
            "Vulcan: TEST note/byPupil/%s NIEUDANY - endpoint=%s",
            first_name,
            NOTES_ENDPOINT,
        )
        return [], info

    raw_notes: list[Any]

    if isinstance(response, list):
        raw_notes = response
    elif isinstance(response, dict):
        raw_notes = []
        found_list = False

        for key in (
            "Items",
            "items",
            "Entries",
            "entries",
            "Notes",
            "notes",
        ):
            candidate = response.get(key)
            if isinstance(candidate, list):
                raw_notes = candidate
                found_list = True
                break

        if not found_list:
            _LOGGER.warning(
                (
                    "Vulcan: TEST note/byPupil/%s NIEUDANY - "
                    "odpowiedź bez listy, klucze=%s"
                ),
                first_name,
                sorted(response.keys()),
            )
            return [], info
    else:
        _LOGGER.warning(
            (
                "Vulcan: TEST note/byPupil/%s NIEUDANY - "
                "nieoczekiwany typ odpowiedzi=%s"
            ),
            first_name,
            type(response).__name__,
        )
        return [], info

    notes: list[dict[str, Any]] = []

    for raw_note in raw_notes:
        if not isinstance(raw_note, dict):
            _LOGGER.warning(
                "Vulcan: pomijam niepoprawny rekord uwagi/%s typu %s",
                first_name,
                type(raw_note).__name__,
            )
            continue

        try:
            notes.append(_note_to_dict(raw_note))
        except Exception:
            _LOGGER.exception(
                "Vulcan: błąd konwersji uwagi/pochwały ucznia %s",
                first_name,
            )

    notes.sort(
        key=lambda item: item.get("date") or "",
        reverse=True,
    )

    dated_notes = [
        str(item["date"])
        for item in notes
        if item.get("date")
    ]

    school_years: dict[str, int] = {}
    for item in notes:
        school_year = item.get("school_year")
        if school_year:
            school_years[school_year] = school_years.get(school_year, 0) + 1

    info.update(
        {
            "available": True,
            "count": len(notes),
            "oldest": min(dated_notes) if dated_notes else None,
            "newest": max(dated_notes) if dated_notes else None,
            "school_years": school_years,
        }
    )

    _LOGGER.info(
        (
            "Vulcan: TEST note/byPupil/%s OK - rekordów=%s, "
            "zakres=%s..%s, lata_szkolne=%s"
        ),
        first_name,
        len(notes),
        info["oldest"],
        info["newest"],
        school_years,
    )

    if len(raw_notes) >= NOTES_PAGE_SIZE:
        _LOGGER.warning(
            (
                "Vulcan: note/byPupil/%s zwrócił pełne %s rekordów; "
                "może być potrzebna paginacja"
            ),
            first_name,
            NOTES_PAGE_SIZE,
        )

    return notes, info


def apply_notes_fetch_patch() -> None:
    """Dołącz uwagi do istniejącego fetch_for_student bez zmiany jego logiki."""

    from . import coordinator as coordinator_module

    original = coordinator_module.fetch_for_student

    if getattr(original, _PATCH_MARKER, False):
        return

    async def fetch_for_student_with_notes(
        client: Any,
        student: Any,
    ) -> dict[str, Any]:
        # Najpierw wykonujemy niezmienioną, dotychczasową logikę integracji.
        result = await original(client, student)

        # Dopiero po jej zakończeniu testujemy niezależny endpoint uwag.
        # Każdy błąd endpointu jest obsłużony wewnątrz _fetch_notes().
        notes, notes_info = await _fetch_notes(client, student)

        result["notes"] = notes
        result["notes_info"] = notes_info

        return result

    setattr(fetch_for_student_with_notes, _PATCH_MARKER, True)
    coordinator_module.fetch_for_student = fetch_for_student_with_notes

    _LOGGER.info(
        "Vulcan: aktywowano bezpieczny patch uwag/pochwał note/byPupil"
    )
