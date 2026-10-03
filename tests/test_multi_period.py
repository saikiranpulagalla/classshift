from __future__ import annotations

from classshift.service import recover_from_raw


def test_two_affected_periods_are_combined_without_cross_period_room_conflict(fixture_loader):
    raw = fixture_loader("multi_period.json")
    dataset = {k: raw[k] for k in ("periods", "rooms", "lessons")}
    result = recover_from_raw(dataset, raw["outages"])

    assert result["status"] == "OPTIMAL"
    assert result["validated"] is True
    assert result["move_count"] == 2
    assert result["assignments"]["A_MON"] == "R3"
    assert result["assignments"]["C_TUE"] == "R3"
    assert result["assignments"]["B_MON"] == "R2"
    assert result["assignments"]["D_TUE"] == "R2"


def test_multi_period_move_records_keep_original_periods(fixture_loader):
    raw = fixture_loader("multi_period.json")
    dataset = {k: raw[k] for k in ("periods", "rooms", "lessons")}
    result = recover_from_raw(dataset, raw["outages"])
    period_by_lesson = {move["lesson_id"]: move["period_id"] for move in result["moves"]}
    assert period_by_lesson == {"A_MON": "MON_P1", "C_TUE": "TUE_P1"}
