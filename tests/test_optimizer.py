from __future__ import annotations

from classshift.input_validator import parse_dataset, parse_outages
from classshift.optimizer import optimize_period


def load_case(fixture_loader, name="direct_move.json"):
    raw = fixture_loader(name)
    dataset = parse_dataset({k: raw[k] for k in ("periods", "rooms", "lessons")})
    outages = parse_outages(raw["outages"], dataset)
    return dataset, outages


class _BaseFakeSolver:
    OPTIMAL = 1
    INFEASIBLE = 2

    def add_arc_with_capacity_and_unit_cost(self, *_args):
        return 0

    def set_node_supply(self, *_args):
        return None


class _BoomSolver:
    def __init__(self, *_args, **_kwargs):
        raise RuntimeError("boom")


def test_solver_error_not_infeasible(monkeypatch, fixture_loader):
    dataset, outages = load_case(fixture_loader)
    monkeypatch.setattr("classshift.optimizer.min_cost_flow.SimpleMinCostFlow", _BoomSolver)
    result = optimize_period(dataset, outages, "MON_P1")
    assert result.status.value == "SOLVER_ERROR"
    assert "boom" not in result.message.lower()


def test_unexpected_solver_status_is_solver_error(monkeypatch, fixture_loader):
    dataset, outages = load_case(fixture_loader)

    class UnexpectedStatusSolver(_BaseFakeSolver):
        def solve(self):
            return 999

    monkeypatch.setattr(
        "classshift.optimizer.min_cost_flow.SimpleMinCostFlow", UnexpectedStatusSolver
    )
    result = optimize_period(dataset, outages, "MON_P1")
    assert result.status.value == "SOLVER_ERROR"
    assert result.status.value != "INFEASIBLE"
    assert "999" not in result.message


def test_incomplete_optimal_assignment_is_solver_error(monkeypatch, fixture_loader):
    dataset, outages = load_case(fixture_loader)

    class EmptyOptimalSolver(_BaseFakeSolver):
        def solve(self):
            return self.OPTIMAL

        def num_arcs(self):
            return 0

    monkeypatch.setattr(
        "classshift.optimizer.min_cost_flow.SimpleMinCostFlow", EmptyOptimalSolver
    )
    result = optimize_period(dataset, outages, "MON_P1")
    assert result.status.value == "SOLVER_ERROR"
    assert result.assignments is None


def test_period_with_no_lessons_is_optimal_empty_without_solver(monkeypatch, fixture_loader):
    dataset, outages = load_case(fixture_loader)
    monkeypatch.setattr(
        "classshift.optimizer.min_cost_flow.SimpleMinCostFlow",
        lambda: (_ for _ in ()).throw(AssertionError("solver should not be constructed")),
    )
    result = optimize_period(dataset, outages, "TUE_UNUSED")
    assert result.status.value == "OPTIMAL"
    assert result.assignments == ()
    assert result.move_count == 0
