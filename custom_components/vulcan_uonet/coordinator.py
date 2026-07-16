"""Koordynator danych integracji Vulcan UONET+."""

from __future__ import annotations

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


def to_iso_date(value: Any) -> str | None:
    """Zamień datę biblioteki Vulcan na tekst ISO."""

    if value is None:
        return None

    nested_date = safe_get(value, "date")

    if nested_date:
        return nested_date.isoformat()

    if isinstance(value, datetime):
        return value.date().isoformat()

    if isinstance(value, date):
        return value.isoformat()

    return str(value)


def lesson_to_dict(lesson: Any) -> dict[str, Any]:
    """Zamień lekcję Vulcan na prosty słownik."""

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
        "date": to_iso_date(safe_get(lesson, "date")),
        "position": safe_get(time_slot, "position"),
        "time": safe_get(time_slot, "displayed_time"),
        "start": str(safe_get(time_slot, "from_", ""))[:5],
        "end": str(safe_get(time_slot, "to", ""))[:5],
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
        "change_type": safe_get(changes, "type"),
        "event": str(event) if event else None,
    }


async def fetch_student_lessons(
    client: Vulcan,
    student: Any,
) -> dict[str, Any]:
    """Pobierz plan jednego ucznia."""

    # Biblioteka Vulcan oficjalnie wybiera tylko pierwszego ucznia.
    # Ten mechanizm umożliwia obsługę wszystkich uczniów konta.
    client._api.student = student  # noqa: SLF001

    start = date.today() - timedelta(days=DAYS_BACK)
    end = date.today() + timedelta(days=DAYS_FORWARD)

    lessons: list[dict[str, Any]] = []

    lesson_generator = await client.data.get_lessons(
        date_from=start,
        date_to=end,
    )

    async for lesson in lesson_generator:
        item = lesson_to_dict(lesson)

        if item["visible"]:
            lessons.append(item)

    lessons.sort(
        key=lambda item: (
            item.get("date") or "",
            item.get("position") or 0,
        )
    )

    pupil = safe_get(student, "pupil")
    unit = safe_get(student, "unit")
    school = safe_get(student, "school")

    first_name = safe_get(pupil, "first_name", "Uczeń")
    last_name = safe_get(pupil, "last_name", "")
    pupil_id = safe_get(pupil, "id")

    full_name = f"{first_name} {last_name}".strip()

    return {
        "id": pupil_id,
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name,
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
    }


class VulcanUonetCoordinator(
    DataUpdateCoordinator[dict[str, Any]]
):
    """Koordynator pobierania danych Vulcan UONET+."""

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

        try:
            students = await self.client.get_students()

            if not students:
                raise UpdateFailed(
                    "Konto Vulcan nie zawiera żadnych uczniów"
                )

            output: dict[str, Any] = {
                "updated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
                "students": {},
            }

            for student in students:
                student_data = await fetch_student_lessons(
                    self.client,
                    student,
                )

                student_id = str(student_data["id"])
                output["students"][student_id] = student_data

            return output

        except UpdateFailed:
            raise

        except Exception as err:
            raise UpdateFailed(
                f"Nie udało się pobrać danych z Vulcan: {err}"
            ) from err
