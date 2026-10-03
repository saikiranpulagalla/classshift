from __future__ import annotations

from itertools import product
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from classshift.domain import Dataset, StepFreeStatus


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


def brute_force_period_details(dataset: Dataset, outages, period_id: str) -> tuple[bool, int | None, int]:
    """Return feasibility, exact minimum moves, and number of optimal assignments."""
    lessons = [l for l in dataset.lessons if l.period_id == period_id]
    # Deliberately rebuild outage membership here instead of sharing production
    # eligibility/support helpers; this oracle is an independent correctness check.
    unavailable = frozenset((outage.room_id, pid) for outage in outages for pid in outage.period_ids)
    options = [[r.id for r in dataset.rooms if _compatible(l, r, unavailable)] for l in lessons]
    if any(not opts for opts in options):
        return False, None, 0
    best = None
    optimal_count = 0
    for choice in product(*options):
        if len(set(choice)) != len(choice):
            continue
        cost = sum(rid != lesson.original_room_id for rid, lesson in zip(choice, lessons))
        if best is None or cost < best:
            best = cost
            optimal_count = 1
        elif cost == best:
            optimal_count += 1
    return best is not None, best, optimal_count


def brute_force_period(dataset: Dataset, outages, period_id: str) -> tuple[bool, int | None]:
    feasible, best, _optimal_count = brute_force_period_details(dataset, outages, period_id)
    return feasible, best
