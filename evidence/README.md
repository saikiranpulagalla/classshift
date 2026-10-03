# Evidence

This directory contains only outputs from checks actually executed in the build environment. Evidence from a test double is explicitly labeled and is never presented as real OR-Tools execution.

- `test-results.txt` — dependency-free pytest subset covering strict input validation, canonical demo serialization, candidate rules, structured independent solution validation, conservative explanations, release-source invariants, focus contrast, benchmark profile construction, and executable JavaScript request-race semantics.
- `full-test-attempt.txt` — the actual `pytest -q` attempt in this sandbox; it records dependency-related collection failures rather than presenting the dependency-free subset as the full suite.
- `oracle-results.txt` — independent brute-force oracle verification for every golden fixture, including the multi-period fixture and optimum-count checks.
- `static-checks.txt` — Python compile, JavaScript syntax, executable request-gate semantics, and diff-whitespace checks.
- `browser-smoke.txt` — headless Chromium execution of the actual frontend JavaScript/CSS with a controlled in-page stub backend, covering stale-response suppression, reset/input clearing, keyboard focus, and narrow/reflow behavior. It is frontend evidence, not Flask/OR-Tools backend evidence.
- `release-verification.txt` — actual release-verification result for this environment, including the mandatory test manifest and current runtime blockers.
- `release-gate-adversarial.txt` — actual adversarial checks showing the release verifier detects deleted/trivialized critical tests, missing source files without crashing, and missing required fixtures without emitting a misleading fixture PASS.
- `hardening-audit.txt` — actual RC5 hardening checks. Its min-cost-flow integration section uses an ephemeral local API-compatible test double because OR-Tools is unavailable here; this is explicitly not a substitute for real OR-Tools execution.
- `dependency-install.txt` — actual dependency installation attempt from this sandbox.
- `benchmark.json` — created and tracked only if `scripts/benchmark.py` actually runs successfully (not present when unverified).

A PASS in a subset or test-double file is not a substitute for full release verification. The release verifier is authoritative for the environment in which it is run.
