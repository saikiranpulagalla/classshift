from __future__ import annotations

from dataclasses import dataclass

from .domain import Dataset, StepFreeStatus


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...]
    move_count: int | None


def validate_solution(dataset: Dataset, outages, assignments: dict[str, str], claimed_move_count: int | None = None) -> ValidationResult:
    errors: list[str] = []
    expected_ids = {l.id for l in dataset.lessons}
    actual_ids = set(assignments)
    missing = sorted(expected_ids - actual_ids)
    invented = sorted(actual_ids - expected_ids)
    if missing:
        errors.append(f"missing lessons: {', '.join(missing)}")
    if invented:
        errors.append(f"invented lessons: {', '.join(invented)}")

    room_by_id = dataset.room_by_id
    # Deliberately compute outage pairs locally: validation must remain independent
    # from production candidate/eligibility helpers and their supporting logic.
    unavailable = frozenset((outage.room_id, pid) for outage in outages for pid in outage.period_ids)
    occupancy: set[tuple[str, str]] = set()
    move_count = 0

    for lesson in dataset.lessons:
        if lesson.id not in assignments:
            continue
        rid = assignments[lesson.id]
        if type(rid) is not str or rid not in room_by_id:
            errors.append(f"{lesson.id}: assigned room does not exist")
            continue
        room = room_by_id[rid]
        if not room.enabled:
            errors.append(f"{lesson.id}: assigned room is disabled")
        if (rid, lesson.period_id) in unavailable:
            errors.append(f"{lesson.id}: assigned room is unavailable")
        if room.capacity < lesson.student_count:
            errors.append(f"{lesson.id}: room capacity is insufficient")
        if not lesson.required_features.issubset(room.features):
            errors.append(f"{lesson.id}: required features are missing")
        if lesson.requires_step_free and room.step_free_status is not StepFreeStatus.VERIFIED:
            errors.append(f"{lesson.id}: verified step-free metadata is required")
        if lesson.locked and rid != lesson.original_room_id:
            errors.append(f"{lesson.id}: locked lesson moved")
        key = (lesson.period_id, rid)
        if key in occupancy:
            errors.append(f"{lesson.period_id}: room {rid} is double-booked")
        occupancy.add(key)
        if rid != lesson.original_room_id:
            move_count += 1

    if claimed_move_count is not None:
        if type(claimed_move_count) is not int or claimed_move_count != move_count:
            errors.append(f"claimed move_count {claimed_move_count!r} does not match recomputed {move_count}")
    return ValidationResult(not errors, tuple(errors), move_count if not missing and not invented else None)
