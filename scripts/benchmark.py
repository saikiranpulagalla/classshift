from __future__ import annotations

import json
import platform
from pathlib import Path
import sys
from time import perf_counter
from unittest.mock import patch

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from classshift.candidates import build_candidate_graph
from classshift.input_validator import parse_dataset, parse_outages
from classshift.solution_validator import validate_solution


SIZES = ((10, 15), (25, 35), (50, 70), (100, 130))
PROFILES = ("dense", "sparse", "bottleneck", "near_infeasible")


def _room(room_id: str, features: list[str]) -> dict:
    return {
        "id": room_id,
        "label": room_id,
        "capacity": 40,
        "features": features,
        "step_free_status": "VERIFIED",
        "enabled": True,
    }


def make_case(n_lessons: int, n_rooms: int, profile: str):
    if n_rooms <= n_lessons:
        raise ValueError("benchmark cases require at least one spare physical room")
    periods = [{"id": "MON_P1", "label": "Monday · Period 1", "order": 1}]

    if profile == "dense":
        rooms = [_room(f"R{i}", ["projector"]) for i in range(n_rooms)]
        lessons = [
            {
                "id": f"L{i}", "label": f"Lesson {i}", "period_id": "MON_P1",
                "original_room_id": f"R{i}", "student_count": 25,
                "required_features": [], "requires_step_free": False, "locked": False,
            }
            for i in range(n_lessons)
        ]
    elif profile == "sparse":
        groups = max(2, min(5, n_lessons // 3 or 2))
        rooms = [_room(f"R{i}", [f"group_{i % groups}"]) for i in range(n_rooms)]
        lessons = [
            {
                "id": f"L{i}", "label": f"Lesson {i}", "period_id": "MON_P1",
                "original_room_id": f"R{i}", "student_count": 25,
                "required_features": [f"group_{i % groups}"],
                "requires_step_free": False, "locked": False,
            }
            for i in range(n_lessons)
        ]
    elif profile in {"bottleneck", "near_infeasible"}:
        # Baseline is valid. Only a tightly limited set of rooms has the required
        # feature. Removing R0 leaves exactly n compatible rooms (bottleneck) or
        # n-1 compatible rooms (near_infeasible).
        compatible_count = n_lessons + 1 if profile == "bottleneck" else n_lessons
        rooms = [
            _room(f"R{i}", ["core"] if i < compatible_count else ["other"])
            for i in range(n_rooms)
        ]
        lessons = [
            {
                "id": f"L{i}", "label": f"Lesson {i}", "period_id": "MON_P1",
                "original_room_id": f"R{i}", "student_count": 25,
                "required_features": ["core"], "requires_step_free": False, "locked": False,
            }
            for i in range(n_lessons)
        ]
    else:
        raise ValueError(f"unknown benchmark profile: {profile}")

    dataset = {"periods": periods, "rooms": rooms, "lessons": lessons}
    outages = [{"room_id": "R0", "period_ids": ["MON_P1"]}]
    return dataset, outages


def timed(n: int, m: int, profile: str) -> dict:
    from classshift.optimizer import optimize_period

    raw, out_raw = make_case(n, m, profile)
    total_start = perf_counter()

    t0 = perf_counter()
    dataset = parse_dataset(raw)
    outages = parse_outages(out_raw, dataset)
    t1 = perf_counter()

    graph = build_candidate_graph(dataset, outages, "MON_P1")
    t2 = perf_counter()

    # Production optimize_period normally builds the graph itself. For benchmark
    # isolation only, supply the already measured graph through a temporary patch
    # so this interval represents OR-Tools solve/result extraction rather than
    # candidate generation a second time.
    with patch("classshift.optimizer.build_candidate_graph", return_value=graph):
        result = optimize_period(dataset, outages, "MON_P1")
    t3 = perf_counter()

    validator_valid = None
    if result.status.value == "OPTIMAL" and result.assignments is not None:
        assignments = {lesson.id: lesson.original_room_id for lesson in dataset.lessons}
        assignments.update(result.assignments)
        checked = validate_solution(dataset, outages, assignments, result.move_count)
        validator_valid = checked.valid
    t4 = perf_counter()

    return {
        "profile": profile,
        "lessons": n,
        "rooms": m,
        "validation_ms": (t1 - t0) * 1000,
        "candidate_generation_ms": (t2 - t1) * 1000,
        "solver_ms": (t3 - t2) * 1000,
        "validator_ms": (t4 - t3) * 1000,
        "total_ms": (t4 - total_start) * 1000,
        "status": result.status.value,
        "move_count": result.move_count,
        "validator_valid": validator_valid,
    }


def main() -> int:
    import ortools

    cases = [timed(n, m, profile) for n, m in SIZES for profile in PROFILES]
    data = {
        "environment": {
            "os": platform.platform(),
            "python": platform.python_version(),
            "ortools": ortools.__version__,
            "cpu": platform.processor() or "unreported",
        },
        "method": "single measured run per deterministic synthetic case; no invented values",
        "cases": cases,
    }
    path = Path(__file__).resolve().parents[1] / "evidence" / "benchmark.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
