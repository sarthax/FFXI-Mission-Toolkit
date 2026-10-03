// Shared gear helpers for the Character Editor: item tiles, the augment / bonus editor and the equip action.
// Used by the Equipped Items tab and by the Inventory item pop-up so both edit an item the same way.
window.CEGear = (() => {
  if (!document.querySelector('.character-editor-page')) return null;

  const api = () => `/character-editor/characters/${selectedChar}`;
  const icon = id => `/character-editor/client-cache/icons/${id}.png`;
  async function getJson(url) {
    const r = await fetch(url);
    const d = await r.json().catch(() => ({detail: r.statusText}));
    if (!r.ok) throw new Error(d.detail || r.statusText);
    return d;
  }
  async function postJson(url, body) {
    const r = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    const d = await r.json().catch(() => ({detail: r.statusText}));
    if (!r.ok) throw new Error(d.detail || r.statusText);
    return d;
  }
  const iconImg = (id, size) => `<img class="ce-icon" src="${icon(id)}" loading="lazy" decoding="async" style="width:${size}px;height:${size}px" onerror="this.style.visibility='hidden'">`;
  const prettyName = s => s.empty ? 'Empty' : (s.name || `Item ${s.item_id ?? s.itemId}`).replace(/_/g, ' ').replace(/\b\w/g, m => m.toUpperCase());
  const gearLine = it => `${it.level ? 'Lv' + it.level + ' ' : ''}${it.jobs || ''}`.trim();
  const signed = n => (n >= 0 ? '+' : '') + n;
  const sfx = e => (e.unit === 'percent' ? '%' : e.unit === 'seconds' ? 's' : '');

  // ---- styles shared by every gear view ----
  if (!document.getElementById('ce-gear-styles')) {
    const st = document.createElement('style');
    st.id = 'ce-gear-styles';
    st.textContent = `
      .ce-gearui .ce-split{display:grid;grid-template-columns:minmax(260px,38%) minmax(0,1fr);gap:12px;align-items:start}
      .ce-gearui .ce-list{max-height:72vh;overflow:auto;padding-right:4px}.ce-gearui .ce-list h4{margin:10px 0 4px;font-size:12px;opacity:.8}
      .ce-gearui .ce-tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(78px,1fr));gap:6px}
      .ce-gearui .ce-tile{position:relative;display:flex;flex-direction:column;align-items:center;gap:2px;padding:6px 4px;border:1px solid var(--border,#444);border-radius:6px;background:transparent;color:inherit;cursor:pointer;font-size:10px;text-align:center}
      .ce-gearui .ce-tile.active{border-color:#6aa9ff;background:rgba(106,169,255,.15)}.ce-gearui .ce-tile .nm{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;line-height:1.15;word-break:break-word}
      .ce-gearui .ce-tile .sl{opacity:.65}.ce-gearui .ce-tile .bd{position:absolute;top:2px;right:3px;font-size:10px;color:#f5c542;font-weight:700}
      .ce-gearui .ce-tile .qt{position:absolute;bottom:2px;right:3px;font-size:10px;font-weight:700;background:rgba(0,0,0,.55);color:#fff;border-radius:3px;padding:0 3px}
      .ce-gearui .ce-tile .wn{position:absolute;top:2px;left:3px;font-size:9px;color:#6fd08c;font-weight:700}
      .ce-gearui .ce-tile.empty{border-style:dashed;opacity:.7}.ce-gearui .ce-tile.blocked{opacity:.45;cursor:not-allowed}.ce-gearui .ce-tile .lv{opacity:.65;font-size:9px}.ce-gearui .ce-tile .bl{color:#ff8a80;font-size:9px;line-height:1.1}
      .ce-gearui .ce-find{display:flex;gap:8px;align-items:center;margin-bottom:6px;font-size:12px;flex-wrap:wrap}.ce-gearui .ce-find input[type=search]{flex:1;min-width:120px;padding:3px 6px}
      .ce-gearui .ce-head{display:flex;gap:12px;align-items:center;margin-bottom:8px}.ce-gearui .ce-head h3{margin:0}
      .ce-gearui .ce-swap{margin:0 0 12px;padding:8px;border:1px solid var(--border,#444);border-radius:6px}
      .ce-gearui .ce-swap-bar{display:flex;gap:8px;align-items:center;margin:6px 0;flex-wrap:wrap}.ce-gearui .ce-swap-bar input[type=search]{flex:1;min-width:0;padding:3px 6px}
      .ce-gearui .ce-swap .ce-tiles{max-height:230px;overflow:auto;grid-template-columns:repeat(auto-fill,minmax(110px,1fr))}
      .ce-gearui .ce-augcard{display:grid;grid-template-columns:90px minmax(130px,1.3fr) minmax(110px,1fr) auto;gap:8px;align-items:center;padding:8px;margin-bottom:6px;border:1px solid var(--border,#444);border-radius:6px}
      .ce-gearui .ce-augcard select{min-width:0;padding:3px 4px}.ce-gearui .ce-augcard.set{border-color:#8a6500;background:rgba(245,197,66,.08)}
      .ce-gearui .ce-native{margin-bottom:6px;font-size:12px}.ce-gearui .ce-native ul{margin:4px 0 0;padding-left:18px;columns:2}.ce-gearui .ce-native ul.ce-cond{columns:1}.ce-gearui .ce-augnote{grid-column:1/-1;font-size:12px;opacity:.85}
      .ce-gearui .ce-total{margin:10px 0;padding:8px;border-radius:6px;background:rgba(255,255,255,.06);font-size:13px}.ce-gearui .ce-aug-actions{display:flex;gap:8px;align-items:center}
      .ce-gearui .ce-warn{color:#ff8a80;font-size:12px}
      @media(max-width:860px){.ce-gearui .ce-split{grid-template-columns:1fr}.ce-gearui .ce-augcard{grid-template-columns:1fr 1fr}}`;
    document.head.appendChild(st);
  }

  // ---- augment catalog: stats a player can pick, and the amounts each stat can reach ----
  let cat = null;
  const eff = (e, v) => (e.value >= 0 ? e.value + v : e.value - v) * (e.multiplier > 1 ? e.multiplier : 1);
  const effText = (e, v) => `${e.mod_name}${e.pet ? ' (pet)' : ''} ${signed(eff(e, v))}${sfx(e)}`;
  async function loadCatalog() {
    if (cat) return cat;
    const d = await getJson('/character-editor/reference/augments.json');
    const byId = new Map((d.rows || []).map(r => [r.id, r]));
    const groups = new Map();
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
  const groupOf = a => { const k = cat.idGroup.get(a.id); return k ? cat.groups.get(k) : null; };

  // Put gear into (or take it out of) an equipment slot. Resolves true when the change was applied.
  async function equip(equipSlot, location, slot, what, slotNames) {
    const body = {equip_slot: equipSlot, location, slot};
    try {
      const p = await postJson(`${api()}/equipment/preview`, body);
      if (!p.ready) throw new Error((p.issues || []).filter(i => i.blocking).map(i => i.message).join('; ') || 'not write-ready');
      const from = p.moved_from != null ? `\n\nThis item is currently worn in the ${(slotNames && slotNames[p.moved_from]) || 'another'} slot and will leave it.` : '';
      if (!confirm(`${what}${from}`)) return false;
      await postJson(`${api()}/equipment/apply`, {...body, expected_source_fingerprint: p.source_fingerprint || '', approved: true});
      return true;
    } catch (e) { alert(`Not changed: ${e.message}`); return false; }
  }

  // Bonuses + augment editor for one gear row ({location, inventory_slot, item_id, name, augments, native, latent, pet}).
  async function mountItemBonuses(el, s, opts = {}) {
    await loadCatalog();
    const offline = editableOnline();
    el.classList.add('ce-gearui');
    let draft = s.augments.map(a => ({id: a.id, value: a.value}));
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
    const draw = () => {
      const changed = draft.some((a, i) => a.id !== s.augments[i].id || a.value !== s.augments[i].value);
      const totals = draft.filter(a => a.id).map(describeAug).filter(Boolean);
      const nat = (s.native || []).map(n => `<li title="${esc(n.comment || '')}"><strong>${esc(n.name)} ${signed(n.value)}${n.unit === 'percent' ? '%' : n.unit === 'seconds' ? 's' : ''}</strong>${n.comment && n.comment.toLowerCase() !== n.name.toLowerCase() ? ` <span class="ce-muted">— ${esc(n.comment)}</span>` : ''}</li>`).join('');
      const cond = [...(s.latent || []), ...(s.pet || [])];
      const condHtml = cond.length ? `<div class="ce-native"><strong>Conditional &amp; pet bonuses</strong> <span class="ce-muted">(only while the condition is met)</span><ul class="ce-cond">${cond.map(c => `<li><strong>${esc(c.text)}</strong> <span class="ce-muted">— ${esc(c.when)}</span></li>`).join('')}</ul></div>` : '';
      el.innerHTML = `<div class="ce-native"><strong>Built-in bonuses</strong> <span class="ce-muted">(every copy of this item has these; edit them in the Items editor)</span>${nat ? `<ul>${nat}</ul>` : '<div class="ce-muted">None defined by the server.</div>'}</div>
        ${condHtml}
        <h4 style="margin:10px 0 6px">Player augments</h4>
        ${draft.map((a, i) => `<div class="ce-augcard${a.id ? ' set' : ''}"><strong>Augment ${i + 1}</strong>${statSelect(a, i)}${amountSelect(a, i)}<button data-i="${i}" data-f="clear" ${a.id && offline ? '' : 'disabled'} title="Remove this augment">Clear</button>${note(a)}</div>`).join('')}
        <div class="ce-total"><strong>Bonuses on this item:</strong> ${totals.length ? esc(totals.join(' · ')) : '<span class="ce-muted">none</span>'}</div>
        <div class="ce-aug-actions"><button class="ce-aug-reset" ${changed ? '' : 'disabled'}>Undo edits</button><button class="ce-aug-apply primary" ${changed && offline ? '' : 'disabled'}>Save augments</button><span class="ce-aug-msg ce-muted">${offline ? '' : 'Log the character out to edit.'}</span></div>`;
      el.querySelectorAll('select[data-f="stat"]').forEach(sel => sel.addEventListener('change', () => {
        if (sel.value === '?') return;
        const i = Number(sel.dataset.i);
        if (!sel.value) draft[i] = {id: 0, value: 0};
        else { const gs = cat.groups.get(sel.value).sorted; const o = gs.find(x => x.amount > 0) || gs[0]; draft[i] = {id: o.id, value: o.v}; }
        draw();
      }));
      el.querySelectorAll('select[data-f="amount"]').forEach(sel => sel.addEventListener('change', () => {
        const [id, v] = sel.value.split(':').map(Number);
        draft[Number(sel.dataset.i)] = {id, value: v};
        draw();
      }));
      el.querySelectorAll('button[data-f="clear"]').forEach(b => b.addEventListener('click', () => { draft[Number(b.dataset.i)] = {id: 0, value: 0}; draw(); }));
      el.querySelector('.ce-aug-reset').addEventListener('click', () => { draft = s.augments.map(a => ({id: a.id, value: a.value})); draw(); });
      el.querySelector('.ce-aug-apply').addEventListener('click', async () => {
        const body = {location: s.location, slot: s.inventory_slot, augments: draft};
        const msg = el.querySelector('.ce-aug-msg');
        try {
          const p = await postJson(`${api()}/augments/preview`, body);
          if (!p.ready) throw new Error((p.issues || []).filter(i => i.blocking).map(i => i.message).join('; ') || 'not write-ready');
          if (!confirm(`Save these augments on ${prettyName(s)}?\n\n${totals.length ? totals.join('\n') : 'All augments removed'}`)) return;
          await postJson(`${api()}/augments/apply`, {...body, expected_source_fingerprint: p.source_fingerprint, approved: true});
        } catch (e) { msg.textContent = `Not saved: ${e.message}`; return; }
        if (opts.onSaved) await opts.onSaved();
      });
    };
    draw();
  }

  return {api, getJson, postJson, iconImg, prettyName, gearLine, signed, loadCatalog, equip, mountItemBonuses};
})();
