from __future__ import annotations

import ast
import importlib.util
from importlib import metadata
import json
import math
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REQUIRED_FILES = {
    "app.py", "requirements.txt", "pytest.ini", "README.md", "SPEC.md", "AI_USAGE.md", "LICENSE",
    "classshift/domain.py", "classshift/loader.py", "classshift/input_validator.py",
    "classshift/candidates.py", "classshift/optimizer.py", "classshift/solution_validator.py",
    "classshift/explain.py", "classshift/service.py", "scripts/brute_force_oracle.py",
    "scripts/benchmark.py", "scripts/browser_smoke.py", "scripts/verify_release.py", "data/demo_school.json",
    "scripts/release_probes.py",
    "templates/index.html", "static/styles.css", "static/request_gate.js", "static/app.js",
}

REQUIRED_RELEASE_PROBES = {
    "probe_primary_chain",
    "probe_infeasible_fixture",
    "probe_validator_rejects_corruption",
    "probe_equal_optimum_minimum",
    "probe_wsgi_entrypoint",
}

REQUIRED_FIXTURES = {
    "no_outage.json", "direct_move.json", "chain_2.json", "chain_3.json",
    "capacity_infeasible.json", "feature_infeasible.json", "locked_infeasible.json",
    "hall_bottleneck.json", "multi_outage.json", "equal_optimum.json", "multi_period.json",
}

REQUIRED_TEST_FILES = {
    "tests/conftest.py",
    "tests/test_input_validation.py",
    "tests/test_loader.py",
    "tests/test_candidates.py",
    "tests/test_optimizer.py",
    "tests/test_solution_validator.py",
    "tests/test_golden_fixtures.py",
    "tests/test_properties.py",
    "tests/test_differential.py",
    "tests/test_api.py",
    "tests/test_release_static.py",
    "tests/test_benchmark_cases.py",
    "tests/test_explain.py",
    "tests/test_oracle.py",
    "tests/test_frontend_race.py",
    "tests/test_multi_period.py",
    "tests/test_service_integrity.py",
    "tests/test_release_verifier.py",
    "tests/js/test_request_gate.js",
}

# These test names encode high-value release invariants. Checking both file
# presence and key test functions prevents a critical file from being replaced
# with an empty/trivial placeholder while pytest still exits successfully.
MANDATORY_TEST_FUNCTIONS = {
    "tests/test_optimizer.py": {
        "test_solver_error_not_infeasible",
        "test_unexpected_solver_status_is_solver_error",
        "test_incomplete_optimal_assignment_is_solver_error",
    },
    "tests/test_solution_validator.py": {
        "test_duplicate_lesson_assignment_detected",
        "test_period_change_detected",
        "test_double_booking",
        "test_fake_move_count",
    },
    "tests/test_api.py": {
        "test_valid_optimal",
        "test_valid_infeasible",
        "test_validator_failure_never_returns_success_or_internal_diagnostics",
        "test_solver_error_does_not_leak_solver_diagnostic",
        "test_recover_server_dataset_validation_failure_is_generic_500",
        "test_unexpected_outage_validation_failure_is_generic_500",
    },
    "tests/test_differential.py": {"test_differential_small_random_cases"},
    "tests/test_golden_fixtures.py": {"test_golden", "test_chain3_exact_assignment"},
    "tests/test_properties.py": {"test_input_order_does_not_change_cost"},
    "tests/test_multi_period.py": {
        "test_two_affected_periods_are_combined_without_cross_period_room_conflict",
        "test_multi_period_request_is_infeasible_if_either_period_cannot_recover",
    },
    "tests/test_service_integrity.py": {
        "test_service_blocks_duplicate_proposals_without_exposing_validator_details",
        "test_service_blocks_period_mutation",
        "test_service_solver_error_is_generic",
    },
    "tests/test_loader.py": {"test_public_demo_serializer_whitelists_canonical_fields"},
    "tests/test_frontend_race.py": {
        "test_request_gate_race_semantics_execute_in_javascript_runtime"
    },
}

# The executable node list is derived from the same manifest used for source
# presence and sanity checks. This keeps every named critical invariant in one
# canonical declaration rather than letting a second list silently drift.
MANDATORY_TEST_NODES = tuple(
    f"{path}::{name}"
    for path in sorted(MANDATORY_TEST_FUNCTIONS)
    for name in sorted(MANDATORY_TEST_FUNCTIONS[path])
)

