from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
REQUIRED = [
    "app.py", "requirements.txt", "pytest.ini", "README.md", "SPEC.md", "AI_USAGE.md", "LICENSE",
    "classshift/domain.py", "classshift/loader.py", "classshift/input_validator.py",
    "classshift/candidates.py", "classshift/optimizer.py", "classshift/solution_validator.py",
    "classshift/explain.py", "classshift/service.py", "scripts/brute_force_oracle.py",
    "scripts/benchmark.py", "scripts/verify_release.py", "data/demo_school.json",
    "templates/index.html", "static/styles.css", "static/app.js",
]
REQUIRED_FIXTURES = {
    "no_outage.json", "direct_move.json", "chain_2.json", "chain_3.json",
    "capacity_infeasible.json", "feature_infeasible.json", "locked_infeasible.json",
    "hall_bottleneck.json", "multi_outage.json", "equal_optimum.json",
}
OFFLINE_TESTS = [
    "tests/test_input_validation.py",
    "tests/test_candidates.py",
    "tests/test_solution_validator.py",
    "tests/test_release_static.py",
    "tests/test_benchmark_cases.py",
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


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)


def main() -> int:
    failures: list[str] = []
    notes: list[str] = []

    for rel in REQUIRED:
        if not (ROOT / rel).is_file():
            failures.append(f"missing required file: {rel}")

    fixture_names = {p.name for p in (ROOT / "fixtures").glob("*.json")}
    missing_fixtures = sorted(REQUIRED_FIXTURES - fixture_names)
    if missing_fixtures:
        failures.append(f"missing required fixture(s): {', '.join(missing_fixtures)}")

    # JSON syntax and strict domain validation are dependency-free and should run
    # even if Flask/OR-Tools cannot be installed in the current environment.
    try:
        from classshift.input_validator import parse_dataset, parse_outages
        from scripts.brute_force_oracle import brute_force_period

        demo_raw = json.loads((ROOT / "data/demo_school.json").read_text(encoding="utf-8"))
        parse_dataset(demo_raw)
        for path in sorted((ROOT / "fixtures").glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            dataset_raw = {k: raw[k] for k in ("periods", "rooms", "lessons")}
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
        forbidden_validator = {name for name in validator_imports if "candidates" in name or "unavailable_pairs" in name}
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
        for rel in ("templates/index.html", "static/styles.css", "static/app.js")
    )
    if ".innerHTML" in frontend_text:
        failures.append("unsafe innerHTML usage found in frontend")
    if "http://" in frontend_text or "https://" in frontend_text:
        failures.append("remote/CDN URL found in bundled frontend assets")
    if not any(token in (ROOT / "static/app.js").read_text(encoding="utf-8") for token in ("AbortController", "generation")):
        failures.append("stale-response protection token not found in frontend")
    else:
        notes.append("frontend release safety source checks: PASS")

    offline_proc = _run([sys.executable, "-m", "pytest", "-q", *OFFLINE_TESTS])
    if offline_proc.returncode != 0:
        failures.append("dependency-free pytest subset failed")
        print(offline_proc.stdout)
        print(offline_proc.stderr, file=sys.stderr)
    else:
        notes.append(f"dependency-free pytest: PASS ({offline_proc.stdout.strip()})")

    missing_runtime = []
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
