from __future__ import annotations

from classshift.domain import ProposedAssignment, PublicStatus
from classshift.input_validator import parse_dataset, parse_outages
from classshift.optimizer import OptimizeResult
from classshift.service import recover


def demo_case(fixture_loader, name="chain_3.json"):
    raw = fixture_loader(name)
    dataset = parse_dataset({k: raw[k] for k in ("periods", "rooms", "lessons")})
    outages = parse_outages(raw["outages"], dataset)
    return dataset, outages


def test_service_blocks_duplicate_proposals_without_exposing_validator_details(monkeypatch, fixture_loader):
    dataset, outages = demo_case(fixture_loader)
    proposals = (
        ProposedAssignment("CHEM_10_MON_P3", "MON_P3", "LAB_B"),
        ProposedAssignment("CHEM_10_MON_P3", "MON_P3", "LAB_B"),
        ProposedAssignment("PHYS_10_MON_P3", "MON_P3", "ROOM_D"),
    )
    monkeypatch.setattr(
        "classshift.service.optimize_period",
        lambda *_: OptimizeResult(PublicStatus.OPTIMAL, proposals, 3),
    )
    result = recover(dataset, outages)
    assert result == {
        "status": "VALIDATOR_FAILURE",
        "validated": False,
        "message": "A proposed recovery failed internal validation and was blocked.",
    }


def test_service_blocks_period_mutation(monkeypatch, fixture_loader):
    dataset, outages = demo_case(fixture_loader)
    proposals = (
        ProposedAssignment("CHEM_10_MON_P3", "TUE_P1", "LAB_B"),
        ProposedAssignment("BIO_10_MON_P3", "MON_P3", "LAB_C"),
        ProposedAssignment("PHYS_10_MON_P3", "MON_P3", "ROOM_D"),
    )
    monkeypatch.setattr(
        "classshift.service.optimize_period",
        lambda *_: OptimizeResult(PublicStatus.OPTIMAL, proposals, 3),
    )
    result = recover(dataset, outages)
    assert result["status"] == "VALIDATOR_FAILURE"
    assert "validation_errors" not in result


def test_service_solver_error_is_generic(monkeypatch, fixture_loader):
    dataset, outages = demo_case(fixture_loader)
    monkeypatch.setattr(
        "classshift.service.optimize_period",
        lambda *_: OptimizeResult(
            PublicStatus.SOLVER_ERROR,
            message="private solver status 918273",
        ),
    )
    result = recover(dataset, outages)
    assert result == {
        "status": "SOLVER_ERROR",
        "validated": False,
        "message": "The optimization solver did not return a proven optimum.",
    }
