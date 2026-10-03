from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Mapping, Tuple


class StepFreeStatus(str, Enum):
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    UNKNOWN = "UNKNOWN"


class PublicStatus(str, Enum):
    OPTIMAL = "OPTIMAL"
    INFEASIBLE = "INFEASIBLE"
    INVALID_INPUT = "INVALID_INPUT"
    SOLVER_ERROR = "SOLVER_ERROR"
    VALIDATOR_FAILURE = "VALIDATOR_FAILURE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True)
class Period:
    id: str
    label: str
    order: int | None = None


@dataclass(frozen=True)
class Room:
    id: str
    label: str
    capacity: int
    features: FrozenSet[str]
    step_free_status: StepFreeStatus
    enabled: bool


@dataclass(frozen=True)
class Lesson:
    id: str
    label: str
    period_id: str
    original_room_id: str
    student_count: int
    required_features: FrozenSet[str]
    requires_step_free: bool
    locked: bool


@dataclass(frozen=True)
class Outage:
    room_id: str
    period_ids: FrozenSet[str]
    reason: str = ""


@dataclass(frozen=True)
class Dataset:
    periods: Tuple[Period, ...]
    rooms: Tuple[Room, ...]
    lessons: Tuple[Lesson, ...]

    @property
    def period_by_id(self) -> Mapping[str, Period]:
        return {p.id: p for p in self.periods}

    @property
    def room_by_id(self) -> Mapping[str, Room]:
        return {r.id: r for r in self.rooms}

    @property
    def lesson_by_id(self) -> Mapping[str, Lesson]:
        return {l.id: l for l in self.lessons}
