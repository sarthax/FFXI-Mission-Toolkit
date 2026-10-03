(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'equipment') await renderEquipment();
  };

  let selectedSlot = null;
  let catalog = null; // {byId: Map, rows: [{id,label,search}]}
  const api = () => `/character-editor/characters/${selectedChar}`;

  async function getJson(url) {
    const r = await fetch(url);
    const d = await r.json().catch(() => ({detail: r.statusText}));
    if (!r.ok) throw new Error(d.detail || r.statusText);
    return d;
  }
  async function postJson(url, body) {
    const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const d = await r.json().catch(() => ({detail: r.statusText}));
    if (!r.ok) throw new Error(d.detail || r.statusText);
    return d;
  }
  // Effective value follows core: (value > 0 ? value + augValue : value - augValue) * (multiplier > 1 ? multiplier : 1)
  const fmtEffect = (e, v) => {
    const eff = (e.value >= 0 ? e.value + v : e.value - v) * (e.multiplier > 1 ? e.multiplier : 1);
    return `${e.mod_name}${e.pet ? ' (pet)' : ''} ${eff >= 0 ? '+' : ''}${eff}`;
  };
  const describe = (id, v) => {
    if (!id) return 'empty';
    const c = catalog && catalog.byId.get(id);
    return c ? c.effects.map(e => fmtEffect(e, v)).join(', ') : `unknown augment ${id}`;
  };
  const baseLabel = c => c.effects.map(e => `${e.mod_name} ${e.value >= 0 ? '+' : ''}${e.value}${e.multiplier > 1 ? ' x' + e.multiplier : ''}`).join(', ');

  async function loadCatalog() {
    if (catalog) return catalog;
    const d = await getJson('/character-editor/reference/augments.json');
    const rows = (d.rows || []).map(c => ({...c, label: baseLabel(c)}));
    catalog = {available: !!d.available, rows, byId: new Map(rows.map(c => [c.id, c]))};
    return catalog;
  }

  async function renderEquipment() {
    const box = document.getElementById('categoryData');
    if (!box || !selectedChar) return;
    box.querySelectorAll(':scope > .ce-equip-manager').forEach(n => n.remove());
    const shell = document.createElement('div');
    shell.className = 'ce-progression ce-equip-manager';
    shell.innerHTML = '<div class="ce-progress-empty">Loading equipment…</div>';
    box.prepend(shell);
    const sweep = () => box.querySelectorAll('details.ce-data-block').forEach(b => { if (/^\s*char_equip\b/.test(b.textContent)) b.remove(); });
    sweep();
    new MutationObserver(sweep).observe(box, { childList: true });
    setTimeout(sweep, 1500);

    let state;
    try { [state] = await Promise.all([getJson(`${api()}/equipment.json`), loadCatalog()]); }
    catch (e) { shell.innerHTML = `<div class="ce-progress-empty">Could not load equipment: ${esc(e.message)}</div>`; return; }
    const offline = editableOnline();
    const dis = offline ? '' : 'disabled';
    const slots = state.slots || [];
    if (!slots.length) { shell.innerHTML = '<div class="ce-progress-empty">This character has nothing equipped.</div>'; return; }
    if (!slots.some(s => s.equip_slot === selectedSlot)) selectedSlot = slots[0].equip_slot;
    let draft = null; // augments being edited for the selected slot: [{id,value}]

    shell.innerHTML = `<style>.ce-equip-manager .ce-split{display:grid;grid-template-columns:230px minmax(0,1fr);gap:10px;align-items:start}
      .ce-equip-manager .ce-split-nav{position:sticky;top:96px;display:flex;flex-direction:column;gap:2px}
      .ce-equip-manager .ce-split-item{display:flex;flex-direction:column;text-align:left;padding:4px 8px;font-size:12px;cursor:pointer;border:1px solid transparent;border-radius:4px;background:transparent;color:inherit}
      .ce-equip-manager .ce-split-item.active{border-color:var(--border,#555);background:rgba(255,255,255,.1)}.ce-equip-manager .ce-split-item small{font-size:10px;opacity:.7}
      .ce-equip-manager .ce-arow{display:grid;grid-template-columns:50px minmax(160px,1.4fr) 80px minmax(140px,1fr);gap:8px;align-items:center;padding:4px 6px;border-top:1px solid var(--border,#333);font-size:12px}
      .ce-equip-manager .ce-arow input{min-width:0;padding:2px 4px}.ce-equip-manager .ce-aug-actions{display:flex;gap:8px;margin-top:8px;align-items:center}
      @media(max-width:760px){.ce-equip-manager .ce-split{grid-template-columns:1fr}.ce-equip-manager .ce-split-nav{position:static}.ce-equip-manager .ce-arow{grid-template-columns:1fr 1fr}}</style>
      <div class="ce-progress-head"><strong>Equipped Items</strong>${offline ? pill('offline editing enabled','ok') : pill('editing locked until offline','warn')}<span class="ce-progress-source">Per-character augments are stored in the item's <code>extra</code> bytes (core layout: 4 slots of augment id + value 0-31). The Items editor changes the item for everyone; this changes only this copy.</span></div>
      <div class="ce-split"><nav class="ce-split-nav"></nav><section class="ce-split-detail"></section></div>
      <datalist id="ce-aug-list">${catalog.rows.map(c => `<option value="${c.id}">${esc(c.label)}</option>`).join('')}</datalist>`;
    const navEl = shell.querySelector('.ce-split-nav'), detail = shell.querySelector('.ce-split-detail');
    const current = () => slots.find(s => s.equip_slot === selectedSlot);
    const drawNav = () => {
      navEl.innerHTML = slots.map(s => {
        const n = s.augments.filter(a => a.id).length;
        return `<button class="ce-split-item${s.equip_slot === selectedSlot ? ' active' : ''}" data-s="${s.equip_slot}"><span><b>${esc(s.slot_name)}</b>: ${esc(s.name || (s.missing_row ? '(missing inventory row)' : `Item ${s.item_id}`))}</span><small>${n ? n + ' augment' + (n > 1 ? 's' : '') : 'no augments'}</small></button>`;
      }).join('');
      navEl.querySelectorAll('[data-s]').forEach(b => b.addEventListener('click', () => { selectedSlot = Number(b.dataset.s); draft = null; drawNav(); drawDetail(); }));
    };
    const drawDetail = () => {
      const s = current();
      if (s.missing_row) { detail.innerHTML = `<div class="ce-progress-empty">char_equip points at ${esc(String(s.location))}/${esc(String(s.inventory_slot))}, but no inventory row exists there.</div>`; return; }
      draft ||= s.augments.map(a => ({id: a.id, value: a.value}));
      const changed = draft.some((a, i) => a.id !== s.augments[i].id || a.value !== s.augments[i].value);
      detail.innerHTML = `<h3>${esc(s.slot_name)}: ${esc(s.name || `Item ${s.item_id}`)}</h3>
        <div class="ce-muted">Item ID ${s.item_id} · container ${s.location} slot ${s.inventory_slot} · extra <code>${esc(s.extra_hex)}</code></div>
        ${draft.map((a, i) => `<div class="ce-arow"><span>Slot ${i + 1}</span>
          <input type="number" min="0" max="2047" list="ce-aug-list" data-i="${i}" data-f="id" value="${a.id}" ${dis} title="Augment ID (0 = empty)">
          <input type="number" min="0" max="31" data-i="${i}" data-f="value" value="${a.value}" ${dis} title="Value 0-31">
          <span class="ce-muted">${esc(describe(a.id, a.value))}</span></div>`).join('')}
        <div class="ce-aug-actions"><button class="ce-aug-discard" ${changed ? '' : 'disabled'}>Reset</button><button class="ce-aug-apply primary" ${dis && 'disabled'} ${changed ? '' : 'disabled'}>Preview &amp; apply</button><span class="ce-aug-msg ce-muted"></span></div>`;
      detail.querySelectorAll('input[data-i]').forEach(inp => inp.addEventListener('change', () => {
        draft[Number(inp.dataset.i)][inp.dataset.f] = Math.max(0, Math.floor(Number(inp.value) || 0));
        drawDetail();
      }));
      detail.querySelector('.ce-aug-discard').addEventListener('click', () => { draft = null; drawDetail(); });
      detail.querySelector('.ce-aug-apply').addEventListener('click', async () => {
        const body = {location: s.location, slot: s.inventory_slot, augments: draft};
        const msg = detail.querySelector('.ce-aug-msg');
        try {
          const p = await postJson(`${api()}/augments/preview`, body);
          if (!p.ready) throw new Error((p.issues || []).filter(i => i.blocking).map(i => i.message).join('; ') || 'not write-ready');
          const lines = draft.map((a, i) => `Slot ${i + 1}: ${describe(a.id, a.value)}`).join('\n');
          if (!confirm(`Apply these augments to ${s.name || 'this item'}?\n\n${lines}`)) return;
          await postJson(`${api()}/augments/apply`, {...body, expected_source_fingerprint: p.source_fingerprint, approved: true});
        } catch (e) { msg.textContent = `Not applied: ${e.message}`; alert(`Not applied: ${e.message}`); return; }
        await selectCharacter(selectedChar);
        await loadCategory('equipment');
      });
    };
    drawNav(); drawDetail();
  }
})();
