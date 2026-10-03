from __future__ import annotations

from typing import Any

from .domain import Dataset, PublicStatus
from .explain import infeasible_message, move_reason
from .input_validator import ValidationError, parse_dataset, parse_outages
from .optimizer import optimize_period
from .solution_validator import validate_solution


def recover_from_raw(dataset_raw: Any, outages_raw: Any) -> dict[str, Any]:
    try:
        dataset = parse_dataset(dataset_raw)
        outages = parse_outages(outages_raw, dataset)
    except ValidationError as exc:
        return {"status": PublicStatus.INVALID_INPUT.value, "validated": False, "message": str(exc)}
    return recover(dataset, outages)


def recover(dataset: Dataset, outages) -> dict[str, Any]:
    affected_periods = sorted({pid for outage in outages for pid in outage.period_ids})
    assignments = {lesson.id: lesson.original_room_id for lesson in dataset.lessons}
    graphs = []
    for period_id in affected_periods:
        result = optimize_period(dataset, outages, period_id)
        graphs.append(result.candidate_graph)
        if result.status is PublicStatus.INFEASIBLE:
            return {
                "status": PublicStatus.INFEASIBLE.value,
                "validated": False,
                "message": "No recovery satisfies all modeled constraints.",
                "explanation": infeasible_message(dataset, result.candidate_graph),
            }
        if result.status is not PublicStatus.OPTIMAL or result.assignments is None:
            return {"status": PublicStatus.SOLVER_ERROR.value, "validated": False, "message": result.message or "The optimization solver did not return a proven optimum."}
        assignments.update(result.assignments)

    claimed_moves = sum(assignments[l.id] != l.original_room_id for l in dataset.lessons)
    checked = validate_solution(dataset, outages, assignments, claimed_moves)
    if not checked.valid:
        return {
            "status": PublicStatus.VALIDATOR_FAILURE.value,
            "validated": False,
            "message": "A proposed recovery failed internal validation and was blocked.",
            "validation_errors": list(checked.errors),
        }

    moves = []
    for lesson in dataset.lessons:
        to_room = assignments[lesson.id]
        if to_room == lesson.original_room_id:
            continue
        moves.append({
            "lesson_id": lesson.id,
            "lesson_label": lesson.label,
            "period_id": lesson.period_id,
            "from_room_id": lesson.original_room_id,
            "to_room_id": to_room,
            "reason": move_reason(dataset, lesson.id, lesson.original_room_id, to_room, outages),
        })
    moves.sort(key=lambda m: (m["period_id"], m["lesson_id"]))
    return {
        "status": PublicStatus.OPTIMAL.value,
        "validated": True,
        "move_count": checked.move_count,
        "time_change_count": 0,
        "moves": moves,
        "assignments": assignments,
    }
