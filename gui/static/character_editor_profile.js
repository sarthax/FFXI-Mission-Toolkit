(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'profile') await renderProfile();
  };

  const SLOTS = [['head', 'Head', 4], ['body', 'Body', 5], ['hands', 'Hands', 6], ['legs', 'Legs', 7], ['feet', 'Feet', 8],
                 ['main', 'Main hand', 0], ['sub', 'Sub / shield', 1], ['ranged', 'Ranged', 2]];
  const RACES = {1:'Hume (male)', 2:'Hume (female)', 3:'Elvaan (male)', 4:'Elvaan (female)', 5:'Tarutaru (male)', 6:'Tarutaru (female)', 7:'Mithra', 8:'Galka'};
  const SIZES = {0:'Small', 1:'Medium', 2:'Large'};
  const FAME = [['fame_sandoria','San d\'Oria'],['fame_bastok','Bastok'],['fame_windurst','Windurst'],['fame_norg','Norg'],['fame_jeuno','Jeuno'],['fame_adoulin','Adoulin']];
  let selectedNav = 'rank';
  let refCache = null;
  const base = () => `/character-editor/characters/${selectedChar}/fields`;

  async function postJson(url, body) {
    const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const d = await r.json().catch(() => ({detail: r.statusText}));
    if (!r.ok) throw new Error(d.detail || r.statusText);
    return d;
  }
  const pretty = c => c.replace(/^fame_aby_/, 'Abyssea ').replace(/^rank_/, '').replace(/_/g, ' ').replace(/\b\w/g, m => m.toUpperCase());

  async function renderProfile() {
    const box = document.getElementById('categoryData');
    if (!box || !selectedChar) return;
    box.querySelectorAll(':scope > .ce-profile-manager').forEach(n => n.remove());
    const shell = document.createElement('div');
    shell.className = 'ce-progression ce-profile-manager';
    shell.innerHTML = '<div class="ce-progress-empty">Loading profile…</div>';
    box.prepend(shell);
    const sweep = () => box.querySelectorAll('details.ce-data-block').forEach(b => { if (/^\s*char_(profile|look|style)\b/.test(b.textContent)) b.remove(); });
    sweep();
    new MutationObserver(sweep).observe(box, { childList: true });
    setTimeout(sweep, 1500);

    if (!refCache) {
      try {
        const d = await (await fetch('/character-editor/reference/appearance.json')).json();
        const items = new Map(); const byModel = new Map();
        for (const [id, name, model, shield, slot] of d.rows || []) {
          const it = {id, name, model, shield, slot}; items.set(id, it);
          for (const [, , idx] of SLOTS) if (slot & (1 << idx)) { const k = `${idx}:${model}`; (byModel.get(k) || byModel.set(k, []).get(k)).push(it); }
        }
        refCache = {items, byModel, available: !!d.available};
      } catch (e) { refCache = {items: new Map(), byModel: new Map(), available: false}; }
    }
    const ref = refCache;
    const t = activeCategoryData?.tables || {};
    const prof = (t.char_profile || [])[0] || {}, look = (t.char_look || [])[0] || {}, style = (t.char_style || [])[0] || {};
    const offline = editableOnline(), dis = offline ? '' : 'disabled';
    const pending = new Map(); // "table|column" -> {table, column, value}
    const stage = (table, column, value, original) => {
      const k = `${table}|${column}`;
      if (value === '' || Number(value) === Number(original)) pending.delete(k); else pending.set(k, {table, column, value: Number(value)});
      refreshBar();
    };
    const val = (table, column, row) => pending.get(`${table}|${column}`)?.value ?? row[column] ?? 0;

    const fameCols = Object.keys(prof).filter(c => /^fame_/.test(c));
    const nav = [{key:'rank', label:'Rank & points', badge:`${Object.keys(prof).filter(c => /^rank_/.test(c)).length} fields`},
                 {key:'fame', label:'Fame', badge:`${fameCols.length} areas`},
                 {key:'appearance', label:'Race, face & size', badge:RACES[look.race] || ''},
                 {key:'look', label:'Equipment look (char_look)', badge:'models'},
                 {key:'style', label:'Lockstyle (char_style)', badge:'items'}];
    if (!nav.some(n => n.key === selectedNav)) selectedNav = 'rank';

    shell.innerHTML = `<style>.ce-profile-manager .ce-split{display:grid;grid-template-columns:210px minmax(0,1fr);gap:10px;align-items:start}
      .ce-profile-manager .ce-split-nav{position:sticky;top:96px;display:flex;flex-direction:column;gap:2px}
      .ce-profile-manager .ce-split-item{display:flex;justify-content:space-between;text-align:left;padding:4px 8px;font-size:12px;cursor:pointer;border:1px solid transparent;border-radius:4px;background:transparent;color:inherit}
      .ce-profile-manager .ce-split-item.active{border-color:var(--border,#555);background:rgba(255,255,255,.1);font-weight:700}.ce-profile-manager .ce-split-item small{font-size:10px;opacity:.7}
      .ce-profile-manager .ce-prow{display:grid;grid-template-columns:minmax(130px,1fr) 120px minmax(0,2fr);gap:8px;align-items:center;padding:4px 6px;border-top:1px solid var(--border,#333);font-size:12px}
      .ce-profile-manager input[type=number]{width:100px;min-width:0;padding:2px 4px}.ce-profile-manager .ce-pending{background:rgba(138,101,0,.18);outline:1px solid #8a6500}
      .ce-profile-manager .ce-pick{width:100%;min-width:0;padding:2px 4px;font-size:12px}
      .ce-profile-manager .ce-note{font-size:11px;opacity:.75;margin:6px 0}
      .ce-profile-manager .ce-apply-inline{position:sticky;bottom:0;display:flex;gap:8px;align-items:center;justify-content:flex-end;padding:8px;background:var(--panel,#1b1b1b);border-top:1px solid var(--border,#444)}
      @media(max-width:760px){.ce-profile-manager .ce-split{grid-template-columns:1fr}.ce-profile-manager .ce-split-nav{position:static;flex-direction:row;flex-wrap:wrap}}</style>
      <div class="ce-progress-head"><strong>Profile</strong>${offline ? pill('offline editing enabled','ok') : pill('editing locked until offline','warn')}<span class="ce-progress-source">Rank, fame and character appearance.${ref.available ? '' : ' Item names unavailable: the selected server has no item_equipment.sql or item_armor.sql.'}</span></div>
      <div class="ce-split"><nav class="ce-split-nav"></nav><section class="ce-split-detail"></section></div>
      <div class="ce-apply-inline" hidden><span class="ce-pending-count"></span><button class="ce-discard">Discard</button><button class="ce-apply primary">Apply changes</button></div>`;
    const navEl = shell.querySelector('.ce-split-nav'), detail = shell.querySelector('.ce-split-detail'), bar = shell.querySelector('.ce-apply-inline');
    const refreshBar = () => { bar.hidden = !pending.size; bar.querySelector('.ce-pending-count').textContent = `${pending.size} pending change${pending.size === 1 ? '' : 's'}`; };
    const drawNav = () => {
      navEl.innerHTML = nav.map(n => `<button class="ce-split-item${n.key === selectedNav ? ' active' : ''}" data-nav="${n.key}"><span>${esc(n.label)}</span><small>${esc(n.badge)}</small></button>`).join('');
      navEl.querySelectorAll('[data-nav]').forEach(b => b.addEventListener('click', () => { selectedNav = b.dataset.nav; drawNav(); drawDetail(); }));
    };
    const numRow = (table, row, col, label, hint = '', extra = '') => `<div class="ce-prow${pending.has(`${table}|${col}`) ? ' ce-pending' : ''}"><span>${esc(label)}<br><small class="ce-muted">${esc(col)}</small></span><input type="number" step="1" min="0" data-t="${table}" data-col="${col}" value="${val(table, col, row)}" ${dis}><span class="ce-muted">${hint}${extra}</span></div>`;
    const wireNums = (table, row, after) => detail.querySelectorAll(`input[data-t="${table}"]`).forEach(inp => inp.addEventListener('change', () => {
      stage(table, inp.dataset.col, inp.value, row[inp.dataset.col]);
      inp.closest('.ce-prow').classList.toggle('ce-pending', pending.has(`${table}|${inp.dataset.col}`));
      if (after) after(inp);
    }));
    const itemLabel = i => i ? `${i.name} (#${i.id})` : '';

    const drawRank = () => {
      const cols = Object.keys(prof).filter(c => /^rank_/.test(c));
      detail.innerHTML = `<h3>Rank &amp; points</h3><div class="ce-note">Nation rank (1–10) per nation and the rank points toward the next promotion.</div>${cols.map(c => numRow('char_profile', prof, c, pretty(c))).join('')}`;
      wireNums('char_profile', prof);
    };
    const drawFame = () => {
      const known = new Set(FAME.map(f => f[0]));
      const rows = [...FAME.filter(f => f[0] in prof).map(([c, l]) => [c, l]), ...fameCols.filter(c => !known.has(c)).map(c => [c, pretty(c)])];
      detail.innerHTML = `<h3>Fame</h3><div class="ce-note">Fame per nation / area (Abyssea areas listed after the cities).</div>${rows.map(([c, l]) => numRow('char_profile', prof, c, l)).join('')}`;
      wireNums('char_profile', prof);
    };
    const drawAppearance = () => {
      detail.innerHTML = `<h3>Race, face &amp; size</h3><div class="ce-note">Stored as small numbers in char_look. Changing race on a live character mismatches its gear models, so treat race as read-mostly.</div>
        ${numRow('char_look', look, 'race', 'Race', '', `<span class="ce-race">${esc(RACES[val('char_look', 'race', look)] || 'unknown')}</span>`)}
        ${numRow('char_look', look, 'face', 'Face', 'Raw face id (0–15).')}
        ${numRow('char_look', look, 'size', 'Size', '', `<span class="ce-size">${esc(SIZES[val('char_look', 'size', look)] || 'unknown')}</span>`)}`;
      wireNums('char_look', look, inp => {
        const row = inp.closest('.ce-prow');
        const tag = row.querySelector('.ce-race, .ce-size');
        if (tag) tag.textContent = (inp.dataset.col === 'race' ? RACES : SIZES)[inp.value] || 'unknown';
      });
    };

    // A slot picker: type a name, choose a suggestion, the numeric field follows. Look = model id, style = item id.
    const drawSlots = mode => {
      const isLook = mode === 'look', table = isLook ? 'char_look' : 'char_style', row = isLook ? look : style;
      detail.innerHTML = isLook
        ? `<h3>Equipment look (char_look)</h3><div class="ce-note">What other players see on each slot. Each value is the <b>model id</b> of an item (<code>item_equipment.MId</code>), <b>not</b> an item id. A model id is only meaningful together with its slot: model 196 on Body and model 196 on Hands are different pieces. Many items share a model (upgrades, +1/+2, recolours). The server rewrites this from your equipped gear whenever you equip or log in, so use Lockstyle for a lasting cosmetic change. 0 = nothing shown.</div>`
        : `<h3>Lockstyle (char_style)</h3><div class="ce-note">The <b>item id</b> whose appearance is shown while lockstyle is on (the real item id, as in inventory). 0 = no lockstyle item for that slot. It only takes effect when the character's style lock is switched on in game; the server also ignores an item the character does not own.</div>`;
      detail.innerHTML += SLOTS.map(([col, label, idx]) => {
        const v = Number(val(table, col, row));
        const hi = isLook && v > 0xFFF;
        const model = isLook ? (v & 0xFFF) : 0;
        const cur = !v ? [] : isLook ? (ref.byModel.get(`${idx}:${model}`) || []) : [ref.items.get(v)].filter(Boolean);
        const hint = cur.length ? esc(cur.slice(0, 4).map(i => i.name).join(', ')) + (cur.length > 4 ? ` +${cur.length - 4} more` : '') : (v ? 'no matching item in this server\'s item_equipment' : 'none');
        return `<div class="ce-prow ce-slot${pending.has(`${table}|${col}`) ? ' ce-pending' : ''}" data-col="${col}" data-idx="${idx}"><span>${esc(label)}<br><small class="ce-muted">${col}${hi ? ' · high bits set: model ' + model : ''}</small></span><input type="number" step="1" min="0" data-t="${table}" data-col="${col}" value="${v}" ${dis}>
          <span><span class="ce-hint ce-muted">${hint}</span><br><input class="ce-pick" list="ce-dl-${col}" placeholder="${ref.available ? 'Find ' + label.toLowerCase() + ' item by name…' : 'item names unavailable'}" ${dis} ${ref.available ? '' : 'disabled'}><datalist id="ce-dl-${col}"></datalist></span></div>`;
      }).join('');
      detail.querySelectorAll('.ce-slot').forEach(rowEl => {
        const col = rowEl.dataset.col, idx = Number(rowEl.dataset.idx), num = rowEl.querySelector('input[type=number]'), pick = rowEl.querySelector('.ce-pick'), dl = rowEl.querySelector('datalist'), hint = rowEl.querySelector('.ce-hint');
        const byLabel = new Map();
        pick.addEventListener('input', () => {
          const q = pick.value.trim().toLowerCase();
          if (byLabel.has(pick.value)) {
            const it = byLabel.get(pick.value); num.value = isLook ? it.model : it.id; num.dispatchEvent(new Event('change')); return;
          }
          if (q.length < 2) { dl.innerHTML = ''; return; }
          const hits = []; for (const it of ref.items.values()) { if ((it.slot & (1 << idx)) && it.name.toLowerCase().includes(q)) { hits.push(it); if (hits.length >= 40) break; } }
          byLabel.clear(); hits.forEach(it => byLabel.set(`${it.name} (#${it.id}${isLook ? ' · model ' + it.model : ''})`, it));
          dl.innerHTML = [...byLabel.keys()].map(k => `<option value="${esc(k)}"></option>`).join('');
        });
        num.addEventListener('change', () => {
          stage(table, col, num.value, row[col]); rowEl.classList.toggle('ce-pending', pending.has(`${table}|${col}`));
          const v = Number(num.value) || 0, cur = !v ? [] : isLook ? (ref.byModel.get(`${idx}:${v & 0xFFF}`) || []) : [ref.items.get(v)].filter(Boolean);
          hint.textContent = cur.length ? cur.slice(0, 4).map(i => i.name).join(', ') + (cur.length > 4 ? ` +${cur.length - 4} more` : '') : (v ? 'no matching item in this server\'s item_equipment' : 'none');
        });
      });
    };

    const drawDetail = () => {
      if (selectedNav === 'rank') drawRank(); else if (selectedNav === 'fame') drawFame(); else if (selectedNav === 'appearance') drawAppearance();
      else drawSlots(selectedNav);
    };

    bar.querySelector('.ce-discard').addEventListener('click', () => { pending.clear(); refreshBar(); drawDetail(); });
    bar.querySelector('.ce-apply').addEventListener('click', async () => {
      if (!pending.size || !confirm(`Apply ${pending.size} change(s) to this character?`)) return;
      const groups = new Map();
      for (const c of pending.values()) { const g = groups.get(c.table) || {table: c.table, changes: {}}; g.changes[c.column] = c.value; groups.set(c.table, g); }
      let done = 0;
      try {
        for (const g of groups.values()) {
          const p = await postJson(`${base()}/preview`, g);
          if (!p.ready) throw new Error((p.issues || []).map(i => i.message).join('; ') || `${g.table} is not write-ready`);
          await postJson(`${base()}/apply`, {...g, expected_before: p.before, approved: true}); done++;
        }
      } catch (e) { alert(`Applied ${done} of ${groups.size} tables. Stopped: ${e.message}`); }
      await selectCharacter(selectedChar);
      await loadCategory('profile');
    });
    drawNav(); drawDetail(); refreshBar();
  }
})();
