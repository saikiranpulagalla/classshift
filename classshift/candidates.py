from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .domain import Dataset, Lesson, Room, StepFreeStatus
from .input_validator import unavailable_pairs


class RejectionCode(str, Enum):
    ROOM_DISABLED = "ROOM_DISABLED"
    ROOM_UNAVAILABLE = "ROOM_UNAVAILABLE"
    CAPACITY = "CAPACITY"
    MISSING_FEATURE = "MISSING_FEATURE"
    STEP_FREE_REQUIRED = "STEP_FREE_REQUIRED"
    LOCKED = "LOCKED"


@dataclass(frozen=True)
class CandidateGraph:
    period_id: str
    eligible: dict[str, tuple[str, ...]]
    rejected: dict[str, dict[str, tuple[RejectionCode, ...]]]


def _reasons(lesson: Lesson, room: Room, unavailable: frozenset[tuple[str, str]]) -> tuple[RejectionCode, ...]:
    reasons: list[RejectionCode] = []
    if not room.enabled:
        reasons.append(RejectionCode.ROOM_DISABLED)
    if (room.id, lesson.period_id) in unavailable:
        reasons.append(RejectionCode.ROOM_UNAVAILABLE)
    if room.capacity < lesson.student_count:
        reasons.append(RejectionCode.CAPACITY)
    if not lesson.required_features.issubset(room.features):
        reasons.append(RejectionCode.MISSING_FEATURE)
    if lesson.requires_step_free and room.step_free_status is not StepFreeStatus.VERIFIED:
        reasons.append(RejectionCode.STEP_FREE_REQUIRED)
    if lesson.locked and room.id != lesson.original_room_id:
        reasons.append(RejectionCode.LOCKED)
    return tuple(reasons)


def build_candidate_graph(dataset: Dataset, outages, period_id: str) -> CandidateGraph:
    unavailable = unavailable_pairs(outages)
    lessons = [l for l in dataset.lessons if l.period_id == period_id]
    eligible: dict[str, tuple[str, ...]] = {}
    rejected: dict[str, dict[str, tuple[RejectionCode, ...]]] = {}
    for lesson in lessons:
        ok: list[str] = []
        bad: dict[str, tuple[RejectionCode, ...]] = {}
        for room in dataset.rooms:
            reasons = _reasons(lesson, room, unavailable)
            if reasons:
                bad[room.id] = reasons
            else:
                ok.append(room.id)
        eligible[lesson.id] = tuple(ok)
        rejected[lesson.id] = bad
    return CandidateGraph(period_id, eligible, rejected)
