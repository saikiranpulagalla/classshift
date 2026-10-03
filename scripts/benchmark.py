from __future__ import annotations

import json
import platform
from pathlib import Path
import sys
from time import perf_counter

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ortools

from classshift.input_validator import parse_dataset, parse_outages
from classshift.optimizer import optimize_period
from classshift.solution_validator import validate_solution


def make_case(n_lessons: int, n_rooms: int):
    periods = [{"id": "MON_P1", "label": "Monday · Period 1", "order": 1}]
    rooms = []
    for i in range(n_rooms):
        rooms.append({"id": f"R{i}", "label": f"Room {i}", "capacity": 40, "features": ["projector"], "step_free_status": "VERIFIED", "enabled": True})
    lessons = []
    for i in range(n_lessons):
        lessons.append({"id": f"L{i}", "label": f"Lesson {i}", "period_id": "MON_P1", "original_room_id": f"R{i}", "student_count": 25, "required_features": [], "requires_step_free": False, "locked": False})
    return {"periods": periods, "rooms": rooms, "lessons": lessons}, [{"room_id": "R0", "period_ids": ["MON_P1"]}]


def timed(n, m):
    raw, out_raw = make_case(n, m)
    t0 = perf_counter(); dataset = parse_dataset(raw); t1 = perf_counter()
    outages = parse_outages(out_raw, dataset); t2 = perf_counter()
    result = optimize_period(dataset, outages, "MON_P1"); t3 = perf_counter()
    assignments = {l.id: l.original_room_id for l in dataset.lessons}
    if result.assignments:
        assignments.update(result.assignments)
    checked = validate_solution(dataset, outages, assignments, result.move_count); t4 = perf_counter()
    return {"lessons": n, "rooms": m, "validation_ms": (t2-t0)*1000, "solver_ms": (t3-t2)*1000, "validator_ms": (t4-t3)*1000, "total_ms": (t4-t0)*1000, "status": result.status.value, "validator_valid": checked.valid}


def main():
    data = {
        "environment": {"os": platform.platform(), "python": platform.python_version(), "ortools": ortools.__version__, "cpu": platform.processor() or "unreported"},
        "cases": [timed(10, 15), timed(25, 35), timed(50, 70), timed(100, 130)],
    }
    path = Path(__file__).resolve().parents[1] / "evidence" / "benchmark.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    main()
