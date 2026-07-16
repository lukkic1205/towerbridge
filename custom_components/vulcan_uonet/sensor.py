"""Sensory integracji Vulcan UONET+."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import VulcanUonetConfigEntry
from .const import DOMAIN
from .coordinator import VulcanUonetCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VulcanUonetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Utwórz encje dla wszystkich uczniów."""

    coordinator = entry.runtime_data.coordinator
    students = coordinator.data.get("students", {})

    entities: list[SensorEntity] = []

    for student_id in students:
        entities.extend(
            [
                VulcanLessonsTodaySensor(
                    coordinator,
                    entry,
                    student_id,
                ),
                VulcanLessonsTomorrowSensor(
                    coordinator,
                    entry,
                    student_id,
                ),
                VulcanExamsSensor(
                    coordinator,
                    entry,
                    student_id,
                ),
                VulcanGradesSensor(
                    coordinator,
                    entry,
                    student_id,
                ),
                VulcanHomeworkSensor(
                    coordinator,
                    entry,
                    student_id,
                ),
                VulcanAttendanceSensor(
                    coordinator,
                    entry,
                    student_id,
                ),
                VulcanLuckyNumberSensor(
                    coordinator,
                    entry,
                    student_id,
                ),
            ]
        )

    async_add_entities(entities)


def parse_iso_datetime(value: Any) -> datetime | None:
    """Zamień tekst ISO na datetime."""

    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(str(value))

        if parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)

        return parsed

    except (TypeError, ValueError):
        pass

    try:
        parsed_date = date.fromisoformat(str(value)[:10])

        return datetime.combine(
            parsed_date,
            datetime.min.time(),
        )

    except (TypeError, ValueError):
        return None


class VulcanStudentEntity(
    CoordinatorEntity[VulcanUonetCoordinator],
    SensorEntity,
):
    """Wspólna klasa encji ucznia."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VulcanUonetCoordinator,
        entry: VulcanUonetConfigEntry,
        student_id: str,
        sensor_key: str,
        sensor_name: str,
        icon: str,
    ) -> None:
        """Zainicjuj encję."""

        super().__init__(coordinator)

        self._entry = entry
        self._student_id = student_id
        self._sensor_key = sensor_key

        student = self.student_data
        full_name = student.get("full_name", "Uczeń")

        self._attr_name = sensor_name
        self._attr_icon = icon
        self._attr_unique_id = (
            f"{entry.entry_id}_{student_id}_{sensor_key}"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{entry.entry_id}_{student_id}",
                )
            },
            name=f"{full_name} – Vulcan UONET+",
            manufacturer="Vulcan",
            model="UONET+",
        )

    @property
    def student_data(self) -> dict[str, Any]:
        """Zwróć aktualne dane ucznia."""

        if not self.coordinator.data:
            return {}

        return self.coordinator.data.get(
            "students",
            {},
        ).get(
            self._student_id,
            {},
        )

    @property
    def common_attributes(self) -> dict[str, Any]:
        """Zwróć wspólne atrybuty ucznia."""

        student = self.student_data

        return {
            "student_id": student.get("id"),
            "first_name": student.get("first_name"),
            "last_name": student.get("last_name"),
            "full_name": student.get("full_name"),
            "class": student.get("class"),
            "unit": student.get("unit"),
            "school": student.get("school"),
            "updated_at": student.get("updated_at"),
        }


class VulcanLessonsTodaySensor(VulcanStudentEntity):
    """Dzisiejsze lekcje."""

    def __init__(
        self,
        coordinator: VulcanUonetCoordinator,
        entry: VulcanUonetConfigEntry,
        student_id: str,
    ) -> None:
        """Zainicjuj sensor."""

        super().__init__(
            coordinator,
            entry,
            student_id,
            "lessons_today",
            "Lekcje dzisiaj",
            "mdi:calendar-today",
        )

    @property
    def lessons(self) -> list[dict[str, Any]]:
        """Zwróć dzisiejsze lekcje."""

        today = date.today().isoformat()

        return [
            lesson
            for lesson in self.student_data.get("lessons", [])
            if str(lesson.get("date", ""))[:10] == today
        ]

    @property
    def native_value(self) -> int:
        """Zwróć liczbę lekcji."""

        return len(self.lessons)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Zwróć plan lekcji."""

        return {
            **self.common_attributes,
            "date": date.today().isoformat(),
            "lessons": self.lessons,
        }


