"""Synchronizacja sprawdzianów Vulcan z Google Calendar."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

CALENDAR_ENTITY = "calendar.familijne"
MARKER_PREFIX = "VULCAN_EXAM_KEY:"


def _as_date(value: Any) -> date | None:
    """Zamień wartość ISO na datę."""
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text = str(value).strip()

    if not text:
        return None

    try:
        return datetime.fromisoformat(
            text.replace("Z", "+00:00")
        ).date()
    except ValueError:
        pass

    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _event_marker(exam: dict[str, Any]) -> str | None:
    """Zbuduj stabilny znacznik sprawdzianu."""
    key = exam.get("key")

    if key:
        return f"{MARKER_PREFIX}{key}"

    exam_id = exam.get("id")

    if exam_id is not None:
        return f"VULCAN_EXAM_ID:{exam_id}"

    return None


def _flatten_upcoming_exams(
    data: dict[str, Any] | None,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Zbierz przyszłe sprawdziany wszystkich uczniów."""
    if not data:
        return []

    today = date.today()
    result: list[tuple[dict[str, Any], dict[str, Any]]] = []

    for student in (data.get("students") or {}).values():
        for exam in student.get("exams") or []:
            deadline = _as_date(exam.get("deadline"))

            if deadline is None or deadline < today:
                continue

            result.append((student, exam))

    return result


async def _existing_markers(
    hass: HomeAssistant,
    exams: list[tuple[dict[str, Any], dict[str, Any]]],
) -> set[str] | None:
    """Pobierz znaczniki wydarzeń Vulcan już obecnych w kalendarzu."""
    if not hass.services.has_service("calendar", "get_events"):
        _LOGGER.warning(
            "Vulcan Calendar: brak akcji calendar.get_events; "
            "pomijam synchronizację"
        )
        return None

    dates: list[date] = []

    for _student, exam in exams:
        created = _as_date(exam.get("date_created"))
        deadline = _as_date(exam.get("deadline"))

        if created:
            dates.append(created)

        if deadline:
            dates.append(deadline)

    today = date.today()
    start = min(dates or [today]) - timedelta(days=30)
    end = max(dates or [today]) + timedelta(days=90)
    start = min(start, today - timedelta(days=180))
    end = max(end, today + timedelta(days=180))

    try:
        response = await hass.services.async_call(
            "calendar",
            "get_events",
            {
                "start_date_time": f"{start.isoformat()} 00:00:00",
                "end_date_time": f"{end.isoformat()} 23:59:59",
            },
            target={"entity_id": CALENDAR_ENTITY},
            blocking=True,
            return_response=True,
        )
    except Exception:
        _LOGGER.exception(
            "Vulcan Calendar: nie udało się odczytać wydarzeń z %s; "
            "nie tworzę nowych wpisów, żeby uniknąć duplikatów",
            CALENDAR_ENTITY,
        )
        return None

    calendar_data = (response or {}).get(CALENDAR_ENTITY, {})
    events = calendar_data.get("events") or []
    markers: set[str] = set()

    for event in events:
        description = str(event.get("description") or "")

        for line in description.splitlines():
            line = line.strip()

            if line.startswith(MARKER_PREFIX):
                markers.add(line)
            elif line.startswith("VULCAN_EXAM_ID:"):
                markers.add(line)

    _LOGGER.warning(
        "Vulcan Calendar: odczytano %s wydarzeń i %s znaczników",
        len(events),
        len(markers),
    )

    return markers


def _summary(
    student: dict[str, Any],
    exam: dict[str, Any],
) -> str:
    """Zbuduj czytelny tytuł wydarzenia."""
    first_name = student.get("first_name") or "Uczeń"
    subject = exam.get("subject") or "Sprawdzian"
    exam_type = exam.get("type") or "Sprawdzian"
    topic = exam.get("topic")

    summary = f"📝 {first_name} · {subject} · {exam_type}"

    if topic:
        summary = f"{summary} — {topic}"

    return summary


def _description(
    student: dict[str, Any],
    exam: dict[str, Any],
    marker: str,
) -> str:
    """Zbuduj opis wydarzenia wraz z technicznym identyfikatorem."""
    deadline = _as_date(exam.get("deadline"))

    lines = [
        exam.get("topic") or "Sprawdzian / kartkówka",
        "",
        (
            "Uczeń: "
            f"{student.get('full_name') or student.get('first_name') or ''}"
        ),
        f"Klasa: {student.get('class') or '-'}",
        f"Typ: {exam.get('type') or '-'}",
        f"Przedmiot: {exam.get('subject') or '-'}",
        f"Nauczyciel: {exam.get('teacher') or '-'}",
        f"Termin: {deadline.isoformat() if deadline else '-'}",
        "",
        marker,
    ]

    if exam.get("id") is not None:
        lines.append(f"VULCAN_EXAM_ID:{exam['id']}")

    if exam.get("date_modified"):
        lines.append(
            f"VULCAN_EXAM_MODIFIED:{exam['date_modified']}"
        )

    return "\n".join(lines)


async def async_sync_exam_calendar(
    hass: HomeAssistant,
    data: dict[str, Any] | None,
) -> None:
    """Dodaj nowe sprawdziany do kalendarza Familijne."""
    exams = _flatten_upcoming_exams(data)

    _LOGGER.warning(
        "Vulcan Calendar: start synchronizacji; przyszłe sprawdziany=%s",
        len(exams),
    )

    if not exams:
        return

    # Nie sprawdzamy hass.states.get(CALENDAR_ENTITY). Encja Google może być
    # prawidłowym celem akcji mimo braku bieżącego stanu w state machine.
    if not hass.services.has_service("google", "create_event"):
        _LOGGER.warning(
            "Vulcan Calendar: brak akcji google.create_event; "
            "Google Calendar jest najpewniej skonfigurowany tylko do odczytu"
        )
        return

    markers = await _existing_markers(hass, exams)

    if markers is None:
        return

    created_count = 0

    for student, exam in exams:
        marker = _event_marker(exam)

        if marker is None:
            _LOGGER.warning(
                "Vulcan Calendar: sprawdzian bez key/id, pomijam: %s",
                exam,
            )
            continue

        if marker in markers:
            continue

        deadline = _as_date(exam.get("deadline"))

        if deadline is None:
            continue

        start_date = (
            _as_date(exam.get("date_created"))
            or date.today()
        )

        if start_date > deadline:
            start_date = deadline

        end_date = deadline + timedelta(days=1)

        try:
            await hass.services.async_call(
                "google",
                "create_event",
                {
                    "summary": _summary(student, exam),
                    "description": _description(
                        student,
                        exam,
                        marker,
                    ),
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
                target={"entity_id": CALENDAR_ENTITY},
                blocking=True,
            )
        except Exception:
            _LOGGER.exception(
                "Vulcan Calendar: nie udało się dodać sprawdzianu do %s: %s",
                CALENDAR_ENTITY,
                _summary(student, exam),
            )
            continue

        markers.add(marker)
        created_count += 1

        _LOGGER.warning(
            "Vulcan Calendar: dodano do %s: %s (%s -> %s)",
            CALENDAR_ENTITY,
            _summary(student, exam),
            start_date,
            deadline,
        )

    _LOGGER.warning(
        "Vulcan Calendar: synchronizacja zakończona; nowe=%s, razem=%s",
        created_count,
        len(exams),
    )
