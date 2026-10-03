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
  const prettyName = s => (s.name || `Item ${s.item_id}`).replace(/_/g, ' ').replace(/\b\w/g, m => m.toUpperCase());

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
        return `<button class="ce-tile${s.key === selectedKey ? ' active' : ''}" data-k="${s.key}" title="${esc(prettyName(s))}">${n ? `<span class="bd">✦${n}</span>` : ''}${s.item_id ? iconImg(s.item_id, 32) : ''}<span class="nm">${esc(prettyName(s))}</span><span class="sl">${esc(s.slot_name)}</span></button>`;
      }).join('')}</div>`).join('') || '<div class="ce-muted">No gear matches.</div>';
      listEl.querySelectorAll('[data-k]').forEach(b => b.addEventListener('click', () => { selectedKey = b.dataset.k; draft = null; drawList(); drawDetail(); }));
    };

    const groupOf = a => { const k = cat.idGroup.get(a.id); return k ? cat.groups.get(k) : null; };
    const statSelect = (a, i) => {
      const cur = groupOf(a);
      const opt = g => `<option value="${esc(g.key)}" title="${esc(g.comment || '')}" ${cur && cur.key === g.key ? 'selected' : ''}>${esc(g.label + g.range)}</option>`;
      const unknown = a.id && !cur ? `<option value="?" selected>Unrecognised augment (#${a.id})</option>` : '';
      return `<select data-i="${i}" data-f="stat" ${offline ? '' : 'disabled'}><option value="">— None —</option>${unknown}
        <optgroup label="Stats">${cat.stats.map(opt).join('')}</optgroup>
        <optgroup label="Combined &amp; pet augments">${cat.combined.map(opt).join('')}</optgroup></select>`;
    };
    const amountSelect = (a, i) => {
      const g = groupOf(a);
      if (!a.id) return '<select disabled><option>—</option></select>';
      if (!g) return `<select disabled><option>Value ${a.value}</option></select>`;
      return `<select data-i="${i}" data-f="amount" ${offline ? '' : 'disabled'}>${g.sorted.map(o =>
        `<option value="${o.id}:${o.v}" ${o.id === a.id && o.v === a.value ? 'selected' : ''}>${esc(o.text)}</option>`).join('')}</select>`;
    };
    const note = a => {
      const g = a.id ? groupOf(a) : null;
      if (!a.id) return '';
      return `<div class="ce-augnote"><strong>${esc(describeAug(a))}</strong>${g && g.comment && g.comment.toLowerCase() !== g.label.toLowerCase() ? ` — ${esc(g.comment)}` : ''}</div>`;
    };
    const drawDetail = () => {
      const s = all.find(x => x.key === selectedKey);
      if (!s) { detail.innerHTML = ''; return; }
      if (s.missing_row) { detail.innerHTML = '<div class="ce-progress-empty">This equip slot points at an inventory entry that no longer exists.</div>'; return; }
      draft ||= s.augments.map(a => ({id: a.id, value: a.value}));
      const changed = draft.some((a, i) => a.id !== s.augments[i].id || a.value !== s.augments[i].value);
      const totals = draft.filter(a => a.id).map(describeAug).filter(Boolean);
      const nat = (s.native || []).map(n => `<li title="${esc(n.comment || '')}"><strong>${esc(n.name)} ${signed(n.value)}${n.unit === 'percent' ? '%' : n.unit === 'seconds' ? 's' : ''}</strong>${n.comment && n.comment.toLowerCase() !== n.name.toLowerCase() ? ` <span class="ce-muted">— ${esc(n.comment)}</span>` : ''}</li>`).join('');
      const cond = [...(s.latent || []), ...(s.pet || [])];
      const condHtml = cond.length ? `<div class="ce-native"><strong>Conditional &amp; pet bonuses</strong> <span class="ce-muted">(only while the condition is met)</span><ul class="ce-cond">${cond.map(c => `<li><strong>${esc(c.text)}</strong> <span class="ce-muted">— ${esc(c.when)}</span></li>`).join('')}</ul></div>` : '';
      detail.innerHTML = `<div class="ce-head">${iconImg(s.item_id, 48)}<div><h3>${esc(prettyName(s))}</h3><div class="ce-muted">${esc(s.carried ? s.group + ' · not equipped' : s.slot_name + ' · equipped')}</div></div></div>
        <div class="ce-native"><strong>Built-in bonuses</strong> <span class="ce-muted">(every copy of this item has these; edit them in the Items editor)</span>${nat ? `<ul>${nat}</ul>` : '<div class="ce-muted">None defined by the server.</div>'}</div>
        ${condHtml}
        <h4 style="margin:10px 0 6px">Player augments</h4>
        ${draft.map((a, i) => `<div class="ce-augcard${a.id ? ' set' : ''}"><strong>Augment ${i + 1}</strong>${statSelect(a, i)}${amountSelect(a, i)}<button data-i="${i}" data-f="clear" ${a.id && offline ? '' : 'disabled'} title="Remove this augment">Clear</button>${note(a)}</div>`).join('')}
        <div class="ce-total"><strong>Bonuses on this item:</strong> ${totals.length ? esc(totals.join(' · ')) : '<span class="ce-muted">none</span>'}</div>
        <div class="ce-aug-actions"><button class="ce-aug-reset" ${changed ? '' : 'disabled'}>Undo edits</button><button class="ce-aug-apply primary" ${changed && offline ? '' : 'disabled'}>Save augments</button><span class="ce-aug-msg ce-muted">${offline ? '' : 'Log the character out to edit.'}</span></div>`;
      detail.querySelectorAll('select[data-f="stat"]').forEach(el => el.addEventListener('change', () => {
        if (el.value === '?') return;
        const i = Number(el.dataset.i);
        if (!el.value) draft[i] = {id: 0, value: 0};
        else { const gs = cat.groups.get(el.value).sorted; const o = gs.find(x => x.amount > 0) || gs[0]; draft[i] = {id: o.id, value: o.v}; }
        drawDetail();
      }));
      detail.querySelectorAll('select[data-f="amount"]').forEach(el => el.addEventListener('change', () => {
        const [id, v] = el.value.split(':').map(Number);
        draft[Number(el.dataset.i)] = {id, value: v};
        drawDetail();
      }));
      detail.querySelectorAll('button[data-f="clear"]').forEach(el => el.addEventListener('click', () => { draft[Number(el.dataset.i)] = {id: 0, value: 0}; drawDetail(); }));
      detail.querySelector('.ce-aug-reset').addEventListener('click', () => { draft = null; drawDetail(); });
      detail.querySelector('.ce-aug-apply').addEventListener('click', async () => {
        const body = {location: s.location, slot: s.inventory_slot, augments: draft};
        const msg = detail.querySelector('.ce-aug-msg');
        try {
          const p = await postJson(`${api()}/augments/preview`, body);
          if (!p.ready) throw new Error((p.issues || []).filter(i => i.blocking).map(i => i.message).join('; ') || 'not write-ready');
          if (!confirm(`Save these augments on ${prettyName(s)}?\n\n${totals.length ? totals.join('\n') : 'All augments removed'}`)) return;
          await postJson(`${api()}/augments/apply`, {...body, expected_source_fingerprint: p.source_fingerprint, approved: true});
        } catch (e) { msg.textContent = `Not saved: ${e.message}`; return; }
        await selectCharacter(selectedChar);
        await loadCategory('equipment');
      });
    };
    shell.querySelector('.ce-find input[type=search]').addEventListener('input', e => { search = e.target.value; drawList(); });
    shell.querySelector('.ce-augonly').addEventListener('change', e => { augOnly = e.target.checked; drawList(); });
    drawList(); drawDetail();
  }
})();
