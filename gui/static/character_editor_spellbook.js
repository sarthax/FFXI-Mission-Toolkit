(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'spells-abilities') await renderSpellbook();
  };

  const JOBS = ['WAR','MNK','WHM','BLM','RDM','THF','PLD','DRK','BST','BRD','RNG','SAM','NIN','DRG','SMN','BLU','COR','PUP','DNC','SCH','GEO','RUN'];
  let selectedNav = 'spell:WhiteMagic';
  let referenceCache = null;
  const base = () => `/character-editor/characters/${selectedChar}`;

  async function postJson(url, body) {
    const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const d = await r.json().catch(() => ({detail: r.statusText}));
    if (!r.ok) throw new Error(d.detail || r.statusText);
    return d;
  }
  async function getJson(url) {
    const r = await fetch(url);
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || r.statusText);
    return d;
  }

  async function renderSpellbook() {
    const box = document.getElementById('categoryData');
    if (!box || !selectedChar) return;
    box.querySelectorAll(':scope > .ce-spellbook').forEach(n => n.remove());
    // These panels are replaced by the spellbook; the raw 835-row char_spells table stays in raw storage.
    box.querySelectorAll(':scope > .ce-spell-manager').forEach(n => n.remove());
    box.querySelectorAll('.ce-bitset-editors [data-capability="abilities"]').forEach(n => n.remove());

    const shell = document.createElement('div');
    shell.className = 'ce-progression ce-spellbook';
    shell.innerHTML = '<div class="ce-progress-empty">Loading spells, abilities, traits and mounts…</div>';
    box.prepend(shell);

    let ref, learnedIds, kiPayload;
    try {
      [ref, learnedIds, kiPayload] = await Promise.all([
        referenceCache ? Promise.resolve(referenceCache) : getJson('/character-editor/reference/spells-abilities.json'),
        getJson(`${base()}/spells.json`),
        getJson(`${base()}/categories/key-items.json`).catch(() => null),
      ]);
      referenceCache = ref;
    } catch (e) {
      shell.innerHTML = `<div class="warn">Could not load spell reference: ${esc(e.message)}</div>`;
      return;
    }
    const offline = editableOnline();
    const learned = new Set((learnedIds.spell_ids || []).map(Number));
    const abEntry = activeCategoryData?.packed?.abilities || {};
    const abilityOk = !!abEntry.decoded;
    const abilitySet = new Set((abEntry.decoded?.set_ids || []).map(Number));
    const abilityEditable = offline && abEntry.editable === true && abilityOk;
    const ki = kiPayload?.packed?.key_items;
    const ownedKi = new Set((ki?.decoded?.owned_ids || []).map(Number));
    const kiEditable = offline && ki?.editable === true && !!ki?.decoded;
    const mountItems = Object.values(ki?.catalog?.items || {}).filter(r => r.category === 'Mounts' || /^Chocobo License$/i.test(r.label)).sort((a, b) => a.id - b.id);

    const spells = ref.spells.rows;
    const abilities = ref.abilities.rows;
    const traits = ref.traits.rows;
    const pending = new Map(); // "kind:id" -> {kind,id,want,label}

    const have = it => pending.has(`${it.kind}:${it.id}`) ? pending.get(`${it.kind}:${it.id}`).want
      : it.kind === 'spell' ? learned.has(it.id) : it.kind === 'ability' ? abilitySet.has(it.id) : ownedKi.has(it.id);
    const stored = it => it.kind === 'spell' ? learned.has(it.id) : it.kind === 'ability' ? abilitySet.has(it.id) : ownedKi.has(it.id);

    const navDefs = [];
    navDefs.push({section: 'Spells'});
    for (const c of ref.spells.categories) {
      const items = spells.filter(s => s.category === c.key).map(s => ({kind:'spell', id:s.id, label:s.name, offServer:!s.on_server, sub:Object.entries(s.jobs).sort((a,b)=>a[1]-b[1]).map(([j,l])=>`${j}${l}`).join(' ')}));
      if (items.length) navDefs.push({key:`spell:${c.key}`, label:c.label, items, editable:offline, note:items.some(i => i.offServer) ? 'Entries marked not on server are missing from the server spell_list and cannot be changed.' : ''});
    }
    const dice = abilities.filter(a => a.type === 'CorsairRoll').map(a => ({kind:'ability', id:a.id, label:a.name, sub:`COR${a.level}`}));
    if (dice.length) navDefs.push({key:'dice', label:'Dice (Corsair Rolls)', items:dice, editable:abilityEditable, note:abilityOk ? '' : (abEntry.decode_error || 'Ability data not decodable.')});
    navDefs.push({section: 'Abilities by job'});
    for (const j of JOBS) {
      const items = abilities.filter(a => a.job_abbr === j && a.type !== 'CorsairRoll').map(a => ({kind:'ability', id:a.id, label:a.name, sub:a.level ? `Lv${a.level}` : '2-hour', type:a.type}));
      if (items.length) navDefs.push({key:`ability:${j}`, label:j, items, editable:abilityEditable, note:abilityOk ? '' : (abEntry.decode_error || 'Ability data not decodable.')});
    }
    navDefs.push({section: 'Traits (automatic from job level)'});
    for (const j of JOBS) {
      const t = traits.filter(r => r.job_abbr === j);
      if (t.length) navDefs.push({key:`trait:${j}`, label:j, trait:t});
    }
    navDefs.push({section: 'Mounts'});
    navDefs.push({key:'mounts', label:'Mounts', items:mountItems.map(r => ({kind:'ki', id:Number(r.id), label:r.label, sub:`Key item ${r.id}`})), editable:kiEditable, note:'The server key item list has no mount key items beyond the Chocobo License; newer mounts need a newer server/client data set.'});

    const navKeys = new Set(navDefs.filter(n => n.key).map(n => n.key));
    if (!navKeys.has(selectedNav)) selectedNav = navDefs.find(n => n.key)?.key;

    const countOf = n => n.items ? `${n.items.filter(stored).length}/${n.items.length}` : `${n.trait.length}`;
    const totalSpells = spells.length;
    shell.innerHTML = `<div class="ce-progress-head"><strong>Spells, Abilities, Traits &amp; Mounts</strong>${pill(`${learned.size}/${totalSpells} spells`)}${abilityOk ? pill(`${abilitySet.size} abilities`) : pill('abilities unavailable','warn')}${offline ? pill('offline editing enabled','ok') : pill('editing locked until offline','warn')}<span class="ce-progress-source">Categories from client resources · abilities/traits from the server checkout</span></div>
      <div class="ce-split"><nav class="ce-split-nav"></nav><section class="ce-split-detail"></section></div>
      <div class="ce-apply-inline" hidden><span class="ce-pending-count"></span><button class="ce-discard">Discard</button><button class="ce-apply primary">Apply changes</button></div>`;
    const style = document.createElement('style');
    style.textContent = `.ce-split{display:grid;grid-template-columns:190px minmax(0,1fr);gap:10px;align-items:start}
      .ce-split-nav{position:sticky;top:96px;display:flex;flex-direction:column;gap:2px;max-height:75vh;overflow:auto}
      .ce-split-section{font-size:9px;text-transform:uppercase;letter-spacing:.06em;opacity:.55;margin:10px 0 2px}
      .ce-split-item{display:flex;justify-content:space-between;align-items:center;text-align:left;padding:4px 8px;font-size:12px;cursor:pointer;border:1px solid transparent;border-radius:4px;background:transparent;color:inherit}
      .ce-split-item:hover{background:rgba(255,255,255,.06)}.ce-split-item.active{border-color:var(--border,#555);background:rgba(255,255,255,.1);font-weight:700}
      .ce-split-item small{font-size:10px;opacity:.7}.ce-split-detail h3{margin:0 0 6px}
      .ce-pending{background:rgba(138,101,0,.18);outline:1px solid #8a6500}
      .ce-apply-inline{position:sticky;bottom:0;display:flex;gap:8px;align-items:center;justify-content:flex-end;padding:8px;background:var(--panel,#1b1b1b);border-top:1px solid var(--border,#444)}
      @media(max-width:760px){.ce-split{grid-template-columns:1fr}.ce-split-nav{position:static;flex-direction:row;flex-wrap:wrap;max-height:none}}`;
    shell.prepend(style);
    const nav = shell.querySelector('.ce-split-nav'), detail = shell.querySelector('.ce-split-detail');
    const bar = shell.querySelector('.ce-apply-inline');
    let filterText = '', learnedOnly = false, jobFilter = '';

    const refreshBar = () => {
      bar.hidden = pending.size === 0;
      bar.querySelector('.ce-pending-count').textContent = `${pending.size} pending change${pending.size === 1 ? '' : 's'}`;
    };

    const drawNav = () => {
      nav.innerHTML = navDefs.map(n => n.section
        ? `<div class="ce-split-section">${esc(n.section)}</div>`
        : `<button class="ce-split-item${n.key === selectedNav ? ' active' : ''}" data-nav="${esc(n.key)}"><span>${esc(n.label)}</span><small>${esc(countOf(n))}</small></button>`).join('');
      nav.querySelectorAll('[data-nav]').forEach(b => b.addEventListener('click', () => { selectedNav = b.dataset.nav; filterText = ''; jobFilter = ''; drawNav(); drawDetail(); }));
    };

    const drawDetail = () => {
      const n = navDefs.find(x => x.key === selectedNav);
      if (!n) { detail.innerHTML = ''; return; }
      if (n.trait) {
        const byName = new Map();
        for (const r of n.trait) { const e = byName.get(r.id) || {name:r.name, ranks:[]}; e.ranks.push(r); byName.set(r.id, e); }
        detail.innerHTML = `<h3>${esc(n.label)} traits</h3><div class="ce-muted">Traits are derived from job level, so they are not stored per character and cannot be edited here.</div>
          <div class="ce-progress-list">${[...byName.values()].map(e => `<div class="ce-progress-row ce-readonly-row"><span>${esc(e.name)}</span><span>${e.ranks.map(r => `Lv${r.level}${e.ranks.length > 1 ? ` (rank ${r.rank})` : ''}`).join(' · ')}</span></div>`).join('')}</div>`;
        return;
      }
      const jobsHere = n.key.startsWith('spell:') ? JOBS.filter(j => spells.some(s => s.category === n.key.slice(6) && s.jobs[j])) : [];
      detail.innerHTML = `<h3>${esc(n.label)}</h3>${n.note ? `<div class="warn">${esc(n.note)}</div>` : ''}${n.editable === false && !n.note ? '<div class="ce-muted">Read only until the character is offline.</div>' : ''}
        <div class="ce-toolbar"><input class="ce-sb-filter" type="search" placeholder="Search name or ID" value="${esc(filterText)}">
        <label><input type="checkbox" class="ce-sb-owned" ${learnedOnly ? 'checked' : ''}> Learned / owned only</label>
        ${jobsHere.length ? `<select class="ce-sb-job"><option value="">All jobs</option>${jobsHere.map(j => `<option ${j === jobFilter ? 'selected' : ''}>${j}</option>`).join('')}</select>` : ''}
        <button class="ce-sb-all" ${n.editable ? '' : 'disabled'}>Select all shown</button><button class="ce-sb-none" ${n.editable ? '' : 'disabled'}>Clear all shown</button></div>
        <div class="ce-progress-list ce-sb-list"></div>`;
      const list = detail.querySelector('.ce-sb-list');
      const shown = () => {
        const q = filterText.toLowerCase();
        return n.items.filter(it => (!learnedOnly || have(it)) && (!q || `${it.label} ${it.id}`.toLowerCase().includes(q)) && (!jobFilter || (it.sub || '').split(' ').some(t => t.startsWith(jobFilter) && /\d/.test(t))));
      };
      const setWant = (it, want) => {
        const k = `${it.kind}:${it.id}`;
        if (want === stored(it)) pending.delete(k); else pending.set(k, {kind:it.kind, id:it.id, want, label:it.label});
      };
      const drawList = () => {
        const rows = shown();
        list.innerHTML = rows.slice(0, 400).map(it => `<label class="ce-progress-row${pending.has(`${it.kind}:${it.id}`) ? ' ce-pending' : ''}"><span>${esc(it.label)}<small>ID ${it.id}${it.offServer ? ' · not on server' : ''}${it.sub ? ' · ' + esc(it.sub) : ''}${it.type ? ' · ' + esc(it.type) : ''}</small></span><span>${have(it) ? 'Yes' : ''}</span><input type="checkbox" data-id="${it.id}" ${have(it) ? 'checked' : ''} ${n.editable && !it.offServer ? '' : 'disabled'}></label>`).join('') || '<div class="ce-progress-empty">Nothing to show.</div>';
        if (rows.length > 400) list.insertAdjacentHTML('beforeend', `<div class="ce-muted">Showing 400 of ${rows.length}. Refine the search.</div>`);
        list.querySelectorAll('input[data-id]').forEach(cb => cb.addEventListener('change', () => {
          setWant(n.items.find(i => String(i.id) === cb.dataset.id), cb.checked); refreshBar(); drawList(); drawNav();
        }));
      };
      detail.querySelector('.ce-sb-filter').addEventListener('input', e => { filterText = e.target.value; drawList(); });
      detail.querySelector('.ce-sb-owned').addEventListener('change', e => { learnedOnly = e.target.checked; drawList(); });
      detail.querySelector('.ce-sb-job')?.addEventListener('change', e => { jobFilter = e.target.value; drawList(); });
      detail.querySelector('.ce-sb-all').addEventListener('click', () => { shown().forEach(it => setWant(it, true)); refreshBar(); drawList(); });
      detail.querySelector('.ce-sb-none').addEventListener('click', () => { shown().forEach(it => setWant(it, false)); refreshBar(); drawList(); });
      drawList();
    };

    bar.querySelector('.ce-discard').addEventListener('click', () => { pending.clear(); refreshBar(); drawNav(); drawDetail(); });
    bar.querySelector('.ce-apply').addEventListener('click', async () => {
      const changes = [...pending.values()];
      if (!changes.length || !confirm(`Apply ${changes.length} change(s) to this character?`)) return;
      const btn = bar.querySelector('.ce-apply'); btn.disabled = true;
      let done = 0;
      try {
        for (const c of changes) {
          if (c.kind === 'spell') {
            const action = c.want ? 'learn' : 'unlearn';
            const p = await postJson(`${base()}/spells/preview`, {spell_id:c.id, action});
            if (!p.ready) throw new Error(`${c.label}: ${(p.issues || []).map(i => i.message).join('; ') || 'not write-ready'}`);
            await postJson(`${base()}/spells/apply`, {spell_id:c.id, action, expected_learned_before:Boolean(p.learned_before), approved:true});
          } else {
            const capability = c.kind === 'ability' ? 'abilities' : 'key_items';
            const operation = c.kind === 'ability' ? {bit_id:c.id, enabled:c.want} : {key_item_id:c.id, owned:c.want};
            const p = await postJson(`${base()}/packed/preview`, {capability, operation});
            if (!p.ready) throw new Error(`${c.label}: ${(p.issues || []).map(i => i.message).join('; ') || 'not write-ready'}`);
            await postJson(`${base()}/packed/apply`, {capability, operation, expected_before_sha256:p.before_sha256, approved:true});
          }
          done++;
        }
      } catch (e) {
        alert(`Applied ${done} of ${changes.length}. Stopped: ${e.message}`);
      }
      await selectCharacter(selectedChar);
      await loadCategory('spells-abilities');
    });

    drawNav(); drawDetail(); refreshBar();
  }
})();
