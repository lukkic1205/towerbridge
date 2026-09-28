"""Rozszerzenie danych zmian planu lekcji Vulcan UONET+."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from typing import Any

from vulcan._api_helper import FilterType
from vulcan._endpoints import DATA_TIMETABLE_CHANGES

from . import coordinator as coordinator_module

_LOGGER = logging.getLogger(__name__)

_PATCHED = False
_ORIGINAL_FETCH_FOR_STUDENT = coordinator_module.fetch_for_student


def _raw_get(value: Any, *keys: str, default: Any = None) -> Any:
    """Pobierz pierwszą istniejącą wartość ze słownika lub obiektu."""

    if value is None:
        return default

    if isinstance(value, dict):
        for key in keys:
            if key in value and value[key] is not None:
                return value[key]
        return default

    for key in keys:
        try:
            result = getattr(value, key)
        except Exception:
            continue

        if result is not None:
            return result

    return default


def _raw_datetime_to_iso(value: Any) -> str | None:
    """Zamień surowy obiekt DateTime Vulcan na ISO bez utraty daty."""

    if value is None:
        return None

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, str):
        return value

    raw_date = _raw_get(value, "Date", "date")
    raw_time = _raw_get(value, "Time", "time")

    if raw_date is None:
        return str(value)

    date_text = str(raw_date)
    if raw_time in (None, "", "00:00:00", "00:00"):
        return date_text

    return f"{date_text}T{raw_time}"


def _display_name(value: Any) -> str | None:
    """Pobierz czytelną nazwę nauczyciela/klasy z raw API."""

    if value is None:
        return None

    direct = _raw_get(
        value,
        "DisplayName",
        "display_name",
        "Name",
        "name",
        "ShortName",
        "short_name",
    )
    if direct:
        return str(direct)

    first = _raw_get(value, "FirstName", "first_name")
    last = _raw_get(value, "LastName", "last_name")
    text = " ".join(str(x).strip() for x in (first, last) if x).strip()
    return text or None


def _changed_lesson_from_raw(raw: Any) -> dict[str, Any]:
    """Zamień surowy rekord schedule/changes na prosty słownik."""

    time_slot = _raw_get(raw, "TimeSlot", "time")
    change = _raw_get(raw, "Change", "changes")
    subject = _raw_get(raw, "Subject", "subject")
    teacher = _raw_get(raw, "TeacherPrimary", "teacher")
    second_teacher = _raw_get(raw, "TeacherSecondary", "second_teacher")
    room = _raw_get(raw, "Room", "room")
    team_class = _raw_get(raw, "Clazz", "team_class")

    change_type = _raw_get(change, "Type", "type")
    separation = _raw_get(change, "Separation", "separation")

    start = _raw_get(time_slot, "Start", "from_")
    end = _raw_get(time_slot, "End", "to")
    displayed = _raw_get(time_slot, "Display", "displayed_time")

    if not displayed and (start or end):
        displayed = f"{str(start or '')[:5]}-{str(end or '')[:5]}".strip("-")

    note = _raw_get(raw, "Note", "note")
    reason = _raw_get(raw, "Reason", "reason")
    event = _raw_get(raw, "Event", "event")

    return {
        "change_id": _raw_get(raw, "Id", "id"),
        "schedule_id": _raw_get(raw, "ScheduleId", "schedule_id"),
        "date": _raw_datetime_to_iso(
            _raw_get(raw, "LessonDate", "lesson_date", "Date", "date")
        ),
        "change_date": _raw_datetime_to_iso(
            _raw_get(raw, "ChangeDate", "change_date")
        ),
        "position": _raw_get(time_slot, "Position", "position"),
        "time": str(displayed) if displayed else None,
        "start": str(start)[:5] if start else None,
        "end": str(end)[:5] if end else None,
        "subject": _raw_get(subject, "Name", "name"),
        "subject_code": _raw_get(subject, "Code", "code"),
        "teacher": _display_name(teacher),
        "second_teacher": _display_name(second_teacher),
        "room": _raw_get(room, "Code", "code"),
        "class": _display_name(team_class),
        "change_type": str(change_type) if change_type is not None else None,
        "separation": separation,
        "note": str(note).strip() if note else None,
        "reason": str(reason).strip() if reason else None,
        "event": str(event).strip() if event else None,
    }


def _day(item: dict[str, Any]) -> str:
    return str(item.get("date") or "")[:10]


def _position_key(item: dict[str, Any]) -> tuple[str, str] | None:
    day = _day(item)
    position = item.get("position")

    if not day or position is None:
        return None

    return day, str(position)


def _time_key(item: dict[str, Any]) -> tuple[str, str] | None:
    day = _day(item)
    start = str(item.get("start") or "").strip()

    if not day or not start:
        return None

    return day, start[:5]


def _apply_detail(lesson: dict[str, Any], detail: dict[str, Any]) -> None:
    """Doklej szczegóły zmiany do standardowego wpisu lekcji."""

    detail_type = detail.get("change_type")

    lesson["changed"] = True

    if detail_type is not None:
        lesson["change_type"] = detail_type

    lesson["cancelled"] = bool(
        lesson.get("cancelled")
        or str(lesson.get("change_type")) == "1"
    )

    lesson["change_id"] = detail.get("change_id")
    lesson["change_schedule_id"] = detail.get("schedule_id")
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

    description_parts: list[str] = []
    for value in (detail.get("reason"), detail.get("note")):
        text = str(value or "").strip()
        if text and text not in description_parts:
            description_parts.append(text)

    lesson["change_description"] = (
        " • ".join(description_parts)
        if description_parts
        else None
    )

    lesson["change_details"] = detail


def _merge_change_details(
    lessons: list[dict[str, Any]],
    changed_lessons: list[dict[str, Any]],
) -> tuple[int, list[dict[str, Any]]]:
    """Połącz rekordy zmian z planem kilkoma metodami."""

    ordered = sorted(
        changed_lessons,
        key=lambda item: str(item.get("change_date") or ""),
    )

    by_schedule_id: dict[str, dict[str, Any]] = {}
    by_position: dict[tuple[str, str], dict[str, Any]] = {}
    by_time: dict[tuple[str, str], dict[str, Any]] = {}

    for detail in ordered:
        schedule_id = detail.get("schedule_id")
        if schedule_id is not None:
            by_schedule_id[str(schedule_id)] = detail

        position_key = _position_key(detail)
        if position_key is not None:
            by_position[position_key] = detail

        time_key = _time_key(detail)
        if time_key is not None:
            by_time[time_key] = detail

    used_change_ids: set[str] = set()
    merged = 0

    for lesson in lessons:
        detail = None
        lesson_id = lesson.get("id")

        if lesson_id is not None:
            detail = by_schedule_id.get(str(lesson_id))

        if detail is None:
            key = _position_key(lesson)
            if key is not None:
                detail = by_position.get(key)

        if detail is None:
            key = _time_key(lesson)
            if key is not None:
                detail = by_time.get(key)

        if detail is None:
            continue

        _apply_detail(lesson, detail)
        merged += 1

        change_id = detail.get("change_id")
        if change_id is not None:
            used_change_ids.add(str(change_id))

    remaining = [
        item
        for item in ordered
        if item.get("change_id") is None
        or str(item.get("change_id")) not in used_change_ids
    ]

    for detail in list(remaining):
        day = _day(detail)
        change_type = str(detail.get("change_type") or "")

        candidates = [
            lesson
            for lesson in lessons
            if _day(lesson) == day
            and bool(lesson.get("changed"))
            and not lesson.get("change_details")
            and (
                not change_type
                or str(lesson.get("change_type") or "") == change_type
            )
        ]

        peers = [
            other
            for other in remaining
            if _day(other) == day
            and str(other.get("change_type") or "") == change_type
        ]

        if len(candidates) == 1 and len(peers) == 1:
            _apply_detail(candidates[0], detail)
            merged += 1
            remaining.remove(detail)

    return merged, remaining


async def _fetch_raw_changes(
    client: Any,
    first_name: str,
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    """Pobierz surowe schedule/changes, omijając błąd modelu ScheduleId."""

    try:
        raw_items = await client._api.helper.get_list(  # noqa: SLF001
            DATA_TIMETABLE_CHANGES,
            FilterType.BY_PUPIL,
            date_from=start,
            date_to=end,
        )
    except Exception:
        _LOGGER.exception(
            "Vulcan: błąd RAW schedule/changes ucznia %s",
            first_name,
        )
        return []

    _LOGGER.warning(
        "Vulcan: RAW schedule/changes/%s: %s rekordów",
        first_name,
        len(raw_items or []),
    )

    changed_lessons: list[dict[str, Any]] = []

    for raw in raw_items or []:
        try:
            detail = _changed_lesson_from_raw(raw)
            changed_lessons.append(detail)

            _LOGGER.warning(
                (
                    "Vulcan: CHANGE/%s id=%s schedule_id=%s date=%s "
                    "pos=%s time=%s type=%s subject=%s teacher=%s "
                    "room=%s reason=%r note=%r"
                ),
                first_name,
                detail.get("change_id"),
                detail.get("schedule_id"),
                detail.get("date"),
                detail.get("position"),
                detail.get("time"),
                detail.get("change_type"),
                detail.get("subject"),
                detail.get("teacher"),
                detail.get("room"),
                detail.get("reason"),
                detail.get("note"),
            )
        except Exception:
            _LOGGER.exception(
                "Vulcan: błąd parsowania RAW zmiany planu ucznia %s: %r",
                first_name,
                raw,
            )

    return changed_lessons


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

    changed_lessons = await _fetch_raw_changes(
        client,
        first_name,
        start,
        end,
    )

    merged, unmatched = _merge_change_details(
        result.get("lessons", []),
        changed_lessons,
    )

    result["changed_lessons"] = changed_lessons

    _LOGGER.warning(
        (
            "Vulcan: szczegóły zmian planu/%s: rekordy=%s "
            "połączone=%s niepołączone=%s"
        ),
        first_name,
        len(changed_lessons),
        merged,
        len(unmatched),
    )

    for detail in unmatched[:10]:
        _LOGGER.warning(
            "Vulcan: NIEPOŁĄCZONA ZMIANA/%s: %s",
            first_name,
            detail,
        )

    return result


def apply_lesson_changes_patch() -> None:
    """Podmień pobieranie danych ucznia na wersję ze szczegółami zmian planu."""

    global _PATCHED

    if _PATCHED:
        return

    coordinator_module.fetch_for_student = _enhanced_fetch_for_student
    _PATCHED = True

    _LOGGER.warning(
        "Vulcan: włączono rozszerzone RAW szczegóły zmian planu lekcji"
    )
