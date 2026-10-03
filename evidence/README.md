# Evidence

This directory contains only outputs from checks actually executed in the build environment.

- `test-results.txt` — dependency-free pytest subset covering strict input validation, candidate rules, independent solution validation, release-source invariants, and benchmark profile construction.
- `oracle-results.txt` — independent brute-force oracle verification for every golden fixture.
- `static-checks.txt` — Python compile, JavaScript syntax, diff whitespace, independence, and frontend safety checks.
- `release-verification.txt` — actual release-verification result for this environment.
- `dependency-install.txt` — actual dependency installation attempt from this sandbox.
- `benchmark.json` — created only if `scripts/benchmark.py` actually runs successfully (not present when unverified).

A PASS in a subset file is not a substitute for full release verification. The release verifier is authoritative for the environment in which it is run.
