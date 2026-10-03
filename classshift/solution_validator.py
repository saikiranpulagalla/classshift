from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .domain import Dataset, ProposedAssignment, StepFreeStatus


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...]
    move_count: int | None


def validate_solution(
    dataset: Dataset,
    outages,
    assignments: Sequence[ProposedAssignment],
    claimed_move_count: int | None = None,
) -> ValidationResult:
    """Independently validate a complete proposed schedule.

    This intentionally does not call candidate-generation helpers. It accepts a
    sequence rather than a mapping so duplicate lesson proposals remain visible
    and period immutability can be checked directly.
    """

    errors: list[str] = []
    expected_ids = {lesson.id for lesson in dataset.lessons}
    lesson_by_id = dataset.lesson_by_id
    room_by_id = dataset.room_by_id

    seen_ids: set[str] = set()
    represented_ids: set[str] = set()
    occupancy: set[tuple[str, str]] = set()
    move_count = 0
    duplicate_found = False
    invented_found = False

    # Deliberately compute outage pairs locally: validation must remain
    # independent from production candidate/eligibility helpers.
    unavailable = frozenset(
        (outage.room_id, period_id)
        for outage in outages
        for period_id in outage.period_ids
    )

    for index, assignment in enumerate(assignments):
        if type(assignment) is not ProposedAssignment:
            errors.append(f"assignment[{index}]: malformed assignment record")
            continue

        lesson_id = assignment.lesson_id
        if type(lesson_id) is not str:
            errors.append(f"assignment[{index}]: lesson_id must be a string")
            continue

        if lesson_id in seen_ids:
            duplicate_found = True
            errors.append(f"duplicated lesson assignment: {lesson_id}")
        seen_ids.add(lesson_id)

        lesson = lesson_by_id.get(lesson_id)
        if lesson is None:
            invented_found = True
            errors.append(f"invented lesson: {lesson_id}")
            continue
        represented_ids.add(lesson_id)

        if type(assignment.period_id) is not str or assignment.period_id != lesson.period_id:
            errors.append(
                f"{lesson.id}: period changed from {lesson.period_id} to {assignment.period_id!r}"
            )

        room_id = assignment.room_id
        if type(room_id) is not str or room_id not in room_by_id:
            errors.append(f"{lesson.id}: assigned room does not exist")
            continue
        room = room_by_id[room_id]

        if not room.enabled:
            errors.append(f"{lesson.id}: assigned room is disabled")
        if (room_id, lesson.period_id) in unavailable:
            errors.append(f"{lesson.id}: assigned room is unavailable")
        if room.capacity < lesson.student_count:
            errors.append(f"{lesson.id}: room capacity is insufficient")
        if not lesson.required_features.issubset(room.features):
            errors.append(f"{lesson.id}: required features are missing")
        if lesson.requires_step_free and room.step_free_status is not StepFreeStatus.VERIFIED:
            errors.append(f"{lesson.id}: verified step-free metadata is required")
        if lesson.locked and room_id != lesson.original_room_id:
            errors.append(f"{lesson.id}: locked lesson moved")

        # Use the immutable baseline lesson period for conflict checking. A
        # corrupted proposed period is already an error and must never be able
        # to hide a same-period room conflict.
        occupancy_key = (lesson.period_id, room_id)
        if occupancy_key in occupancy:
            errors.append(f"{lesson.period_id}: room {room_id} is double-booked")
        occupancy.add(occupancy_key)

        if room_id != lesson.original_room_id:
            move_count += 1

    missing = sorted(expected_ids - represented_ids)
    if missing:
        errors.append(f"missing lessons: {', '.join(missing)}")

    if claimed_move_count is not None:
        if type(claimed_move_count) is not int or claimed_move_count != move_count:
            errors.append(
                f"claimed move_count {claimed_move_count!r} does not match recomputed {move_count}"
            )

    structural_failure = bool(missing) or duplicate_found or invented_found
    return ValidationResult(
        valid=not errors,
        errors=tuple(errors),
        move_count=None if structural_failure else move_count,
    )
