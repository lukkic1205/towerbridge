"""Koordynator danych integracji Vulcan UONET+."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta
import logging
from typing import Any

from vulcan import Vulcan

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=15)

DAYS_BACK = 60
DAYS_FORWARD = 14


def safe_get(
    obj: Any,
    attr: str,
    default: Any = None,
) -> Any:
    """Bezpiecznie pobierz atrybut obiektu."""

    try:
        value = getattr(obj, attr)
        return value if value is not None else default
    except Exception:
        return default


def vulcan_datetime_to_iso(value: Any) -> str | None:
    """Zamień obiekt daty Vulcan na tekst ISO."""

    if value is None:
        return None

    date_value = safe_get(value, "date")
    time_value = safe_get(value, "time")

    if isinstance(date_value, date):
        if time_value:
            return f"{date_value.isoformat()}T{time_value}"

        return date_value.isoformat()

    if isinstance(date_value, str):
        if time_value:
            return f"{date_value}T{time_value}"

        return date_value

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    return str(value)


async def collect_items(
    generator: AsyncIterator[Any] | list[Any],
) -> list[Any]:
    """Zbierz elementy z generatora asynchronicznego."""

    if isinstance(generator, list):
        return generator

    items: list[Any] = []

    async for item in generator:
        items.append(item)

    return items


async def safely_collect(
    label: str,
    awaitable: Any,
) -> list[Any]:
    """Pobierz kategorię danych bez blokowania całej integracji."""

    try:
        generator = await awaitable
        items = await collect_items(generator)

        _LOGGER.info(
            "Vulcan: pobrano kategorię %s, liczba rekordów: %s",
            label,
            len(items),
        )

        return items

    except Exception:
        _LOGGER.exception(
            "Vulcan: błąd podczas pobierania kategorii %s",
            label,
        )

        return []


def lesson_to_dict(lesson: Any) -> dict[str, Any]:
    """Zamień lekcję na słownik."""

    subject = safe_get(lesson, "subject")
    teacher = safe_get(lesson, "teacher")
    second_teacher = safe_get(lesson, "second_teacher")
    room = safe_get(lesson, "room")
    time_slot = safe_get(lesson, "time")
    changes = safe_get(lesson, "changes")
    event = safe_get(lesson, "event")
    team_class = safe_get(lesson, "team_class")

    return {
        "id": safe_get(lesson, "id"),
        "date": vulcan_datetime_to_iso(
            safe_get(lesson, "date")
        ),
        "position": safe_get(time_slot, "position"),
        "time": safe_get(time_slot, "displayed_time"),
        "start": str(
            safe_get(time_slot, "from_", "")
        )[:5],
        "end": str(
            safe_get(time_slot, "to", "")
        )[:5],
        "subject": safe_get(subject, "name"),
        "subject_code": safe_get(subject, "code"),
        "teacher": safe_get(teacher, "display_name"),
        "second_teacher": safe_get(
            second_teacher,
            "display_name",
        ),
        "room": safe_get(room, "code"),
        "class": safe_get(team_class, "display_name"),
        "visible": safe_get(lesson, "visible", True),
        "changed": changes is not None,
        "change_type": (
            str(safe_get(changes, "type"))
            if changes is not None
            else None
        ),
        "event": str(event) if event else None,
    }


def exam_to_dict(exam: Any) -> dict[str, Any]:
    """Zamień sprawdzian na słownik."""

    subject = safe_get(exam, "subject")
    creator = safe_get(exam, "creator")

    return {
        "id": safe_get(exam, "id"),
        "key": safe_get(exam, "key"),
        "type": safe_get(exam, "type"),
        "topic": safe_get(exam, "topic"),
        "deadline": vulcan_datetime_to_iso(
            safe_get(exam, "deadline")
        ),
        "date_created": vulcan_datetime_to_iso(
            safe_get(exam, "date_created")
        ),
        "date_modified": vulcan_datetime_to_iso(
            safe_get(exam, "date_modified")
        ),
        "subject": safe_get(subject, "name"),
        "subject_code": safe_get(subject, "code"),
        "teacher": safe_get(creator, "display_name"),
    }


def grade_to_dict(grade: Any) -> dict[str, Any]:
    """Zamień ocenę na słownik."""

    column = safe_get(grade, "column")
    subject = safe_get(column, "subject")
    category = safe_get(column, "category")
    teacher = safe_get(grade, "teacher_created")

    return {
        "id": safe_get(grade, "id"),
        "key": safe_get(grade, "key"),
        "pupil_id": safe_get(grade, "pupil_id"),
        "content": safe_get(grade, "content"),
        "content_raw": safe_get(grade, "content_raw"),
        "value": safe_get(grade, "value"),
        "comment": safe_get(grade, "comment"),
        "date_created": vulcan_datetime_to_iso(
            safe_get(grade, "date_created")
        ),
        "date_modified": vulcan_datetime_to_iso(
            safe_get(grade, "date_modified")
        ),
        "column_name": safe_get(column, "name"),
        "column_code": safe_get(column, "code"),
        "weight": safe_get(column, "weight"),
        "subject": safe_get(subject, "name"),
        "subject_code": safe_get(subject, "code"),
        "category": safe_get(category, "name"),
        "teacher": safe_get(teacher, "display_name"),
    }


def homework_to_dict(homework: Any) -> dict[str, Any]:
    """Zamień zadanie domowe na słownik."""

    subject = safe_get(homework, "subject")
    creator = safe_get(homework, "creator")
    attachments = safe_get(homework, "attachments", [])

    attachment_list: list[Any] = []

    try:
        for attachment in attachments:
            if hasattr(attachment, "as_dict"):
                attachment_list.append(attachment.as_dict)
            else:
                attachment_list.append(str(attachment))
    except Exception:
        _LOGGER.exception(
            "Vulcan: błąd przetwarzania załączników zadania"
        )

    return {
        "id": safe_get(homework, "id"),
        "homework_id": safe_get(homework, "homework_id"),
        "key": safe_get(homework, "key"),
        "content": safe_get(homework, "content"),
        "date_created": vulcan_datetime_to_iso(
            safe_get(homework, "date_created")
        ),
        "deadline": vulcan_datetime_to_iso(
            safe_get(homework, "deadline")
        ),
        "answer_deadline": vulcan_datetime_to_iso(
            safe_get(homework, "answer_deadline")
        ),
        "answer_date": vulcan_datetime_to_iso(
            safe_get(homework, "answer_date")
        ),
        "is_answer_required": safe_get(
            homework,
            "is_answer_required",
            False,
        ),
        "subject": safe_get(subject, "name"),
        "subject_code": safe_get(subject, "code"),
        "teacher": safe_get(creator, "display_name"),
        "attachments": attachment_list,
    }


def attendance_to_dict(attendance: Any) -> dict[str, Any]:
    """Zamień wpis frekwencji na słownik."""

    try:
        if hasattr(attendance, "as_dict"):
            return attendance.as_dict
    except Exception:
        _LOGGER.exception(
            "Vulcan: błąd konwersji wpisu frekwencji"
        )

    return {
        "value": str(attendance),
    }


async def fetch_for_student(
    client: Vulcan,
    student: Any,
) -> dict[str, Any]:
    """Pobierz dane jednego ucznia."""

    pupil = safe_get(student, "pupil")
    pupil_id = safe_get(pupil, "id")
    first_name = safe_get(pupil, "first_name", "Uczeń")
    last_name = safe_get(pupil, "last_name", "")

    _LOGGER.info(
        "Vulcan: rozpoczynam pobieranie danych ucznia %s, ID %s",
        first_name,
        pupil_id,
    )

    client._api.student = student  # noqa: SLF001

    start = date.today() - timedelta(days=DAYS_BACK)
    end = date.today() + timedelta(days=DAYS_FORWARD)

    lessons_raw = await safely_collect(
        f"lekcje/{first_name}",
        client.data.get_lessons(
            date_from=start,
            date_to=end,
        ),
    )

    exams_raw = await safely_collect(
        f"sprawdziany/{first_name}",
        client.data.get_exams(),
    )

    grades_raw = await safely_collect(
        f"oceny/{first_name}",
        client.data.get_grades(),
    )

    homework_raw = await safely_collect(
        f"zadania/{first_name}",
        client.data.get_homework(),
    )

    attendance_raw = await safely_collect(
        f"frekwencja/{first_name}",
        client.data.get_attendance(
            date_from=start,
            date_to=end,
        ),
    )

    lessons: list[dict[str, Any]] = []

    for item in lessons_raw:
        try:
            lesson = lesson_to_dict(item)

            if lesson["visible"]:
                lessons.append(lesson)
        except Exception:
            _LOGGER.exception(
                "Vulcan: błąd konwersji lekcji ucznia %s",
                first_name,
            )

    exams: list[dict[str, Any]] = []

    for item in exams_raw:
        try:
            exams.append(exam_to_dict(item))
        except Exception:
            _LOGGER.exception(
                "Vulcan: błąd konwersji sprawdzianu ucznia %s",
                first_name,
            )

    grades: list[dict[str, Any]] = []

    for item in grades_raw:
        try:
            grades.append(grade_to_dict(item))
        except Exception:
            _LOGGER.exception(
                "Vulcan: błąd konwersji oceny ucznia %s",
                first_name,
            )

    homework: list[dict[str, Any]] = []

    for item in homework_raw:
        try:
            homework.append(homework_to_dict(item))
        except Exception:
            _LOGGER.exception(
                "Vulcan: błąd konwersji zadania ucznia %s",
                first_name,
            )

    attendance = [
        attendance_to_dict(item)
        for item in attendance_raw
    ]

    lessons.sort(
        key=lambda item: (
            item.get("date") or "",
            item.get("position") or 0,
        )
    )

    exams.sort(
        key=lambda item: item.get("deadline") or ""
    )

    grades.sort(
        key=lambda item: item.get("date_created") or "",
        reverse=True,
    )

    homework.sort(
        key=lambda item: item.get("deadline") or ""
    )

    try:
        lucky_number_obj = await client.data.get_lucky_number()

        lucky_number = {
            "date": vulcan_datetime_to_iso(
                safe_get(lucky_number_obj, "date")
            ),
            "number": safe_get(
                lucky_number_obj,
                "number",
            ),
        }

        _LOGGER.info(
            "Vulcan: pobrano szczęśliwy numerek ucznia %s",
            first_name,
        )

    except Exception:
        _LOGGER.exception(
            "Vulcan: błąd pobierania szczęśliwego numerka ucznia %s",
            first_name,
        )

        lucky_number = {
            "date": date.today().isoformat(),
            "number": None,
        }

    unit = safe_get(student, "unit")
    school = safe_get(student, "school")

    result = {
        "id": pupil_id,
        "first_name": first_name,
        "last_name": last_name,
        "full_name": f"{first_name} {last_name}".strip(),
        "class": safe_get(student, "class_"),
        "unit": safe_get(unit, "code"),
        "school": safe_get(school, "short_name"),
        "updated_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "range": {
            "from": start.isoformat(),
            "to": end.isoformat(),
            "days_back": DAYS_BACK,
            "days_forward": DAYS_FORWARD,
        },
        "lessons": lessons,
        "exams": exams,
        "grades": grades,
        "homework": homework,
        "attendance": attendance,
        "lucky_number": lucky_number,
    }

    _LOGGER.info(
        (
            "Vulcan: zakończono ucznia %s: "
            "lekcje=%s, sprawdziany=%s, oceny=%s, "
            "zadania=%s, frekwencja=%s"
        ),
        first_name,
        len(lessons),
        len(exams),
        len(grades),
        len(homework),
        len(attendance),
    )

    return result


class VulcanUonetCoordinator(
    DataUpdateCoordinator[dict[str, Any]]
):
    """Koordynator danych Vulcan UONET+."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: Vulcan,
    ) -> None:
        """Zainicjuj koordynator."""

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Pobierz dane wszystkich uczniów."""

        _LOGGER.info(
            "Vulcan: rozpoczęcie pełnego odświeżenia"
        )

        try:
            students = await self.client.get_students()

        except Exception as err:
            _LOGGER.exception(
                "Vulcan: nie udało się pobrać listy uczniów"
            )

            raise UpdateFailed(
                f"Nie udało się pobrać listy uczniów: {err}"
            ) from err

        if not students:
            _LOGGER.error(
                "Vulcan: konto nie zawiera żadnych uczniów"
            )

            raise UpdateFailed(
                "Konto Vulcan nie zawiera żadnych uczniów"
            )

        _LOGGER.info(
            "Vulcan: liczba uczniów na koncie: %s",
            len(students),
        )

        output: dict[str, Any] = {
            "updated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "students": {},
        }

        successful_students = 0

        for student in students:
            try:
                student_data = await fetch_for_student(
                    self.client,
                    student,
                )

                student_id = str(student_data["id"])

                output["students"][student_id] = student_data
                successful_students += 1

            except Exception:
                pupil = safe_get(student, "pupil")
                first_name = safe_get(
                    pupil,
                    "first_name",
                    "nieznany",
                )

                _LOGGER.exception(
                    "Vulcan: krytyczny błąd obsługi ucznia %s",
                    first_name,
                )

        if successful_students == 0:
            raise UpdateFailed(
                "Nie udało się pobrać danych żadnego ucznia"
            )

        _LOGGER.info(
            "Vulcan: zakończono pełne odświeżenie, uczniowie: %s/%s",
            successful_students,
            len(students),
        )

        return output
