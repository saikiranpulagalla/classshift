from __future__ import annotations

import pytest

from classshift.input_validator import parse_dataset, parse_outages
from scripts.benchmark import PROFILES, SIZES, make_case, timed
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


def test_benchmark_infeasible_case_marks_validator_not_executed():
    case = timed(4, 6, "near_infeasible")
    assert case["status"] == "INFEASIBLE"
    assert case["validator_executed"] is False
    assert case["validator_ms"] is None
    assert "pipeline_total_ms" in case


def test_benchmark_matrix_is_four_profiles_by_four_sizes():
    assert len(PROFILES) == 4
    assert len(SIZES) == 4
