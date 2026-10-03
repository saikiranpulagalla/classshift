# Evidence

This directory contains only outputs from checks actually executed in the build environment.

- `test-results.txt` — dependency-free pytest subset covering input validation, candidate rules, and independent solution validation.
- `oracle-results.txt` — independent brute-force oracle verification for every golden fixture.
- `static-checks.txt` — Python compile, JavaScript syntax, independence, and unsafe-pattern checks.
- `release-verification.txt` — actual release-verification result for this environment.
- `benchmark.json` — created only if `scripts/benchmark.py` is actually run successfully (not present when unverified).

A PASS in a subset file is not a substitute for full release verification. The release verifier is authoritative for the environment in which it is run.
