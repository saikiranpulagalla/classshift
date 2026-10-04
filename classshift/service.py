from __future__ import annotations

import logging
from typing import Any

from .domain import Dataset, ProposedAssignment, PublicStatus
from .explain import infeasible_message, move_reason
from .input_validator import ValidationError, parse_dataset, parse_outages
from .optimizer import optimize_period
from .solution_validator import validate_solution

LOGGER = logging.getLogger(__name__)


def recover_from_raw(dataset_raw: Any, outages_raw: Any) -> dict[str, Any]:
    try:
        dataset = parse_dataset(dataset_raw)
        outages = parse_outages(outages_raw, dataset)
    except ValidationError as exc:
        return {
            "status": PublicStatus.INVALID_INPUT.value,
            "validated": False,
            "message": str(exc),
        }
    return recover(dataset, outages)


def recover(dataset: Dataset, outages) -> dict[str, Any]:
    # Service callers may supply any iterable; retain one stable outage snapshot
    # for period discovery, optimization, explanation, and validation.
    outages = tuple(outages)
    affected_periods = sorted({pid for outage in outages for pid in outage.period_ids})
    affected_period_set = set(affected_periods)

    # Preserve proposals as records until the independent validator has proved
    # exact lesson identity, period immutability, uniqueness and room validity.
    proposals: list[ProposedAssignment] = [
        ProposedAssignment(lesson.id, lesson.period_id, lesson.original_room_id)
        for lesson in dataset.lessons
        if lesson.period_id not in affected_period_set
    ]
    claimed_moves = 0

    for period_id in affected_periods:
        result = optimize_period(dataset, outages, period_id)
        if result.status is PublicStatus.INFEASIBLE:
            return {
                "status": PublicStatus.INFEASIBLE.value,
                "validated": False,
                "message": "No recovery satisfies all modeled constraints.",
                "explanation": infeasible_message(dataset, result.candidate_graph),
            }
        if result.status is not PublicStatus.OPTIMAL or result.assignments is None:
            return {
                "status": PublicStatus.SOLVER_ERROR.value,
                "validated": False,
                "message": "The optimization solver did not return a proven optimum.",
            }
        proposals.extend(result.assignments)
        if result.move_count is None:
            return {
                "status": PublicStatus.SOLVER_ERROR.value,
                "validated": False,
                "message": "The optimization solver did not return a complete move count.",
            }
        claimed_moves += result.move_count

    checked = validate_solution(dataset, outages, tuple(proposals), claimed_moves)
    if not checked.valid:
        LOGGER.error("Independent validator blocked recovery: %s", "; ".join(checked.errors))
        # Do not leak internal validator diagnostics through the public service
        # response. The UI only needs to know that the proposal was blocked.
        return {
            "status": PublicStatus.VALIDATOR_FAILURE.value,
            "validated": False,
            "message": "A proposed recovery failed internal validation and was blocked.",
        }

    # Safe only after validation has proved one proposal per exact lesson.
    assignments = {proposal.lesson_id: proposal.room_id for proposal in proposals}
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
            "reason": move_reason(
                dataset, lesson.id, lesson.original_room_id, to_room, outages
            ),
        })
    moves.sort(key=lambda move: (move["period_id"], move["lesson_id"]))
    return {
        "status": PublicStatus.OPTIMAL.value,
        "validated": True,
        "move_count": checked.move_count,
        "time_change_count": 0,
        "moves": moves,
        "assignments": assignments,
    }
