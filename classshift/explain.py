from __future__ import annotations

from .candidates import CandidateGraph, RejectionCode
from .domain import Dataset


def move_reason(dataset: Dataset, lesson_id: str, from_room_id: str, to_room_id: str, outages) -> str:
    lesson = dataset.lesson_by_id[lesson_id]
    room = dataset.room_by_id[to_room_id]
    unavailable = any(o.room_id == from_room_id and lesson.period_id in o.period_ids for o in outages)
    if unavailable:
        return f"{lesson.label} moved to {room.label} because its original room is unavailable and this room satisfies the modeled capacity, feature, accessibility-metadata, and lock constraints."
    return f"{lesson.label} moved to {room.label} as part of the minimum-change complete assignment for this period while satisfying the modeled hard constraints."


def infeasible_message(dataset: Dataset, graph: CandidateGraph | None) -> str:
    """Return only explanations that are directly proven by the candidate graph.

    The assignment solver is the feasibility authority. These diagnostics explain a
    zero-candidate lesson when a simple universal reason is provable; otherwise they
    deliberately fall back to conservative wording rather than inferring a minimal
    conflict set.
    """
    if graph is None:
        return "No complete room assignment satisfies all modeled constraints simultaneously."

    zero = [lid for lid, rooms in graph.eligible.items() if not rooms]
    if not zero:
        return "Individual compatible rooms exist, but no complete room assignment satisfies all modeled constraints simultaneously without a room conflict."

    lesson = dataset.lesson_by_id[zero[0]]
    rejected = graph.rejected.get(lesson.id, {})

    # A locked lesson can use only its original room. If that room itself is
    # unavailable/disabled, the lock/outage conflict is directly demonstrated.
    original_codes = set(rejected.get(lesson.original_room_id, ()))
    if lesson.locked and original_codes.intersection({RejectionCode.ROOM_UNAVAILABLE, RejectionCode.ROOM_DISABLED}):
        return f"{lesson.label} is locked to its original room, which is unavailable for this recovery."

    # For feature/capacity/accessibility explanations, consider rooms that are
    # physically enabled and not failed in this period. A statement is made only
    # when every such room is rejected for that same reason.
    available_codes = [
        set(codes)
        for codes in rejected.values()
        if RejectionCode.ROOM_DISABLED not in codes and RejectionCode.ROOM_UNAVAILABLE not in codes
    ]
    if available_codes:
        if lesson.required_features and all(RejectionCode.MISSING_FEATURE in codes for codes in available_codes):
            return f"No available room satisfies {lesson.label}'s required room features."
        if all(RejectionCode.CAPACITY in codes for codes in available_codes):
            return f"No available room has sufficient capacity for {lesson.label}."
        if lesson.requires_step_free and all(RejectionCode.STEP_FREE_REQUIRED in codes for codes in available_codes):
            return f"No available room has VERIFIED step-free metadata for {lesson.label}."

    return f"No available room satisfies all modeled constraints for {lesson.label}."
