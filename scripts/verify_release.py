from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "app.py", "requirements.txt", "README.md", "SPEC.md", "AI_USAGE.md", "LICENSE",
    "classshift/domain.py", "classshift/input_validator.py", "classshift/candidates.py",
    "classshift/optimizer.py", "classshift/solution_validator.py", "classshift/service.py",
    "data/demo_school.json", "templates/index.html", "static/styles.css", "static/app.js",
]


def main() -> int:
    failures = []
    for rel in REQUIRED:
        if not (ROOT / rel).is_file():
            failures.append(f"missing required file: {rel}")
    try:
        json.loads((ROOT / "data/demo_school.json").read_text(encoding="utf-8"))
        for path in sorted((ROOT / "fixtures").glob("*.json")):
            json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        failures.append(f"JSON load failed: {exc}")
    for module in ("flask", "waitress", "ortools"):
        if importlib.util.find_spec(module) is None:
            failures.append(f"missing required runtime dependency: {module}")
    if sys.version_info[:2] != (3, 11):
        failures.append(f"release target requires Python 3.11; running {sys.version.split()[0]}")
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    if "debug=True" in app_text:
        failures.append("debug=True found in app.py")
    js_text = (ROOT / "static/app.js").read_text(encoding="utf-8")
    if ".innerHTML" in js_text:
        failures.append("unsafe innerHTML usage found in static/app.js")
    proc = None
    if not any(item.startswith("missing required runtime dependency") for item in failures):
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, text=True, capture_output=True)
        if proc.returncode != 0:
            failures.append("pytest failed")
            print(proc.stdout)
            print(proc.stderr, file=sys.stderr)
    if failures:
        print("RELEASE VERIFICATION: FAIL")
        for item in failures:
            print(f"- {item}")
        return 1
    print("RELEASE VERIFICATION: PASS")
    if proc is not None:
        print(proc.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
