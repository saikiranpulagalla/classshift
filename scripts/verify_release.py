from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REQUIRED_FILES = {
    "app.py", "requirements.txt", "pytest.ini", "README.md", "SPEC.md", "AI_USAGE.md", "LICENSE",
    "classshift/domain.py", "classshift/loader.py", "classshift/input_validator.py",
    "classshift/candidates.py", "classshift/optimizer.py", "classshift/solution_validator.py",
    "classshift/explain.py", "classshift/service.py", "scripts/brute_force_oracle.py",
    "scripts/benchmark.py", "scripts/verify_release.py", "data/demo_school.json",
    "templates/index.html", "static/styles.css", "static/request_gate.js", "static/app.js",
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
    },
    "tests/test_differential.py": {"test_differential_small_random_cases"},
    "tests/test_golden_fixtures.py": {"test_golden", "test_chain3_exact_assignment"},
    "tests/test_properties.py": {"test_input_order_does_not_change_cost"},
    "tests/test_multi_period.py": {
        "test_two_affected_periods_are_combined_without_cross_period_room_conflict"
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


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)


def main() -> int:
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
    if manifest_ok:
        notes.append("mandatory test manifest: PASS")

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

    try:
        from classshift.input_validator import parse_dataset, parse_outages
        from scripts.brute_force_oracle import brute_force_period, brute_force_period_details

        demo_raw = json.loads((ROOT / "data/demo_school.json").read_text(encoding="utf-8"))
        parse_dataset(demo_raw)
        for path in sorted(fixture_dir.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
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

    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    if "debug=True" in app_text:
        failures.append("debug=True found in app.py")
    if "MAX_CONTENT_LENGTH" not in app_text:
        failures.append("request size limit not configured in app.py")

    frontend_text = "\n".join(
        (ROOT / rel).read_text(encoding="utf-8")
        for rel in (
            "templates/index.html",
            "static/styles.css",
            "static/request_gate.js",
            "static/app.js",
        )
    )
    if "http://" in frontend_text or "https://" in frontend_text:
        failures.append("remote/CDN URL found in bundled frontend assets")
    dangerous_sinks = [
        sink for sink in (".innerHTML", ".outerHTML", "insertAdjacentHTML", "document.write", "eval(")
        if sink in frontend_text
    ]
    if dangerous_sinks:
        failures.append(f"dangerous frontend HTML/code sink(s) found: {', '.join(dangerous_sinks)}")

    gate_text = (ROOT / "static/request_gate.js").read_text(encoding="utf-8")
    js_text = (ROOT / "static/app.js").read_text(encoding="utf-8")
    if not all(token in gate_text for token in ("AbortController", "generation", "ClassShiftRequestGate")):
        failures.append("request gate is missing stale-response primitives")
    if not all(token in js_text for token in ("model.gate.begin()", "model.gate.isCurrent", "model.gate.invalidate()")):
        failures.append("app.js is not consistently using the request gate")
    else:
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
        notes.append("JavaScript request-gate race semantics: UNVERIFIED (Node.js unavailable)")

    offline_proc = _run([sys.executable, "-m", "pytest", "-q", *OFFLINE_TESTS])
    if offline_proc.returncode != 0:
        failures.append("dependency-free pytest subset failed")
        print(offline_proc.stdout)
        print(offline_proc.stderr, file=sys.stderr)
    else:
        notes.append(f"dependency-free pytest: PASS ({offline_proc.stdout.strip()})")

    missing_runtime: list[str] = []
    for module in ("flask", "waitress", "ortools"):
        if importlib.util.find_spec(module) is None:
            missing_runtime.append(module)
            failures.append(f"missing required runtime dependency: {module}")
    if sys.version_info[:2] != (3, 11):
        failures.append(f"release target requires Python 3.11; running {sys.version.split()[0]}")

    if not missing_runtime:
        proc = _run([sys.executable, "-m", "pytest", "-q"])
        if proc.returncode != 0:
            failures.append("full pytest failed")
            print(proc.stdout)
            print(proc.stderr, file=sys.stderr)
        else:
            notes.append(f"full pytest: PASS ({proc.stdout.strip()})")

    benchmark_path = ROOT / "evidence" / "benchmark.json"
    if benchmark_path.is_file():
        try:
            benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
            if not benchmark.get("cases") or not benchmark.get("environment"):
                failures.append("benchmark evidence exists but is incomplete")
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
    raise SystemExit(main())
