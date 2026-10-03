from __future__ import annotations

from itertools import product
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from classshift.domain import Dataset, StepFreeStatus
from classshift.input_validator import unavailable_pairs


def _compatible(lesson, room, unavailable) -> bool:
    if not room.enabled:
        return False
    if (room.id, lesson.period_id) in unavailable:
        return False
    if room.capacity < lesson.student_count:
        return False
    if not lesson.required_features.issubset(room.features):
        return False
    if lesson.requires_step_free and room.step_free_status is not StepFreeStatus.VERIFIED:
        return False
    if lesson.locked and room.id != lesson.original_room_id:
        return False
    return True


def brute_force_period(dataset: Dataset, outages, period_id: str) -> tuple[bool, int | None]:
    lessons = [l for l in dataset.lessons if l.period_id == period_id]
    unavailable = unavailable_pairs(outages)
    options = [[r.id for r in dataset.rooms if _compatible(l, r, unavailable)] for l in lessons]
    if any(not opts for opts in options):
        return False, None
    best = None
    for choice in product(*options):
        if len(set(choice)) != len(choice):
            continue
        cost = sum(rid != lesson.original_room_id for rid, lesson in zip(choice, lessons))
        if best is None or cost < best:
            best = cost
    return best is not None, best
