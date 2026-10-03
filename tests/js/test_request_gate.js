'use strict';

require('../../static/request_gate.js');
const RequestGate = globalThis.ClassShiftRequestGate;

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const gate = new RequestGate();
const first = gate.begin();
assert(gate.isCurrent(first.generation), 'first request should be current');
assert(first.signal.aborted === false, 'first request should start active');

const second = gate.begin();
assert(first.signal.aborted === true, 'starting request B must abort request A');
assert(!gate.isCurrent(first.generation), 'request A must become stale');
assert(gate.isCurrent(second.generation), 'request B must be current');
assert(gate.finish(first.generation) === false, 'stale A completion must not own cleanup');
assert(gate.isCurrent(second.generation), 'stale A completion must not invalidate B');

const generationAfterReset = gate.invalidate();
assert(second.signal.aborted === true, 'reset/input change must abort request B');
assert(!gate.isCurrent(second.generation), 'request B must become stale after reset');
assert(gate.isCurrent(generationAfterReset), 'reset generation should be current');
assert(gate.finish(second.generation) === false, 'late B completion must be ignored');

const third = gate.begin();
assert(gate.finish(third.generation) === true, 'current request should own cleanup');
assert(gate.controller === null, 'current cleanup should release controller');


// Simulate the application response-commit pattern. Even if an old request
// resolves after a newer request, the stale generation must never render.
const rendered = [];
function commitIfCurrent(token, label) {
  if (!gate.isCurrent(token.generation)) return false;
  rendered.push(label);
  return true;
}
const requestA = gate.begin();
const requestB = gate.begin();
assert(commitIfCurrent(requestB, 'B') === true, 'new request B should render');
assert(commitIfCurrent(requestA, 'A') === false, 'late stale request A must not render');
assert(rendered.join(',') === 'B', 'stale response must not overwrite current result');

const requestC = gate.begin();
gate.invalidate();
assert(commitIfCurrent(requestC, 'C') === false, 'response after reset/input change must not render');
assert(rendered.join(',') === 'B', 'reset-stale response must leave current rendered history unchanged');

process.stdout.write('request gate race semantics: PASS\n');
