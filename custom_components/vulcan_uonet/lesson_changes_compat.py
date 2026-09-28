"""Rozszerzenie danych zmian planu lekcji Vulcan UONET+."""

from __future__ import annotations

from datetime import date, timedelta
import logging
from typing import Any

from . import coordinator as coordinator_module

_LOGGER = logging.getLogger(__name__)

_PATCHED = False
_ORIGINAL_FETCH_FOR_STUDENT = coordinator_module.fetch_for_student


def _changed_lesson_to_dict(item: Any) -> dict[str, Any]:
    """Zamień wpis z endpointu zmian planu na prosty słownik."""

    safe_get = coordinator_module.safe_get
    to_iso = coordinator_module.vulcan_datetime_to_iso

    subject = safe_get(item, "subject")
    teacher = safe_get(item, "teacher")
    second_teacher = safe_get(item, "second_teacher")
    room = safe_get(item, "room")
    time_slot = safe_get(item, "time")
    changes = safe_get(item, "changes")
    team_class = safe_get(item, "team_class")

    change_type = safe_get(changes, "type") if changes is not None else None
    separation = safe_get(changes, "separation") if changes is not None else None

    event = safe_get(item, "event")
    note = safe_get(item, "note")
    reason = safe_get(item, "reason")

    return {
        "change_id": safe_get(item, "id"),
        "schedule_id": safe_get(item, "schedule_id"),
        "date": to_iso(safe_get(item, "lesson_date")),
        "change_date": to_iso(safe_get(item, "change_date")),
        "position": safe_get(time_slot, "position"),
        "time": safe_get(time_slot, "displayed_time"),
        "start": str(safe_get(time_slot, "from_", ""))[:5],
        "end": str(safe_get(time_slot, "to", ""))[:5],
        "subject": safe_get(subject, "name"),
        "subject_code": safe_get(subject, "code"),
        "teacher": safe_get(teacher, "display_name"),
        "second_teacher": safe_get(second_teacher, "display_name"),
        "room": safe_get(room, "code"),
        "class": safe_get(team_class, "display_name"),
        "change_type": str(change_type) if change_type is not None else None,
        "separation": separation,
        "note": str(note) if note else None,
        "reason": str(reason) if reason else None,
        "event": str(event) if event else None,
    }


def _slot_key(item: dict[str, Any]) -> tuple[str, str] | None:
    """Zbuduj klucz data + numer lekcji do łączenia wpisów zmian."""

    day = str(item.get("date") or "")[:10]
    position = item.get("position")

    if not day or position is None:
        return None

    return day, str(position)


def _merge_change_details(
    lessons: list[dict[str, Any]],
    changed_lessons: list[dict[str, Any]],
) -> None:
    """Dołącz szczegóły zmian do zwykłych wpisów planu."""

    by_schedule_id: dict[str, dict[str, Any]] = {}
    by_slot: dict[tuple[str, str], dict[str, Any]] = {}

    # Najnowszy wpis ma wygrać, dlatego sortujemy po dacie zmiany.
    ordered = sorted(
        changed_lessons,
        key=lambda item: str(item.get("change_date") or ""),
    )

    for detail in ordered:
        schedule_id = detail.get("schedule_id")
        if schedule_id is not None:
            by_schedule_id[str(schedule_id)] = detail

        key = _slot_key(detail)
        if key is not None:
            by_slot[key] = detail

    for lesson in lessons:
        detail = None
        lesson_id = lesson.get("id")

        if lesson_id is not None:
            detail = by_schedule_id.get(str(lesson_id))

        if detail is None:
            key = _slot_key(lesson)
            if key is not None:
                detail = by_slot.get(key)

        if detail is None:
            continue

        detail_type = detail.get("change_type")

        lesson["changed"] = True
        if detail_type is not None:
            lesson["change_type"] = detail_type

        lesson["cancelled"] = bool(
            lesson.get("cancelled")
            or str(lesson.get("change_type")) == "1"
        )

        lesson["change_id"] = detail.get("change_id")
        lesson["change_date"] = detail.get("change_date")
        lesson["change_note"] = detail.get("note")
        lesson["change_reason"] = detail.get("reason")
        lesson["change_teacher"] = detail.get("teacher")
        lesson["change_second_teacher"] = detail.get("second_teacher")
        lesson["change_room"] = detail.get("room")
        lesson["change_subject"] = detail.get("subject")
        lesson["change_subject_code"] = detail.get("subject_code")
        lesson["change_time"] = detail.get("time")
        lesson["change_start"] = detail.get("start")
        lesson["change_end"] = detail.get("end")
        lesson["change_event"] = detail.get("event")
        lesson["change_separation"] = detail.get("separation")

        description_parts = []
        for value in (detail.get("reason"), detail.get("note")):
            text = str(value or "").strip()
            if text and text not in description_parts:
                description_parts.append(text)

        lesson["change_description"] = (
            " • ".join(description_parts)
            if description_parts
            else None
        )

        # Pełny obiekt zostawiamy również do diagnostyki i dalszej rozbudowy karty.
        lesson["change_details"] = detail


async def _enhanced_fetch_for_student(
    client: Any,
    student: Any,
) -> dict[str, Any]:
    """Pobierz standardowe dane ucznia i dołącz szczegóły zmian planu."""

    result = await _ORIGINAL_FETCH_FOR_STUDENT(client, student)

    safe_get = coordinator_module.safe_get
    pupil = safe_get(student, "pupil")
    first_name = safe_get(pupil, "first_name", "Uczeń")

    start = date.today() - timedelta(days=coordinator_module.DAYS_BACK)
    end = date.today() + timedelta(days=coordinator_module.DAYS_FORWARD)

    changed_raw = await coordinator_module.safely_collect(
        f"zmiany planu/{first_name}",
        client.data.get_changed_lessons(
            date_from=start,
            date_to=end,
        ),
    )

    changed_lessons: list[dict[str, Any]] = []

    for item in changed_raw:
        try:
            changed_lessons.append(_changed_lesson_to_dict(item))
        except Exception:
            _LOGGER.exception(
                "Vulcan: błąd konwersji zmiany planu ucznia %s",
                first_name,
            )

    _merge_change_details(
        result.get("lessons", []),
        changed_lessons,
    )

    result["changed_lessons"] = changed_lessons

    _LOGGER.info(
        "Vulcan: szczegóły zmian planu ucznia %s: %s",
        first_name,
        len(changed_lessons),
    )

    return result


def apply_lesson_changes_patch() -> None:
    """Podmień pobieranie danych ucznia na wersję ze szczegółami zmian planu."""

    global _PATCHED

    if _PATCHED:
        return

    coordinator_module.fetch_for_student = _enhanced_fetch_for_student
    _PATCHED = True

    _LOGGER.info(
        "Vulcan: włączono rozszerzone szczegóły zmian planu lekcji"
    )
