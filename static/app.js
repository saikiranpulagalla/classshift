'use strict';

const State = Object.freeze({
  READY: 'READY', IMPACT_PREVIEW: 'IMPACT_PREVIEW', SOLVING: 'SOLVING',
  OPTIMAL_RESULT: 'OPTIMAL_RESULT', INFEASIBLE_RESULT: 'INFEASIBLE_RESULT',
  INVALID_INPUT: 'INVALID_INPUT', ERROR: 'ERROR'
});

const model = { demo: null, state: State.READY, generation: 0, controller: null };
const $ = (id) => document.getElementById(id);

function setState(next) { model.state = next; }
function selectedPeriod() { return $('periodSelect').value; }
function selectedRooms() { return [...document.querySelectorAll('input[name="outage-room"]:checked')].map((el) => el.value); }

function text(tag, value, className = '') {
  const el = document.createElement(tag); el.textContent = value; if (className) el.className = className; return el;
}

function clearNode(node) { while (node.firstChild) node.removeChild(node.firstChild); }

function invalidateResults() {
  model.generation += 1;
  if (model.controller) model.controller.abort();
  model.controller = null;
  $('impactPanel').classList.add('hidden');
  $('resultPanel').classList.add('hidden');
  clearNode($('impactContent')); clearNode($('resultContent'));
  $('controlError').textContent = '';
  $('solveButton').disabled = false;
  setState(State.READY);
  renderTimetable();
}

function renderPeriods() {
  const select = $('periodSelect'); clearNode(select);
  for (const p of model.demo.periods) {
    const option = document.createElement('option'); option.value = p.id; option.textContent = p.label; select.appendChild(option);
  }
  const preferred = model.demo.periods.find((p) => p.id === 'MON_P3'); if (preferred) select.value = preferred.id;
}

function renderRooms() {
  const box = $('roomOptions'); clearNode(box);
  for (const room of model.demo.rooms.filter((r) => r.enabled)) {
    const label = document.createElement('label'); label.className = 'room-choice';
    const input = document.createElement('input'); input.type = 'checkbox'; input.name = 'outage-room'; input.value = room.id;
    input.addEventListener('change', invalidateResults);
    const span = document.createElement('span');
    span.appendChild(text('strong', room.label));
    span.appendChild(text('span', `Capacity ${room.capacity} · ${room.step_free_status}`, 'room-meta'));
    label.appendChild(input); label.appendChild(span); box.appendChild(label);
  }
}

function renderTimetable() {
  if (!model.demo) return;
  const body = $('timetableBody'); clearNode(body);
  const rooms = new Map(model.demo.rooms.map((r) => [r.id, r]));
  for (const lesson of model.demo.lessons.filter((l) => l.period_id === selectedPeriod())) {
    const tr = document.createElement('tr');
    tr.appendChild(text('td', lesson.label));
    tr.appendChild(text('td', rooms.get(lesson.original_room_id)?.label || lesson.original_room_id));
    tr.appendChild(text('td', String(lesson.student_count)));
    const req = document.createElement('td');
    if (lesson.required_features.length === 0 && !lesson.requires_step_free) req.textContent = 'Standard room';
    for (const feature of lesson.required_features) req.appendChild(text('span', feature, 'badge'));
    if (lesson.requires_step_free) req.appendChild(text('span', 'verified step-free metadata', 'badge'));
    if (lesson.locked) req.appendChild(text('span', 'locked', 'badge'));
    tr.appendChild(req); body.appendChild(tr);
  }
}

function previewImpact() {
  const rooms = selectedRooms();
  if (!rooms.length) { $('controlError').textContent = 'Select at least one unavailable room.'; return; }
  $('controlError').textContent = '';
  const affected = model.demo.lessons.filter((l) => l.period_id === selectedPeriod() && rooms.includes(l.original_room_id));
  clearNode($('impactContent'));
  if (!affected.length) $('impactContent').appendChild(text('p', 'No lesson is directly assigned to the selected unavailable room(s) in this period. The solver will still consider the full period if you continue.'));
  else {
    const list = document.createElement('ul');
    for (const lesson of affected) list.appendChild(text('li', `${lesson.label} is directly affected because its original room is unavailable.`));
    $('impactContent').appendChild(list);
  }
  $('impactPanel').classList.remove('hidden'); setState(State.IMPACT_PREVIEW);
}

function addStatus(container, className, heading, body) {
  const status = document.createElement('div'); status.className = `status ${className}`;
  const h = text('h2', heading); h.tabIndex = -1; status.appendChild(h); status.appendChild(text('p', body)); container.appendChild(status); return h;
}

