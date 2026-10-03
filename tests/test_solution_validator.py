from __future__ import annotations

from classshift.domain import ProposedAssignment
from classshift.input_validator import parse_dataset, parse_outages
from classshift.solution_validator import validate_solution


def case(fixture_loader, name="chain_3.json"):
    raw = fixture_loader(name)
    dataset = parse_dataset({k: raw[k] for k in ("periods", "rooms", "lessons")})
    outages = parse_outages(raw["outages"], dataset)
    return dataset, outages


def proposal(lesson_id: str, period_id: str, room_id: str) -> ProposedAssignment:
    return ProposedAssignment(lesson_id, period_id, room_id)


def original_proposals(dataset):
    return tuple(
        proposal(lesson.id, lesson.period_id, lesson.original_room_id)
        for lesson in dataset.lessons
    )


def test_valid_chain(fixture_loader):
    dataset, outages = case(fixture_loader)
    assignments = (
        proposal("CHEM_10_MON_P3", "MON_P3", "LAB_B"),
        proposal("BIO_10_MON_P3", "MON_P3", "LAB_C"),
        proposal("PHYS_10_MON_P3", "MON_P3", "ROOM_D"),
    )
    result = validate_solution(dataset, outages, assignments, 3)
    assert result.valid
    assert result.move_count == 3


def test_missing_lesson(fixture_loader):
    dataset, outages = case(fixture_loader)
    result = validate_solution(
        dataset,
        outages,
        (proposal("CHEM_10_MON_P3", "MON_P3", "LAB_B"),),
    )
    assert not result.valid
    assert result.move_count is None
    assert any("missing lessons" in error for error in result.errors)


def test_invented_lesson(fixture_loader):
    dataset, outages = case(fixture_loader)
    assignments = original_proposals(dataset) + (proposal("FAKE", "MON_P3", "ROOM_D"),)
    result = validate_solution(dataset, outages, assignments)
    assert not result.valid
    assert result.move_count is None
    assert any("invented lesson" in error for error in result.errors)


def test_duplicate_lesson_assignment_detected(fixture_loader):
    dataset, outages = case(fixture_loader, "direct_move.json")
    assignments = (
        proposal("A", "MON_P1", "R2"),
        proposal("A", "MON_P1", "R2"),
    )
    result = validate_solution(dataset, outages, assignments)
    assert not result.valid
    assert result.move_count is None
    assert any("duplicated lesson assignment" in error for error in result.errors)


def test_period_change_detected(fixture_loader):
    dataset, outages = case(fixture_loader, "direct_move.json")
    result = validate_solution(
        dataset,
        outages,
        (proposal("A", "TUE_P9", "R2"),),
    )
    assert not result.valid
    assert any("period changed" in error for error in result.errors)


def test_period_change_cannot_hide_double_booking(fixture_loader):
    dataset, outages = case(fixture_loader, "no_outage.json")
    assignments = (
        proposal("A", "MON_P1", "R1"),
        proposal("B", "TUE_P9", "R1"),
    )
    result = validate_solution(dataset, outages, assignments)
    assert not result.valid
    assert any("period changed" in error for error in result.errors)
    assert any("double-booked" in error for error in result.errors)


def test_unknown_room(fixture_loader):
    dataset, outages = case(fixture_loader, "direct_move.json")
    assert not validate_solution(
        dataset, outages, (proposal("A", "MON_P1", "NOPE"),)
    ).valid


def test_unavailable_room(fixture_loader):
    dataset, outages = case(fixture_loader, "direct_move.json")
    assert not validate_solution(
        dataset, outages, (proposal("A", "MON_P1", "R1"),)
    ).valid


def test_undersized_room(fixture_loader):
    raw = fixture_loader("direct_move.json")
    raw["rooms"][1]["capacity"] = 19
    dataset = parse_dataset({k: raw[k] for k in ("periods", "rooms", "lessons")})
    outages = parse_outages([], dataset)
    assert not validate_solution(
        dataset, outages, (proposal("A", "MON_P1", "R2"),)
    ).valid


def test_missing_feature(fixture_loader):
    dataset, outages = case(fixture_loader, "feature_infeasible.json")
    assert not validate_solution(
        dataset, outages, (proposal("A", "MON_P1", "R2"),)
    ).valid


def test_accessibility_violation(fixture_loader):
    raw = fixture_loader("direct_move.json")
    raw["lessons"][0]["requires_step_free"] = True
    raw["rooms"][0]["step_free_status"] = "VERIFIED"
    raw["rooms"][1]["step_free_status"] = "UNKNOWN"
    dataset = parse_dataset({k: raw[k] for k in ("periods", "rooms", "lessons")})
    outages = parse_outages([], dataset)
    assert not validate_solution(
        dataset, outages, (proposal("A", "MON_P1", "R2"),)
    ).valid


def test_lock_violation(fixture_loader):
    raw = fixture_loader("no_outage.json")
    raw["lessons"][0]["locked"] = True
    dataset = parse_dataset({k: raw[k] for k in ("periods", "rooms", "lessons")})
    outages = parse_outages([], dataset)
    assignments = (
        proposal("A", "MON_P1", "R3"),
        proposal("B", "MON_P1", "R2"),
    )
    assert not validate_solution(dataset, outages, assignments).valid


def test_double_booking(fixture_loader):
    dataset, outages = case(fixture_loader, "no_outage.json")
    assignments = (
        proposal("A", "MON_P1", "R1"),
        proposal("B", "MON_P1", "R1"),
    )
    assert not validate_solution(dataset, outages, assignments).valid


def test_fake_move_count(fixture_loader):
    dataset, outages = case(fixture_loader, "direct_move.json")
    result = validate_solution(
        dataset,
        outages,
        (proposal("A", "MON_P1", "R2"),),
        0,
    )
    assert not result.valid
    assert any("move_count" in error for error in result.errors)


def test_malformed_assignment_record_is_blocked(fixture_loader):
    dataset, outages = case(fixture_loader, "direct_move.json")
    result = validate_solution(dataset, outages, (object(),))  # type: ignore[arg-type]
    assert not result.valid
    assert any("malformed assignment record" in error for error in result.errors)


def test_validator_does_not_depend_on_candidate_helper(monkeypatch, fixture_loader):
    monkeypatch.setattr(
        "classshift.candidates.build_candidate_graph",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not be called")),
    )
    dataset, outages = case(fixture_loader, "direct_move.json")
    assignments = (proposal("A", "MON_P1", "R2"),)
    assert validate_solution(dataset, outages, assignments, 1).valid