class VulcanLessonsTomorrowSensor(VulcanStudentEntity):
    """Jutrzejsze lekcje."""

    def __init__(
        self,
        coordinator: VulcanUonetCoordinator,
        entry: VulcanUonetConfigEntry,
        student_id: str,
    ) -> None:
        """Zainicjuj sensor."""

        super().__init__(
            coordinator,
            entry,
            student_id,
            "lessons_tomorrow",
            "Lekcje jutro",
            "mdi:calendar-arrow-right",
        )

    @property
    def tomorrow(self) -> date:
        """Zwróć datę jutra."""

        return date.today() + timedelta(days=1)

    @property
    def lessons(self) -> list[dict[str, Any]]:
        """Zwróć jutrzejsze lekcje."""

        tomorrow = self.tomorrow.isoformat()

        return [
            lesson
            for lesson in self.student_data.get("lessons", [])
            if str(lesson.get("date", ""))[:10] == tomorrow
        ]

    @property
    def native_value(self) -> int:
        """Zwróć liczbę lekcji."""

        return len(self.lessons)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Zwróć plan lekcji."""

        return {
            **self.common_attributes,
            "date": self.tomorrow.isoformat(),
            "lessons": self.lessons,
        }


class VulcanExamsSensor(VulcanStudentEntity):
    """Nadchodzące sprawdziany."""

    def __init__(
        self,
        coordinator: VulcanUonetCoordinator,
        entry: VulcanUonetConfigEntry,
        student_id: str,
    ) -> None:
        """Zainicjuj sensor."""

        super().__init__(
            coordinator,
            entry,
            student_id,
            "exams",
            "Nadchodzące sprawdziany",
            "mdi:file-document-alert",
        )

    @property
    def exams(self) -> list[dict[str, Any]]:
        """Zwróć przyszłe sprawdziany."""

        now = datetime.now()
        result: list[dict[str, Any]] = []

        for exam in self.student_data.get("exams", []):
            deadline = parse_iso_datetime(
                exam.get("deadline")
            )

            if deadline is None or deadline >= now:
                result.append(exam)

        result.sort(
            key=lambda item: item.get("deadline") or ""
        )

        return result

    @property
    def native_value(self) -> int:
        """Zwróć liczbę sprawdzianów."""

        return len(self.exams)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Zwróć dane sprawdzianów."""

        return {
            **self.common_attributes,
            "next_exam": self.exams[0] if self.exams else None,
            "exams": self.exams[:20],
        }


class VulcanGradesSensor(VulcanStudentEntity):
    """Ostatnie oceny."""

    def __init__(
        self,
        coordinator: VulcanUonetCoordinator,
        entry: VulcanUonetConfigEntry,
        student_id: str,
    ) -> None:
        """Zainicjuj sensor."""

        super().__init__(
            coordinator,
            entry,
            student_id,
            "grades",
            "Oceny",
            "mdi:star-box",
        )

    @property
    def grades(self) -> list[dict[str, Any]]:
        """Zwróć oceny."""

        return self.student_data.get("grades", [])

    @property
    def native_value(self) -> int:
        """Zwróć liczbę pobranych ocen."""

        return len(self.grades)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Zwróć ostatnie oceny."""

        return {
            **self.common_attributes,
            "latest_grade": self.grades[0] if self.grades else None,
            "grades": self.grades[:30],
        }


class VulcanHomeworkSensor(VulcanStudentEntity):
    """Aktualne zadania domowe."""

    def __init__(
        self,
        coordinator: VulcanUonetCoordinator,
        entry: VulcanUonetConfigEntry,
        student_id: str,
    ) -> None:
        """Zainicjuj sensor."""

        super().__init__(
            coordinator,
            entry,
            student_id,
            "homework",
            "Zadania domowe",
            "mdi:book-open-page-variant",
        )

    @property
    def homework(self) -> list[dict[str, Any]]:
        """Zwróć zadania z przyszłym terminem."""

        now = datetime.now()
        result: list[dict[str, Any]] = []

        for homework in self.student_data.get("homework", []):
            deadline = parse_iso_datetime(
                homework.get("deadline")
            )

            if deadline is None or deadline >= now:
                result.append(homework)

        result.sort(
            key=lambda item: item.get("deadline") or ""
        )

        return result

    @property
    def native_value(self) -> int:
        """Zwróć liczbę aktualnych zadań."""

        return len(self.homework)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Zwróć zadania domowe."""

        return {
            **self.common_attributes,
            "next_homework": (
                self.homework[0]
                if self.homework
                else None
            ),
            "homework": self.homework[:20],
        }


class VulcanAttendanceSensor(VulcanStudentEntity):
    """Frekwencja ucznia."""

    def __init__(
        self,
        coordinator: VulcanUonetCoordinator,
        entry: VulcanUonetConfigEntry,
        student_id: str,
    ) -> None:
        """Zainicjuj sensor."""

        super().__init__(
            coordinator,
            entry,
            student_id,
            "attendance",
            "Wpisy frekwencji",
            "mdi:account-check",
        )

    @property
    def attendance(self) -> list[dict[str, Any]]:
        """Zwróć wpisy frekwencji."""

        return self.student_data.get("attendance", [])

    @property
    def native_value(self) -> int:
        """Zwróć liczbę wpisów."""

        return len(self.attendance)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Zwróć wpisy frekwencji."""

        return {
            **self.common_attributes,
            "attendance": self.attendance[:50],
        }


class VulcanLuckyNumberSensor(VulcanStudentEntity):
    """Szczęśliwy numerek."""

    def __init__(
        self,
        coordinator: VulcanUonetCoordinator,
        entry: VulcanUonetConfigEntry,
        student_id: str,
    ) -> None:
        """Zainicjuj sensor."""

        super().__init__(
            coordinator,
            entry,
            student_id,
            "lucky_number",
            "Szczęśliwy numerek",
            "mdi:clover",
        )

    @property
    def lucky_number(self) -> dict[str, Any]:
        """Zwróć szczęśliwy numerek."""

        return self.student_data.get(
            "lucky_number",
            {},
        )

    @property
    def native_value(self) -> int | None:
        """Zwróć numer."""

        return self.lucky_number.get("number")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Zwróć szczegóły numerka."""

        return {
            **self.common_attributes,
            "date": self.lucky_number.get("date"),
        }
