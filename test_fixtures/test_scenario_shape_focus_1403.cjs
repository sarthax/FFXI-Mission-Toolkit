/* #1403 malformed-shape boundaries and #1391 validation-summary focus. Synthetic only. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const M = require('../gui/static/scenario_guided_model.js');

// Forking a published case that lacks steps yields renderable arrays.
const published = M.clone(M.fresh());
delete published.steps; delete published.cleanup;
const forked = M.forkPublished(published);
assert.deepEqual(forked.steps, []);
assert.deepEqual(forked.cleanup, []);
assert.equal(published.steps, undefined, 'source object must not be mutated');

// Wrong-typed array fields are rejected with field-specific feedback, never thrown as TypeError.
const wrong = M.clone(M.fresh());
wrong.cleanup = 'x';
assert.throws(() => M.parseAdvanced(JSON.stringify(wrong)), /cleanup: must be an array/);
const badStep = M.clone(M.fresh());
badStep.steps[0].evidence_refs = 'client_bag';
assert.throws(() => M.parseAdvanced(JSON.stringify(badStep)), /steps\[0\]\.evidence_refs: must be an array/);
const badBehavior = M.clone(M.fresh());
badBehavior.behavior.given = 'x';
assert.throws(() => M.parseAdvanced(JSON.stringify(badBehavior)), /behavior\.given/);
const badFork = M.clone(M.fresh());
badFork.steps = {};
assert.throws(() => M.forkPublished(badFork), /steps: must be an array/);

// Missing arrays default; valid drafts round-trip unchanged.
const minimal = M.clone(M.fresh());
delete minimal.steps;
assert.deepEqual(M.parseAdvanced(JSON.stringify(minimal)).steps, []);
assert.deepEqual(M.parseAdvanced(JSON.stringify(M.fresh())), M.fresh());
assert.deepEqual(M.shapeIssues(M.fresh()), []);

// #1391: focus lands on the summary after errors are shown.
class Element {
  constructor() { this.hidden = true; this.children = []; this.attributes = {}; this.focused = false; }
  append(n) { this.children.push(n); }
  replaceChildren() { this.children = []; }
  setAttribute(k, v) { this.attributes[k] = v; }
  removeAttribute(k) { delete this.attributes[k]; }
  focus() { this.focused = true; }
}
const summary = new Element();
const win = {document: {getElementById: id => id === 'sd-validation-summary' ? summary : null,
  createElement: () => new Element()}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../gui/static/scenario_validation_feedback.js'), 'utf8'), {window: win});
assert.equal(win.ScenarioValidationFeedback.show([{field: 'purpose', message: 'Required'}]), true);
assert.equal(summary.focused, true);
assert.equal(summary.attributes.tabindex, '-1');
summary.focused = false;
assert.equal(win.ScenarioValidationFeedback.show([]), false);
assert.equal(summary.focused, false, 'no focus move when there is nothing to show');
console.log('Scenario shape boundaries and validation focus: PASS');
