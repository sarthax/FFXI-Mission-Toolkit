(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'spells-abilities') renderBlueSpellSlots();
  };

  function sourceText(catalog) {
    const src = catalog?.source || {};
    if (!src.available) return 'checkout spell catalog unavailable · numeric spell IDs shown';
    return `${src.kind || 'catalog'} · ${src.path || ''}`;
  }

  function rowFor(catalog, spellId) {
    const row = catalog?.items?.[String(spellId)];
    return row || {id:spellId, label:`Blue Spell ${spellId}`};
  }

  function renderBlueSpellSlots() {
    const box = document.getElementById('categoryData');
    const entry = activeCategoryData?.packed?.blue_spells;
    if (!box || !entry?.decoded) return;
    const decoded = entry.decoded || {};
    const catalog = entry.catalog || {};
    const shell = document.createElement('div');
    shell.className = 'ce-progression ce-blue-spell-slots';
    shell.innerHTML = `<div class="ce-progress-head"><strong>Set Blue Magic</strong>${pill(decoded.family?.toUpperCase() || '')}${pill(`${decoded.set_count || 0} / ${decoded.slot_count || 20} slots`)}${pill('read only')}<span class="ce-progress-source">${esc(sourceText(catalog))}</span></div><div class="ce-progress-card"><div class="ce-progress-list ce-blue-slot-list"></div></div>`;
    box.prepend(shell);
    const list = shell.querySelector('.ce-blue-slot-list');
    list.innerHTML = (decoded.slots || []).map(slot => {
      if (slot.empty) {
        return `<div class="ce-progress-row ce-readonly-row"><span>Slot ${slot.slot + 1}<small>stored 0 · empty</small></span><span class="ce-readonly-badge">Empty</span></div>`;
      }
      const row = rowFor(catalog, Number(slot.spell_id));
      return `<div class="ce-progress-row ce-readonly-row"><span>Slot ${slot.slot + 1}: ${esc(row.label)}<small>spell ID ${esc(slot.spell_id)} · stored ${esc(slot.stored_value)}${row.symbol ? ' · '+esc(row.symbol) : ''}</small></span><span class="ce-readonly-badge">Set</span></div>`;
    }).join('') || '<div class="ce-progress-empty">No blue-spell slot data.</div>';
  }
})();
