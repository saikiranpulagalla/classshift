from __future__ import annotations

import copy

from classshift.candidates import build_candidate_graph
from classshift.explain import infeasible_message
from classshift.input_validator import parse_dataset, parse_outages


def parsed(raw):
    dataset = parse_dataset({k: raw[k] for k in ("periods", "rooms", "lessons")})
    outages = parse_outages(raw.get("outages", []), dataset)
    period_id = sorted({pid for outage in outages for pid in outage.period_ids})[0]
    graph = build_candidate_graph(dataset, outages, period_id)
    return dataset, graph


def test_feature_explanation_is_proven(fixture_loader):
    dataset, graph = parsed(fixture_loader("feature_infeasible.json"))
    assert infeasible_message(dataset, graph) == "No available room satisfies A's required room features."


def test_capacity_explanation_is_proven(fixture_loader):
    dataset, graph = parsed(fixture_loader("capacity_infeasible.json"))
    assert infeasible_message(dataset, graph) == "No available room has sufficient capacity for A."


def test_locked_outage_explanation_is_proven(fixture_loader):
    dataset, graph = parsed(fixture_loader("locked_infeasible.json"))
    assert infeasible_message(dataset, graph) == "A is locked to its original room, which is unavailable for this recovery."


def test_mixed_rejections_fall_back_to_conservative_wording(fixture_loader):
    raw = copy.deepcopy(fixture_loader("feature_infeasible.json"))
    # R2 keeps the required feature but is too small. R3 has enough capacity but
    # lacks the feature. No single reason applies to every available room.
    raw["rooms"][1]["features"] = ["chem"]
    raw["rooms"][1]["capacity"] = 10
    raw["rooms"].append({
        "id": "R3", "label": "R3", "capacity": 30, "features": [],
        "step_free_status": "VERIFIED", "enabled": True,
    })
    dataset, graph = parsed(raw)
    assert infeasible_message(dataset, graph) == "No available room satisfies all modeled constraints for A."
