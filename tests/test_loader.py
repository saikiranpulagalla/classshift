from __future__ import annotations

import json
from pathlib import Path

import pytest

from classshift.input_validator import parse_dataset
from classshift.loader import DuplicateJsonKeyError, dataset_to_public_dict, load_json

ROOT = Path(__file__).resolve().parents[1]


def test_public_demo_serializer_whitelists_canonical_fields():
    raw = json.loads((ROOT / "data/demo_school.json").read_text(encoding="utf-8"))
    dataset = parse_dataset(raw)
    public = dataset_to_public_dict(dataset)

    assert set(public) == {"periods", "rooms", "lessons"}
    assert all(set(room) == {"id", "label", "capacity", "features", "step_free_status", "enabled"} for room in public["rooms"])
    assert all(set(lesson) == {"id", "label", "period_id", "original_room_id", "student_count", "required_features", "requires_step_free", "locked"} for lesson in public["lessons"])
    assert "outages" not in public


@pytest.mark.parametrize("payload", [
    '{"capacity": 20, "capacity": 30}',
    '{"enabled": false, "enabled": true}',
])
def test_bundled_json_loader_rejects_duplicate_object_keys(tmp_path, payload):
    path = tmp_path / "duplicate.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(DuplicateJsonKeyError, match="duplicate JSON object key"):
        load_json(path)
