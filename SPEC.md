# ClassShift Specification

## Purpose
ClassShift is a decision-support tool for school timetable/operations administrators. It repairs **room assignments only** when one or more rooms are unavailable for whole scheduled period instances.

## Frozen scope
ClassShift may change only a lesson's room. It never changes lesson identity, teacher, period/time, student count, or requirements. It does not publish changes automatically. Teacher absence, cross-period walking/continuity, equipment movement, notifications, accounts, databases, maps, IoT, runtime AI, and full timetable generation are outside this MVP.

## Period and outage semantics
Period IDs are unique scheduled instances such as `MON_P3`. An outage applies to the whole period. Periods are solved independently because this MVP intentionally has no cross-period constraints. Adding room continuity, teacher walking, portable equipment, or similar cross-period constraints would invalidate that decomposition.

## Hard constraints
A room assignment is eligible only when the room is enabled, not unavailable for the lesson period, has capacity `>= student_count`, contains every required feature, satisfies step-free metadata when required (`VERIFIED` only), and respects an absolute lesson lock. `UNKNOWN` is never treated as verified.

The accessibility check is only a check against supplied metadata. It is not a claim of real-world accessibility or legal/ADA compliance.

## Input validity
Untrusted JSON is validated before optimization. IDs and references must be valid and unique. Capacities and student counts are strict positive integers (booleans and floats are rejected). Feature identifiers are trimmed, lowercased, deduplicated, and must match `^[a-z0-9_]+$`.

The baseline timetable must already satisfy room existence, enabled state, capacity, required features, step-free metadata, and no same-period double booking. A malformed/invalid baseline is `INVALID_INPUT`; it is not a recovery infeasibility.

Duplicate/overlapping outage entries are canonicalized by unioning period IDs per room.

## Exact objective
For every affected period, every lesson in that period participates in a bipartite assignment against rooms. Eligible original-room edges cost 0; eligible moved-room edges cost 1. Each lesson must be assigned exactly once and each room at most once per period. OR-Tools min-cost flow minimizes the total cost, which is exactly the number of room changes.

This whole-period assignment is necessary to discover relocation chains that a directly-affected-only greedy approach would miss.

## Locks
`locked=true` is absolute. The lesson may only remain in its original room. If that room is unavailable for the period, the recovery is infeasible.

## Status semantics
- `OPTIMAL`: OR-Tools returned a proven optimum and the complete combined assignment passed the independent validator.
- `INFEASIBLE`: a valid model has no complete constraint-valid assignment.
- `INVALID_INPUT`: request or baseline data is malformed/invalid.
- `SOLVER_ERROR`: optimizer exception or non-optimal/non-infeasible solver state. Public solver-error text is generic; low-level status/exception detail is internal logging only.
- `VALIDATOR_FAILURE`: solver output failed independent validation and is blocked. Public responses do not expose validator diagnostics.
- `INTERNAL_ERROR`: unexpected application failure.

## Independent validator
Every successful proposal is independently checked without calling production candidate-eligibility logic. Solver output remains a sequence of immutable assignment records `(lesson_id, period_id, room_id)` until validation, rather than being collapsed into a dictionary first. This preserves duplicate lesson proposals and proposed period IDs so the validator can independently detect duplicates, missing/invented lessons, period mutation, known/enabled/available rooms, capacity, features, step-free metadata, locks, double booking, and false move counts. Only a validated proposal is converted to the public assignment map.

## Limitations
The MVP uses synthetic data, whole-period outages, room-only repair, and no cross-period constraints. Multi-period requests are composed from independently solved period instances and independently validated as one complete proposal; the same physical room may therefore be reused in different periods. It is a prototype decision-support tool, not a school information system or automatic publishing system.
