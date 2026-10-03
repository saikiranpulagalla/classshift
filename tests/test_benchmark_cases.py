from __future__ import annotations

import pytest

from classshift.input_validator import parse_dataset, parse_outages
from scripts.benchmark import make_case
from scripts.brute_force_oracle import brute_force_period


@pytest.mark.parametrize("profile", ["dense", "sparse", "bottleneck", "near_infeasible"])
def test_benchmark_profiles_start_from_valid_baselines(profile):
    raw, outage_raw = make_case(4, 6, profile)
    dataset = parse_dataset(raw)
    outages = parse_outages(outage_raw, dataset)
    assert len(dataset.lessons) == 4
    assert len(dataset.rooms) == 6
    assert outages


@pytest.mark.parametrize("profile", ["dense", "sparse", "bottleneck"])
def test_benchmark_feasible_profiles_have_recovery(profile):
    raw, outage_raw = make_case(4, 6, profile)
    dataset = parse_dataset(raw)
    outages = parse_outages(outage_raw, dataset)
    feasible, moves = brute_force_period(dataset, outages, "MON_P1")
    assert feasible is True
    assert moves is not None


def test_benchmark_near_infeasible_profile_is_globally_infeasible():
    raw, outage_raw = make_case(4, 6, "near_infeasible")
    dataset = parse_dataset(raw)
    outages = parse_outages(outage_raw, dataset)
    feasible, moves = brute_force_period(dataset, outages, "MON_P1")
    assert feasible is False
    assert moves is None
