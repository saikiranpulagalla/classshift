from __future__ import annotations

import copy
import pytest

from classshift.input_validator import parse_dataset, parse_outages
from classshift.solution_validator import validate_solution


def case(fixture_loader,name="chain_3.json"):
    raw=fixture_loader(name); ds=parse_dataset({k:raw[k] for k in ("periods","rooms","lessons")}); out=parse_outages(raw["outages"],ds); return ds,out


def test_valid_chain(fixture_loader):
    ds,out=case(fixture_loader); a={"CHEM_10_MON_P3":"LAB_B","BIO_10_MON_P3":"LAB_C","PHYS_10_MON_P3":"ROOM_D"}
    r=validate_solution(ds,out,a,3); assert r.valid and r.move_count==3


def test_missing_lesson(fixture_loader):
    ds,out=case(fixture_loader); r=validate_solution(ds,out,{"CHEM_10_MON_P3":"LAB_B"}); assert not r.valid and any("missing lessons" in e for e in r.errors)


def test_invented_lesson(fixture_loader):
    ds,out=case(fixture_loader); a={l.id:l.original_room_id for l in ds.lessons}; a["FAKE"]="ROOM_D"; assert not validate_solution(ds,out,a).valid


def test_unknown_room(fixture_loader):
    ds,out=case(fixture_loader,"direct_move.json"); assert not validate_solution(ds,out,{"A":"NOPE"}).valid


def test_unavailable_room(fixture_loader):
    ds,out=case(fixture_loader,"direct_move.json"); assert not validate_solution(ds,out,{"A":"R1"}).valid


def test_undersized_room(fixture_loader):
    raw=fixture_loader("direct_move.json"); raw["rooms"][1]["capacity"]=19
    ds=parse_dataset({k:raw[k] for k in ("periods","rooms","lessons")}); out=parse_outages([],ds); assert not validate_solution(ds,out,{"A":"R2"}).valid


def test_missing_feature(fixture_loader):
    ds,out=case(fixture_loader,"feature_infeasible.json"); assert not validate_solution(ds,out,{"A":"R2"}).valid


def test_accessibility_violation(fixture_loader):
    raw=fixture_loader("direct_move.json"); raw["lessons"][0]["requires_step_free"]=True; raw["rooms"][0]["step_free_status"]="VERIFIED"; raw["rooms"][1]["step_free_status"]="UNKNOWN"
    ds=parse_dataset({k:raw[k] for k in ("periods","rooms","lessons")}); out=parse_outages([],ds); assert not validate_solution(ds,out,{"A":"R2"}).valid


def test_lock_violation(fixture_loader):
    raw=fixture_loader("no_outage.json"); raw["lessons"][0]["locked"]=True
    ds=parse_dataset({k:raw[k] for k in ("periods","rooms","lessons")}); out=parse_outages([],ds); a={"A":"R3","B":"R2"}; assert not validate_solution(ds,out,a).valid


def test_double_booking(fixture_loader):
    ds,out=case(fixture_loader,"no_outage.json"); assert not validate_solution(ds,out,{"A":"R1","B":"R1"}).valid


def test_fake_move_count(fixture_loader):
    ds,out=case(fixture_loader,"direct_move.json"); r=validate_solution(ds,out,{"A":"R2"},0); assert not r.valid and any("move_count" in e for e in r.errors)


def test_validator_does_not_depend_on_candidate_helper(monkeypatch, fixture_loader):
    monkeypatch.setattr("classshift.candidates.build_candidate_graph", lambda *a,**k: (_ for _ in ()).throw(AssertionError("should not be called")))
    ds,out=case(fixture_loader,"direct_move.json"); assert validate_solution(ds,out,{"A":"R2"},1).valid
