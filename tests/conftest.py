from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


@pytest.fixture
def fixture_loader():
    def load(name: str):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return load


@pytest.fixture
def valid_raw(fixture_loader):
    data = fixture_loader("direct_move.json")
    return {k: copy.deepcopy(v) for k, v in data.items() if k in {"periods", "rooms", "lessons"}}
