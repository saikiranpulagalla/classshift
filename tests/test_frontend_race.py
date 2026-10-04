from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_request_gate_race_semantics_execute_in_javascript_runtime():
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for the mandatory JavaScript race-semantic test")
    proc = subprocess.run(
        [node, "tests/js/test_request_gate.js"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "PASS" in proc.stdout