OFFLINE_TESTS = [
    "tests/test_input_validation.py",
    "tests/test_loader.py",
    "tests/test_candidates.py",
    "tests/test_solution_validator.py",
    "tests/test_release_static.py",
    "tests/test_benchmark_cases.py",
    "tests/test_explain.py",
    "tests/test_oracle.py",
    "tests/test_frontend_race.py",
]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            found.add(module)
            found.update(f"{module}.{alias.name}" if module else alias.name for alias in node.names)
    return found


def _test_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
    }


def _top_level_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _meaningful_test_body(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Reject obvious no-op tests without prescribing a test coding style."""
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body.pop(0)
    if not body:
        return False
    if isinstance(body[0], ast.Return):
        return False
    return not all(
        isinstance(statement, ast.Pass)
        or (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant))
        or (isinstance(statement, ast.Return) and statement.value is None)
        or isinstance(statement, (ast.Assign, ast.AnnAssign))
        or (
            isinstance(statement, ast.Assert)
            and isinstance(statement.test, ast.Constant)
            and statement.test.value is True
        )
        for statement in body
    )


def _trivial_required_probes(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return {name for name in REQUIRED_RELEASE_PROBES if name in functions and not _meaningful_test_body(functions[name])}


def _forbidden_pytest_outcomes(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"skip", "skipif", "xfail"}:
            found.add(node.func.attr)
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "pytestmark" for target in node.targets):
            if any(isinstance(child, ast.Attribute) and child.attr in {"skip", "skipif", "xfail"} for child in ast.walk(node.value)):
                found.add("module-level skip/xfail")
    return found


def _app_entrypoint_is_present(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return any(
        isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "app" for target in node.targets)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "create_app"
        for node in tree.body
    )


def _debug_enabled(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "run":
            if any(keyword.arg == "debug" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True for keyword in node.keywords):
                return True
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and node.value.value is True:
            for target in node.targets:
                if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant) and target.slice.value == "DEBUG":
                    return True
    return False


def _has_remote_asset_reference(html: str, css: str) -> bool:
    asset = re.compile(r"(?:src|href)\s*=\s*[\"']\s*(?://|https?://)|@import\s+(?:url\()?\s*[\"']?\s*(?://|https?://)|url\(\s*[\"']?\s*(?://|https?://)", re.I)
    return bool(asset.search(html) or asset.search(css))


def _mandatory_junit_passed(proc: subprocess.CompletedProcess[str], xml_path: Path) -> bool:
    if proc.returncode != 0 or not xml_path.is_file():
        return False
    root = ET.parse(xml_path).getroot()
    cases = root.findall(".//testcase")
    return (
        len(cases) >= len(MANDATORY_TEST_NODES)
        and not root.findall(".//skipped")
        and not root.findall(".//failure")
        and not root.findall(".//error")
    )


def _trivial_mandatory_tests(path: Path, required_names: set[str]) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    return {
        name for name in required_names
        if name in functions and not _meaningful_test_body(functions[name])
    }


def normalize_release_tag(tag: str) -> str | None:
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)-(rc\d+)", tag)
    if match is None:
        return None
    return f"{match.group(1)}.{match.group(2)}.{match.group(3)}{match.group(4)}"


def _package_version() -> str:
    source = (ROOT / "classshift" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']\s*$', source, re.MULTILINE)
    if match is None:
        raise ValueError("classshift.__version__ is missing")
    version = match.group(1)
    if re.fullmatch(r"\d+\.\d+\.\d+rc\d+", version) is None:
        raise ValueError(f"classshift.__version__ is malformed: {version!r}")
    return version


def version_tag_error(package_version: str, release_tags: list[str]) -> str | None:
    if len(release_tags) > 1:
        return "multiple exact release tags found"
    if not release_tags:
        return None
    expected_version = normalize_release_tag(release_tags[0])
    if expected_version is None:
        return f"malformed exact release tag: {release_tags[0]}"
    if package_version != expected_version:
        return f"package version/tag mismatch: package {package_version}, tag {release_tags[0]}"
    return None


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)


def _major_minor(version: str) -> tuple[int, int]:
    parts = version.split(".")
    if len(parts) < 2:
        raise ValueError(f"version has no major/minor pair: {version!r}")
    return int(parts[0]), int(parts[1])


def _exact_release_tags() -> list[str]:
    git = shutil.which("git")
    if not git or not (ROOT / ".git").exists():
        return []
    proc = _run([git, "tag", "--points-at", "HEAD"])
    if proc.returncode != 0:
        raise RuntimeError("could not inspect exact Git release tag")
    return [tag.strip() for tag in proc.stdout.splitlines() if tag.strip().startswith("v")]


def _is_finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _benchmark_provenance_error(benchmark: dict[str, object], package_version: str) -> str | None:
    environment = benchmark.get("environment")
    measured = benchmark.get("measured_code_commit")
    if not isinstance(environment, dict) or not isinstance(measured, str) or not measured:
        return "benchmark evidence exists but is incomplete"
    if benchmark.get("classshift_version") != package_version:
        return "benchmark classshift_version does not match package version"
    if not str(environment.get("python", "")).startswith("3.11."):
        return "benchmark evidence was not measured on Python 3.11"
    if not str(environment.get("ortools", "")).startswith("9.15."):
        return "benchmark evidence was not measured with OR-Tools 9.15.x"
    if not environment.get("os") or not environment.get("cpu"):
        return "benchmark environment provenance is incomplete"

    git = shutil.which("git")
    if git and (ROOT / ".git").exists():
        exists = _run([git, "cat-file", "-e", f"{measured}^{{commit}}"])
        if exists.returncode != 0:
            return "benchmark measured_code_commit does not name a local commit"
        ancestor = _run([git, "merge-base", "--is-ancestor", measured, "HEAD"])
        if ancestor.returncode != 0:
            return "benchmark measured_code_commit is not an ancestor of HEAD"
        changed = _run([git, "diff", "--name-only", f"{measured}..HEAD"])
        if changed.returncode != 0:
            return "could not inspect benchmark provenance diff"
        paths = [path for path in changed.stdout.splitlines() if path]
        if any(not path.startswith("evidence/final/") for path in paths):
            return "source changed after benchmark measurement"
    return None


def _benchmark_matrix_error(benchmark: dict[str, object]) -> str | None:
    expected_pairs = {
        (profile, lessons, rooms)
        for lessons, rooms in ((10, 15), (25, 35), (50, 70), (100, 130))
        for profile in ("dense", "sparse", "bottleneck", "near_infeasible")
    }
    cases = benchmark.get("cases")
    if not isinstance(cases, list):
        return "benchmark evidence exists but is incomplete"
    pairs = [(case.get("profile"), case.get("lessons"), case.get("rooms")) for case in cases if isinstance(case, dict)]
    if len(cases) != len(expected_pairs) or len(set(pairs)) != len(pairs) or set(pairs) != expected_pairs:
        return "benchmark matrix is incomplete or contains duplicate cases"
    for case in cases:
        if not isinstance(case, dict):
            return "benchmark matrix contains a malformed case"
        expected_status = "INFEASIBLE" if case["profile"] == "near_infeasible" else "OPTIMAL"
        if case.get("status") != expected_status:
            return "benchmark case status is inconsistent with its profile"
        timings = ("validation_ms", "candidate_generation_ms", "solver_ms", "pipeline_total_ms")
        if not all(_is_finite_number(case.get(name)) for name in timings):
            return "benchmark timing metadata is malformed"
        if expected_status == "INFEASIBLE":
            if case.get("validator_executed") is not False or case.get("validator_ms") is not None or case.get("validator_valid") is not None:
                return "benchmark validator execution metadata is inconsistent"
        elif (
            case.get("validator_executed") is not True
            or case.get("validator_valid") is not True
            or not _is_finite_number(case.get("validator_ms"))
        ):
            return "benchmark validator execution metadata is inconsistent"
    return None


def main(static_only: bool = False) -> int:
    failures: list[str] = []
    notes: list[str] = []

    for rel in sorted(REQUIRED_FILES | REQUIRED_TEST_FILES):
        if not (ROOT / rel).is_file():
            failures.append(f"missing required file: {rel}")

    fixture_dir = ROOT / "fixtures"
    fixture_names = {path.name for path in fixture_dir.glob("*.json")} if fixture_dir.is_dir() else set()
    missing_fixtures = sorted(REQUIRED_FIXTURES - fixture_names)
    if missing_fixtures:
        failures.append(f"missing required fixture(s): {', '.join(missing_fixtures)}")

    manifest_ok = all((ROOT / rel).is_file() for rel in REQUIRED_TEST_FILES)
    for rel, required_names in MANDATORY_TEST_FUNCTIONS.items():
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            present = _test_functions(path)
        except Exception as exc:
            failures.append(f"could not inspect mandatory tests in {rel}: {exc}")
            continue
        missing_names = sorted(required_names - present)
        if missing_names:
            manifest_ok = False
            failures.append(
                f"{rel} is missing mandatory release test(s): {', '.join(missing_names)}"
            )
        try:
            trivial_names = sorted(_trivial_mandatory_tests(path, required_names))
        except Exception as exc:
            failures.append(f"could not inspect mandatory test bodies in {rel}: {exc}")
            continue
        if trivial_names:
            manifest_ok = False
            failures.append(
                f"{rel} has trivial mandatory release test(s): {', '.join(trivial_names)}"
            )
        forbidden_outcomes = _forbidden_pytest_outcomes(path)
        if forbidden_outcomes:
            manifest_ok = False
            failures.append(f"{rel} uses forbidden mandatory pytest outcome(s): {', '.join(sorted(forbidden_outcomes))}")
    if manifest_ok:
        notes.append("mandatory test manifest: PASS")

    probes_path = ROOT / "scripts" / "release_probes.py"
    try:
        probe_names = _top_level_functions(probes_path)
        missing_probes = sorted(REQUIRED_RELEASE_PROBES - probe_names)
        if missing_probes:
            failures.append(
                f"release probe layer is missing required probe(s): {', '.join(missing_probes)}"
            )
        else:
            trivial_probes = sorted(_trivial_required_probes(probes_path))
            if trivial_probes:
                failures.append(f"release probe layer has trivial required probe(s): {', '.join(trivial_probes)}")
            else:
                notes.append("release probe manifest: PASS")
    except Exception as exc:
        failures.append(f"could not inspect release probe layer: {exc}")

    try:
        package_version = _package_version()
        git = shutil.which("git")
        if git and (ROOT / ".git").exists():
            release_tags = _exact_release_tags()
            tag_error = version_tag_error(package_version, release_tags)
            if tag_error:
                failures.append(tag_error)
            elif release_tags:
                notes.append(f"package version/tag consistency: PASS ({package_version})")
            else:
                notes.append("package version/tag consistency: UNVERIFIED (no exact release tag)")
        else:
            notes.append("package version/tag consistency: UNVERIFIED (Git metadata unavailable)")
    except Exception as exc:
        failures.append(f"package version verification failed: {exc}")

    try:
        python_files = [
            path for path in ROOT.rglob("*.py")
            if not any(part in {".git", ".venv", "__pycache__"} for part in path.parts)
        ]
        for path in python_files:
            ast.parse(
                path.read_text(encoding="utf-8"),
                filename=str(path),
                feature_version=(3, 11),
            )
        notes.append(f"Python 3.11 grammar parse: PASS ({len(python_files)} files)")
    except Exception as exc:
        failures.append(f"Python 3.11 grammar parse failed: {type(exc).__name__}: {exc}")

    fixture_failure_count = len(failures)
    try:
        from classshift.input_validator import parse_dataset, parse_outages
        from classshift.loader import load_json
        from scripts.brute_force_oracle import brute_force_period, brute_force_period_details

        demo_raw = load_json(ROOT / "data/demo_school.json")
        parse_dataset(demo_raw)
        for path in sorted(fixture_dir.glob("*.json")):
            raw = load_json(path)
            dataset_raw = {key: raw[key] for key in ("periods", "rooms", "lessons")}
            dataset = parse_dataset(dataset_raw)
            outages = parse_outages(raw.get("outages", []), dataset)
            expected = raw.get("expected", {})
            periods = sorted({pid for outage in outages for pid in outage.period_ids})
            total_moves = 0
            feasible = True
            for period_id in periods:
                period_feasible, moves = brute_force_period(dataset, outages, period_id)
                if not period_feasible:
                    feasible = False
                    break
                total_moves += moves or 0
            if not periods:
                feasible, total_moves = True, 0

            if expected.get("status") == "OPTIMAL":
                if not feasible or total_moves != expected.get("move_count"):
                    failures.append(f"fixture oracle mismatch: {path.name}")
                if path.name in {"chain_2.json", "chain_3.json"} and len(periods) == 1:
                    _ok, _best, optimal_count = brute_force_period_details(dataset, outages, periods[0])
                    if optimal_count != 1:
                        failures.append(f"fixture is not a unique minimum recovery: {path.name}")
                if path.name == "equal_optimum.json" and len(periods) == 1:
                    _ok, _best, optimal_count = brute_force_period_details(dataset, outages, periods[0])
                    if optimal_count < 2:
                        failures.append("equal_optimum fixture does not actually have multiple optima")
            elif expected.get("status") == "INFEASIBLE":
                if feasible:
                    failures.append(f"fixture expected infeasible but oracle found recovery: {path.name}")
            else:
                failures.append(f"fixture missing/invalid expected status: {path.name}")
        if not missing_fixtures and len(failures) == fixture_failure_count:
            notes.append("strict demo/fixture validation and brute-force fixture oracle: PASS")
    except Exception as exc:
        failures.append(f"fixture/domain verification failed: {type(exc).__name__}: {exc}")

    try:
        validator_imports = _imports(ROOT / "classshift" / "solution_validator.py")
        forbidden_validator = {
            name for name in validator_imports
            if "candidates" in name or "unavailable_pairs" in name
        }
        if forbidden_validator:
            failures.append("independent validator imports production candidate/outage eligibility support")

        oracle_imports = _imports(ROOT / "scripts" / "brute_force_oracle.py")
        forbidden_oracle = {
            name for name in oracle_imports
            if any(term in name for term in ("candidates", "optimizer", "solution_validator", "unavailable_pairs"))
        }
        if forbidden_oracle:
            failures.append("brute-force oracle imports production eligibility/optimizer/validator logic")
        if not forbidden_validator and not forbidden_oracle:
            notes.append("validator/oracle independence source check: PASS")
    except Exception as exc:
        failures.append(f"independence source check failed: {exc}")

    app_path = ROOT / "app.py"
    if app_path.is_file():
        app_text = app_path.read_text(encoding="utf-8")
        if _debug_enabled(app_path):
            failures.append("debug=True found in app.py")
        if "MAX_CONTENT_LENGTH" not in app_text:
            failures.append("request size limit not configured in app.py")
        if not _app_entrypoint_is_present(app_path):
            failures.append("documented app:app entrypoint is missing")

    frontend_paths = [
        ROOT / "templates/index.html",
        ROOT / "static/styles.css",
        ROOT / "static/request_gate.js",
        ROOT / "static/app.js",
    ]
    frontend_failure_count = len(failures)
    if all(path.is_file() for path in frontend_paths):
        html_text = (ROOT / "templates/index.html").read_text(encoding="utf-8")
        css_text = (ROOT / "static/styles.css").read_text(encoding="utf-8")
        frontend_text = "\n".join(path.read_text(encoding="utf-8") for path in frontend_paths)
        if _has_remote_asset_reference(html_text, css_text):
            failures.append("remote/CDN URL found in bundled frontend assets")
        dangerous_sinks = [
            sink
            for sink in (".innerHTML", ".outerHTML", "insertAdjacentHTML", "document.write", "eval(")
            if sink in frontend_text
        ]
        if dangerous_sinks:
            failures.append(
                f"dangerous frontend HTML/code sink(s) found: {', '.join(dangerous_sinks)}"
            )

        gate_text = (ROOT / "static/request_gate.js").read_text(encoding="utf-8")
        js_text = (ROOT / "static/app.js").read_text(encoding="utf-8")
        if not all(
            token in gate_text
            for token in ("AbortController", "generation", "ClassShiftRequestGate")
        ):
            failures.append("request gate is missing stale-response primitives")
        if not all(
            token in js_text
            for token in (
                "model.gate.begin()",
                "model.gate.isCurrent",
                "model.gate.invalidate()",
            )
        ):
            failures.append("app.js is not consistently using the request gate")

        if len(failures) == frontend_failure_count:
            notes.append("frontend release safety source checks: PASS")

        node = shutil.which("node")
        if node:
            node_proc = _run([node, "tests/js/test_request_gate.js"])
            if node_proc.returncode != 0:
                failures.append("JavaScript request-gate race test failed")
                print(node_proc.stdout)
                print(node_proc.stderr, file=sys.stderr)
            else:
                notes.append("JavaScript request-gate race semantics: PASS")
        else:
            notes.append(
                "JavaScript request-gate race semantics: UNVERIFIED (Node.js unavailable)"
            )

    browser_available = (
        importlib.util.find_spec("playwright") is not None
        and (shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome") or shutil.which("google-chrome-stable")) is not None
    )
    if browser_available and not static_only:
        browser_proc = _run([sys.executable, "scripts/browser_smoke.py"])
        if browser_proc.returncode != 0:
            failures.append("browser frontend smoke test failed")
            print(browser_proc.stdout)
            print(browser_proc.stderr, file=sys.stderr)
        else:
            notes.append(f"browser frontend smoke: PASS ({browser_proc.stdout.strip()})")
    else:
        notes.append("browser frontend smoke: UNVERIFIED (Playwright/Chromium unavailable)")

    if not static_only:
        offline_proc = _run([sys.executable, "-m", "pytest", "-q", *OFFLINE_TESTS])
        if offline_proc.returncode != 0:
            failures.append("dependency-free pytest subset failed")
            print(offline_proc.stdout)
            print(offline_proc.stderr, file=sys.stderr)
        else:
            notes.append(f"dependency-free pytest: PASS ({offline_proc.stdout.strip()})")

    runtime_targets = {
        "flask": ("Flask", (3, 1)),
        "waitress": ("waitress", (3, 0)),
        "ortools": ("ortools", (9, 15)),
    }
    missing_runtime: list[str] = []
    for module, (distribution, expected) in runtime_targets.items():
        if static_only:
            break
        if importlib.util.find_spec(module) is None:
            missing_runtime.append(module)
            failures.append(f"missing required runtime dependency: {module}")
            continue
        try:
            installed = metadata.version(distribution)
            actual = _major_minor(installed)
        except Exception as exc:
            failures.append(
                f"could not verify {distribution} version: {type(exc).__name__}: {exc}"
            )
            continue
        version_matches = actual[0] == expected[0] if module == "waitress" else actual == expected
        if not version_matches:
            failures.append(
                f"{distribution} release version mismatch: expected {expected[0]}.{expected[1]}.x, "
                f"running {installed}"
            )
        else:
            notes.append(f"{distribution} version: PASS ({installed})")

    if not static_only and sys.version_info[:2] != (3, 11):
        failures.append(f"release target requires Python 3.11; running {sys.version.split()[0]}")

    if not static_only and not missing_runtime:
        try:
            from scripts import release_probes

            for probe_name in sorted(REQUIRED_RELEASE_PROBES):
                getattr(release_probes, probe_name)()
            notes.append("independent release probes: PASS")
        except Exception as exc:
            failures.append(f"independent release probe failed: {type(exc).__name__}: {exc}")

        with tempfile.TemporaryDirectory() as temporary:
            junit_path = Path(temporary) / "mandatory.xml"
            mandatory_proc = _run([sys.executable, "-m", "pytest", "-q", f"--junitxml={junit_path}", *MANDATORY_TEST_NODES])
            mandatory_passed = _mandatory_junit_passed(mandatory_proc, junit_path)
        if not mandatory_passed:
            failures.append("mandatory critical pytest nodes did not all pass")
            print(mandatory_proc.stdout)
            print(mandatory_proc.stderr, file=sys.stderr)
        else:
            notes.append(f"mandatory critical pytest nodes: PASS ({mandatory_proc.stdout.strip()})")

        proc = _run([sys.executable, "-m", "pytest", "-q"])
        if proc.returncode != 0:
            failures.append("full pytest failed")
            print(proc.stdout)
            print(proc.stderr, file=sys.stderr)
        else:
            notes.append(f"full pytest: PASS ({proc.stdout.strip()})")

    benchmark_path = ROOT / "evidence" / "final" / "benchmark.json"
    exact_release = bool(_exact_release_tags()) if shutil.which("git") and (ROOT / ".git").exists() else False
    required_final_evidence = (
        "benchmark.json",
        "full-pytest.txt",
        "release-summary.txt",
        "waitress-smoke.txt",
    )
    if exact_release:
        missing_evidence = [name for name in required_final_evidence if not (ROOT / "evidence" / "final" / name).is_file()]
        if missing_evidence:
            failures.append(f"tagged release is missing required final evidence: {', '.join(missing_evidence)}")
    if benchmark_path.is_file():
        try:
            from classshift.loader import load_json

            benchmark = load_json(benchmark_path)
            if not isinstance(benchmark, dict):
                failures.append("benchmark evidence exists but is incomplete")
            elif (error := _benchmark_provenance_error(benchmark, package_version)):
                failures.append(error)
            elif (error := _benchmark_matrix_error(benchmark)):
                failures.append(error)
            else:
                notes.append(f"benchmark evidence: PRESENT ({len(benchmark['cases'])} measured cases)")
        except Exception as exc:
            failures.append(f"benchmark evidence is invalid: {exc}")
    else:
        notes.append("benchmark evidence: UNVERIFIED/not present")

    for note in notes:
        print(f"- {note}")
    if failures:
        print("RELEASE VERIFICATION: FAIL")
        for item in failures:
            print(f"- {item}")
        return 1

    print("RELEASE VERIFICATION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(static_only="--static-only" in sys.argv[1:]))