function renderOptimal(result) {
  const root = $('resultContent'); clearNode(root);
  const heading = addStatus(root, 'success', 'Minimum-change recovery found', 'OR-Tools returned a proven optimum and the independent validator accepted the complete assignment.');
  const summary = document.createElement('div'); summary.className = 'summary-grid';
  for (const [value, label] of [[result.move_count, 'room changes'], [0, 'time changes'], ['Yes', 'modeled constraints validated']]) {
    const card = document.createElement('div'); card.className = 'summary-card'; card.appendChild(text('strong', String(value))); card.appendChild(text('span', label)); summary.appendChild(card);
  }
  root.appendChild(summary);
  const wrap = document.createElement('div'); wrap.className = 'table-wrap';
  const table = document.createElement('table');
  const thead = document.createElement('thead'); const hr = document.createElement('tr');
  for (const label of ['Lesson','Before','After','Why']) { const th = text('th', label); th.scope = 'col'; hr.appendChild(th); }
  thead.appendChild(hr); table.appendChild(thead);
  const tbody = document.createElement('tbody');
  if (result.moves.length === 0) {
    const tr = document.createElement('tr'); const td = text('td', 'No room changes are required.'); td.colSpan = 4; tr.appendChild(td); tbody.appendChild(tr);
  } else for (const move of result.moves) {
    const tr = document.createElement('tr');
    tr.appendChild(text('td', move.lesson_label)); tr.appendChild(text('td', move.from_room_id)); tr.appendChild(text('td', move.to_room_id, 'changed')); tr.appendChild(text('td', move.reason)); tbody.appendChild(tr);
  }
  table.appendChild(tbody); wrap.appendChild(table); root.appendChild(wrap);
  $('resultPanel').classList.remove('hidden'); setState(State.OPTIMAL_RESULT); heading.focus();
}

function renderFailure(result) {
  const root = $('resultContent'); clearNode(root); let heading;
  if (result.status === 'INFEASIBLE') { heading = addStatus(root, 'warn', 'No valid recovery found', 'No recovery satisfies all modeled constraints. ClassShift did not relax any hard constraint.'); if (result.explanation) root.appendChild(text('p', result.explanation)); setState(State.INFEASIBLE_RESULT); }
  else if (result.status === 'INVALID_INPUT') { heading = addStatus(root, 'error', 'Input could not be processed', result.message || 'The recovery request is invalid.'); setState(State.INVALID_INPUT); }
  else if (result.status === 'VALIDATOR_FAILURE') { heading = addStatus(root, 'error', 'Recovery blocked', 'A proposed recovery failed internal validation and was not displayed.'); setState(State.ERROR); }
  else { heading = addStatus(root, 'error', 'Recovery service error', 'The recovery engine did not return a usable result. This is different from an infeasible schedule.'); setState(State.ERROR); }
  $('resultPanel').classList.remove('hidden'); heading.focus();
}

async function solve() {
  const rooms = selectedRooms();
  if (!rooms.length) { $('controlError').textContent = 'Select at least one unavailable room.'; return; }
  $('controlError').textContent = ''; previewImpact();
  const generation = ++model.generation;
  if (model.controller) model.controller.abort();
  model.controller = new AbortController();
  setState(State.SOLVING); $('solveButton').disabled = true;
  clearNode($('resultContent')); const waiting = addStatus($('resultContent'), 'warn', 'Finding a constraint-valid recovery…', 'Considering every lesson in the affected period.');
  $('resultPanel').classList.remove('hidden');
  try {
    const response = await fetch('/api/recover', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ outages: rooms.map((room_id) => ({room_id, period_ids:[selectedPeriod()]})) }), signal: model.controller.signal });
    const result = await response.json();
    if (generation !== model.generation) return;
    if (result.status === 'OPTIMAL' && result.validated === true) renderOptimal(result); else renderFailure(result);
  } catch (error) {
    if (error.name === 'AbortError' || generation !== model.generation) return;
    renderFailure({status:'ERROR'});
  } finally {
    if (generation === model.generation) { $('solveButton').disabled = false; model.controller = null; }
  }
}

function reset() {
  if (model.controller) model.controller.abort();
  model.generation += 1;
  document.querySelectorAll('input[name="outage-room"]').forEach((el) => { el.checked = false; });
  const preferred = model.demo.periods.find((p) => p.id === 'MON_P3'); if (preferred) $('periodSelect').value = preferred.id;
  invalidateResults();
}

async function boot() {
  try {
    const response = await fetch('/api/demo'); if (!response.ok) throw new Error('demo load failed'); model.demo = await response.json();
    renderPeriods(); renderRooms(); renderTimetable();
    $('periodSelect').addEventListener('change', invalidateResults);
    $('previewButton').addEventListener('click', previewImpact); $('solveButton').addEventListener('click', solve); $('resetButton').addEventListener('click', reset);
  } catch (_error) {
    clearNode($('resultContent')); addStatus($('resultContent'), 'error', 'Demo could not load', 'The local demo dataset could not be loaded.'); $('resultPanel').classList.remove('hidden');
  }
}

document.addEventListener('DOMContentLoaded', boot);
