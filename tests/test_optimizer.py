from __future__ import annotations

from classshift.input_validator import parse_dataset, parse_outages
from classshift.optimizer import optimize_period


def test_solver_error_not_infeasible(monkeypatch, fixture_loader):
    raw=fixture_loader("direct_move.json"); ds=parse_dataset({k:raw[k] for k in ("periods","rooms","lessons")}); out=parse_outages(raw["outages"],ds)
    class Boom:
        def __init__(self,*a,**k): raise RuntimeError("boom")
    monkeypatch.setattr("classshift.optimizer.min_cost_flow.SimpleMinCostFlow", Boom)
    result=optimize_period(ds,out,"MON_P1")
    assert result.status.value=="SOLVER_ERROR"
