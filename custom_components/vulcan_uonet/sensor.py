"""Sensory integracji Vulcan UONET+."""

from __future__ import annotations

from datetime import date
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
    """Utwórz sensory uczniów."""

    coordinator = entry.runtime_data.coordinator
    students = coordinator.data.get("students", {})

    entities: list[VulcanStudentSensor] = []

    for student_id in students:
        entities.append(
            VulcanStudentSensor(
                coordinator=coordinator,
                entry=entry,
                student_id=student_id,
            )
        )

    async_add_entities(entities)


class VulcanStudentSensor(
    CoordinatorEntity[VulcanUonetCoordinator],
    SensorEntity,
):
    """Sensor planu lekcji jednego ucznia."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:school"

    def __init__(
        self,
        coordinator: VulcanUonetCoordinator,
        entry: VulcanUonetConfigEntry,
        student_id: str,
    ) -> None:
        """Zainicjuj sensor ucznia."""

        super().__init__(coordinator)

        self._entry = entry
        self._student_id = student_id

        student = self._student_data

        first_name = student.get("first_name", "Uczeń")
        full_name = student.get("full_name", first_name)

        self._attr_name = f"Plan lekcji {first_name}"
        self._attr_unique_id = (
            f"{entry.entry_id}_student_{student_id}_lessons"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{entry.entry_id}_{student_id}",
                )
            },
            name=full_name,
            manufacturer="Vulcan",
            model="UONET+",
            configuration_url="https://uonetplus.vulcan.net.pl/",
        )

    @property
    def _student_data(self) -> dict[str, Any]:
        """Zwróć aktualne dane ucznia."""

        return self.coordinator.data.get(
            "students",
            {},
        ).get(
            self._student_id,
            {},
        )

    @property
    def native_value(self) -> int:
        """Zwróć liczbę dzisiejszych lekcji."""

        return len(self._lessons_for_date(date.today().isoformat()))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Zwróć dane planu jako atrybuty encji."""

        student = self._student_data

        today = date.today()
        tomorrow = date.fromordinal(today.toordinal() + 1)

        all_lessons = student.get("lessons", [])

        return {
            "student_id": student.get("id"),
            "first_name": student.get("first_name"),
            "last_name": student.get("last_name"),
            "full_name": student.get("full_name"),
            "class": student.get("class"),
            "unit": student.get("unit"),
            "school": student.get("school"),
            "updated_at": student.get("updated_at"),
            "range": student.get("range"),
            "today": self._lessons_for_date(
                today.isoformat()
            ),
            "tomorrow": self._lessons_for_date(
                tomorrow.isoformat()
            ),
            "lessons": all_lessons,
        }

    def _lessons_for_date(
        self,
        lesson_date: str,
    ) -> list[dict[str, Any]]:
        """Zwróć lekcje z wybranego dnia."""

        lessons = self._student_data.get("lessons", [])

        return [
            lesson
            for lesson in lessons
            if lesson.get("date") == lesson_date
        ]
