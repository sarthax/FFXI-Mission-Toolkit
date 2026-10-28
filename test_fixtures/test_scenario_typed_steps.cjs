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

console.log('Scenario typed step builder helpers: PASS');
