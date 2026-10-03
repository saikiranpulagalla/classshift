# Evidence

This directory contains only outputs from checks actually executed in the build environment.

- `test-results.txt` — dependency-free pytest subset covering strict input validation, candidate rules, independent solution validation, conservative explanations, release-source invariants, and benchmark profile construction.
- `full-test-attempt.txt` — the actual `pytest -q` attempt in this sandbox; it records dependency-related collection failures rather than presenting the dependency-free subset as the full suite.
- `oracle-results.txt` — independent brute-force oracle verification for every golden fixture.
- `static-checks.txt` — Python compile, JavaScript syntax, diff whitespace, independence, and frontend safety checks.
- `release-verification.txt` — actual release-verification result for this environment.
- `dependency-install.txt` — actual dependency installation attempt from this sandbox.
- `benchmark.json` — created only if `scripts/benchmark.py` actually runs successfully (not present when unverified).

A PASS in a subset file is not a substitute for full release verification. The release verifier is authoritative for the environment in which it is run.
