from __future__ import annotations

from classshift.input_validator import parse_dataset, parse_outages
from scripts.brute_force_oracle import brute_force_period_details


def _details(raw):
    dataset = parse_dataset({k: raw[k] for k in ("periods", "rooms", "lessons")})
    outages = parse_outages(raw.get("outages", []), dataset)
    periods = sorted({pid for outage in outages for pid in outage.period_ids})
    assert len(periods) == 1
    return brute_force_period_details(dataset, outages, periods[0])


def test_two_step_chain_has_unique_minimum(fixture_loader):
    feasible, moves, optimal_count = _details(fixture_loader("chain_2.json"))
    assert feasible is True
    assert moves == 2
    assert optimal_count == 1


def test_three_step_demo_chain_has_unique_minimum(fixture_loader):
    feasible, moves, optimal_count = _details(fixture_loader("chain_3.json"))
    assert feasible is True
    assert moves == 3
    assert optimal_count == 1
