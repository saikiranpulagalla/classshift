from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names.add(module)
            names.update(f"{module}.{alias.name}" if module else alias.name for alias in node.names)
    return names


def test_solution_validator_is_independent_of_candidate_layer():
    names = imported_names(ROOT / "classshift" / "solution_validator.py")
    assert not any("candidates" in name or "unavailable_pairs" in name for name in names)


def test_brute_force_oracle_is_independent_of_production_solver_validation():
    names = imported_names(ROOT / "scripts" / "brute_force_oracle.py")
    forbidden = ("candidates", "optimizer", "solution_validator", "unavailable_pairs")
    assert not any(any(term in name for term in forbidden) for name in names)


def test_frontend_has_no_remote_dependency_or_innerhtml():
    text = "\n".join(
        (ROOT / rel).read_text(encoding="utf-8")
        for rel in ("templates/index.html", "static/styles.css", "static/app.js")
    )
    assert "http://" not in text
    assert "https://" not in text
    assert ".innerHTML" not in text


def test_frontend_contains_stale_response_defense():
    js = (ROOT / "static/app.js").read_text(encoding="utf-8")
    assert "generation" in js
    assert "AbortController" in js


def test_release_app_source_has_size_limit_and_no_debug_true():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "MAX_CONTENT_LENGTH" in source
    assert "debug=True" not in source


def test_room_selection_error_is_associated_with_control():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert '<fieldset aria-describedby="controlError">' in html
    assert 'id="controlError"' in html
