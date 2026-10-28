/* #1411 typed step builder: pure helpers. The DOM and server validation are covered by the Python route tests
 * and by a real-browser run; nothing here touches a network, game client or draft. */
const assert = require('node:assert/strict');
const T = require('../gui/static/scenario_typed_steps.js');

// number text: numbers become numbers, anything else is passed through for the server to reject with its reason
assert.equal(T.parseNumberText('12'), 12);
assert.equal(T.parseNumberText(' -4.5 '), -4.5);
assert.equal(T.parseNumberText('1e3'), 1000);
assert.equal(T.parseNumberText(''), undefined);
assert.equal(T.parseNumberText('   '), undefined);
assert.equal(T.parseNumberText(undefined), undefined);
assert.equal(T.parseNumberText('abc'), 'abc');
assert.equal(T.parseNumberText('1,5'), '1,5');
assert.equal(T.parseNumberText('Infinity'), 'Infinity');
assert.equal(T.parseNumberText('NaN'), 'NaN');
assert.equal(T.parseNumberText('9007199254740992'), 9007199254740992, '2^53 is a valid upper bound');
assert.equal(T.parseNumberText('9007199254740993'), '9007199254740993', 'beyond 2^53 cannot be represented, so the text is kept');
assert.equal(T.parseNumberText('1e400'), '1e400', 'overflow to infinity is not turned into a number');

// walk target composition
assert.deepEqual(T.composeWalkTarget({x: '1', y: '', z: '2'}), {value: [1, 2]});
assert.deepEqual(T.composeWalkTarget({x: '1', y: '3', z: '2'}), {value: [1, 3, 2]});
assert.deepEqual(T.composeWalkTarget({x: '1', z: '2', timeout_ms: '5000'}), {value: {coords: [1, 2], timeout_ms: 5000}});
assert.deepEqual(T.composeWalkTarget({x: '1', y: '3', z: '2', timeout_ms: '5000', stall_ms: '100'}),
  {value: {coords: [1, 3, 2], timeout_ms: 5000, stall_ms: 100}});
assert.deepEqual(T.composeWalkTarget({x: '1', z: '2', stall_ms: '7'}), {value: {coords: [1, 2], stall_ms: 7}});
assert.ok(T.composeWalkTarget({x: '', z: '2'}).error);
assert.ok(T.composeWalkTarget({x: '1', z: ''}).error);
assert.deepEqual(T.composeWalkTarget({x: 'a', z: '2'}), {value: ['a', 2]}, 'bad text still reaches the server for its reason');

// names
assert.equal(T.uniqueName('step', []), 'step');
assert.equal(T.uniqueName('step', ['step']), 'step (2)');
assert.equal(T.uniqueName('step', ['step', 'step (2)']), 'step (3)');
assert.equal(T.uniqueName('  ', []), 'step');
assert.equal(T.uniqueName(undefined, ['step']), 'step (2)');
assert.equal(T.uniqueName('x'.repeat(300), []).length, 100);

// native scenario shape: named steps with do / expect maps, copied (never aliased)
const built = {do: {walk_to: [1, 2]}, expect: {x_near: 3}, support_tier: 'HEADLESS_SCHEMA_ONLY', oracle_status: 'UNAPPROVED', verdict: 'UNKNOWN', execution_enabled: false};
const entries = [{name: 'go', step: built}, {name: 'talk', step: {do: {talk_npc: 7}, expect: {event_active: true}}}];
const native = T.nativeScenario(entries);
assert.deepEqual(native, [{name: 'go', do: {walk_to: [1, 2]}, expect: {x_near: 3}},
  {name: 'talk', do: {talk_npc: 7}, expect: {event_active: true}}]);
assert.ok(!('oracle_status' in native[0]) && !('verdict' in native[0]) && !('execution_enabled' in native[0]),
  'authority fields are Toolkit draft metadata, not part of the native step');
native[0].do.walk_to.push(9);
assert.deepEqual(built.do.walk_to, [1, 2], 'output must not alias the built step');
assert.deepEqual(JSON.parse(T.nativeJson(entries)), T.nativeScenario(entries));
assert.deepEqual(T.nativeScenario([]), []);

// readable description
assert.equal(T.describeStep({label: 'navigate near'}, built), 'navigate near — walk_to [1,2], then check x_near = 3');

// reorder
assert.deepEqual(T.moveItem([1, 2, 3], 1, -1), [2, 1, 3]);
assert.deepEqual(T.moveItem([1, 2, 3], 1, 1), [1, 3, 2]);
assert.deepEqual(T.moveItem([1, 2, 3], 0, -1), [1, 2, 3]);
assert.deepEqual(T.moveItem([1, 2, 3], 2, 1), [1, 2, 3]);
assert.deepEqual(T.moveItem([1, 2, 3], 5, 1), [1, 2, 3]);
const original = [1, 2, 3]; T.moveItem(original, 0, 1); assert.deepEqual(original, [1, 2, 3], 'input list is not mutated');

// ---- catalog picker helpers
assert.equal(T.catalogQueryProblem(''), 'Type part of a name to search.');
assert.equal(T.catalogQueryProblem('   '), 'Type part of a name to search.');
assert.equal(T.catalogQueryProblem(undefined), 'Type part of a name to search.');
assert.equal(T.catalogQueryProblem('guard'), '');
assert.equal(T.catalogQueryProblem('x'.repeat(64)), '');
assert.match(T.catalogQueryProblem('x'.repeat(65)), /at most 64/);
assert.equal(T.catalogUrl('npc', ' guard '), '/scenario-developer/catalog/search?kind=npc&query=guard&limit=12');
assert.equal(T.catalogUrl('zone', 'a&b=c d', 5), '/scenario-developer/catalog/search?kind=zone&query=a%26b%3Dc%20d&limit=5',
  'query text is encoded and cannot add parameters');
