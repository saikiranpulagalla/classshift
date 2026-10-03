from __future__ import annotations

from classshift.candidates import RejectionCode, build_candidate_graph
from classshift.input_validator import parse_dataset, parse_outages


def parse_case(raw):
    ds=parse_dataset({k:v for k,v in raw.items() if k in {"periods","rooms","lessons"}})
    out=parse_outages(raw.get("outages",[]),ds)
    return ds,out


def test_outage_removes_room(fixture_loader):
    ds,out=parse_case(fixture_loader("direct_move.json")); g=build_candidate_graph(ds,out,"MON_P1")
    assert "R1" not in g.eligible["A"]
    assert RejectionCode.ROOM_UNAVAILABLE in g.rejected["A"]["R1"]


def test_outage_period_specific(fixture_loader):
    raw=fixture_loader("direct_move.json"); raw["periods"].append({"id":"TUE_P1","label":"Tuesday · Period 1","order":1})
    raw["lessons"].append({**raw["lessons"][0],"id":"B","period_id":"TUE_P1","original_room_id":"R2"})
    ds,out=parse_case(raw); g=build_candidate_graph(ds,out,"TUE_P1")
    assert "R1" in g.eligible["B"]


def test_exact_capacity_accepted(fixture_loader):
    raw=fixture_loader("direct_move.json"); raw["rooms"][1]["capacity"]=20
    ds,out=parse_case(raw); g=build_candidate_graph(ds,out,"MON_P1")
    assert "R2" in g.eligible["A"]


def test_undersized_rejected(fixture_loader):
    raw=fixture_loader("direct_move.json"); raw["rooms"][1]["capacity"]=19
    ds,out=parse_case(raw); g=build_candidate_graph(ds,out,"MON_P1")
    assert RejectionCode.CAPACITY in g.rejected["A"]["R2"]


def test_missing_feature_rejected(fixture_loader):
    raw=fixture_loader("feature_infeasible.json"); ds,out=parse_case(raw); g=build_candidate_graph(ds,out,"MON_P1")
    assert RejectionCode.MISSING_FEATURE in g.rejected["A"]["R2"]


def test_unknown_accessibility_rejected_when_required(fixture_loader):
    raw=fixture_loader("direct_move.json"); raw["rooms"][1]["step_free_status"]="UNKNOWN"; raw["lessons"][0]["requires_step_free"]=True; raw["rooms"][0]["step_free_status"]="VERIFIED"
    ds,out=parse_case(raw); g=build_candidate_graph(ds,out,"MON_P1")
    assert RejectionCode.STEP_FREE_REQUIRED in g.rejected["A"]["R2"]


def test_unknown_accessibility_allowed_when_not_required(fixture_loader):
    raw=fixture_loader("direct_move.json"); raw["rooms"][1]["step_free_status"]="UNKNOWN"
    ds,out=parse_case(raw); g=build_candidate_graph(ds,out,"MON_P1")
    assert "R2" in g.eligible["A"]


def test_locked_lesson_only_original(fixture_loader):
    raw=fixture_loader("no_outage.json"); raw["lessons"][0]["locked"]=True
    ds,out=parse_case(raw); g=build_candidate_graph(ds,out,"MON_P1")
    assert g.eligible["A"]==("R1",)


def test_disabled_room_rejected(fixture_loader):
    raw=fixture_loader("direct_move.json"); raw["rooms"].append({"id":"R3","label":"R3","capacity":30,"features":[],"step_free_status":"VERIFIED","enabled":False})
    ds,out=parse_case(raw); g=build_candidate_graph(ds,out,"MON_P1")
    assert RejectionCode.ROOM_DISABLED in g.rejected["A"]["R3"]
