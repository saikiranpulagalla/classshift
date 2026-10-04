from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _copy_repo(tmp_path: Path) -> Path:
    destination = tmp_path / "repo"
    shutil.copytree(
        ROOT,
        destination,
        ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache"),
    )
    return destination


def _verify(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/verify_release.py", "--static-only"],
        cwd=repo,
        text=True,
        capture_output=True,
        timeout=30,
    )


def _tag_rc6(repo: Path) -> None:
    for command in (
        ["git", "init"],
        ["git", "add", "."],
        ["git", "-c", "user.name=Release Test", "-c", "user.email=release-test@example.invalid", "commit", "-m", "release test"],
        ["git", "tag", "v1.0.0-rc6"],
    ):
        subprocess.run(command, cwd=repo, check=True, text=True, capture_output=True, timeout=30)


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    [
        ("delete_optimizer", "missing required file: tests/test_optimizer.py"),
        ("delete_release_verifier", "missing required file: tests/test_release_verifier.py"),
        ("rename_optimizer_test", "missing mandatory release test(s)"),
        ("pass_optimizer_test", "trivial mandatory release test(s)"),
        ("docstring_optimizer_test", "trivial mandatory release test(s)"),
        ("assert_true_optimizer_test", "trivial mandatory release test(s)"),
        ("return_true_optimizer_test", "trivial mandatory release test(s)"),
        ("delete_fixture", "missing required fixture(s): chain_3.json"),
        ("debug", "debug=True found in app.py"),
        ("unsafe_dom", "dangerous frontend HTML/code sink(s) found"),
        ("remove_probe", "release probe layer is missing required probe(s)"),
        ("skip_optimizer_test", "uses forbidden mandatory pytest outcome(s): skip"),
        ("skipif_optimizer_test", "uses forbidden mandatory pytest outcome(s): skipif"),
        ("module_skipif_optimizer_test", "uses forbidden mandatory pytest outcome(s): module-level skip/xfail"),
        ("xfail_optimizer_test", "uses forbidden mandatory pytest outcome(s): xfail"),
        ("trivial_probe", "release probe layer has trivial required probe(s)"),
        ("missing_wsgi", "documented app:app entrypoint is missing"),
        ("protocol_relative_cdn", "remote/CDN URL found in bundled frontend assets"),
        ("spaced_debug", "debug=True found in app.py"),
        ("duplicate_demo_key", "fixture/domain verification failed"),
    ],
)
def test_release_verifier_rejects_adversarial_mutations(tmp_path, mutation, expected_reason):
    repo = _copy_repo(tmp_path)
    optimizer = repo / "tests" / "test_optimizer.py"
    if mutation == "delete_optimizer":
        optimizer.unlink()
    elif mutation == "delete_release_verifier":
        (repo / "tests" / "test_release_verifier.py").unlink()
    elif mutation == "rename_optimizer_test":
        optimizer.write_text(optimizer.read_text(encoding="utf-8").replace(
            "test_solver_error_not_infeasible", "test_renamed_solver_error"
        ), encoding="utf-8")
    elif mutation == "pass_optimizer_test":
        optimizer.write_text(
            "def test_solver_error_not_infeasible():\n    pass\n\n"
            "def test_unexpected_solver_status_is_solver_error():\n    pass\n\n"
            "def test_incomplete_optimal_assignment_is_solver_error():\n    pass\n",
            encoding="utf-8",
        )
    elif mutation == "docstring_optimizer_test":
        optimizer.write_text(
            "def test_solver_error_not_infeasible():\n    \"placeholder\"\n\n"
            "def test_unexpected_solver_status_is_solver_error():\n    \"placeholder\"\n\n"
            "def test_incomplete_optimal_assignment_is_solver_error():\n    \"placeholder\"\n",
            encoding="utf-8",
        )
    elif mutation == "assert_true_optimizer_test":
        optimizer.write_text(
            "def test_solver_error_not_infeasible():\n    assert True\n\n"
            "def test_unexpected_solver_status_is_solver_error():\n    assert True\n\n"
            "def test_incomplete_optimal_assignment_is_solver_error():\n    assert True\n",
            encoding="utf-8",
        )
    elif mutation == "return_true_optimizer_test":
        optimizer.write_text(
            "def test_solver_error_not_infeasible():\n    return True\n\n"
            "def test_unexpected_solver_status_is_solver_error():\n    return True\n\n"
            "def test_incomplete_optimal_assignment_is_solver_error():\n    return True\n",
            encoding="utf-8",
        )
    elif mutation == "delete_fixture":
        (repo / "fixtures" / "chain_3.json").unlink()
    elif mutation == "debug":
        app = repo / "app.py"
        app.write_text(app.read_text(encoding="utf-8").replace("debug=False", "debug=True"), encoding="utf-8")
    elif mutation == "unsafe_dom":
        app_js = repo / "static" / "app.js"
        app_js.write_text(app_js.read_text(encoding="utf-8") + "\nnode.innerHTML = 'unsafe';\n", encoding="utf-8")
    elif mutation == "remove_probe":
        probes = repo / "scripts" / "release_probes.py"
        probes.write_text(probes.read_text(encoding="utf-8").replace(
            "def probe_primary_chain() -> None:", "def removed_primary_chain() -> None:"
        ), encoding="utf-8")
    elif mutation in {"skip_optimizer_test", "skipif_optimizer_test", "xfail_optimizer_test"}:
        outcome = "skipif" if mutation.startswith("skipif") else ("skip" if mutation.startswith("skip") else "xfail")
        optimizer.write_text(
            "import pytest\n\n"
            f"def test_solver_error_not_infeasible():\n    pytest.{outcome}('disabled')\n\n"
            f"def test_unexpected_solver_status_is_solver_error():\n    pytest.{outcome}('disabled')\n\n"
            f"def test_incomplete_optimal_assignment_is_solver_error():\n    pytest.{outcome}('disabled')\n",
            encoding="utf-8",
        )
    elif mutation == "module_skipif_optimizer_test":
        optimizer.write_text(
            "import pytest\npytestmark = pytest.mark.skipif(True, reason='disabled')\n\n"
            "def test_solver_error_not_infeasible():\n    assert False\n\n"
            "def test_unexpected_solver_status_is_solver_error():\n    assert False\n\n"
            "def test_incomplete_optimal_assignment_is_solver_error():\n    assert False\n",
            encoding="utf-8",
        )
    elif mutation == "trivial_probe":
        probes = repo / "scripts" / "release_probes.py"
        probes.write_text(probes.read_text(encoding="utf-8").replace(
            "def probe_primary_chain() -> None:\n", "def probe_primary_chain() -> None:\n    return\n"
        ), encoding="utf-8")
    elif mutation == "missing_wsgi":
        app = repo / "app.py"
        app.write_text(app.read_text(encoding="utf-8").replace("app = create_app()", "application = create_app()"), encoding="utf-8")
    elif mutation == "protocol_relative_cdn":
        html = repo / "templates" / "index.html"
        html.write_text(html.read_text(encoding="utf-8") + '\n<script src="//cdn.example.com/test.js"></script>\n', encoding="utf-8")
    elif mutation == "spaced_debug":
        app = repo / "app.py"
        app.write_text(app.read_text(encoding="utf-8").replace("debug=False", "debug = True"), encoding="utf-8")
    elif mutation == "duplicate_demo_key":
        demo = repo / "data" / "demo_school.json"
        demo.write_text(demo.read_text(encoding="utf-8").replace('"capacity": 30,', '"capacity": 30, "capacity": 31,', 1), encoding="utf-8")
    else:
        raise AssertionError(f"unknown mutation: {mutation}")

    result = _verify(repo)
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert expected_reason in output


def test_release_verifier_rejects_version_tag_mismatch():
    from scripts.verify_release import version_tag_error

    assert version_tag_error("1.0.0rc2", ["v1.0.0-rc8"]) == (
        "package version/tag mismatch: package 1.0.0rc2, tag v1.0.0-rc8"
    )
