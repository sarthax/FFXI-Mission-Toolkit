// Inventory screen: containers that hold items open by default, readable item details instead of raw "Extra" bytes,
// search / filters / tile view, and an item pop-up that can edit any item (not just worn gear).
(() => {
  const G = window.CEGear;
  if (!G || !document.querySelector('.character-editor-page') || typeof loadInventory !== 'function') return;

  const GIL_ID = 65535;
  const pane = () => document.getElementById('inventoryContainers');
  const st = {view: 'tiles', filter: 'all', q: '', open: {}};
  try { st.view = localStorage.getItem('ceInvView') || 'tiles'; } catch (e) {}
  let data = null; // {containers, gear: Map, worn: Map, eq, player}
  const key = (l, s) => `${l}:${s}`;

  if (!document.getElementById('ce-inv-styles')) {
    const s = document.createElement('style');
    s.id = 'ce-inv-styles';
    s.textContent = `
      #inventoryContainers.ce-gearui .ce-invbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0}
      #inventoryContainers .ce-invbar input[type=search]{min-width:160px;padding:3px 6px}
      #inventoryContainers .ce-chip{padding:2px 9px;border:1px solid var(--border,#444);border-radius:12px;background:transparent;color:inherit;cursor:pointer;font-size:12px}
      #inventoryContainers .ce-chip.on{border-color:#6aa9ff;background:rgba(106,169,255,.2)}
      #inventoryContainers .ce-gil{font-weight:700;color:#f5c542;margin-left:auto}
      #inventoryContainers details.ce-bag{border:1px solid var(--border,#444);border-radius:6px;margin-bottom:8px;padding:0 8px}
      #inventoryContainers details.ce-bag>summary{cursor:pointer;padding:8px 0;display:flex;gap:10px;align-items:center}
      #inventoryContainers .ce-bar{width:90px;height:6px;border-radius:3px;background:rgba(255,255,255,.12);overflow:hidden}
      #inventoryContainers .ce-bar i{display:block;height:100%;background:#6aa9ff}.ce-bar.full i{background:#ff8a80}
      #inventoryContainers .ce-bagbody{padding-bottom:8px}
      #inventoryContainers .ce-invtable{width:100%;border-collapse:collapse;font-size:12px}
      #inventoryContainers .ce-invtable td,#inventoryContainers .ce-invtable th{padding:3px 6px;text-align:left;border-bottom:1px solid rgba(255,255,255,.08)}
      #inventoryContainers .ce-invtable tr.row{cursor:pointer}#inventoryContainers .ce-invtable tr.row:hover{background:rgba(106,169,255,.1)}
      #ceItemDialog{max-width:min(860px,94vw);width:100%;border:1px solid var(--border,#555);border-radius:8px;background:var(--bg,#1e1e1e);color:inherit;padding:14px}
      #ceItemDialog::backdrop{background:rgba(0,0,0,.6)}
      #ceItemDialog .ce-x{float:right}#ceItemDialog .ce-desc{margin:6px 0;padding:6px 8px;border-left:3px solid #6aa9ff;background:rgba(255,255,255,.05);font-size:13px}
      #ceItemDialog .ce-acts{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:8px 0}
      #ceItemDialog .ce-acts input[type=number]{width:90px}`;
    document.head.appendChild(s);
  }

  const rareText = it => [it?.rare ? 'Rare' : '', it?.exclusive ? 'Ex' : ''].filter(Boolean).join('/');
  const augSummary = g => (g.augments || []).filter(a => a.id).map(a => describeAug(a)).join(', ');
  let cat = null;
  const describeAug = a => { const r = cat && cat.byId.get(a.id); return r ? r.effects.map(e => `${e.mod_name}${e.pet ? ' (pet)' : ''} ${G.signed((e.value >= 0 ? e.value + a.value : e.value - a.value) * (e.multiplier > 1 ? e.multiplier : 1))}${e.unit === 'percent' ? '%' : ''}`).join(', ') : `Augment #${a.id}`; };

  function infoFor(c, r) {
    const id = Number(r.itemId ?? r.item_id ?? 0);
    const g = data.gear.get(key(c.location, r.slot));
    const w = data.worn.get(key(c.location, r.slot));
    return {c, r, id, g, w, name: (r.item?.name || g?.name || `Item ${id}`).replace(/_/g, ' ').replace(/\b\w/g, m => m.toUpperCase()),
      rare: rareText(r.item), stack: Number(r.item?.stack_size || 1), aug: g ? (g.augments || []).filter(a => a.id).length : 0};
  }
  function detailText(i) {
    const bits = [];
    if (i.w) bits.push(`Worn: ${i.w}`);
    if (i.g) { const l = G.gearLine(i.g); if (l) bits.push(l); if (i.g.equip_block) bits.push('⚠ ' + i.g.equip_block); const a = augSummary(i.g); if (a) bits.push('✦ ' + a); }
    if (i.rare) bits.push(i.rare);
    if (i.r.bazaar) bits.push('Bazaar');
    return bits.join(' · ');
  }
  const passes = i => {
    const q = st.q.trim().toLowerCase();
    if (q && !i.name.toLowerCase().includes(q)) return false;
    switch (st.filter) {
      case 'gear': return !!i.g;
      case 'aug': return i.aug > 0;
      case 'worn': return !!i.w;
      case 'stack': return i.stack > 1;
      case 'rare': return !!i.rare;
      default: return true;
    }
  };

  function render() {
    const box = pane();
    box.classList.add('ce-gearui');
    const gilRow = (data.containers.find(c => c.location === 0)?.rows || []).find(r => Number(r.itemId) === GIL_ID);
    const chips = [['all', 'All'], ['gear', 'Gear'], ['aug', 'Augmented'], ['worn', 'Equipped'], ['stack', 'Stackable'], ['rare', 'Rare/Ex']];
    const bags = data.containers.map(c => {
      const rows = (c.rows || []).filter(r => Number(r.itemId ?? r.item_id) !== GIL_ID).map(r => infoFor(c, r));
      const shown = rows.filter(passes);
      const cap = c.capacity;
      const used = rows.length;
      const filtering = st.q || st.filter !== 'all';
      const open = st.open[c.location] ?? used > 0;
      if (filtering && !shown.length) return '';
      const pct = cap ? Math.min(100, Math.round(used / cap * 100)) : 0;
      const body = !shown.length ? '<div class="ce-muted">Empty</div>' : st.view === 'tiles'
        ? `<div class="ce-tiles">${shown.map(i => `<button class="ce-tile" data-loc="${c.location}" data-slot="${i.r.slot}" title="${esc(i.name)}${i.w ? ' — worn in ' + esc(i.w) : ''}">${i.aug ? `<span class="bd">✦${i.aug}</span>` : ''}${i.w ? '<span class="wn">worn</span>' : ''}${G.iconImg(i.id, 32)}<span class="nm">${esc(i.name)}</span>${i.r.quantity > 1 ? `<span class="qt">${i.r.quantity}</span>` : ''}</button>`).join('')}</div>`
        : `<table class="ce-invtable"><thead><tr><th></th><th>Slot</th><th>Item</th><th>Qty</th><th>Details</th></tr></thead><tbody>${shown.map(i => `<tr class="row" data-loc="${c.location}" data-slot="${i.r.slot}"><td>${G.iconImg(i.id, 24)}</td><td>${esc(i.r.slot)}</td><td><strong>${esc(i.name)}</strong></td><td>${esc(i.r.quantity)}</td><td class="ce-muted">${esc(detailText(i))}</td></tr>`).join('')}</tbody></table>`;
      return `<details class="ce-bag" data-loc="${c.location}" ${open ? 'open' : ''}><summary><strong>${esc(c.label || c.name)}</strong>${cap ? `<span class="ce-bar${used >= cap ? ' full' : ''}"><i style="width:${pct}%"></i></span><span class="ce-muted">${used}/${cap}</span>` : `<span class="ce-muted">${used} item${used === 1 ? '' : 's'} · capacity not tracked</span>`}</summary><div class="ce-bagbody">${body}</div></details>`;
    }).join('');
    box.innerHTML = `<div class="ce-invbar"><input type="search" placeholder="Search all containers…" value="${esc(st.q)}">${chips.map(([k, l]) => `<button class="ce-chip${st.filter === k ? ' on' : ''}" data-f="${k}">${l}</button>`).join('')}<button class="ce-chip" data-view="${st.view === 'tiles' ? 'list' : 'tiles'}">${st.view === 'tiles' ? 'List view' : 'Tile view'}</button>${gilRow ? `<span class="ce-gil" title="Gil in Inventory slot 0">${Number(gilRow.quantity).toLocaleString()} gil</span>` : ''}</div>${bags || '<div class="ce-muted">Nothing matches.</div>'}`;
    const q = box.querySelector('input[type=search]');
    q.addEventListener('input', () => { st.q = q.value; const p = q.selectionStart; render(); const n = pane().querySelector('input[type=search]'); n.focus(); n.setSelectionRange(p, p); });
    box.querySelectorAll('[data-f]').forEach(b => b.addEventListener('click', () => { st.filter = b.dataset.f; render(); }));
    box.querySelectorAll('[data-view]').forEach(b => b.addEventListener('click', () => { st.view = b.dataset.view; try { localStorage.setItem('ceInvView', st.view); } catch (e) {} render(); }));
    box.querySelectorAll('details.ce-bag').forEach(d => d.addEventListener('toggle', () => { st.open[d.dataset.loc] = d.open; }));
    box.querySelectorAll('[data-loc][data-slot]').forEach(b => b.addEventListener('click', () => {
      const c = data.containers.find(x => x.location === Number(b.dataset.loc));
      const r = c.rows.find(x => x.slot === Number(b.dataset.slot));
      openItem(infoFor(c, r));
    }));
  }

  async function load() {
    if (!selectedChar) return;
    const box = pane();
    if (!data) box.innerHTML = '<div class="ce-muted">Loading…</div>';
    try {
      cat = await G.loadCatalog().catch(() => null);
      const [inv, aug, eq] = await Promise.all([
        G.getJson(`${G.api()}/inventory.json`),
        G.getJson(`${G.api()}/augmentable-inventory.json`).catch(() => ({items: []})),
        G.getJson(`${G.api()}/equipment.json`).catch(() => ({slots: []}))]);
      const gear = new Map((aug.items || []).map(g => [key(g.location, g.inventory_slot), g]));
      const worn = new Map((eq.slots || []).filter(s => !s.empty && !s.missing_row).map(s => [key(s.location, s.inventory_slot), s.slot_name]));
      data = {containers: inv.containers || [], gear, worn, eq: eq.slots || [], player: aug.player || eq.player};
      if (window.CEInventoryRefreshState) window.CEInventoryRefreshState().catch(() => {});
      render();
    } catch (e) { box.textContent = e.message; }
  }

  // ---- item pop-up ----
  async function openItem(i) {
    let dlg = document.getElementById('ceItemDialog');
    if (!dlg) { dlg = document.createElement('dialog'); dlg.id = 'ceItemDialog'; dlg.className = 'ce-gearui'; document.body.appendChild(dlg); }
    const offline = editableOnline() && Number(i.c.location) !== 3;
    let meta = {};
    try { meta = (await G.getJson(`/character-editor/client-cache/items/${i.id}.json`)).metadata || {}; } catch (e) {}
    const flags = [i.rare, i.stack > 1 ? `Stacks to ${i.stack}` : '', meta.type_name].filter(Boolean).join(' · ');
    const dests = data.containers.filter(c => c.capacity && c.location !== 3 && c.location !== i.c.location && c.count < c.capacity);
    const slotsFor = i.g ? data.eq.filter(e => (i.g.slot_mask & (1 << e.equip_slot)) && [0, 8, 10, 11, 12].includes(i.c.location)) : [];
    dlg.innerHTML = `<button class="ce-x" aria-label="Close">✕</button>
      <div class="ce-head">${G.iconImg(i.id, 48)}<div><h3>${esc(i.name)}</h3><div class="ce-muted">${esc(i.c.label || i.c.name)} · slot ${i.r.slot} · qty ${i.r.quantity}${flags ? ' · ' + esc(flags) : ''}</div></div></div>
      ${meta.description ? `<div class="ce-desc">${esc(meta.description)}</div>` : ''}
      ${i.w ? `<div class="ce-muted">Currently worn in the ${esc(i.w)} slot.</div>` : ''}
      ${i.g && i.g.equip_block ? `<div class="ce-warn">⚠ ${esc(i.g.equip_block)} — can't be equipped by this character.</div>` : ''}
      <div class="ce-acts">
        ${i.stack > 1 ? `<label>Quantity <input type="number" min="1" max="${i.stack}" value="${i.r.quantity}" class="ce-q" ${offline ? '' : 'disabled'}></label><button data-a="quantity" ${offline ? '' : 'disabled'}>Set</button>` : ''}
        <label>Move to <select class="ce-dest" ${offline && dests.length ? '' : 'disabled'}>${dests.map(c => `<option value="${c.location}">${esc(c.label || c.name)} (${c.count}/${c.capacity})</option>`).join('') || '<option>No free space</option>'}</select></label><button data-a="move" ${offline && dests.length ? '' : 'disabled'}>Move</button>
        <button data-a="remove" ${offline ? '' : 'disabled'}>Remove</button>
        ${offline ? '' : '<span class="ce-muted">Log the character out to make changes.</span>'}
      </div>
      ${slotsFor.length ? `<div class="ce-acts"><strong>Equip in:</strong>${slotsFor.map(e => `<button data-eq="${e.equip_slot}" ${offline && !i.g.equip_block ? '' : 'disabled'}>${esc(e.slot_name)}</button>`).join('')}</div>` : ''}
      <div class="ce-bonuses"></div>`;
    dlg.querySelector('.ce-x').onclick = () => dlg.close();
    const refresh = async () => { dlg.close(); await selectCharacter(selectedChar); data = null; await load(); };
    dlg.querySelectorAll('[data-a]').forEach(b => b.addEventListener('click', async () => {
      const body = {source_location: i.c.location, source_slot: i.r.slot, action: b.dataset.a};
      if (body.action === 'quantity') body.quantity = Number(dlg.querySelector('.ce-q').value);
      if (body.action === 'move') body.destination_location = Number(dlg.querySelector('.ce-dest').value);
      try {
        const p = await G.postJson(`${G.api()}/inventory/preview`, body);
        if (!p.ready) throw new Error((p.issues || []).filter(x => x.blocking).map(x => x.message).join('; ') || 'not write-ready');
        const what = body.action === 'remove' ? `Delete ${i.name} from ${i.c.label || i.c.name}?` : body.action === 'move' ? `Move ${i.name} to ${p.destination_name}?` : `Set ${i.name} quantity to ${body.quantity}?`;
        if (!confirm(what)) return;
        await G.postJson(`${G.api()}/inventory/apply`, {...body, expected_source_fingerprint: p.source_fingerprint, approved: true});
        await refresh();
      } catch (e) { alert(`Not changed: ${e.message}`); }
    }));
    dlg.querySelectorAll('[data-eq]').forEach(b => b.addEventListener('click', async () => {
      const e = data.eq.find(x => x.equip_slot === Number(b.dataset.eq));
      if (await G.equip(e.equip_slot, i.c.location, i.r.slot, `Equip ${i.name} in the ${e.slot_name} slot${e.empty ? '' : ' (replacing ' + G.prettyName(e) + ')'}?`, Object.fromEntries(data.eq.map(x => [x.equip_slot, x.slot_name])))) await refresh();
    }));
    if (i.g) { dlg.querySelector('.ce-bonuses').insertAdjacentHTML('beforebegin', '<hr>'); G.mountItemBonuses(dlg.querySelector('.ce-bonuses'), i.g, {onSaved: refresh}); }
    dlg.showModal();
  }

  loadInventory = async function () { data = null; await load(); };
  const note = document.querySelector('#pane-inventory > .ce-muted');
  if (note) note.textContent = 'Click any item to see its details and edit it. Changes are offline-only; Storage and Temporary Items stay protected.';
})();
