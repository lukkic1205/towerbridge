"""Zgodność pobierania sprawdzianów z aktualnym API Vulcan UONET+."""

from __future__ import annotations

from datetime import date, timedelta
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

_PATCH_APPLIED = False

EXAM_DAYS_BACK = 14
EXAM_DAYS_FORWARD = 60


def apply_exam_fetch_patch() -> None:
    """Dostosuj get_exams do aktualnego zapytania aplikacji Dzienniczek VULCAN."""

    global _PATCH_APPLIED

    if _PATCH_APPLIED:
        return

    from vulcan._data import VulcanData
    from vulcan.data import Exam

    original_get_exams = VulcanData.get_exams

    if getattr(original_get_exams, "_towerbridge_exam_fetch_compat", False):
        _PATCH_APPLIED = True
        return

    async def compatibility_get_exams(
        self: Any,
        last_sync: Any = None,
        deleted: bool = False,
        **kwargs: Any,
    ) -> list[Any]:
        """Pobierz sprawdziany po zakresie dat, bez periodId."""

        if deleted:
            return await original_get_exams(
                self,
                last_sync=last_sync,
                deleted=deleted,
                **kwargs,
            )

        student = self._api.student  # noqa: SLF001

        if student is None:
            raise AttributeError("No student is selected.")

        date_from = kwargs.pop(
            "date_from",
            date.today() - timedelta(days=EXAM_DAYS_BACK),
        )
        date_to = kwargs.pop(
            "date_to",
            date.today() + timedelta(days=EXAM_DAYS_FORWARD),
        )

        query = {
            "unitId": student.unit.id,
            "pupilId": student.pupil.id,
            "dateFrom": date_from.strftime("%Y-%m-%d"),
            "dateTo": date_to.strftime("%Y-%m-%d"),
            "lastId": "-2147483648",
            "pageSize": 500,
        }

        _LOGGER.info(
            "Vulcan: sprawdziany raw: pupil=%s zakres=%s..%s",
            student.pupil.id,
            query["dateFrom"],
            query["dateTo"],
        )

        try:
            raw_items = await self._api.get(  # noqa: SLF001
                "api/mobile/exam/byPupil",
                query,
                **kwargs,
            )

            _LOGGER.info(
                "Vulcan: sprawdziany raw: API zwróciło %s rekordów",
                len(raw_items or []),
            )

            return [
                Exam.load(item)
                for item in (raw_items or [])
            ]

        except Exception:
            _LOGGER.exception(
                "Vulcan: bezpośrednie pobranie sprawdzianów nie powiodło się; "
                "próba starej metody"
            )

            return await original_get_exams(
                self,
                last_sync=last_sync,
                deleted=deleted,
                date_from=date_from,
                date_to=date_to,
                **kwargs,
            )

    compatibility_get_exams._towerbridge_exam_fetch_compat = True
    VulcanData.get_exams = compatibility_get_exams

    _PATCH_APPLIED = True

    _LOGGER.warning(
        "Vulcan UONET+: aktywowano pobieranie sprawdzianów po zakresie dat"
    )
