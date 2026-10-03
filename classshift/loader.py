from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .domain import Dataset
from .input_validator import parse_dataset


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_dataset(path: str | Path) -> Dataset:
    return parse_dataset(load_json(path))
