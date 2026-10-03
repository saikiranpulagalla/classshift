"""Small independent release probes for the solver-backed release gate."""

from __future__ import annotations

import json
from pathlib import Path

from classshift.domain import ProposedAssignment
from classshift.input_validator import parse_dataset, parse_outages
from classshift.service import recover_from_raw
from classshift.solution_validator import validate_solution
from scripts.brute_force_oracle import brute_force_period_details

ROOT = Path(__file__).resolve().parents[1]


def _fixture(name: str) -> dict:
    return json.loads((ROOT / "fixtures" / name).read_text(encoding="utf-8"))


def probe_primary_chain() -> None:
    raw = _fixture("chain_3.json")
    result = recover_from_raw(
        {key: raw[key] for key in ("periods", "rooms", "lessons")}, raw["outages"]
    )
    assert result["status"] == "OPTIMAL"
    assert result["validated"] is True
    assert result["move_count"] == 3
    assert result["assignments"] == {
        "CHEM_10_MON_P3": "LAB_B",
        "BIO_10_MON_P3": "LAB_C",
        "PHYS_10_MON_P3": "ROOM_D",
    }


def probe_infeasible_fixture() -> None:
    raw = _fixture("locked_infeasible.json")
    result = recover_from_raw(
        {key: raw[key] for key in ("periods", "rooms", "lessons")}, raw["outages"]
    )
    assert result["status"] == "INFEASIBLE"


def probe_validator_rejects_corruption() -> None:
    raw = _fixture("chain_3.json")
    dataset = parse_dataset({key: raw[key] for key in ("periods", "rooms", "lessons")})
    outages = parse_outages(raw["outages"], dataset)
    corrupt = (
        ProposedAssignment("CHEM_10_MON_P3", "MON_P3", "LAB_B"),
        ProposedAssignment("CHEM_10_MON_P3", "MON_P3", "LAB_B"),
        ProposedAssignment("PHYS_10_MON_P3", "MON_P3", "ROOM_D"),
    )
    assert not validate_solution(dataset, outages, corrupt, claimed_move_count=3).valid


def probe_equal_optimum_minimum() -> None:
    raw = _fixture("equal_optimum.json")
    dataset = parse_dataset({key: raw[key] for key in ("periods", "rooms", "lessons")})
    outages = parse_outages(raw["outages"], dataset)
    feasible, move_count, optimum_count = brute_force_period_details(
        dataset, outages, "MON_P1"
    )
    assert feasible is True
    assert move_count == 1
    assert optimum_count >= 2
