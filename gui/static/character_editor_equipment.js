(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'equipment') await renderEquipment();
  };

  let selectedKey = null;
  let search = '';
  let augOnly = false;
  let cat = null; // augment catalog, built once
  const api = () => `/character-editor/characters/${selectedChar}`;
  const icon = id => `/character-editor/client-cache/icons/${id}.png`;

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

  // ---- augment catalog: stats a player can pick, and the amounts each stat can reach ----
  const sfx = e => (e.unit === 'percent' ? '%' : e.unit === 'seconds' ? 's' : '');
  const eff = (e, v) => (e.value >= 0 ? e.value + v : e.value - v) * (e.multiplier > 1 ? e.multiplier : 1);
  const signed = n => (n >= 0 ? '+' : '') + n;
  const effText = (e, v) => `${e.mod_name}${e.pet ? ' (pet)' : ''} ${signed(eff(e, v))}${sfx(e)}`;

  async function loadCatalog() {
    if (cat) return cat;
    const d = await getJson('/character-editor/reference/augments.json');
    const byId = new Map((d.rows || []).map(r => [r.id, r]));
    const groups = new Map(); // key -> {key,label,special,options:Map(amount -> {id,v,text})}
    const idGroup = new Map();
    for (const r of d.rows || []) {
      const e = r.effects[0];
      const single = r.effects.length === 1 && !e.pet;
      const key = single ? `s|${e.mod}|${e.multiplier > 1 ? e.multiplier : 1}` : `c|${r.id}`;
      let g = groups.get(key);
      if (!g) {
        const label = single ? e.mod_name : r.effects.map(x => x.mod_name + (x.pet ? ' (pet)' : '')).join(' + ');
        g = {key, label, special: !single, options: new Map(), comment: single ? (e.comment || '') : r.effects.map(x => x.comment).filter(Boolean).join(' / '), unit: single ? sfx(e) : ''};
        groups.set(key, g);
      }
      idGroup.set(r.id, key);
      for (let v = 0; v < 32; v++) {
        const amount = single ? eff(e, v) : v;
        if (!g.options.has(amount)) g.options.set(amount, {amount, id: r.id, v, text: single ? `${signed(amount)}${sfx(e)}` : r.effects.map(x => effText(x, v)).join(', ')});
      }
    }
    for (const g of groups.values()) { g.sorted = [...g.options.entries()].sort((a, b) => a[0] - b[0]).map(([, o]) => o); g.range = g.special ? '' : ` (${g.sorted[0].text} to ${g.sorted[g.sorted.length - 1].text})`; }
    const list = [...groups.values()].sort((a, b) => a.label.localeCompare(b.label));
    cat = {available: !!d.available, byId, groups, idGroup, stats: list.filter(g => !g.special), combined: list.filter(g => g.special)};
    return cat;
  }
  const describeAug = a => {
    if (!a.id) return '';
    const r = cat.byId.get(a.id);
    return r ? r.effects.map(e => effText(e, a.value)).join(', ') : `Unrecognised augment (#${a.id})`;
  };
  const iconImg = (id, size) => `<img class="ce-icon" src="${icon(id)}" loading="lazy" decoding="async" style="width:${size}px;height:${size}px" onerror="this.style.visibility='hidden'">`;
  const prettyName = s => s.empty ? 'Empty' : (s.name || `Item ${s.item_id}`).replace(/_/g, ' ').replace(/\b\w/g, m => m.toUpperCase());

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

    let state, inv;
    try { [state, inv] = await Promise.all([getJson(`${api()}/equipment.json`), getJson(`${api()}/augmentable-inventory.json`), loadCatalog()]); }
    catch (e) { shell.innerHTML = `<div class="ce-progress-empty">Could not load equipment: ${esc(e.message)}</div>`; return; }
    const offline = editableOnline();
    const eq = (state.slots || []).map(s => ({...s, key: `e${s.equip_slot}`, group: 'Equipped'}));
    const eqLoc = new Set(eq.map(s => `${s.location}:${s.inventory_slot}`));
    const carried = (inv.items || []).filter(i => !eqLoc.has(`${i.location}:${i.inventory_slot}`))
      .map(i => ({...i, key: `i${i.location}:${i.inventory_slot}`, group: i.container, slot_name: `Slot ${i.inventory_slot}`, carried: true}));
    const all = [...eq, ...carried];
    if (!all.length) { shell.innerHTML = '<div class="ce-progress-empty">This character has no armor or weapons.</div>'; return; }
    if (!all.some(s => s.key === selectedKey)) selectedKey = all[0].key;
    let draft = null; // [{id,value}] for the selected item
    let pickSearch = '';

    shell.innerHTML = `<style>.ce-equip-manager .ce-split{display:grid;grid-template-columns:minmax(260px,38%) minmax(0,1fr);gap:12px;align-items:start}
      .ce-equip-manager .ce-list{max-height:72vh;overflow:auto;padding-right:4px}.ce-equip-manager .ce-list h4{margin:10px 0 4px;font-size:12px;opacity:.8}
      .ce-equip-manager .ce-tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(78px,1fr));gap:6px}
      .ce-equip-manager .ce-tile{position:relative;display:flex;flex-direction:column;align-items:center;gap:2px;padding:6px 4px;border:1px solid var(--border,#444);border-radius:6px;background:transparent;color:inherit;cursor:pointer;font-size:10px;text-align:center}
      .ce-equip-manager .ce-tile.active{border-color:#6aa9ff;background:rgba(106,169,255,.15)}.ce-equip-manager .ce-tile .nm{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;line-height:1.15;word-break:break-word}
      .ce-equip-manager .ce-tile .sl{opacity:.65}.ce-equip-manager .ce-tile .bd{position:absolute;top:2px;right:3px;font-size:10px;color:#f5c542;font-weight:700}
      .ce-equip-manager .ce-find{display:flex;gap:8px;align-items:center;margin-bottom:6px;font-size:12px}.ce-equip-manager .ce-find input[type=search]{flex:1;min-width:0;padding:3px 6px}
      .ce-equip-manager .ce-head{display:flex;gap:12px;align-items:center;margin-bottom:8px}.ce-equip-manager .ce-head h3{margin:0}
      .ce-equip-manager .ce-augcard{display:grid;grid-template-columns:90px minmax(130px,1.3fr) minmax(110px,1fr) auto;gap:8px;align-items:center;padding:8px;margin-bottom:6px;border:1px solid var(--border,#444);border-radius:6px}
      .ce-equip-manager .ce-augcard select{min-width:0;padding:3px 4px}.ce-equip-manager .ce-augcard.set{border-color:#8a6500;background:rgba(245,197,66,.08)}
      .ce-equip-manager .ce-native{margin-bottom:6px;font-size:12px}.ce-equip-manager .ce-native ul{margin:4px 0 0;padding-left:18px;columns:2}.ce-equip-manager .ce-native ul.ce-cond{columns:1}.ce-equip-manager .ce-augnote{grid-column:1/-1;font-size:12px;opacity:.85}.ce-equip-manager .ce-total{margin:10px 0;padding:8px;border-radius:6px;background:rgba(255,255,255,.06);font-size:13px}
      .ce-equip-manager .ce-aug-actions{display:flex;gap:8px;align-items:center}
      .ce-equip-manager .ce-tile .wn{position:absolute;top:2px;left:3px;font-size:10px;font-weight:700}.ce-equip-manager .ce-tile.blocked{opacity:.45;cursor:not-allowed}.ce-equip-manager .ce-tile .bl{color:#ff8a80;font-size:9px;line-height:1.1}.ce-equip-manager .ce-warn{color:#ff8a80;font-size:12px}
      .ce-equip-manager .ce-tile.empty{border-style:dashed;opacity:.7}.ce-equip-manager .ce-swap{margin:0 0 12px;padding:8px;border:1px solid var(--border,#444);border-radius:6px}
      .ce-equip-manager .ce-swap-bar{display:flex;gap:8px;align-items:center;margin:6px 0}.ce-equip-manager .ce-swap-bar input[type=search]{flex:1;min-width:0;padding:3px 6px}
      .ce-equip-manager .ce-swap .ce-tiles{max-height:230px;overflow:auto;grid-template-columns:repeat(auto-fill,minmax(110px,1fr))}.ce-equip-manager .ce-tile .lv{opacity:.65;font-size:9px}
      @media(max-width:860px){.ce-equip-manager .ce-split{grid-template-columns:1fr}.ce-equip-manager .ce-augcard{grid-template-columns:1fr 1fr}}</style>
      <div class="ce-progress-head"><strong>Equipped Items</strong>${offline ? pill('offline editing enabled','ok') : pill('editing locked until offline','warn')}<span class="ce-progress-source">Pick a piece of gear, then choose the bonus stats on it. This changes only this character's copy; the Items editor changes the item for everyone.</span></div>
      <div class="ce-split"><section><div class="ce-find"><input type="search" placeholder="Search gear…" value="${esc(search)}"><label><input type="checkbox" class="ce-augonly" ${augOnly ? 'checked' : ''}> Augmented only</label></div><div class="ce-list"></div></section><section class="ce-split-detail"></section></div>`;
    const listEl = shell.querySelector('.ce-list'), detail = shell.querySelector('.ce-split-detail');
    const augCount = s => s.augments.filter(a => a.id).length;

    const drawList = () => {
      const q = search.trim().toLowerCase().replace(/_/g, ' ');
      const shown = all.filter(s => (!q || (s.name || '').toLowerCase().replace(/_/g, ' ').includes(q)) && (!augOnly || augCount(s)));
      const order = [];
      shown.forEach(s => { if (!order.includes(s.group)) order.push(s.group); });
      listEl.innerHTML = order.map(gname => `<h4>${esc(gname)}</h4><div class="ce-tiles">${shown.filter(s => s.group === gname).map(s => {
        const n = augCount(s);
        return `<button class="ce-tile${s.key === selectedKey ? ' active' : ''}${s.empty ? ' empty' : ''}" data-k="${s.key}" title="${esc(prettyName(s))}">${n ? `<span class="bd">✦${n}</span>` : ''}${s.equip_block ? '<span class="wn" style="color:#ff8a80" title="Cannot be worn by this character">⚠</span>' : ''}${s.item_id ? iconImg(s.item_id, 32) : ''}<span class="nm">${esc(prettyName(s))}</span><span class="sl">${esc(s.slot_name)}</span></button>`;
      }).join('')}</div>`).join('') || '<div class="ce-muted">No gear matches.</div>';
      listEl.querySelectorAll('[data-k]').forEach(b => b.addEventListener('click', () => { selectedKey = b.dataset.k; draft = null; draft = null; pickSearch = ''; drawList(); drawDetail(); }));
    };

    const EQUIPPABLE = new Set([0, 8, 10, 11, 12]);
    const fits = (it, slot) => (it.slot_mask & (1 << slot)) && EQUIPPABLE.has(it.location);
    const wornAt = new Map(eq.filter(x => !x.empty && !x.missing_row).map(x => [`${x.location}:${x.inventory_slot}`, x.slot_name]));
    const gearLine = it => `${it.level ? 'Lv' + it.level + ' ' : ''}${it.jobs || ''}`.trim();
    const pickTiles = s => {
      const q = pickSearch.trim().toLowerCase().replace(/_/g, ' ');
      const cands = (inv.items || []).filter(it => fits(it, s.equip_slot) && !(it.location === s.location && it.inventory_slot === s.inventory_slot)
        && (!q || (it.name || '').toLowerCase().replace(/_/g, ' ').includes(q)));
      if (!cands.length) return '<div class="ce-muted">No matching gear in the Inventory or Wardrobes.</div>';
      cands.sort((a, b) => !!a.equip_block - !!b.equip_block);
      return `<div class="ce-tiles">${cands.map(it => {
        const n = it.augments.filter(a => a.id).length, worn = wornAt.get(`${it.location}:${it.inventory_slot}`);
        return `<button class="ce-tile${it.equip_block ? ' blocked' : ''}" data-pick="${it.location}:${it.inventory_slot}" title="${esc(prettyName(it) + (it.equip_block ? ' — ' + it.equip_block : ''))}" ${offline && !it.equip_block ? '' : 'disabled'}>${n ? `<span class="bd">✦${n}</span>` : ''}${iconImg(it.item_id, 32)}<span class="nm">${esc(prettyName(it))}</span><span class="lv">${esc(gearLine(it))}</span><span class="sl">${esc(worn ? 'worn: ' + worn : it.container)}</span>${it.equip_block ? `<span class="bl">${esc(it.equip_block)}</span>` : ''}</button>`;
      }).join('')}</div>`;
    };
    const swapPanel = s => {
      if (s.carried) {
        const targets = eq.filter(e => fits(s, e.equip_slot));
        if (!EQUIPPABLE.has(s.location)) return `<div class="ce-swap ce-muted">To equip this, first move it into the Inventory or a Mog Wardrobe (Inventory tab).</div>`;
        if (!targets.length) return '';
        return `<div class="ce-swap"><strong>Equip this item</strong><div class="ce-swap-bar">${targets.map(e => `<button data-equip-to="${e.equip_slot}" ${offline ? '' : 'disabled'}>${esc(e.slot_name)}${e.empty ? '' : ' (replaces ' + esc(prettyName(e)) + ')'}</button>`).join('')}</div></div>`;
      }
      return `<div class="ce-swap"><strong>${s.empty ? 'Equip an item' : 'Change item'}</strong> <span class="ce-muted">— gear in Inventory and Wardrobes that fits ${esc(s.slot_name)}</span>
        <div class="ce-swap-bar"><input type="search" class="ce-pick-search" placeholder="Search…" value="${esc(pickSearch)}">${s.empty ? '' : `<button class="ce-unequip" ${offline ? '' : 'disabled'}>Unequip</button>`}</div>
        <div class="ce-pick-tiles">${pickTiles(s)}</div></div>`;
    };
    async function doEquip(equipSlot, loc, slot, what) {
      const body = {equip_slot: equipSlot, location: loc, slot};
      try {
        const p = await postJson(`${api()}/equipment/preview`, body);
        if (!p.ready) throw new Error((p.issues || []).filter(i => i.blocking).map(i => i.message).join('; ') || 'not write-ready');
        const swappedFrom = p.moved_from != null ? `

This item is currently worn in the ${eq.find(e => e.equip_slot === p.moved_from)?.slot_name || 'another'} slot and will leave it.` : '';
        if (!confirm(`${what}${swappedFrom}`)) return;
        await postJson(`${api()}/equipment/apply`, {...body, expected_source_fingerprint: p.source_fingerprint || '', approved: true});
      } catch (e) { alert(`Not changed: ${e.message}`); return; }
      selectedKey = `e${equipSlot}`; draft = null; pickSearch = '';
      await selectCharacter(selectedChar);
      await loadCategory('equipment');
    }
    const bindSwap = s => {
      detail.querySelectorAll('[data-equip-to]').forEach(b => b.addEventListener('click', () => {
        const slotNo = Number(b.dataset.equipTo);
        doEquip(slotNo, s.location, s.inventory_slot, `Equip ${prettyName(s)} in the ${eq.find(e => e.equip_slot === slotNo).slot_name} slot?`);
      }));
      const un = detail.querySelector('.ce-unequip');
      if (un) un.addEventListener('click', () => doEquip(s.equip_slot, null, null, `Unequip ${prettyName(s)} from the ${s.slot_name} slot?`));
      const tiles = detail.querySelector('.ce-pick-tiles');
      const bindPicks = () => tiles && tiles.querySelectorAll('[data-pick]').forEach(b => b.addEventListener('click', () => {
        const [loc, slot] = b.dataset.pick.split(':').map(Number);
        const it = inv.items.find(x => x.location === loc && x.inventory_slot === slot);
        doEquip(s.equip_slot, loc, slot, `Put ${prettyName(it)} in the ${s.slot_name} slot${s.empty ? '' : ' (replacing ' + prettyName(s) + ')'}?`);
      }));
      bindPicks();
      const box = detail.querySelector('.ce-pick-search');
      if (box) box.addEventListener('input', () => { pickSearch = box.value; tiles.innerHTML = pickTiles(s); bindPicks(); });
    };
    const drawDetail = () => {
      const s = all.find(x => x.key === selectedKey);
      if (!s) { detail.innerHTML = ''; return; }
      if (s.empty || s.missing_row) {
        detail.innerHTML = `<div class="ce-head"><div><h3>${esc(s.slot_name)}</h3><div class="ce-muted">${s.missing_row ? 'This slot points at an inventory entry that no longer exists.' : 'Nothing equipped'}</div></div></div>${swapPanel(s)}`;
        bindSwap(s);
        return;
      }
      const worn = s.carried ? '' : esc(s.slot_name + ' · equipped');
      const info = s.equip_block ? '' : (s.level ? ' · ' + esc(gearLine(s)) : '');
      detail.innerHTML = `<div class="ce-head">${iconImg(s.item_id, 48)}<div><h3>${esc(prettyName(s))}</h3><div class="ce-muted">${s.carried ? esc(s.group + ' · not equipped') : worn}${info}</div></div></div>
        ${s.equip_block && !s.carried ? `<div class="ce-warn" style="margin:0 0 8px">⚠ ${esc(s.equip_block)}. The server will unequip this when the character logs in.</div>` : ''}
        ${swapPanel(s)}
        <div class="ce-bonuses"></div>`;
      bindSwap(s);
      CEGear.mountItemBonuses(detail.querySelector('.ce-bonuses'), s, {onSaved: async () => { await selectCharacter(selectedChar); await loadCategory('equipment'); }});
    };
    CEGear.bindTips(listEl, '[data-k]', el => {
      const s = all.find(x => x.key === el.dataset.k);
      if (!s || s.empty || !s.item_id) return null;
      return {id: s.item_id, name: prettyName(s), where: s.carried ? s.group : s.slot_name, g: s, action: 'view and edit', describe: describeAug};
    });
    shell.querySelector('.ce-find input[type=search]').addEventListener('input', e => { search = e.target.value; drawList(); });
    shell.querySelector('.ce-augonly').addEventListener('change', e => { augOnly = e.target.checked; drawList(); });
    drawList(); drawDetail();
  }
})();
