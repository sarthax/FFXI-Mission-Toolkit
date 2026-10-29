'use strict';
const assert = require('node:assert/strict');
const R = require('../gui/static/catalog_entry_review.js');
const data = (state, revision = '2') => ({feature: 'inventory_observation', case: 'INV-1', revision, state});

// a publish request needs a reviewer note before anything is sent
assert.match(R.requestFor(data('PUBLISHED'), '').error, /Write a note first/);
assert.match(R.requestFor(data('PUBLISHED'), '   \n ').error, /Write a note first/);
assert.deepEqual(R.requestFor(data('PUBLISHED'), '  reviewed: shape only  ').body,
  {feature_id: 'inventory_observation', case_id: 'INV-1', revision: 2, state: 'PUBLISHED', note: 'reviewed: shape only'});
// other steps do not need a note, and keep one if given
assert.deepEqual(R.requestFor(data('VALIDATED_DESIGN'), '').body.note, '');
assert.equal(R.requestFor(data('ARCHIVED'), 'old').body.note, 'old');
// bounds: the note limit matches the server's, and the revision must be a positive integer
assert.equal(R.NOTE_MAX, 300);
assert.match(R.requestFor(data('ARCHIVED'), 'x'.repeat(301)).error, /longer than 300/);
assert.ok(R.requestFor(data('ARCHIVED'), 'x'.repeat(300)).body);
for (const bad of ['0', '-1', 'abc', '1.5', '', null]) assert.match(R.requestFor(data('ARCHIVED', bad), 'n').error, /Unknown revision/, String(bad));
// the request carries the state the button names; nothing is inferred
assert.equal(R.requestFor(data('VALIDATED_DESIGN'), '').body.state, 'VALIDATED_DESIGN');

console.log('Catalog entry review request builder: PASS');
