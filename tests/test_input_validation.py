from __future__ import annotations

import copy
import pytest

from classshift.input_validator import ValidationError, parse_dataset, parse_outages


def bad(raw, mutator):
    data = copy.deepcopy(raw); mutator(data); return data


def test_wrong_top_level(valid_raw):
    with pytest.raises(ValidationError): parse_dataset([])


def test_missing_top_level_field(valid_raw):
    d = copy.deepcopy(valid_raw); d.pop("rooms")
    with pytest.raises(ValidationError): parse_dataset(d)

@pytest.mark.parametrize("field,value", [("capacity", -1),("capacity",0),("capacity",30.5),("capacity",True),("capacity","30")])
def test_bad_capacity_types(valid_raw, field, value):
    d=copy.deepcopy(valid_raw); d["rooms"][0][field]=value
    with pytest.raises(ValidationError): parse_dataset(d)


@pytest.mark.parametrize("value", [-1,0,20.5,True,"20"])
def test_bad_student_count_types(valid_raw, value):
    d=copy.deepcopy(valid_raw); d["lessons"][0]["student_count"]=value
    with pytest.raises(ValidationError): parse_dataset(d)


def test_string_boolean(valid_raw):
    d=copy.deepcopy(valid_raw); d["rooms"][0]["enabled"]="true"
    with pytest.raises(ValidationError): parse_dataset(d)


def test_invalid_accessibility(valid_raw):
    d=copy.deepcopy(valid_raw); d["rooms"][0]["step_free_status"]="YES"
    with pytest.raises(ValidationError): parse_dataset(d)


def test_feature_normalization(valid_raw):
    d=copy.deepcopy(valid_raw); d["rooms"][0]["features"]=[" Projector ","projector"]
    ds=parse_dataset(d); assert ds.rooms[0].features==frozenset({"projector"})


def test_malformed_feature(valid_raw):
    d=copy.deepcopy(valid_raw); d["rooms"][0]["features"]=["projector screen"]
    with pytest.raises(ValidationError): parse_dataset(d)

@pytest.mark.parametrize("kind", ["periods","rooms","lessons"])
def test_duplicate_ids(valid_raw, kind):
    d=copy.deepcopy(valid_raw); d[kind].append(copy.deepcopy(d[kind][0]))
    with pytest.raises(ValidationError): parse_dataset(d)


def test_unknown_room_reference(valid_raw):
    d=copy.deepcopy(valid_raw); d["lessons"][0]["original_room_id"]="NOPE"
    with pytest.raises(ValidationError): parse_dataset(d)


def test_unknown_period_reference(valid_raw):
    d=copy.deepcopy(valid_raw); d["lessons"][0]["period_id"]="NOPE"
    with pytest.raises(ValidationError): parse_dataset(d)


def test_disabled_baseline_room(valid_raw):
    d=copy.deepcopy(valid_raw); d["rooms"][0]["enabled"]=False
    with pytest.raises(ValidationError): parse_dataset(d)


def test_baseline_capacity_violation(valid_raw):
    d=copy.deepcopy(valid_raw); d["lessons"][0]["student_count"]=31
    with pytest.raises(ValidationError): parse_dataset(d)


def test_baseline_feature_violation(valid_raw):
    d=copy.deepcopy(valid_raw); d["lessons"][0]["required_features"]=["chem"]
    with pytest.raises(ValidationError): parse_dataset(d)


def test_baseline_accessibility_violation(valid_raw):
    d=copy.deepcopy(valid_raw); d["lessons"][0]["requires_step_free"]=True; d["rooms"][0]["step_free_status"]="UNKNOWN"
    with pytest.raises(ValidationError): parse_dataset(d)


def test_baseline_double_booking(valid_raw):
    d=copy.deepcopy(valid_raw); second=copy.deepcopy(d["lessons"][0]); second["id"]="B"; d["lessons"].append(second)
    with pytest.raises(ValidationError): parse_dataset(d)


def test_outage_unknown_room(valid_raw):
    ds=parse_dataset(valid_raw)
    with pytest.raises(ValidationError): parse_outages([{"room_id":"NOPE","period_ids":["MON_P1"]}],ds)


def test_outage_unknown_period(valid_raw):
    ds=parse_dataset(valid_raw)
    with pytest.raises(ValidationError): parse_outages([{"room_id":"R1","period_ids":["NOPE"]}],ds)


def test_outage_malformed_period_list(valid_raw):
    ds=parse_dataset(valid_raw)
    with pytest.raises(ValidationError): parse_outages([{"room_id":"R1","period_ids":"MON_P1"}],ds)


def test_duplicate_outages_are_canonicalized(valid_raw):
    ds=parse_dataset(valid_raw)
    out=parse_outages([{"room_id":"R1","period_ids":["MON_P1"]},{"room_id":"R1","period_ids":["MON_P1"]}],ds)
    assert len(out)==1 and out[0].period_ids==frozenset({"MON_P1"})
