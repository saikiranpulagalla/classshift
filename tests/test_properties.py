from __future__ import annotations

import copy
from classshift.service import recover_from_raw


def run(raw): return recover_from_raw({k:raw[k] for k in ("periods","rooms","lessons")},raw.get("outages",[]))


def test_no_outage_zero_moves(fixture_loader):
    r=run(fixture_loader("chain_3.json") | {"outages":[]}); assert r["status"]=="OPTIMAL" and r["move_count"]==0


def test_adding_compatible_free_room_cannot_hurt(fixture_loader):
    raw=fixture_loader("chain_3.json"); a=run(raw); b=copy.deepcopy(raw); b["rooms"].append({"id":"EXTRA","label":"Extra","capacity":40,"features":["chem_lab","bio_lab","physics_lab"],"step_free_status":"VERIFIED","enabled":True}); br=run(b)
    assert br["status"]=="OPTIMAL" and br["move_count"]<=a["move_count"]


def test_removing_outage_cannot_worsen(fixture_loader):
    raw=fixture_loader("chain_3.json"); a=run(raw); b=copy.deepcopy(raw); b["outages"]=[]; br=run(b); assert br["status"]=="OPTIMAL" and br["move_count"]<=a["move_count"]


def test_increasing_capacity_preserves_feasibility(fixture_loader):
    raw=fixture_loader("direct_move.json"); a=run(raw); b=copy.deepcopy(raw); b["rooms"][1]["capacity"]+=100; br=run(b); assert a["status"]==br["status"]=="OPTIMAL"


def test_adding_room_feature_cannot_reduce_eligibility(fixture_loader):
    raw=fixture_loader("direct_move.json"); a=run(raw); b=copy.deepcopy(raw); b["rooms"][1]["features"].append("extra"); br=run(b); assert br["status"]=="OPTIMAL" and br["move_count"]<=a["move_count"]


def test_input_order_does_not_change_cost(fixture_loader):
    raw=fixture_loader("chain_3.json"); a=run(raw); b=copy.deepcopy(raw); b["rooms"].reverse(); b["lessons"].reverse(); br=run(b); assert br["status"]==a["status"] and br["move_count"]==a["move_count"]


def test_adding_outage_cannot_improve_minimum_move_count(fixture_loader):
    raw=fixture_loader("chain_3.json")
    baseline=copy.deepcopy(raw); baseline["outages"]=[]
    a=run(baseline); b=run(raw)
    assert a["status"]==b["status"]=="OPTIMAL"
    assert b["move_count"]>=a["move_count"]


def test_successful_service_result_is_marked_validated(fixture_loader):
    result=run(fixture_loader("direct_move.json"))
    assert result["status"]=="OPTIMAL"
    assert result["validated"] is True
