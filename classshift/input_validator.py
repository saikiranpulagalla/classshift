from __future__ import annotations

import re
from typing import Any, Iterable

from .domain import Dataset, Lesson, Outage, Period, Room, StepFreeStatus

FEATURE_RE = re.compile(r"^[a-z0-9_]+$")
ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


class ValidationError(ValueError):
    pass


def _require_dict(value: Any, path: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise ValidationError(f"{path} must be an object")
    return value


def _require_list(value: Any, path: str) -> list[Any]:
    if type(value) is not list:
        raise ValidationError(f"{path} must be a list")
    return value


def _strict_bool(value: Any, path: str) -> bool:
    if type(value) is not bool:
        raise ValidationError(f"{path} must be a boolean")
    return value


def _positive_int(value: Any, path: str) -> int:
    if type(value) is not int:
        raise ValidationError(f"{path} must be an integer")
    if value <= 0:
        raise ValidationError(f"{path} must be greater than 0")
    return value


def _optional_int(value: Any, path: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int:
        raise ValidationError(f"{path} must be an integer or null")
    return value


def _clean_id(value: Any, path: str) -> str:
    if type(value) is not str:
        raise ValidationError(f"{path} must be a string")
    cleaned = value.strip()
    if not cleaned or not ID_RE.fullmatch(cleaned):
        raise ValidationError(f"{path} is malformed")
    return cleaned


def _clean_label(value: Any, path: str) -> str:
    if type(value) is not str:
        raise ValidationError(f"{path} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ValidationError(f"{path} must not be empty")
    return cleaned


def _features(value: Any, path: str) -> frozenset[str]:
    raw = _require_list(value, path)
    result: set[str] = set()
    for idx, item in enumerate(raw):
        if type(item) is not str:
            raise ValidationError(f"{path}[{idx}] must be a string")
        feature = item.strip().lower()
        if not feature or not FEATURE_RE.fullmatch(feature):
            raise ValidationError(f"{path}[{idx}] is malformed")
        result.add(feature)
    return frozenset(result)


def _reject_extra(obj: dict[str, Any], allowed: set[str], path: str) -> None:
    extras = set(obj) - allowed
    if extras:
        raise ValidationError(f"{path} has unexpected field(s): {', '.join(sorted(extras))}")


def parse_dataset(payload: Any) -> Dataset:
    obj = _require_dict(payload, "dataset")
    _reject_extra(obj, {"periods", "rooms", "lessons"}, "dataset")
    for field in ("periods", "rooms", "lessons"):
        if field not in obj:
            raise ValidationError(f"dataset.{field} is required")

    periods_raw = _require_list(obj["periods"], "dataset.periods")
    rooms_raw = _require_list(obj["rooms"], "dataset.rooms")
    lessons_raw = _require_list(obj["lessons"], "dataset.lessons")

    periods: list[Period] = []
    seen_periods: set[str] = set()
    for i, raw in enumerate(periods_raw):
        item = _require_dict(raw, f"dataset.periods[{i}]")
        _reject_extra(item, {"id", "label", "order"}, f"dataset.periods[{i}]")
        if "id" not in item or "label" not in item:
            raise ValidationError(f"dataset.periods[{i}] requires id and label")
        pid = _clean_id(item["id"], f"dataset.periods[{i}].id")
        if pid in seen_periods:
            raise ValidationError(f"duplicate period id: {pid}")
        seen_periods.add(pid)
        periods.append(Period(pid, _clean_label(item["label"], f"dataset.periods[{i}].label"), _optional_int(item.get("order"), f"dataset.periods[{i}].order")))

    rooms: list[Room] = []
    seen_rooms: set[str] = set()
    for i, raw in enumerate(rooms_raw):
        item = _require_dict(raw, f"dataset.rooms[{i}]")
        _reject_extra(item, {"id", "label", "capacity", "features", "step_free_status", "enabled"}, f"dataset.rooms[{i}]")
        required = {"id", "label", "capacity", "features", "step_free_status", "enabled"}
        missing = required - set(item)
        if missing:
            raise ValidationError(f"dataset.rooms[{i}] missing: {', '.join(sorted(missing))}")
        rid = _clean_id(item["id"], f"dataset.rooms[{i}].id")
        if rid in seen_rooms:
            raise ValidationError(f"duplicate room id: {rid}")
        seen_rooms.add(rid)
        status_raw = item["step_free_status"]
        if type(status_raw) is not str or status_raw not in {s.value for s in StepFreeStatus}:
            raise ValidationError(f"dataset.rooms[{i}].step_free_status is invalid")
        rooms.append(Room(
            rid,
            _clean_label(item["label"], f"dataset.rooms[{i}].label"),
            _positive_int(item["capacity"], f"dataset.rooms[{i}].capacity"),
            _features(item["features"], f"dataset.rooms[{i}].features"),
            StepFreeStatus(status_raw),
            _strict_bool(item["enabled"], f"dataset.rooms[{i}].enabled"),
        ))

    lessons: list[Lesson] = []
    seen_lessons: set[str] = set()
    for i, raw in enumerate(lessons_raw):
        item = _require_dict(raw, f"dataset.lessons[{i}]")
        allowed = {"id", "label", "period_id", "original_room_id", "student_count", "required_features", "requires_step_free", "locked"}
        _reject_extra(item, allowed, f"dataset.lessons[{i}]")
        missing = allowed - set(item)
        if missing:
            raise ValidationError(f"dataset.lessons[{i}] missing: {', '.join(sorted(missing))}")
        lid = _clean_id(item["id"], f"dataset.lessons[{i}].id")
        if lid in seen_lessons:
            raise ValidationError(f"duplicate lesson id: {lid}")
        seen_lessons.add(lid)
        period_id = _clean_id(item["period_id"], f"dataset.lessons[{i}].period_id")
        room_id = _clean_id(item["original_room_id"], f"dataset.lessons[{i}].original_room_id")
        if period_id not in seen_periods:
            raise ValidationError(f"unknown period reference: {period_id}")
        if room_id not in seen_rooms:
            raise ValidationError(f"unknown room reference: {room_id}")
        lessons.append(Lesson(
            lid,
            _clean_label(item["label"], f"dataset.lessons[{i}].label"),
            period_id,
            room_id,
            _positive_int(item["student_count"], f"dataset.lessons[{i}].student_count"),
            _features(item["required_features"], f"dataset.lessons[{i}].required_features"),
            _strict_bool(item["requires_step_free"], f"dataset.lessons[{i}].requires_step_free"),
            _strict_bool(item["locked"], f"dataset.lessons[{i}].locked"),
        ))

    dataset = Dataset(tuple(periods), tuple(rooms), tuple(lessons))
    validate_baseline(dataset)
    return dataset


def validate_baseline(dataset: Dataset) -> None:
    room_by_id = dataset.room_by_id
    occupied: set[tuple[str, str]] = set()
    for lesson in dataset.lessons:
        room = room_by_id[lesson.original_room_id]
        if not room.enabled:
            raise ValidationError(f"baseline lesson {lesson.id} uses disabled room {room.id}")
        if room.capacity < lesson.student_count:
            raise ValidationError(f"baseline lesson {lesson.id} exceeds room capacity")
        if not lesson.required_features.issubset(room.features):
            raise ValidationError(f"baseline lesson {lesson.id} is missing required room features")
        if lesson.requires_step_free and room.step_free_status is not StepFreeStatus.VERIFIED:
            raise ValidationError(f"baseline lesson {lesson.id} lacks verified step-free room metadata")
        key = (lesson.period_id, room.id)
        if key in occupied:
            raise ValidationError(f"baseline double booking in period {lesson.period_id} room {room.id}")
        occupied.add(key)


def parse_outages(payload: Any, dataset: Dataset) -> tuple[Outage, ...]:
    raw_list = _require_list(payload, "outages")
    room_ids = set(dataset.room_by_id)
    period_ids = set(dataset.period_by_id)
    # Policy: duplicate/overlapping outages are canonicalized by unioning periods per room.
    merged: dict[str, set[str]] = {}
    reasons: dict[str, str] = {}
    for i, raw in enumerate(raw_list):
        item = _require_dict(raw, f"outages[{i}]")
        _reject_extra(item, {"room_id", "period_ids", "reason"}, f"outages[{i}]")
        if "room_id" not in item or "period_ids" not in item:
            raise ValidationError(f"outages[{i}] requires room_id and period_ids")
        rid = _clean_id(item["room_id"], f"outages[{i}].room_id")
        if rid not in room_ids:
            raise ValidationError(f"outage references unknown room: {rid}")
        plist = _require_list(item["period_ids"], f"outages[{i}].period_ids")
        if not plist:
            raise ValidationError(f"outages[{i}].period_ids must not be empty")
        clean_periods: set[str] = set()
        for j, raw_pid in enumerate(plist):
            pid = _clean_id(raw_pid, f"outages[{i}].period_ids[{j}]")
            if pid not in period_ids:
                raise ValidationError(f"outage references unknown period: {pid}")
            clean_periods.add(pid)
        reason = item.get("reason", "")
        if type(reason) is not str:
            raise ValidationError(f"outages[{i}].reason must be a string")
        merged.setdefault(rid, set()).update(clean_periods)
        cleaned_reason = reason.strip()
        if cleaned_reason:
            # Duplicate outages are canonicalized independent of request ordering.
            previous = reasons.get(rid)
            if previous is None or cleaned_reason < previous:
                reasons[rid] = cleaned_reason
    return tuple(Outage(rid, frozenset(sorted(pids)), reasons.get(rid, "")) for rid, pids in sorted(merged.items()))


def unavailable_pairs(outages: Iterable[Outage]) -> frozenset[tuple[str, str]]:
    return frozenset((outage.room_id, pid) for outage in outages for pid in outage.period_ids)
