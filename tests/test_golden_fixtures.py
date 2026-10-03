from __future__ import annotations

import pytest

from classshift.service import recover_from_raw

NAMES=["no_outage.json","direct_move.json","chain_2.json","chain_3.json","capacity_infeasible.json","feature_infeasible.json","locked_infeasible.json","hall_bottleneck.json","multi_outage.json","equal_optimum.json","multi_period.json"]

@pytest.mark.parametrize("name",NAMES)
def test_golden(name, fixture_loader):
    raw=fixture_loader(name)
    dataset={k:raw[k] for k in ("periods","rooms","lessons")}
    result=recover_from_raw(dataset,raw["outages"])
    assert result["status"]==raw["expected"]["status"]
    if result["status"]=="OPTIMAL":
        assert result["validated"] is True
        assert result["move_count"]==raw["expected"]["move_count"]


def test_chain3_exact_assignment(fixture_loader):
    raw=fixture_loader("chain_3.json"); result=recover_from_raw({k:raw[k] for k in ("periods","rooms","lessons")},raw["outages"])
    assert result["assignments"]=={"CHEM_10_MON_P3":"LAB_B","BIO_10_MON_P3":"LAB_C","PHYS_10_MON_P3":"ROOM_D"}


def test_hall_has_no_zero_candidate_lesson(fixture_loader):
    from classshift.input_validator import parse_dataset, parse_outages
    from classshift.candidates import build_candidate_graph
    raw=fixture_loader("hall_bottleneck.json"); ds=parse_dataset({k:raw[k] for k in ("periods","rooms","lessons")}); out=parse_outages(raw["outages"],ds); g=build_candidate_graph(ds,out,"MON_P1")
    assert all(g.eligible.values())