const good = {kind: 'npc', id: 17719298, name: 'Synthetic Guard', source_path: 'sql/npc_list.sql',
  identity_status: 'unreconciled_source_candidate', duplicate_id_in_results: false};
assert.equal(T.usableCandidate(good, 'npc'), true);
assert.equal(T.usableCandidate({...good, id: 0}, 'npc'), true);
for (const bad of [null, undefined, 'x', 7, [], {...good, kind: 'zone'}, {...good, id: -1}, {...good, id: 1.5},
  {...good, id: '5'}, {...good, id: 2 ** 60}, {...good, name: ''}, {...good, name: '  '}, {...good, name: 5},
  {...good, source_path: undefined}, {kind: 'npc'}])
  assert.equal(T.usableCandidate(bad, 'npc'), false, JSON.stringify(bad));
assert.equal(T.usableCandidate(good, 'zone'), false, 'a row of the wrong kind is never offered');
assert.equal(T.describeCandidate(good), 'Synthetic Guard (id 17719298)');
assert.match(T.describeCandidate({...good, duplicate_id_in_results: true}), /AMBIGUOUS: this ID appears more than once/);
assert.equal(T.describeCandidate({...good, name: 'n'.repeat(300)}).indexOf('n'.repeat(121)), -1, 'long names are cut');
assert.equal(T.provenanceNote(good, 'npc_id'), 'npc_id = 17719298 (Synthetic Guard) — unreconciled DSP source candidate from ' +
  'sql/npc_list.sql; not verified for this zone or client');
assert.equal(T.describeAction(built), 'walk_to [1,2], then check x_near = 3');
assert.equal(T.describeStep({label: 'navigate near'}, built), 'navigate near — ' + T.describeAction(built));

// ---- native import helpers
assert.deepEqual(T.parseNativeText(''), {error: 'Paste native scenario JSON to review.'});
assert.deepEqual(T.parseNativeText('   '), {error: 'Paste native scenario JSON to review.'});
assert.deepEqual(T.parseNativeText(undefined), {error: 'Paste native scenario JSON to review.'});
assert.match(T.parseNativeText('{oops').error, /^That is not valid JSON: /);
assert.match(T.parseNativeText('{"name":"solo"}').error, /array of steps\. Wrap a single step/);
assert.match(T.parseNativeText('"text"').error, /array of steps/);
assert.match(T.parseNativeText('null').error, /array of steps/);
assert.match(T.parseNativeText('[]').error, /1 to 100 steps/);
assert.match(T.parseNativeText(JSON.stringify(Array(101).fill({}))).error, /1 to 100 steps/);
assert.match(T.parseNativeText('[' + '"x",'.repeat(8000) + '"x"]').error, /too large/);
assert.deepEqual(T.parseNativeText(' [{"name":"a"}] '), {steps: [{name: 'a'}]});
assert.equal(T.parseNativeText(JSON.stringify(Array(100).fill(1))).steps.length, 100);
assert.equal(T.reviewRowText({index: 0, name: 'go', status: 'SUPPORTED', reasons: []}), '#1 go — SUPPORTED');
assert.equal(T.reviewRowText({index: 3, name: 'bad', status: 'INVALID', reasons: ['a', 'b']}), '#4 bad — INVALID: a; b');
assert.equal(T.reviewRowText({index: 1, name: null, status: 'INVALID', reasons: ['name']}), '#2 (unnamed) — INVALID: name');
assert.equal(T.reviewRowText({index: 0, name: 'n'.repeat(300), status: 'SUPPORTED', reasons: []}).length, '#1 '.length + 100 + ' — SUPPORTED'.length);
assert.equal(T.importProvenance({index: 2, name: 'go'}), 'Imported from pasted native JSON (step 3, "go") — unreviewed source; ' +
  'shape-checked only; accepted by a human reviewer');

// ---- single-sided steps (an action only, or a check only)
assert.equal(T.describeAction({do: {walk_to: [1, 2]}}), 'walk_to [1,2]');
assert.equal(T.describeAction({expect: {zone: 231}}), 'check zone = 231');
assert.equal(T.describeAction({do: {rest_hp: 50}, expect: {hpp: 90}}), 'rest_hp 50, then check hpp = 90');
const only = [{name: 'a', step: {do: {walk_to: [1, 2]}}}, {name: 'c', step: {expect: {zone: 231}}}];
assert.deepEqual(T.nativeScenario(only), [{name: 'a', do: {walk_to: [1, 2]}}, {name: 'c', expect: {zone: 231}}]);
assert.deepEqual(Object.keys(T.nativeScenario(only)[0]), ['name', 'do'], 'no empty expect object is written');
assert.deepEqual(Object.keys(T.nativeScenario(only)[1]), ['name', 'expect'], 'no empty do object is written');
assert.deepEqual(JSON.parse(T.nativeJson(only)), T.nativeScenario(only));

// ---- editor bridge: comparison ignores key order but not content, and the bridge is inert until the builder mounts
assert.equal(T.sameSteps({library_version: 1, steps: [{name: 'a', do: {x: 1}, expect: {y: 2}}]},
                         {steps: [{expect: {y: 2}, do: {x: 1}, name: 'a'}], library_version: 1}), true);
assert.equal(T.sameSteps({steps: [{name: 'a'}]}, {steps: [{name: 'b'}]}), false);
assert.equal(T.sameSteps({steps: [1, 2]}, {steps: [2, 1]}), false, 'step order is meaning');
assert.equal(T.sameSteps(null, {steps: []}), false);
assert.equal(T.bridge.get(), null, 'before mounting there is nothing to read, so the editor leaves native_steps alone');

console.log('Scenario typed step builder helpers: PASS');
