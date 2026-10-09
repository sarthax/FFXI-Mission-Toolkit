(() => {
  // Reuse the Character Editor's stat grouping and encoded ID/value choices.
  // The underlying AH preview/execute remains the existing DSP Test-only path.
  const $ = id => document.getElementById(id);
  if (!$('ibAugSlots')) return;
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
  const signed = n => (n >= 0 ? '+' : '') + n;
  const suffix = e => e.unit === 'percent' ? '%' : e.unit === 'seconds' ? 's' : '';
  const effective = (e, v) => (e.value >= 0 ? e.value + v : e.value - v) * (e.multiplier > 1 ? e.multiplier : 1);
  const effectText = (e, v) => e.mod_name + (e.pet ? ' (pet)' : '') + ' ' + signed(effective(e, v)) + suffix(e);
  const draft = Array.from({length:4}, () => ({id:0, value:0}));
  let groups = new Map(), idGroup = new Map(), sorted = [], chosen = null, searchTimer = null, lookupSeq = 0;

  async function json(url) {
    const response = await fetch(url, {headers:{Accept:'application/json'}});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || response.statusText);
    return data;
  }
  function normalizeCatalog(rows) {
    groups = new Map(); idGroup = new Map();
    for (const record of rows) {
      const effects = record.effects || [];
      if (!effects.length) continue;
      const e = effects[0], single = effects.length === 1 && !e.pet;
      const key = single ? 's|' + e.mod + '|' + (e.multiplier > 1 ? e.multiplier : 1) : 'c|' + record.id;
      let group = groups.get(key);
      if (!group) {
        group = {key, label:single ? e.mod_name : effects.map(x => x.mod_name + (x.pet ? ' (pet)' : '')).join(' + '),
          special:!single, comment:single ? (e.comment || '') : effects.map(x => x.comment).filter(Boolean).join(' / '), options:new Map()};
        groups.set(key, group);
      }
      idGroup.set(Number(record.id), key);
      for (let v = 0; v < 32; v++) {
        const amount = single ? effective(e, v) : v;
        if (!group.options.has(amount)) group.options.set(amount, {id:Number(record.id), v, amount,
          text:single ? signed(amount) + suffix(e) : effects.map(x => effectText(x, v)).join(', ')});
      }
    }
    sorted = [...groups.values()].sort((a,b) => a.label.localeCompare(b.label));
    for (const g of sorted) {
      g.choices = [...g.options.values()].sort((a,b) => a.amount - b.amount);
      g.range = g.special ? '' : ' (' + g.choices[0].text + ' to ' + g.choices[g.choices.length-1].text + ')';
    }
  }
  function describe(a) {
    if (!a.id) return '';
    const group = groups.get(idGroup.get(a.id));
    const entry = group?.choices.find(x => x.id === a.id && x.v === a.value);
    return group ? group.label + ' ' + (entry?.text || '#' + a.id + ':' + a.value) : '#' + a.id;
  }
  function syncLegacyInputs() {
    $('ibAugItemId').value = chosen?.item_id || '';
    $('ibAugPairs').value = draft.filter(a => a.id).map(a => a.id + ':' + a.value).join(', ');
    $('ibAugSummary').textContent = draft.some(a => a.id)
      ? 'Configured bonuses: ' + draft.filter(a => a.id).map(describe).join(' · ')
      : 'Choose up to four bonuses. Each slot can be cleared independently.';
    $('ibAugChosen').style.display = chosen ? '' : 'none';
    if (chosen) {
      $('ibAugChosen').innerHTML = '<strong>' + esc(chosen.item_name) + '</strong> <small>#' +
        Number(chosen.item_id) + ' · ' + esc(chosen.category_path || 'Equipment') + '</small>';
    }
  }
  function render() {
    const q = $('ibAugStatSearch').value.toLowerCase().trim();
    const stats = sorted.filter(g => !q || (g.label + ' ' + g.comment + ' ' + g.key).toLowerCase().includes(q));
    $('ibAugSlots').innerHTML = draft.map((a, i) => {
      const current = groups.get(idGroup.get(a.id));
      const available = current && !stats.includes(current) ? [current,...stats] : stats;
      const option = g => '<option value="' + esc(g.key) + '"' + (current?.key === g.key ? ' selected' : '') +
        '>' + esc(g.label + g.range) + '</option>';
      const choices = current?.choices || [];
      return '<div class="ahc-card" style="display:grid;grid-template-columns:90px minmax(155px,1.4fr) minmax(110px,1fr) auto;gap:7px;align-items:center;margin:6px 0">' +
        '<strong>Augment ' + (i+1) + '</strong><select data-slot="' + i + '" data-field="stat">' +
        '<option value="">— None —</option><optgroup label="Stats">' + available.filter(g => !g.special).map(option).join('') +
        '</optgroup><optgroup label="Combined & pet">' + available.filter(g => g.special).map(option).join('') + '</optgroup></select>' +
        '<select data-slot="' + i + '" data-field="amount"' + (!current ? ' disabled' : '') + '>' +
        (current ? choices.map(x => '<option value="' + x.id + ':' + x.v + '"' +
          (x.id === a.id && x.v === a.value ? ' selected' : '') + '>' + esc(x.text) + '</option>').join('') :
          '<option>— Amount —</option>') + '</select>' +
        '<button class="b" data-slot="' + i + '" data-field="clear" type="button"' + (!a.id ? ' disabled' : '') + '>Clear</button>' +
        (a.id ? '<small style="grid-column:1/-1">' + esc(describe(a) + (current?.comment ? ' — ' + current.comment : '')) + '</small>' : '') +
        '</div>';
    }).join('');
    syncLegacyInputs();
  }
  $('ibAugSlots').addEventListener('change', event => {
    const t = event.target, i = Number(t.dataset.slot);
    if (!Number.isInteger(i) || i < 0 || i > 3) return;
    if (t.dataset.field === 'stat') {
      const g = groups.get(t.value), choice = g?.choices.find(x => x.amount > 0) || g?.choices[0];
      draft[i] = choice ? {id:choice.id,value:choice.v} : {id:0,value:0};
    } else if (t.dataset.field === 'amount') {
      const [id,value] = t.value.split(':').map(Number);
      draft[i] = {id,value};
    }
    render();
  });
  $('ibAugSlots').addEventListener('click', event => {
    const button = event.target.closest('[data-field="clear"]');
    if (!button) return;
    draft[Number(button.dataset.slot)] = {id:0,value:0}; render();
  });
  $('ibAugStatSearch').addEventListener('input', render);

  async function searchItems() {
    const q = $('ibAugItemSearch').value.trim();
    if (!q) { $('ibAugItemResults').hidden = true; return; }
    const seq = ++lookupSeq;
    try {
      const data = await json('/auction-house/console/item-search.json?q=' + encodeURIComponent(q) + '&limit=40');
      if (seq !== lookupSeq) return;
      const rows = (data.rows || []).filter(x => Number(x.stack_size || 1) === 1);
      $('ibAugItemResults').hidden = false;
      $('ibAugItemResults').innerHTML = rows.length ? rows.map((x,i) =>
        '<button class="b" style="display:flex;align-items:center;gap:8px;width:100%;text-align:left" data-item-index="' + i + '">' +
        '<img src="/character-editor/client-cache/icons/' + Number(x.item_id) + '.png" width="30" height="30" loading="lazy" onerror="this.style.display=\'none\'">' +
        '<span>' + esc((x.item_name || x.name || 'Item').replace(/_/g,' ')) + ' <small>#' + Number(x.item_id) + '</small></span></button>'
      ).join('') : '<div class="mut">No nonstacking items found.</div>';
      $('ibAugItemResults').querySelectorAll('[data-item-index]').forEach(b => b.addEventListener('click', () => {
        chosen = {...rows[Number(b.dataset.itemIndex)], item_name:rows[Number(b.dataset.itemIndex)].item_name ||
          rows[Number(b.dataset.itemIndex)].name || 'Item'};
        $('ibAugItemSearch').value = chosen.item_name.replace(/_/g,' ');
        $('ibAugItemResults').hidden = true;
        syncLegacyInputs();
      }));
    } catch (e) { $('ibAugItemResults').hidden = false; $('ibAugItemResults').textContent = e.message; }
  }
  $('ibAugItemSearch').addEventListener('input', () => {
    chosen = null; syncLegacyInputs();
    clearTimeout(searchTimer); searchTimer = setTimeout(searchItems, 180);
  });
  $('ibAugClear').addEventListener('click', () => {
    chosen = null; $('ibAugItemSearch').value = '';
    draft.forEach(a => { a.id = 0; a.value = 0; });
    $('ibAugItemResults').hidden = true; render();
  });
  let savedConfigs = [];
  async function refreshSaved() {
    const data = await json('/auction-house/rewards/augments/saved.json');
    savedConfigs = data.rows || [];
    const previous = $('ibAugSaved').value;
    $('ibAugSaved').innerHTML = '<option value="">Saved augmented rewards…</option>' +
      savedConfigs.map((x,i) => '<option value="' + i + '">' + esc(x.name) + ' · #' + x.item_id +
        ' (' + esc(x.family.toUpperCase()) + ')</option>').join('');
    if (previous && savedConfigs[Number(previous)]) $('ibAugSaved').value = previous;
  }
  $('ibAugLoad').addEventListener('click', () => {
    const config = savedConfigs[Number($('ibAugSaved').value)];
    if (!config || $('ibAugSaved').value === '') return;
    chosen = {item_id:config.item_id, item_name:'Item #' + config.item_id};
    $('ibAugItemSearch').value = chosen.item_name;
    draft.forEach((a,i) => {const next=config.augments[i] || {id:0,value:0};a.id=next.id;a.value=next.value;});
    render();
    $('ibAugResult').textContent = 'Loaded saved configuration. Inspect to verify against the active server.';
  });
  $('ibAugSave').addEventListener('click', async () => {
    try {
      if (!chosen?.item_id || !draft.some(a => a.id)) throw Error('Select an item and at least one augment');
      const name = window.prompt('Configuration name (1–120 characters):', chosen.item_name || 'Augmented reward');
      if (name == null) return;
      const response = await fetch('/auction-house/rewards/augments/save.json', {
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({name, item_id:chosen.item_id, augments:draft.filter(a=>a.id)})
      });
      const data = await response.json().catch(()=>({}));
      if (!response.ok) throw Error(data.detail || 'Save failed');
      await refreshSaved();
      const idx = savedConfigs.findIndex(x=>x.id===data.id);
      if (idx>=0) $('ibAugSaved').value=String(idx);
      $('ibAugResult').textContent='Saved ' + data.name + '. Delivery remains Test-gated.';
    } catch(e) { $('ibAugResult').textContent=e.message; }
  });
  $('ibAugDelete').addEventListener('click', async () => {
    const config=savedConfigs[Number($('ibAugSaved').value)];
    if (!config || $('ibAugSaved').value === '' || !window.confirm('Delete saved augmented reward "'+config.name+'"?')) return;
    try {
      const response=await fetch('/auction-house/rewards/augments/delete.json', {
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:config.id})
      });
      if(!response.ok)throw Error('Delete failed');
      await refreshSaved();
    } catch(e){ $('ibAugResult').textContent=e.message; }
  });
  refreshSaved().catch(e => {$('ibAugResult').textContent='Saved catalog unavailable: '+e.message;});
  json('/auction-house/rewards/augments/catalog.json')
    .then(data => { normalizeCatalog(data.rows || []); render(); })
    .catch(e => { $('ibAugSlots').textContent = 'Augment catalog unavailable: ' + e.message; });
  render();
})();
