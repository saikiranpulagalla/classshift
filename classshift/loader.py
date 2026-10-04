from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .domain import Dataset
from .input_validator import parse_dataset


class DuplicateJsonKeyError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=_reject_duplicate_keys)


def load_dataset(path: str | Path) -> Dataset:
    return parse_dataset(load_json(path))


def dataset_to_public_dict(dataset: Dataset) -> dict[str, list[dict[str, Any]]]:
    """Serialize only the canonical synthetic-demo fields used by the UI.

    The function accepts an already validated Dataset, so arbitrary keys from a
    JSON file can never flow directly to `/api/demo`.
    """

    periods = [
        {
            "id": period.id,
            "label": period.label,
            **({"order": period.order} if period.order is not None else {}),
        }
        for period in dataset.periods
    ]
    rooms = [
        {
            "id": room.id,
            "label": room.label,
            "capacity": room.capacity,
            "features": sorted(room.features),
            "step_free_status": room.step_free_status.value,
            "enabled": room.enabled,
        }
        for room in dataset.rooms
    ]
    lessons = [
        {
            "id": lesson.id,
            "label": lesson.label,
            "period_id": lesson.period_id,
            "original_room_id": lesson.original_room_id,
            "student_count": lesson.student_count,
            "required_features": sorted(lesson.required_features),
            "requires_step_free": lesson.requires_step_free,
            "locked": lesson.locked,
        }
        for lesson in dataset.lessons
    ]
    return {"periods": periods, "rooms": rooms, "lessons": lessons}
