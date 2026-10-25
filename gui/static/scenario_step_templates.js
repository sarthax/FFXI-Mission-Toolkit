/* Starter step templates. Pure data + helper; never executes anything.
   "Do ..." wording is a written instruction for a human tester. Every step still binds
   read-only checks, because the canonical schema requires each step to link at least one
   assertion and one observation. Subject text is only interpolated into step wording. */
(function (root) {
  'use strict';
  const BAG_SAME = {observed: 'client_bag', operation: 'same_rows', expected: 'db_bag'};
  const SAFE_SAME = {observed: 'client_safe', operation: 'same_rows', expected: 'db_safe'};
  const TEMPLATES = [
    {key: 'add-item', label: 'Add an item to the bag, then confirm it was recorded',
      subject: 'Item name', fallback: 'the item',
      title: s => 'Tester adds ' + s + ' to the bag, then compares bag views',
      expected: s => 'After adding ' + s + ', the game client bag and the database bag list the same rows, and ' + s + ' appears in both.',
      checks: [BAG_SAME]},
    {key: 'remove-item', label: 'Remove an item from the bag, then confirm it was recorded',
      subject: 'Item name', fallback: 'the item',
      title: s => 'Tester removes ' + s + ' from the bag, then compares bag views',
      expected: s => 'After removing ' + s + ', the game client bag and the database bag list the same rows, and ' + s + ' appears in neither.',
      checks: [BAG_SAME]},
    {key: 'bag-matches', label: 'Confirm the client bag matches the database bag',
      title: () => 'Compare the bag in the game client with the bag in the database',
      expected: () => 'Both bag views list the same items and quantities.',
      checks: [BAG_SAME]},
    {key: 'item-in-bag', label: 'Confirm an item is in the bag (client and database)',
      subject: 'Item name', fallback: 'the item',
      title: s => 'Confirm ' + s + ' is in the bag in the client and the database',
      expected: s => 'Both bag views list the same rows and ' + s + ' is present in them.',
      checks: [BAG_SAME]},
    {key: 'item-gone', label: 'Confirm an item is no longer in the bag',
      subject: 'Item name', fallback: 'the item',
      title: s => 'Confirm ' + s + ' is not in the bag in the client or the database',
      expected: s => 'Both bag views list the same rows and ' + s + ' is absent from them.',
      checks: [BAG_SAME]},
    {key: 'bag-empty', label: 'Confirm the bag is empty',
      title: () => 'Confirm the bag is empty in the client and the database',
      expected: () => 'The game client bag and the database bag both contain no items.',
      checks: [{observed: 'client_bag', operation: 'equals', expected: []},
               {observed: 'db_bag', operation: 'equals', expected: []}]},
    {key: 'key-item-held', label: 'Confirm a key item is held (client and database)',
      subject: 'Key item name', fallback: 'the key item',
      title: s => 'Confirm ' + s + ' is held in the client and the database',
      expected: s => 'Both key item lists are populated and include ' + s + ' (checked by the reviewer).',
      checks: [{observed: 'client_key_items', operation: 'nonempty', expected: null},
               {observed: 'db_key_items', operation: 'nonempty', expected: null}]},
    {key: 'move-bag-safe', label: 'Move an item between the bag and the Mog Safe, then confirm both',
      subject: 'Item name', fallback: 'the item',
      title: s => 'Tester moves ' + s + ' between the bag and the Mog Safe, then compares both views',
      expected: s => 'After moving ' + s + ', client and database agree for both the bag and the Mog Safe.',
      checks: [BAG_SAME, SAFE_SAME]}
  ];

  function clone(x) { return JSON.parse(JSON.stringify(x)); }

  /** Returns a new spec with one step (plus any missing observations/checks) appended. */
  function apply(spec, key, subject) {
    const t = TEMPLATES.find(x => x.key === key);
    if (!t) throw new Error('Unknown step template');
    const name = (subject || '').trim().slice(0, 80) || t.fallback || '';
    const next = clone(spec);
    next.observations = next.observations || [];
    next.assertions = next.assertions || [];
    next.steps = next.steps || [];
    const ids = [];
    for (const c of t.checks) {
      if (!next.observations.includes(c.observed)) next.observations.push(c.observed);
      let found = next.assertions.find(a => a.observed === c.observed &&
        a.operation === c.operation && JSON.stringify(a.expected) === JSON.stringify(c.expected));
      if (!found) {
        let n = 1, id;
        const taken = new Set(next.assertions.map(a => a.id));
        const base = c.observed + '_' + c.operation;
        do { id = base + (n === 1 ? '' : '_' + n); n++; } while (taken.has(id));
        found = {id, operation: c.operation, observed: c.observed, expected: clone(c.expected)};
        next.assertions.push(found);
      }
      ids.push(found.id);
    }
    const used = new Set(next.steps.map(s => s.id));
    let n = 1, sid;
    do { sid = next.case_id + '-S' + String(n++).padStart(2, '0'); } while (used.has(sid));
    next.steps.push({
      id: sid, title: t.title(name).slice(0, 500), intent: 'observation',
      expected: t.expected(name).slice(0, 500),
      assertion_ids: ids, evidence_refs: t.checks.map(c => c.observed)
        .filter((v, i, a) => a.indexOf(v) === i),
      confidence_note: 'Created from a template. Expected outcome is the author intent, not source-verified.'
    });
    return next;
  }
  root.ScenarioStepTemplates = {list: () => TEMPLATES.map(t => ({key: t.key, label: t.label, subject: t.subject || ''})), apply};
})(typeof window !== 'undefined' ? window : globalThis);
