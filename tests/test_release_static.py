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


def test_frontend_has_no_remote_dependency_or_dangerous_html_sink():
    text = "\n".join(
        (ROOT / rel).read_text(encoding="utf-8")
        for rel in (
            "templates/index.html",
            "static/styles.css",
            "static/request_gate.js",
            "static/app.js",
        )
    )
    assert "http://" not in text
    assert "https://" not in text
    for sink in (".innerHTML", ".outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert sink not in text


def test_frontend_uses_explicit_request_gate_for_stale_response_defense():
    gate = (ROOT / "static/request_gate.js").read_text(encoding="utf-8")
    app = (ROOT / "static/app.js").read_text(encoding="utf-8")
    html = (ROOT / "templates/index.html").read_text(encoding="utf-8")
    assert "AbortController" in gate
    assert "generation" in gate
    assert "ClassShiftRequestGate" in gate
    assert "model.gate.begin()" in app
    assert "model.gate.isCurrent" in app
    assert "model.gate.invalidate()" in app
    assert html.index("request_gate.js") < html.index("app.js")


def test_release_app_source_has_size_limit_and_no_debug_true():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "MAX_CONTENT_LENGTH" in source
    assert "debug=True" not in source


def test_room_selection_error_is_associated_with_control():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert '<fieldset aria-describedby="controlError">' in html
    assert 'id="controlError"' in html


def test_scrollable_timetable_is_keyboard_focusable():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert 'class="table-wrap" tabindex="0"' in html
    assert ".table-wrap:focus-visible" in css
    assert "wrap.tabIndex = 0" in js


def test_focus_indicator_uses_opaque_high_contrast_token():
    css = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")
    assert "--focus: #003a8c" in css
    assert "outline: 3px solid var(--focus)" in css


def _relative_luminance(hex_color: str) -> float:
    values = [int(hex_color[i:i+2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(a: str, b: str) -> float:
    la, lb = sorted((_relative_luminance(a), _relative_luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_focus_indicator_contrast_exceeds_three_to_one_against_white():
    assert _contrast_ratio("#003a8c", "#ffffff") >= 3.0


def test_real_benchmark_evidence_is_not_gitignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "evidence/final/benchmark.json" not in gitignore


def test_release_verifier_manifest_covers_dependency_bound_critical_tests():
    from scripts.verify_release import REQUIRED_TEST_FILES, MANDATORY_TEST_FUNCTIONS

    critical_files = {
        "tests/test_api.py",
        "tests/test_optimizer.py",
        "tests/test_differential.py",
        "tests/test_golden_fixtures.py",
        "tests/test_properties.py",
        "tests/test_multi_period.py",
        "tests/test_service_integrity.py",
    }
    assert critical_files <= REQUIRED_TEST_FILES
    assert {
        "tests/test_api.py",
        "tests/test_optimizer.py",
        "tests/test_differential.py",
        "tests/test_golden_fixtures.py",
        "tests/test_properties.py",
        "tests/test_multi_period.py",
        "tests/test_service_integrity.py",
    } <= set(MANDATORY_TEST_FUNCTIONS)


def test_input_changes_are_wired_to_clear_and_invalidate_results():
    app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "model.gate.invalidate();" in app
    assert "clearNode($('resultContent'))" in app
    assert "input.addEventListener('change', invalidateResults)" in app
    assert "$('periodSelect').addEventListener('change', invalidateResults)" in app


def test_room_grid_can_shrink_below_nominal_card_width_for_zoom_reflow():
    css = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")
    assert "minmax(min(190px, 100%), 1fr)" in css


def test_release_tag_normalization_accepts_only_expected_rc_format():
    from scripts.verify_release import normalize_release_tag, version_tag_error

    assert normalize_release_tag("v1.0.0-rc6") == "1.0.0rc6"
    assert normalize_release_tag("1.0.0rc6") is None
    assert normalize_release_tag("v1.0.0") is None
    assert version_tag_error("1.0.0rc6", ["v1.0.0-rc6"]) is None
    assert "mismatch" in (version_tag_error("1.0.0rc5", ["v1.0.0-rc6"]) or "")
    assert version_tag_error("1.0.0rc6", []) is None
    assert "malformed" in (version_tag_error("1.0.0rc6", ["v1.0.0"]) or "")


def test_release_probe_manifest_covers_release_defining_invariants():
    from scripts.verify_release import REQUIRED_RELEASE_PROBES, _top_level_functions

    assert REQUIRED_RELEASE_PROBES <= _top_level_functions(ROOT / "scripts" / "release_probes.py")


def test_documented_wsgi_entrypoint_is_importable():
    from app import app

    assert callable(app.wsgi_app)
