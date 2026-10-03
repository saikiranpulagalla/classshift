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
    if graph is None:
        return "No complete room assignment satisfies all modeled constraints simultaneously."
    zero = [lid for lid, rooms in graph.eligible.items() if not rooms]
    if not zero:
        return "Individual compatible rooms exist, but no complete room assignment satisfies all modeled constraints simultaneously without a room conflict."
    lesson = dataset.lesson_by_id[zero[0]]
    rejected = graph.rejected.get(lesson.id, {})
    all_codes = {code for codes in rejected.values() for code in codes}
    if RejectionCode.MISSING_FEATURE in all_codes:
        return f"No available room satisfies {lesson.label}'s modeled room requirements; required features are among the blocking constraints."
    if RejectionCode.CAPACITY in all_codes:
        return f"No available compatible room has sufficient capacity for {lesson.label}."
    if RejectionCode.LOCKED in all_codes or RejectionCode.ROOM_UNAVAILABLE in all_codes:
        return f"{lesson.label} cannot be assigned while preserving its modeled lock and outage constraints."
    return f"No available room satisfies all modeled constraints for {lesson.label}."
