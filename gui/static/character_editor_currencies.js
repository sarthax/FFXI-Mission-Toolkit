(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'currencies') await renderCurrencies();
  };

  // Grouping is by column name only; anything not matched lands in "Other" so no column is ever hidden.
  const GROUPS = [
    ['conquest', 'Conquest & Nation', c => /^(sandoria|bastok|windurst)_(cp|supply)$/.test(c), 'Conquest points and regional supply, per nation.'],
    ['seals', 'Seals & Crests', c => /^(beastman_seal|kindred_seal|kindred_crest|high_kindred_crest|sacred_kindred_crest|ancient_beastcoin)$/.test(c), 'Seals, crests and coins spent on Ark Angel / beastman gear.'],
    ['assault', 'Assault', c => /_assault_point$|^id_tags$/.test(c), 'Assault points per area, plus Imperial ID tags.'],
    ['campaign', 'Campaign & Dominion', c => /^(allied_notes|dominion_note|imperial_standing)$|_echelon_trophy$/.test(c), 'Allied Notes, Imperial Standing, Dominion Notes and echelon trophies.'],
    ['guild', 'Guild (Crafting)', c => /^guild_/.test(c), 'Guild points per craft.'],
    ['synergy', 'Synergy', c => /_fewell$/.test(c), 'Elemental fewell fuel used by the Synergy Furnace.'],
    ['crystals', 'Crystals', c => /_(crystals|clusters)$/.test(c), 'Stored elemental crystals and clusters.'],
    ['abyssea', 'Abyssea', c => /^(cruor|traverser_stones)$/.test(c), 'Cruor and traverser stones.'],
    ['eminence', 'Eminence & Unity', c => /^(spark_of_eminence|unity_accolades)$/.test(c), 'Sparks of Eminence and Unity accolades.'],
    ['other', 'Other', () => true, 'Every remaining point or currency column in char_points.'],
  ];
  const SKIP = new Set(['charid']);
  let selectedGroup = 'conquest';
  const base = () => `/character-editor/characters/${selectedChar}/fields`;

  async function postJson(url, body) {
    const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const d = await r.json().catch(() => ({detail: r.statusText}));
    if (!r.ok) throw new Error(d.detail || r.statusText);
    return d;
  }
  const pretty = c => c.replace(/_/g, ' ').replace(/\b\w/g, m => m.toUpperCase()).replace(/\bCp\b/, 'CP').replace(/\bTp\b/, 'TP').replace(/\bId\b/, 'ID');

  async function renderCurrencies() {
    const box = document.getElementById('categoryData');
    if (!box || !selectedChar) return;
    box.querySelectorAll(':scope > .ce-currency-manager').forEach(n => n.remove());
    const shell = document.createElement('div');
    shell.className = 'ce-progression ce-currency-manager';
    box.prepend(shell);
    const sweep = () => box.querySelectorAll('details.ce-data-block').forEach(b => { if (/^\s*char_points\b/.test(b.textContent)) b.remove(); });
    sweep();
    new MutationObserver(sweep).observe(box, { childList: true });
    setTimeout(sweep, 1500);

    const row = ((activeCategoryData?.tables || {}).char_points || [])[0];
    if (!row) { shell.innerHTML = '<div class="ce-progress-empty">This character has no char_points row.</div>'; return; }
    const offline = editableOnline();
    const dis = offline ? '' : 'disabled';
    const pending = new Map(); // column -> value

    const cols = Object.keys(row).filter(c => !SKIP.has(c));
    const members = {};
    for (const c of cols) { const g = GROUPS.find(x => x[2](c)); (members[g[0]] ||= []).push(c); }
    const live = GROUPS.filter(g => (members[g[0]] || []).length);
    if (!live.some(g => g[0] === selectedGroup)) selectedGroup = live[0][0];

    shell.innerHTML = `<style>.ce-currency-manager .ce-split{display:grid;grid-template-columns:190px minmax(0,1fr);gap:10px;align-items:start}
      .ce-currency-manager .ce-split-nav{position:sticky;top:96px;display:flex;flex-direction:column;gap:2px}
      .ce-currency-manager .ce-split-item{display:flex;justify-content:space-between;text-align:left;padding:4px 8px;font-size:12px;cursor:pointer;border:1px solid transparent;border-radius:4px;background:transparent;color:inherit}
      .ce-currency-manager .ce-split-item.active{border-color:var(--border,#555);background:rgba(255,255,255,.1);font-weight:700}.ce-currency-manager .ce-split-item small{font-size:10px;opacity:.7}
      .ce-currency-manager .ce-crow{display:grid;grid-template-columns:minmax(150px,1fr) 130px;gap:8px;align-items:center;padding:4px 6px;border-top:1px solid var(--border,#333);font-size:12px}
      .ce-currency-manager input[type=number]{width:120px;min-width:0;padding:2px 4px}.ce-currency-manager .ce-pending{background:rgba(138,101,0,.18);outline:1px solid #8a6500}
      .ce-currency-manager .ce-apply-inline{position:sticky;bottom:0;display:flex;gap:8px;align-items:center;justify-content:flex-end;padding:8px;background:var(--panel,#1b1b1b);border-top:1px solid var(--border,#444)}
      @media(max-width:760px){.ce-currency-manager .ce-split{grid-template-columns:1fr}.ce-currency-manager .ce-split-nav{position:static;flex-direction:row;flex-wrap:wrap}}</style>
      <div class="ce-progress-head"><strong>Currencies</strong>${offline ? pill('offline editing enabled','ok') : pill('editing locked until offline','warn')}<span class="ce-progress-source">Every column of this character's char_points row, grouped by what it is used for.</span></div>
      <div class="ce-split"><nav class="ce-split-nav"></nav><section class="ce-split-detail"></section></div>
      <div class="ce-apply-inline" hidden><span class="ce-pending-count"></span><button class="ce-discard">Discard</button><button class="ce-apply primary">Apply changes</button></div>`;
    const navEl = shell.querySelector('.ce-split-nav'), detail = shell.querySelector('.ce-split-detail'), bar = shell.querySelector('.ce-apply-inline');
    const refreshBar = () => { bar.hidden = !pending.size; bar.querySelector('.ce-pending-count').textContent = `${pending.size} pending change${pending.size === 1 ? '' : 's'}`; };
    const total = g => members[g[0]].reduce((n, c) => n + (Number(row[c]) > 0 ? 1 : 0), 0);
    const drawNav = () => {
      navEl.innerHTML = live.map(g => `<button class="ce-split-item${g[0] === selectedGroup ? ' active' : ''}" data-g="${g[0]}"><span>${esc(g[1])}</span><small>${total(g)}/${members[g[0]].length} held</small></button>`).join('');
      navEl.querySelectorAll('[data-g]').forEach(b => b.addEventListener('click', () => { selectedGroup = b.dataset.g; drawNav(); drawDetail(); }));
    };
    const drawDetail = () => {
      const g = GROUPS.find(x => x[0] === selectedGroup);
      detail.innerHTML = `<h3>${esc(g[1])}</h3><div class="ce-muted">${esc(g[3])}</div>
        ${members[g[0]].map(c => `<div class="ce-crow${pending.has(c) ? ' ce-pending' : ''}"><span>${esc(pretty(c))}<br><small class="ce-muted">${esc(c)}</small></span><input type="number" step="1" data-col="${esc(c)}" value="${pending.get(c) ?? row[c]}" ${dis}></div>`).join('')}`;
      detail.querySelectorAll('input[data-col]').forEach(inp => inp.addEventListener('change', () => {
        const c = inp.dataset.col;
        if (inp.value === '' || Number(inp.value) === Number(row[c])) pending.delete(c); else pending.set(c, Number(inp.value));
        inp.closest('.ce-crow').classList.toggle('ce-pending', pending.has(c));
        refreshBar();
      }));
    };
    bar.querySelector('.ce-discard').addEventListener('click', () => { pending.clear(); refreshBar(); drawDetail(); });
    bar.querySelector('.ce-apply').addEventListener('click', async () => {
      if (!pending.size || !confirm(`Apply ${pending.size} change(s) to this character?`)) return;
      const body = {table:'char_points', changes:Object.fromEntries(pending)};
      try {
        const p = await postJson(`${base()}/preview`, body);
        if (!p.ready) throw new Error((p.issues || []).map(i => i.message).join('; ') || 'char_points is not write-ready');
        await postJson(`${base()}/apply`, {...body, expected_before:p.before, approved:true});
      } catch (e) { alert(`Not applied: ${e.message}`); }
      await selectCharacter(selectedChar);
      await loadCategory('currencies');
    });
    drawNav(); drawDetail(); refreshBar();
  }
})();
