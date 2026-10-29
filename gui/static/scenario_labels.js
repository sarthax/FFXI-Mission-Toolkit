/* Plain-language labels for canonical observation and operation names.
   Presentation only: the canonical names remain the stored values. Unknown names
   fall back to the raw canonical name so a new backend observation never disappears. */
(function (root) {
  'use strict';
  const OBSERVATIONS = {
    session: ['Session', 'Session established for the expected character'],
    client_bag: ['Bag (game client)', 'Bag contents as the game client shows them'],
    db_bag: ['Bag (database)', 'Bag contents saved in the server database'],
    client_safe: ['Mog Safe (game client)', 'Mog Safe contents as the game client shows them'],
    db_safe: ['Mog Safe (database)', 'Mog Safe contents saved in the server database'],
    client_key_items: ['Key items (game client)', 'Key items the client shows as held'],
    db_key_items: ['Key items (database)', 'Key items saved in the server database'],
    stored_furnishings: ['Stored furnishings', 'Furnishings held in storage, not installed'],
    installed_layout: ['Installed furnishing layout', 'Furnishings placed in the Mog House'],
    gm_active_ki: ['Active key items (GM readout)', 'Active key items reported by a read-only GM diagnostic'],
    gm_aura: ['Aura breakdown (GM readout)', 'Aura values reported by a read-only GM diagnostic']
  };
  const GROUPS = [
    ['Game client (what the player sees)', ['client_bag', 'client_safe', 'client_key_items']],
    ['Database (what the server saved)', ['db_bag', 'db_safe', 'db_key_items', 'stored_furnishings', 'installed_layout']],
    ['GM readouts (read-only diagnostics)', ['gm_active_ki', 'gm_aura']],
    ['Session', ['session']]
  ];
  const OPERATIONS = {
    equals: ['equals', 'is exactly equal to the expected value'],
    nonempty: ['is not empty', 'has at least one entry'],
    same_rows: ['has the same rows as', 'lists the same items and quantities as another observation'],
    all_zero: ['is all zeros', 'is eight values that are all 0']
  };
  // Operations that ignore the expected value.
  const NO_EXPECTED = new Set(['nonempty', 'all_zero']);

  function observation(name) {
    const e = OBSERVATIONS[name];
    return e ? e[0] : String(name);
  }
  function observationHint(name) { const e = OBSERVATIONS[name]; return e ? e[1] : ''; }
  function operation(name) { const e = OPERATIONS[name]; return e ? e[0] : String(name); }
  function operationHint(name) { const e = OPERATIONS[name]; return e ? e[1] : ''; }
  function groupOf(name) {
    for (const [title, names] of GROUPS) if (names.includes(name)) return title;
    return 'Other';
  }
  function sentence(row) {
    const exp = NO_EXPECTED.has(row.operation) ? ''
      : ' ' + (row.expected == null ? '(value not set)' : JSON.stringify(row.expected));
    return 'Check that ' + observation(row.observed) + ' ' + operation(row.operation) + exp + '.';
  }
  root.ScenarioLabels = {observation, observationHint, operation, operationHint, groupOf,
    sentence, noExpected: n => NO_EXPECTED.has(n), groups: () => GROUPS.map(g => g[0])};
})(typeof window !== 'undefined' ? window : globalThis);
