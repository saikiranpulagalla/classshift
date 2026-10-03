from __future__ import annotations

import pytest

from app import create_app
from classshift.domain import ProposedAssignment, PublicStatus
from classshift.optimizer import OptimizeResult
from classshift.solution_validator import ValidationResult


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_demo_is_canonical_sanitized_shape(client):
    response = client.get("/api/demo")
    assert response.status_code == 200
    body = response.get_json()
    assert set(body) == {"periods", "rooms", "lessons"}
    assert all(set(room) == {"id", "label", "capacity", "features", "step_free_status", "enabled"} for room in body["rooms"])
    assert all(set(lesson) == {"id", "label", "period_id", "original_room_id", "student_count", "required_features", "requires_step_free", "locked"} for lesson in body["lessons"])


def test_demo_loader_failure_is_generic_500(monkeypatch, client):
    monkeypatch.setattr("app.load_dataset", lambda *_: (_ for _ in ()).throw(RuntimeError("secret path detail")))
    response = client.get("/api/demo")
    body = response.get_json()
    assert response.status_code == 500
    assert body == {
        "status": "INTERNAL_ERROR",
        "validated": False,
        "message": "The server could not process the request.",
    }
    assert "secret" not in response.get_data(as_text=True)


def test_valid_optimal(client):
    response = client.post(
        "/api/recover",
        json={"outages": [{"room_id": "LAB_A", "period_ids": ["MON_P3"]}]},
    )
    body = response.get_json()
    assert response.status_code == 200
    assert body["status"] == "OPTIMAL"
    assert body["validated"] is True
    assert body["move_count"] == 3


def test_valid_infeasible(client):
    response = client.post(
        "/api/recover",
        json={
            "outages": [
                {"room_id": "LAB_A", "period_ids": ["MON_P3"]},
                {"room_id": "LAB_B", "period_ids": ["MON_P3"]},
                {"room_id": "LAB_C", "period_ids": ["MON_P3"]},
            ]
        },
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == "INFEASIBLE"


def test_wrong_content_type(client):
    response = client.post("/api/recover", data="{}", content_type="text/plain")
    assert response.status_code == 400
    assert response.get_json()["status"] == "INVALID_INPUT"


def test_malformed_json(client):
    response = client.post("/api/recover", data="{", content_type="application/json")
    assert response.status_code == 400
    assert response.get_json()["status"] == "INVALID_INPUT"


def test_invalid_outage(client):
    response = client.post(
        "/api/recover",
        json={"outages": [{"room_id": "NOPE", "period_ids": ["MON_P3"]}]},
    )
    assert response.status_code == 400
    assert response.get_json()["status"] == "INVALID_INPUT"


def test_internal_exception_maps_to_generic_internal_error(monkeypatch, client):
    monkeypatch.setattr(
        "app.load_dataset",
        lambda *_: (_ for _ in ()).throw(RuntimeError("secret implementation detail")),
    )
    response = client.post("/api/recover", json={"outages": []})
    body = response.get_json()
    assert response.status_code == 500
    assert body["status"] == "INTERNAL_ERROR"
    assert "secret" not in response.get_data(as_text=True)


def test_validator_failure_never_returns_success_or_internal_diagnostics(monkeypatch, client):
    monkeypatch.setattr(
        "classshift.service.validate_solution",
        lambda *args, **kwargs: ValidationResult(
            False,
            ("CHEM_10_MON_P3: assigned room is unavailable",),
            None,
        ),
    )
    response = client.post(
        "/api/recover",
        json={"outages": [{"room_id": "LAB_A", "period_ids": ["MON_P3"]}]},
    )
    body = response.get_json()
    assert response.status_code == 500
    assert body == {
        "status": "VALIDATOR_FAILURE",
        "validated": False,
        "message": "A proposed recovery failed internal validation and was blocked.",
    }
    assert "validation_errors" not in body
    assert "CHEM_10" not in response.get_data(as_text=True)


def test_solver_error_does_not_leak_solver_diagnostic(monkeypatch, client):
    monkeypatch.setattr(
        "classshift.service.optimize_period",
        lambda *_: OptimizeResult(
            PublicStatus.SOLVER_ERROR,
            message="OR-Tools returned secret status 918273",
        ),
    )
    response = client.post(
        "/api/recover",
        json={"outages": [{"room_id": "LAB_A", "period_ids": ["MON_P3"]}]},
    )
    body = response.get_json()
    assert response.status_code == 500
    assert body == {
        "status": "SOLVER_ERROR",
        "validated": False,
        "message": "The optimization solver did not return a proven optimum.",
    }
    assert "918273" not in response.get_data(as_text=True)


def test_service_blocks_duplicate_solver_proposals_before_map_conversion(monkeypatch, client):
    proposals = (
        ProposedAssignment("CHEM_10_MON_P3", "MON_P3", "LAB_B"),
        ProposedAssignment("CHEM_10_MON_P3", "MON_P3", "LAB_B"),
        ProposedAssignment("PHYS_10_MON_P3", "MON_P3", "ROOM_D"),
    )
    monkeypatch.setattr(
        "classshift.service.optimize_period",
        lambda *_: OptimizeResult(PublicStatus.OPTIMAL, proposals, 3),
    )
    response = client.post(
        "/api/recover",
        json={"outages": [{"room_id": "LAB_A", "period_ids": ["MON_P3"]}]},
    )
    assert response.status_code == 500
    assert response.get_json()["status"] == "VALIDATOR_FAILURE"


def test_service_blocks_period_mutation_from_solver(monkeypatch, client):
    proposals = (
        ProposedAssignment("CHEM_10_MON_P3", "TUE_P1", "LAB_B"),
        ProposedAssignment("BIO_10_MON_P3", "MON_P3", "LAB_C"),
        ProposedAssignment("PHYS_10_MON_P3", "MON_P3", "ROOM_D"),
    )
    monkeypatch.setattr(
        "classshift.service.optimize_period",
        lambda *_: OptimizeResult(PublicStatus.OPTIMAL, proposals, 3),
    )
    response = client.post(
        "/api/recover",
        json={"outages": [{"room_id": "LAB_A", "period_ids": ["MON_P3"]}]},
    )
    assert response.status_code == 500
    assert response.get_json()["status"] == "VALIDATOR_FAILURE"


def test_unexpected_request_field_is_invalid(client):
    response = client.post("/api/recover", json={"outages": [], "extra": True})
    assert response.status_code == 400
    assert response.get_json()["status"] == "INVALID_INPUT"


def test_request_size_limit(client):
    payload = '{"outages":[],"padding":"' + ("x" * (129 * 1024)) + '"}'
    response = client.post(
        "/api/recover", data=payload, content_type="application/json"
    )
    assert response.status_code == 413
    assert response.get_json()["status"] == "INVALID_INPUT"
