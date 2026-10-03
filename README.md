# ClassShift

**When a classroom goes offline, repair the schedule—not the whole school day.**

ClassShift is a deterministic decision-support prototype that finds the minimum number of same-time room changes needed after a classroom outage while preserving modeled room constraints.

## Why it exists
A classroom outage can create a chain reaction. Moving only the directly affected class can fail even when a valid recovery exists. ClassShift therefore solves **all lessons in each affected period** as one exact assignment problem.

The primary synthetic demo shows:

- Chemistry: `LAB_A → LAB_B`
- Biology: `LAB_B → LAB_C`
- Physics: `LAB_C → ROOM_D`

The three-room chain is forced by room feature compatibility. The objective is exactly the number of lessons whose room changes.

## Scope
ClassShift changes room assignments only. It does not change time/period, teacher, lesson identity, class size, or requirements, and it never auto-publishes a recovery. See [SPEC.md](SPEC.md) for the frozen contract and limitations.

## Architecture

`input validation → candidate graph → exact min-cost-flow assignment → independent solution validator → service/API → human review UI`

- `classshift/input_validator.py`: strict schema and baseline integrity checks
- `classshift/candidates.py`: eligible edges plus diagnostic rejection codes
- `classshift/optimizer.py`: OR-Tools exact min-cost-flow assignment
- `classshift/solution_validator.py`: deliberately independent correctness check over structured assignment records, preserving duplicate lessons and proposed period IDs until validation
- `scripts/brute_force_oracle.py`: independent tiny-instance exhaustive oracle
- `classshift/service.py`: status mapping, period decomposition, validation, explanations
- `app.py`: thin Flask API/UI host

## Hard constraints
Rooms must be enabled, available for the period, large enough, include all required features, satisfy `VERIFIED` step-free metadata when required, and respect absolute lesson locks. A room can host at most one lesson in a period.

`UNKNOWN` step-free metadata is not treated as verified. Passing this modeled check is not a claim of real-world accessibility or ADA compliance.

## Exact objective
Original-room edge cost = 0. Any other eligible room edge cost = 1. OR-Tools minimizes total edge cost, therefore minimizing the number of room changes. `OPTIMAL` is returned only for a proven optimum that subsequently passes the independent validator.

## Statuses
`OPTIMAL`, `INFEASIBLE`, `INVALID_INPUT`, `SOLVER_ERROR`, `VALIDATOR_FAILURE`, `INTERNAL_ERROR`.

`INFEASIBLE` is reserved for valid inputs where no complete recovery exists. Invalid baseline data is `INVALID_INPUT`; backend/solver failures are never relabeled as infeasibility. Public 500-class responses are intentionally generic; detailed solver/validator diagnostics stay in server logs.

## Install
Target runtime: **Python 3.11**.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run locally
Development only:

```bash
python app.py
```

Robust local/demo serving with Waitress:

```bash
waitress-serve --listen=127.0.0.1:8000 app:app
```

Then open `http://127.0.0.1:8000`.

## Tests

```bash
pytest -q
python scripts/verify_release.py
```

`pytest.ini` pins the repository root on the import path so the documented `pytest -q` command works consistently across launchers.

Tests cover strict input types, baseline integrity, candidate boundaries, exact-capacity behavior, outages, locks, step-free metadata, golden fixtures, forced-chain uniqueness, multi-period decomposition, conservative infeasibility explanations, duplicate/period-mutated solver proposals, API status separation, solver-error branches, executable request-race semantics, metamorphic properties, and OR-Tools-vs-brute-force differential checks on tiny deterministic instances. When Playwright and Chromium are available, `python scripts/browser_smoke.py` additionally executes the real frontend JavaScript/CSS against a controlled in-page stub backend to test stale-response suppression, reset/input clearing, keyboard focus, and narrow/reflow behavior without changing the runtime stack.

## Demo
1. Select **Monday · Period 3**.
2. Mark **Science Lab A** unavailable.
3. Preview impact: Chemistry is directly affected.
4. Find recovery.
5. Review the three-step chain and validation state.
6. For an infeasible example, select Monday · Period 1 and mark `ART_1` unavailable; Art 9 requires the synthetic `art_sink` feature, so no valid replacement exists and the system refuses to weaken hard constraints.

ClassShift does not invent a schedule when the constraints cannot be satisfied.

## Data and privacy
All bundled demo/fixture data is synthetic. There are no student names, real school records, accounts, secrets, or PII. The prototype accepts only outage selections against the bundled demo timetable through the UI API. `/api/demo` first loads the strict validated domain model and then serializes a canonical whitelist of period, room, and lesson fields; raw JSON keys are never passed through directly.

## Frontend robustness and accessibility design
The UI uses semantic controls and tables, a high-contrast focus indicator, keyboard-focusable horizontal table regions, text plus color for status, focus management for results, a narrow responsive layout, and reduced-motion-safe behavior. A dedicated `RequestGate` owns generation tokens and `AbortController`; its race semantics are executable in a JavaScript runtime so a stale response cannot overwrite a changed/reset selection. Dynamic content is inserted with safe DOM APIs (`textContent`), not HTML-string sinks.

These are implementation design measures, not a claim of formal accessibility certification.

## Performance
`scripts/benchmark.py` can record measured validation, candidate-generation, solver, validator, and total timings for deterministic **dense, sparse, bottleneck, and near-infeasible** synthetic cases at several sizes into `evidence/benchmark.json`. Do not quote numbers unless that file was produced by an actual run in the environment being discussed.

## Evidence policy
Only actual executed evidence belongs in `evidence/`. The release verifier checks a mandatory test-file/function manifest, rejects obviously trivialized mandatory tests, executes critical behavioral test nodes when target dependencies are available, and runs independent release probes. These checks are defenses against accidental or casual weakening, not a claim that a local repository verifier makes deliberate tampering impossible. It also checks strict fixture/oracle validity, validator/oracle independence, unsafe frontend sinks, request-gate wiring, JavaScript race semantics when Node.js is available, the browser frontend smoke when Playwright/Chromium are available, required runtime versions, Python 3.11, and pytest. Real benchmark evidence is intentionally trackable in Git once generated. No fabricated benchmark, user-validation, or test claims are included.

## AI disclosure
See [AI_USAGE.md](AI_USAGE.md). AI was used during development assistance, but no LLM participates in runtime recovery or runtime validation.

## License
MIT.
