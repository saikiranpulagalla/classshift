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

process.stdout.write('request gate race semantics: PASS\n');
