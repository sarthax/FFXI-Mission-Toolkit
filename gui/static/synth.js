(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const nm = s => String(s || '').replace(/_/g, ' ');
  const fmt = n => Number(n).toLocaleString();
  const CRAFTS = ['Wood', 'Smith', 'Gold', 'Cloth', 'Leather', 'Bone', 'Alchemy', 'Cook'];
  const PAGE = 100;
  const st = {offset: 0, total: 0, rows: [], sel: null, flavor: '', env: ''};

  async function req(url, opt) {
    const r = await fetch(url, opt);
    let d = null; try { d = await r.json(); } catch (e) {}
    if (!r.ok) throw new Error((d && (d.detail || d.message)) || ('HTTP ' + r.status));
    return d;
  }
  const post = (url, body) => req(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const debounce = (f, ms = 300) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => f(...a), ms); }; };
  const pill = s => '<span class="sy-pill ' + s + '">' + ({ok: 'obtainable', script: 'script ref', ah_only: 'AH only', missing: 'no source', bad: 'bad item'}[s] || s) + '</span>';

  /* ---- tabs ---- */
  function tab(t) {
    document.querySelectorAll('#syTabs button').forEach(b => b.classList.toggle('on', b.dataset.t === t));
    document.querySelectorAll('.sy .ahc-pane').forEach(p => p.classList.toggle('on', p.id === 'p-' + t));
    if (t === 'editor' && !$('syEditor').innerHTML) openEditor(null);
  }
  $('syTabs').onclick = e => { const b = e.target.closest('button[data-t]'); if (b) tab(b.dataset.t); };
  CRAFTS.forEach(c => $('syCraft').insertAdjacentHTML('beforeend', '<option>' + c + '</option>'));

  /* ---- recipe list ---- */
  async function load(reset) {
    if (reset) st.offset = 0;
    const p = new URLSearchParams({craft: $('syCraft').value, min_skill: $('syMin').value || 0, max_skill: $('syMax').value || 255, q: $('syQ').value, mode: $('syMode').value, limit: PAGE, offset: st.offset, with_status: 1});
    $('syCount').textContent = 'Loading…';
    try {
      const d = await req('/synth/recipes.json?' + p);
      st.rows = d.recipes; st.total = d.total; st.flavor = d.flavor;
      $('syFlavor').textContent = d.flavor.toUpperCase() + ' table layout';
      drawList();
    } catch (e) { $('syCount').textContent = e.message; }
  }
  function drawList() {
    const only = $('syOnlyMissing').checked;
    const rows = st.rows.filter(r => !only || r.status !== 'ok');
    $('syCount').textContent = fmt(st.total) + ' recipe(s)' + (only ? ' · ' + rows.length + ' incomplete on this page' : '');
    $('syPage').textContent = (st.total ? st.offset + 1 : 0) + '–' + Math.min(st.offset + PAGE, st.total);
    $('syPrev').disabled = st.offset <= 0; $('syNext').disabled = st.offset + PAGE >= st.total;
    $('syTable').querySelector('tbody').innerHTML = rows.map(r => '<tr data-id="' + r.id + '"' + (r.id === st.sel ? ' class="sel"' : '') + '><td>' + r.id + '</td><td>' + esc(nm(r.name)) + (r.desynth ? ' <small class="mut">(desynth)</small>' : '') + '</td><td>' + esc(r.craft) + '</td><td class="n">' + r.level + '</td><td class="sy-src">' + esc(r.ingredient_names.map(nm).join(', ')) + '</td><td>' + pill(r.status || 'ok') + '</td></tr>').join('');
  }
  $('syTable').onclick = e => { const tr = e.target.closest('tr[data-id]'); if (tr) showRecipe(+tr.dataset.id); };
  $('syPrev').onclick = () => { st.offset = Math.max(0, st.offset - PAGE); load(); };
  $('syNext').onclick = () => { st.offset += PAGE; load(); };
  ['syCraft', 'syMin', 'syMax', 'syMode'].forEach(i => $(i).onchange = () => load(true));
  $('syQ').oninput = debounce(() => load(true));
  $('syOnlyMissing').onchange = drawList;

  /* ---- detail + availability ---- */
  async function showRecipe(id) {
    st.sel = id; drawList();
    $('syDetail').innerHTML = '<div class="ahc-empty">Checking ingredients…</div>';
    try {
      const d = await req('/synth/check.json?id=' + id), r = d.recipe;
      const sk = CRAFTS.filter(c => r.skills[c]).map(c => c + ' ' + r.skills[c]).join(' / ');
      let h = '<h3 style="margin:0">' + esc(nm(r.name)) + ' <small class="mut">recipe #' + r.id + (r.desynth ? ' · desynth' : '') + '</small></h3>' +
        '<div class="mut">' + esc(sk) + (r.key_item ? ' · key item ' + r.key_item : '') + (r.content_tag ? ' · ' + esc(r.content_tag) : '') + '</div>' +
        '<p>' + (d.craftable ? '<span class="sy-pill ok">All ingredients have a source</span>' : '<span class="sy-pill missing">Missing: ' + esc(d.missing.map(nm).join(', ')) + '</span>') +
        ' <span class="mut">Estimated cost ' + (d.estimated_cost ? fmt(d.estimated_cost) + 'g' + (d.cost_complete ? '' : ' + unpriced items') : 'unknown') + '</span></p>' +
        '<table><thead><tr><th>Ingredient</th><th class="n">Qty</th><th>Status</th><th>Where it comes from</th></tr></thead><tbody>' +
        d.lines.map(l => {
          const src = [];
          if (l.vendor) src.push('Vendor ' + fmt(l.vendor.price) + 'g (' + esc(l.vendor.vendor + (l.vendor.zone ? ' · ' + l.vendor.zone.replace(/_/g, ' ') : '')) + ')');
          if (l.drops) src.push('Drops: ' + l.drops.sample.map(s => esc(s.mob) + ' (zone ' + s.zone_id + ')').join(', ') + (l.drops.mobs > l.drops.sample.length ? ' +' + (l.drops.mobs - l.drops.sample.length) + ' more' : ''));
          if (l.orphan_drop && !l.drops) src.push('<span class="sy-warn">In a droplist, but no spawning mob uses it</span>');
          if (l.bcnm) src.push('BCNM loot');
          if (l.engine) src.push('Elemental crystal/cluster: dropped by mobs in the game engine (not in the droplist table)');
          (l.scripts || []).forEach(s => src.push('<span class="mut">' + esc(s.kind) + ': ' + esc(s.file) + ' (low confidence)</span>'));
          if (l.ah) src.push('AH ' + l.ah.count + ' listed, from ' + fmt(l.ah.min) + 'g');
          if (l.recipes.length) src.push('Craftable: recipe ' + l.recipes.map(x => '<a href="#" data-r="' + x + '">#' + x + '</a>').join(', '));
          return '<tr><td>' + esc(nm(l.name)) + ' <small class="mut">#' + l.item_id + '</small></td><td class="n">' + l.qty + '</td><td>' + pill(l.in_item_basic ? l.status : 'bad') + '</td><td class="sy-src">' + (src.join('<br>') || '<span class="mut">none known</span>') + '</td></tr>';
        }).join('') + '</tbody></table>' +
        '<h4 style="margin:10px 0 4px">Results</h4><table><tbody>' + r.results.map((x, i) => '<tr><td>' + ['NQ', 'HQ1', 'HQ2', 'HQ3'][i] + '</td><td>' + esc(nm(x.name)) + ' <small class="mut">#' + x.item_id + '</small></td><td class="n">×' + x.qty + '</td></tr>').join('') + '</tbody></table>' +
        '<div class="sy-actions"><button class="b pri" id="syEdit" type="button">Edit</button><button class="b" id="syDup" type="button">Duplicate</button><button class="b" id="syDel" type="button">Delete…</button><button class="b" id="syUses" type="button">Recipes using this result</button></div>' +
        '<small class="mut">' + esc(d.note) + '</small>';
      $('syDetail').innerHTML = h;
      $('syEdit').onclick = () => openEditor(r, 'update'); $('syDup').onclick = () => openEditor(r, 'create');
      $('syDel').onclick = () => { openEditor(r, 'update'); preview('delete'); };
      $('syUses').onclick = () => { $('syQ').value = ''; useItem(r.results[0].item_id, 'ingredient'); };
    } catch (e) { $('syDetail').innerHTML = '<div class="ahc-empty">' + esc(e.message) + '</div>'; }
  }
  $('syDetail').onclick = e => { const a = e.target.closest('a[data-r]'); if (a) { e.preventDefault(); showRecipe(+a.dataset.r); } };
  async function useItem(id, role) {
    const d = await req('/synth/recipes.json?mode=all&item_id=' + id + '&role=' + role + '&limit=100&with_status=1');
    st.rows = d.recipes; st.total = d.total; st.offset = 0; drawList();
  }

  /* ---- audit ---- */
  $('syAuditRun').onclick = async () => {
    $('syAuditTiles').innerHTML = '<div class="ahc-empty">Auditing…</div>';
    try {
      const d = await req('/synth/audit.json?mode=' + $('syAuditMode').value + '&limit=500'), c = d.counts;
      $('syAuditTiles').innerHTML = [['Recipes', d.total], ['Fully obtainable', c.ok], ['Script-referenced only', c.script], ['Only via AH', c.ah_only], ['Missing a source', c.missing], ['Unknown item id', c.bad_item]].map(x => '<div class="ahc-tile"><b>' + fmt(x[1]) + '</b><span>' + x[0] + '</span></div>').join('');
      $('syAuditNote').textContent = d.note;
      $('syAuditTable').querySelector('tbody').innerHTML = d.problems.map(p => '<tr data-id="' + p.id + '" style="cursor:pointer"><td>' + p.id + '</td><td>' + esc(nm(p.name)) + '</td><td class="sy-src">' +
        (p.invalid.length ? '<span class="sy-err">Unknown item id: ' + p.invalid.join(', ') + '</span> ' : '') + p.gaps.map(g => esc(nm(g.name || '#' + g.item_id)) + ' ' + pill(g.status)).join(' · ') + '</td></tr>').join('') +
        (d.problem_count > d.problems.length ? '<tr><td colspan="3" class="mut">Showing the first ' + d.problems.length + ' of ' + d.problem_count + '</td></tr>' : '');
    } catch (e) { $('syAuditTiles').innerHTML = '<div class="ahc-empty">' + esc(e.message) + '</div>'; }
  };
  $('syAuditTable').onclick = e => { const tr = e.target.closest('tr[data-id]'); if (tr) { tab('recipes'); showRecipe(+tr.dataset.id); } };


  $('syResRun').onclick = async () => {
    const box = $('syResBody'); box.innerHTML = '<div class="ahc-empty">Researching…</div>';
    try {
      const o = $('cmpOther') && $('cmpOther').value, d = await req('/synth/research.json' + (o ? '?other=' + o : ''));
      const nt = (rows, f) => rows.length ? '<div class="sy-scroll sy-cap"><table class="sy-t"><tbody>' + rows.map(f).join('') + '</tbody></table></div>' : '<p class="mut">None.</p>';
      box.innerHTML = '<p class="mut">' + esc(d.note) + '</p>' +
        '<h4>Guild NPCs with thin stock (' + d.thin_guilds + ' under 12 rows) — vendor gaps</h4>' +
        nt(d.guilds, g => '<tr><td>' + esc(g.npc.replace(/_/g, ' ')) + '</td><td>' + esc(g.zone.replace(/_/g, ' ')) + '</td><td>guild #' + g.guild + '</td><td class="n ' + (g.rows < 12 ? 'sy-warn' : '') + '">' + g.rows + ' rows</td>' + (d.other_label ? '<td class="n">' + esc(d.other_label) + ': ' + (g.other_rows == null ? '—' : g.other_rows) + '</td>' : '') + '</tr>') +
        '<h4>Name ≠ sort name, not just a prefix (' + d.mismatch.length + ')</h4>' + nt(d.mismatch, m => '<tr><td>#' + m.item_id + '</td><td>' + esc(m.name) + '</td><td>' + esc(m.sortname) + '</td></tr>') +
        '<h4>Prefix-only aliases (' + d.alias.length + ')</h4>' + nt(d.alias, m => '<tr><td>#' + m.item_id + '</td><td>' + esc(m.name) + '</td><td>' + esc(m.sortname) + '</td></tr>') +
        '<h4>Different ids sharing one normalized name (' + d.clash.length + ')</h4>' + nt(d.clash, c => '<tr><td>' + esc(c.norm) + '</td><td>' + c.ids.map((i, k) => '#' + i + ' ' + esc(c.names[k] || '')).join('; ') + '</td></tr>') +
        (d.other_label ? '<h4>Same id, different name in ' + esc(d.other_label) + ' (' + d.cross.length + ')</h4>' + nt(d.cross, m => '<tr><td>#' + m.item_id + '</td><td>' + esc(m.name) + '</td><td>' + esc(m.other) + '</td></tr>') : '');
    } catch (e) { box.innerHTML = '<div class="sy-err">' + esc(e.message) + '</div>'; }
  };

  $('syGapRun').onclick = async () => {
    const box = $('syResBody'); box.innerHTML = '<div class="ahc-empty">Matching missing ingredients to guild vendors…</div>';
    try {
      const d = await req('/synth/gaps.json?limit=300');
      const rows = d.items.map(x => '<tr><td>' + ico(x.item_id) + esc(nm(x.name)) + ' <small class="mut">#' + x.item_id + '</small></td><td class="n">' + x.recipes + '</td><td>' + esc(x.craft || '') + '</td><td>' +
        (x.proof.length ? '<span class="sy-ok">' + x.proof.map(p => esc(p.env) + ' guild ' + p.guild + (p.price ? ' @' + fmt(p.price) + 'g' : '')).join(', ') + '</span>' : '<span class="mut">no proof elsewhere</span>') + '</td><td class="sy-src">' +
        x.guilds.slice(0, 3).map(g => '#' + g.guild + ' (' + g.rows + ' rows)' + (g.npcs.length ? ' ' + esc(g.npcs.slice(0, 2).join(', ')) : '')).join(' · ') + '</td><td>' + (x.staple ? 'staple-like' : '') + '</td></tr>').join('');
      box.innerHTML = '<p class="mut">' + esc(d.note) + '</p><h4>Missing ingredients → candidate guild vendors (' + d.count + ' total, ranked: proof elsewhere, staple-like, recipes blocked)</h4>' +
        '<div class="sy-scroll sy-cap"><table class="sy-t"><thead><tr><th>Ingredient</th><th>Recipes</th><th>Craft</th><th>Proof</th><th>Candidate guilds</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div>';
    } catch (e) { box.innerHTML = '<div class="sy-err">' + esc(e.message) + '</div>'; }
  };

  /* ---- visual editor ---- */
  const ico = id => id ? '<img class="sy-ico" src="/auction-house/items/' + id + '/icon.png" loading="lazy" alt="" onerror="this.style.visibility=\'hidden\'">' : '';
  let editing = null, editMode = 'create', slots = null, picking = null, keyItem = 0, keyList = null;
  const tileHtml = (key, label, id, name, qty) =>
    '<button type="button" class="sy-tile' + (id ? '' : ' empty') + (picking === key ? ' pick' : '') + '" data-slot="' + key + '" title="' + esc(label) + '">' +
    (id ? '<span class="x" data-clear="' + key + '" title="Clear">✕</span>' : '') + ico(id) +
    '<span class="nm">' + (id ? esc(nm(name || ('Item ' + id))) : '<span class="mut">' + esc(label) + '</span>') + '</span>' +
    (id ? '<span class="id">#' + id + '</span>' : '') + (id && qty != null ? '<span class="tier">' + esc(label) + '</span><input type="number" min="1" max="99" class="sy-q" data-q="' + key + '" value="' + (qty || 1) + '" title="Quantity made at ' + esc(label) + '">' : '') + '</button>';
  const CRYSTALS = ['Fire', 'Ice', 'Wind', 'Earth', 'Lightning', 'Water', 'Light', 'Dark'];
  const HQ = [['Inferno', 4238], ['Terra', 4241], ['Torrent', 4243], ['Cyclone', 4240], ['Glacier', 4239], ['Plasma', 4242], ['Aurora', 4244], ['Twilight', 4245]];
  function crystalSelect(key) {
    const hq = key === 'hq_crystal';
    if (!slots[key].id) slots[key].id = hq ? 4238 : 4096;                       // both crystals are mandatory: default to Inferno / Fire
    const opts = hq ? HQ.map(([n, id]) => [id, n + ' Crystal']) : CRYSTALS.map((n, i) => [4096 + i, n + ' Crystal']);
    const cur = slots[key].id, known = opts.some(o => o[0] === cur);
    return '<select data-crys="' + key + '" title="' + (hq ? 'High Quality Crystal' : 'Crystal') + ' (required)">' + opts.map(o => '<option value="' + o[0] + '"' + (o[0] === cur ? ' selected' : '') + '>' + o[1] + ' (#' + o[0] + ')</option>').join('') + (cur && !known ? '<option value="' + cur + '" selected>Item #' + cur + '</option>' : '') + '</select>';
  }
  const liveRun = debounce(async () => {
    const box = $('syLive'); if (!box) return;
    try {
      const d = await post('/synth/live.json', {editing: editing && editMode !== 'create' ? editing.id : 0, recipe: collect()});
      const rl = r => '<li><a href="#" data-r="' + r.id + '">#' + r.id + '</a> ' + ico(r.result) + esc(nm(r.name)) + ' <small class="mut">' + esc(Object.entries(r.skills).map(([k, v]) => k + ' ' + v).join(', ')) + '</small></li>';
      let h = '<h4>Live check</h4>';
      if (d.errors.length) h += '<ul class="sy-msg sy-err">' + d.errors.map(x => '<li>' + esc(x) + '</li>').join('') + '</ul>';
      if (d.warnings.length) h += '<ul class="sy-msg sy-warn">' + d.warnings.map(x => '<li>' + esc(x) + '</li>').join('') + '</ul>';
      if (d.ingredients.length) h += '<table class="sy-t"><tbody>' + d.ingredients.map(i => '<tr><td>' + ico(i.item_id) + esc(nm(i.name)) + ' ×' + i.count + '</td><td>' + pill(i.status === 'ok' ? 'ok' : i.status) + '</td><td class="n">' + (i.price != null ? fmt(i.price * i.count) + 'g' : '<span class="mut">no vendor</span>') + '</td></tr>').join('') + '</tbody></table>' +
        '<p class="mut">Vendor cost ' + fmt(d.cost) + 'g' + (d.unpriced ? ' + ' + d.unpriced + ' unpriced' : '') + ' · NPC value of result ' + fmt(d.npc_value) + 'g' + (!d.unpriced && d.cost && d.npc_value > d.cost ? ' <span class="sy-warn">(profit loop risk)</span>' : '') + '</p>';
      h += d.exact.length ? '<div class="sy-warn"><b>Duplicate:</b> same crystal and ingredients already used by</div><ul>' + d.exact.map(rl).join('') + '</ul>' : '<div class="sy-pill ok">No exact duplicate</div>';
      if (d.near.length) h += '<div class="mut">Near-duplicates (same crystal, ≤2 ingredients different)</div><ul>' + d.near.map(rl).join('') + '</ul>';
      if (d.same_result.length) h += '<div class="mut">Other recipes with the same result</div><ul>' + d.same_result.map(rl).join('') + '</ul>';
      box.innerHTML = h;
      box.querySelectorAll('a[data-r]').forEach(a => a.onclick = ev => { ev.preventDefault(); tab('recipes'); showRecipe(+a.dataset.r); });
    } catch (e) { box.innerHTML = '<span class="sy-err">' + esc(e.message) + '</span>'; }
  }, 500);
  function sortIngredients() {                 // schema: Ingredient1..8 ascending by item id, empty slots last
    slots.ing = slots.ing.filter(x => x.id).sort((a, b) => a.id - b.id);
  }
  function renderSlots() {
    sortIngredients();
    const g = $('syGrid'); if (!g) return;
    liveRun();
    g.innerHTML =
      '<div class="sy-grp"><h4>Crystals</h4><div class="sy-crys"><label>Crystal ' + crystalSelect('crystal') + '</label><label>High Quality Crystal ' + crystalSelect('hq_crystal') + '</label></div></div>' +
      '<div class="sy-grp"><h4>Ingredients <small class="mut">(' + slots.ing.length + '/8 · stored smallest id first)</small></h4><div class="sy-tiles sy-r4">' +
        Array.from({length: 8}, (_, i) => { const x = slots.ing[i] || {}; return tileHtml('ing' + i, 'Ingredient ' + (i + 1), x.id, x.name); }).join('') + '</div></div>' +
      '<div class="sy-grp"><h4>Results <small class="mut">(empty HQ tiers copy NQ)</small></h4><div class="sy-tiles sy-r4">' +
        slots.res.map((x, i) => tileHtml('res' + i, ['NQ', 'HQ1', 'HQ2', 'HQ3'][i], x.id, x.name, x.qty)).join('') + '</div></div>';
  }
  function slotRef(key) {
    if (key === 'crystal' || key === 'hq_crystal') return slots[key];
    if (key.startsWith('res')) return slots.res[+key.slice(3)];
    const i = +key.slice(3);
    if (!slots.ing[i]) slots.ing[i] = {};
    return slots.ing[i];
  }
  function openPicker(key, cur) {
    picking = key; renderSlots();
    $('syPick').style.display = 'block';
    const lbl = key.startsWith('ing') ? 'an ingredient' : key.startsWith('res') ? 'a result' : 'a crystal';
    $('syPickT').textContent = (cur && cur.id ? 'Replace ' + nm(cur.name || ('#' + cur.id)) + ' with ' : 'Add ') + lbl + ' — search by name or numeric id';
    $('syPickQ').value = ''; $('syPickR').innerHTML = ''; $('syPickQ').focus();
  }
  const pickSearch = debounce(async () => {
    const q = $('syPickQ').value.trim(); if (!q) { $('syPickR').innerHTML = ''; return; }
    try {
      const d = await req('/synth/items.json?q=' + encodeURIComponent(q) + '&limit=30');
      $('syPickR').innerHTML = d.items.length ? d.items.map(i => '<button type="button" class="sy-hit" data-id="' + i.item_id + '" data-n="' + esc(i.name) + '">' + ico(i.item_id) + '<span>' + esc(nm(i.name)) + '</span><small class="mut">#' + i.item_id + '</small></button>').join('') : '<div class="mut">No item matches.</div>';
    } catch (e) { $('syPickR').innerHTML = '<div class="sy-err">' + esc(e.message) + '</div>'; }
  }, 200);
  function chooseItem(id, name) {
    if (!picking) return;
    const ref = slotRef(picking);
    if (picking.startsWith('ing') && !ref.id) { slots.ing[+picking.slice(3)] = {id, name}; }
    else { ref.id = id; ref.name = name; if (picking.startsWith('res') && !ref.qty) ref.qty = picking === 'res0' ? 1 : 0; }
    picking = null; $('syPick').style.display = 'none'; renderSlots();
  }
  function renderKey() {
    const k = keyList && keyList.find(x => x.id === keyItem);
    $('eKeyBtn').textContent = keyItem ? (k && k.name ? k.name + ' (#' + keyItem + ')' : 'Key item #' + keyItem) : 'None';
  }
  async function openKeyChooser() {
    const box = $('syKeyBox');
    if (box.style.display === 'block') { box.style.display = 'none'; return; }
    box.style.display = 'block'; box.innerHTML = 'Loading…';
    try {
      if (!keyList) { const d = await req('/synth/keyitems.json'); keyList = d.keyitems; }
      const groups = {};
      keyList.forEach(k => (groups[k.craft || 'Other'] = groups[k.craft || 'Other'] || []).push(k));
      box.innerHTML = '<div class="mut">Key items already used by synth recipes on this server (names from its keyitems.lua). The server stores the id, and ids differ between DSP/Topaz/LSB.</div>' +
        '<button type="button" class="sy-ki' + (keyItem ? '' : ' on') + '" data-ki="0">None</button>' +
        Object.keys(groups).sort().map(g => '<div class="sy-kig"><b>' + esc(g) + '</b><div>' + groups[g].map(k => '<button type="button" class="sy-ki' + (k.id === keyItem ? ' on' : '') + '" data-ki="' + k.id + '" title="' + k.count + ' recipe(s)">' + esc(k.name || ('#' + k.id)) + ' <small class="mut">#' + k.id + ' · ' + k.count + '</small></button>').join('') + '</div></div>').join('') +
        '<div class="sy-row"><span>Other id</span><input type="number" min="0" id="eKeyOther" placeholder="numeric key item id"><button type="button" class="b" id="eKeyOtherGo">Use</button></div>';
      box.onclick = e => {
        const b = e.target.closest('[data-ki]'); if (b) { keyItem = +b.dataset.ki; box.style.display = 'none'; renderKey(); return; }
        if (e.target.id === 'eKeyOtherGo') { keyItem = Math.max(0, +$('eKeyOther').value || 0); box.style.display = 'none'; renderKey(); }
      };
    } catch (e) { box.innerHTML = '<span class="sy-err">' + esc(e.message) + '</span>'; }
  }
  async function showInfo(id) {
    const box = $('syInfo'); box.innerHTML = '<div class="mut">Loading #' + id + '…</div>';
    try {
      const d = await req('/synth/item.json?id=' + id);
      const li = [];
      if (d.vendor) li.push('Vendor: ' + fmt(d.vendor.price) + 'g — ' + esc(d.vendor.vendor) + (d.vendor.zone ? ' (' + esc(d.vendor.zone.replace(/_/g, ' ')) + ')' : ''));
      if (d.drops) li.push('Drops: ' + d.drops.sample.map(s => esc(nm(s.mob)) + (s.zone ? ' (' + esc(nm(s.zone)) + ')' : ' (zone ' + s.zone_id + ')')).join(', ') + (d.drops.mobs > d.drops.sample.length ? ' +' + (d.drops.mobs - d.drops.sample.length) + ' more' : ''));
      if (d.orphan_drop && !d.drops) li.push('<span class="sy-warn">In a droplist, but no spawning mob uses it</span>');
      if (d.bcnm) li.push('BCNM loot');
      if (d.engine) li.push('Elemental crystal/cluster: dropped by mobs in the game engine');
      d.scripts.forEach(s => li.push('<span class="mut">' + esc(s.kind) + ': ' + esc(s.file) + ' (low confidence)</span>'));
      if (d.made_by.length) li.push('Crafted by recipe ' + d.made_by.map(m => '<a href="#" data-r="' + m.id + '">#' + m.id + '</a> <small class="mut">(' + esc(m.craft) + ')</small>').join(', '));
      if (d.ah) li.push('AH: ' + d.ah.count + ' listed from ' + fmt(d.ah.min) + 'g');
      box.innerHTML = '<div class="sy-info-h">' + ico(d.item_id) + '<div><b>' + esc(nm(d.name)) + '</b> <small class="mut">#' + d.item_id + '</small><br><small class="mut">stack ' + d.stack + ' · NPC pays ' + fmt(d.sell) + 'g' + (d.nosale ? ' (not sellable)' : '') + ' · used in ' + d.used_in + ' recipe(s)</small></div>' + pill(d.status === 'ok' ? 'ok' : d.status) + '</div>' +
        (li.length ? '<ul class="sy-src">' + li.map(x => '<li>' + x + '</li>').join('') + '</ul>' : '<div class="sy-warn">No known source for this item.</div>');
      box.querySelectorAll('a[data-r]').forEach(a => a.onclick = ev => { ev.preventDefault(); tab('recipes'); showRecipe(+a.dataset.r); });
    } catch (e) { box.innerHTML = '<span class="sy-err">' + esc(e.message) + '</span>'; }
  }
  function openEditor(r, mode) {
    editing = r; editMode = mode || 'create';
    const isNew = editMode === 'create';
    const base = r || {skills: {}, ingredients: [], results: [{}, {}, {}, {}], desynth: false, key_item: 0, crystal: 0, hq_crystal: 0};
    const inames = base.ingredient_names || [];
    slots = {crystal: {id: base.crystal || 0, name: base.crystal_name}, hq_crystal: {id: base.hq_crystal || 0, name: base.hq_crystal_name},
             ing: base.ingredients.map((id, i) => ({id, name: inames[i]})),
             res: [0, 1, 2, 3].map(i => { const x = base.results[i] || {}; return {id: x.item_id || 0, name: x.name, qty: x.qty || 0}; })};
    picking = null;
    keyItem = base.key_item || 0;
    $('syEditor').innerHTML = '<h3 style="margin:0 0 6px">' + (isNew ? (r ? 'New recipe (copy of #' + r.id + ')' : 'New recipe') : 'Edit recipe #' + r.id) + '</h3>' +
      '<div class="sy-ed"><div class="sy-edl">' +
      '<fieldset class="ce-card"><legend>Basics</legend><div class="sy-row"><label>ID <input id="eId" type="number" ' + (isNew ? 'placeholder="auto"' : 'value="' + r.id + '" readonly') + '></label>' +
      '<label><input type="checkbox" id="eDesynth"' + (base.desynth ? ' checked' : '') + '> Desynth</label></div>' +
      '<div class="sy-row"><label>Result name <input id="eName" value="' + esc(base.result_name || '') + '" placeholder="auto from result"></label></div>' +
      '<div class="sy-row"><span>Key item</span><button type="button" class="b" id="eKeyBtn"></button></div><div id="syKeyBox" class="sy-pickbox" style="display:none"></div></fieldset>' +
      '<fieldset class="ce-card"><legend>Skill levels</legend><div class="sy-skills">' + CRAFTS.map(c => '<label>' + c + '<input type="number" min="0" max="255" data-sk="' + c + '" value="' + (base.skills[c] || 0) + '"></label>').join('') + '</div></fieldset>' +
      '<fieldset class="ce-card"><legend>Comment (added to the SQL as -- lines)</legend><textarea id="eComment" rows="2" class="sy-sql" placeholder="why this change, source, ticket…">' + esc(base.comment || '') + '</textarea></fieldset>' +
      '</div><div class="sy-edr">' +
      '<div id="syPick" class="sy-pickbox" style="display:none"><div id="syPickT" class="mut"></div><div class="sy-row"><input id="syPickQ" type="search" placeholder="e.g. mahogany lumber or 689" autocomplete="off"><button class="b" type="button" id="syPickX">Cancel</button></div><div id="syPickR" class="sy-hits"></div></div>' +
      '<div class="sy-work"><div id="syGrid" class="sy-grid"></div>' +
      '<div class="sy-side"><div id="syInfo" class="sy-info"><div class="mut">Click a filled slot to see where that item comes from, then search to replace it.</div></div>' +
      '<div id="syLive" class="sy-info"><div class="mut">Live check appears once the recipe has items.</div></div></div></div></div></div>' +
      '<div class="sy-actions"><button class="b pri" id="ePrev" type="button">Preview SQL</button>' + (isNew ? '' : '<button class="b" id="eDelete" type="button">Preview delete</button>') + '</div><div id="ePreview"></div>';
    $('eKeyBtn').onclick = openKeyChooser; renderKey();
    $('ePrev').onclick = () => preview(editMode);
    if ($('eDelete')) $('eDelete').onclick = () => preview('delete');
    $('syGrid').onclick = e => {
      const c = e.target.closest('[data-clear]');
      if (c) { e.stopPropagation(); const k = c.dataset.clear; const ref = slotRef(k); ref.id = 0; ref.name = ''; if (k.startsWith('res')) ref.qty = 0; renderSlots(); return; }
      if (e.target.matches('.sy-q')) return;
      const t = e.target.closest('.sy-tile'); if (!t) return;
      let k = t.dataset.slot;
      const cur = k.startsWith('ing') ? (slots.ing[+k.slice(3)] || {}) : slotRef(k);
      if (cur.id) { showInfo(cur.id); openPicker(k, cur); return; }                                     // filled slot: show info and allow replacing
      if (k.startsWith('ing')) k = 'ing' + slots.ing.length;                                            // empty ingredient tile = append
      openPicker(k);
    };
    $('syGrid').onchange = e => { const s = e.target.closest('[data-crys]'); if (s) { slots[s.dataset.crys].id = +s.value; slots[s.dataset.crys].name = ''; if (+s.value) showInfo(+s.value); } };
    $('syEditor').addEventListener('input', e => { if (e.target.closest('[data-sk],#eDesynth,.sy-q')) liveRun(); });
    $('syGrid').oninput = e => { const q = e.target.closest('.sy-q'); if (q) slotRef(q.dataset.q).qty = Math.max(1, Math.min(99, +q.value || 1)); };
    $('syPickQ').oninput = pickSearch;
    $('syPickQ').onkeydown = e => { if (e.key === 'Enter') { const h = $('syPickR').querySelector('.sy-hit'); if (h) chooseItem(+h.dataset.id, h.dataset.n); } };
    $('syPickR').onclick = e => { const h = e.target.closest('.sy-hit'); if (h) chooseItem(+h.dataset.id, h.dataset.n); };
    $('syPickX').onclick = () => { picking = null; $('syPick').style.display = 'none'; renderSlots(); };
    renderSlots();
    tab('editor');
  }
  function collect() {
    sortIngredients();
    return {
      id: +$('eId').value || 0, desynth: $('eDesynth').checked, key_item: keyItem || 0, result_name: $('eName').value, comment: $('eComment').value,
      skills: Object.fromEntries([...document.querySelectorAll('[data-sk]')].map(i => [i.dataset.sk, +i.value || 0])),
      crystal: slots.crystal.id || 0, hq_crystal: slots.hq_crystal.id || 0, ingredients: slots.ing.map(x => x.id),
      results: slots.res.map((x, i) => ({item_id: x.id || 0, qty: x.id ? (x.qty || 1) : 0})),
    };
  }
  async function preview(mode) {
    const box = $('ePreview'); box.innerHTML = 'Checking…';
    const rec = collect();
    try {
      const d = await post('/synth/preview.json', mode === 'delete' ? {mode, id: editing ? editing.id : rec.id, comment: rec.comment} : {mode, recipe: rec});
      let h = '';
      if (d.errors.length) h += '<ul class="sy-msg sy-err">' + d.errors.map(x => '<li>' + esc(x) + '</li>').join('') + '</ul>';
      if (d.warnings.length) h += '<ul class="sy-msg sy-warn">' + d.warnings.map(x => '<li>' + esc(x) + '</li>').join('') + '</ul>';
      if (d.ok) {
        h += '<div class="sy-filters">SQL for: ' + ['dsp', 'topaz', 'lsb'].map(f => '<button class="b' + (f === d.active_flavor ? ' pri' : '') + '" data-f="' + f + '" type="button">' + f.toUpperCase() + (f === d.active_flavor ? ' (this server)' : '') + '</button>').join('') +
          '<button class="b" id="eCopy" type="button">Copy</button></div><textarea class="sy-sql" id="eSql" rows="6" readonly></textarea>' +
          '<div class="sy-actions"><button class="b pri" id="eApply" type="button">Apply to this server…</button><small class="mut">Needs a Test environment with test writes enabled and the profile name typed to confirm. Otherwise run the SQL yourself, then reimport/restart as usual.</small></div>';
      }
      box.innerHTML = h;
      if (!d.ok) return;
      const show = f => { $('eSql').value = d.sql[f]; box.querySelectorAll('button[data-f]').forEach(b => b.classList.toggle('pri', b.dataset.f === f)); };
      show(d.active_flavor);
      box.onclick = e => { const b = e.target.closest('button[data-f]'); if (b) show(b.dataset.f); };
      $('eCopy').onclick = () => { $('eSql').select(); document.execCommand('copy'); };
      $('eApply').onclick = async () => {
        const conf = prompt('Type the active Test profile name to apply this ' + mode + ' to ' + (st.env || 'the server') + ':');
        if (conf == null) return;
        try {
          const r = await post('/synth/save.json', {mode, confirmation: conf, id: editing ? editing.id : rec.id, recipe: rec});
          box.insertAdjacentHTML('beforeend', '<p class="sy-pill ok">Applied: ' + esc(r.mode) + ' recipe #' + r.id + ' (' + r.rows + ' row)</p>');
          load();
        } catch (e) { box.insertAdjacentHTML('beforeend', '<p class="sy-err">' + esc(e.message) + '</p>'); }
      };
    } catch (e) { box.innerHTML = '<div class="sy-err">' + esc(e.message) + '</div>'; }
  }


  /* ---- health / compare / economy ---- */
  const tiles = (id, arr) => { $(id).innerHTML = arr.map(a => '<div class="ahc-tile"><b>' + fmt(a[1]) + '</b><span>' + a[0] + '</span></div>').join(''); };
  const openRecipe = e => { const a = e.target.closest('[data-rid]'); if (a) { e.preventDefault(); tab('recipes'); showRecipe(+a.dataset.rid); } };
  $('syHealthRun').onclick = async () => {
    $('syHealthBody').innerHTML = '<div class="ahc-empty">Checking…</div>';
    try {
      const d = await req('/synth/health.json'), c = d.sources;
      tiles('syHealthTiles', [['Recipes', d.total], ['Sources ok', c.ok], ['Script ref only', c.script], ['No source', c.missing], ['Unknown item id', c.bad_item]]);
      $('syHealthBody').innerHTML = '<h4>Structural checks</h4>' + (d.structural.length ? '<table class="sy-t"><thead><tr><th>Check</th><th class="n">Recipes</th><th>First ids</th></tr></thead><tbody>' +
        d.structural.map(s => '<tr><td>' + esc(s.label) + '</td><td class="n">' + fmt(s.count) + '</td><td class="sy-src">' + s.ids.slice(0, 12).map(i => '<a href="#" data-rid="' + i + '">#' + i + '</a>').join(', ') + '</td></tr>').join('') + '</tbody></table>' : '<p class="sy-pill ok">No structural problems found</p>') +
        '<h4>Ingredients with no source, ranked by recipes they block</h4><table class="sy-t"><thead><tr><th>Item</th><th class="n">Recipes blocked</th></tr></thead><tbody>' +
        d.blockers.map(b => '<tr><td>' + ico(b.item_id) + ' ' + esc(nm(b.name)) + ' <small class="mut">#' + b.item_id + '</small></td><td class="n">' + fmt(b.recipes) + '</td></tr>').join('') + '</tbody></table>';
    } catch (e) { $('syHealthBody').innerHTML = '<div class="sy-err">' + esc(e.message) + '</div>'; }
  };
  $('syHealthBody').onclick = openRecipe;

  async function loadProfiles() {
    try {
      const d = await req('/synth/profiles.json');
      $('cmpOther').innerHTML = d.profiles.filter(p => !p.active).map(p => '<option value="' + p.profile_id + '">' + esc(p.name + ' (' + p.environment + ', ' + p.family + ')') + '</option>').join('') || '<option value="">No other profile configured</option>';
    } catch (e) {}
  }
  let cmp = null;
  const recLine = r => '<tr><td>#' + r.id + '</td><td>' + ico(r.result) + ' ' + esc(nm(r.name)) + (r.desynth ? ' <small class="mut">(desynth)</small>' : '') + '</td><td class="sy-src">' + esc(Object.entries(r.skills).map(([k, v]) => k + ' ' + v).join(', ')) + '</td></tr>';
  $('cmpRun').onclick = async () => {
    const other = $('cmpOther').value; if (!other) return;
    $('cmpBody').innerHTML = '<div class="ahc-empty">Comparing…</div>';
    try {
      const d = cmp = await req('/synth/compare.json?other=' + other + '&limit=500');
      tiles('cmpTiles', [[esc(d.a.label) + ' recipes', d.a.count], [esc(d.b.label) + ' recipes', d.b.count], ['Identical', d.same], ['Only in ' + esc(d.a.label), d.only_a_count], ['Only in ' + esc(d.b.label), d.only_b_count], ['Changed', d.changed_count]]);
      const sect = (title, rows, side) => '<h4>' + title + ' (' + rows.length + ')</h4>' + (rows.length ? '<div class="sy-actions"><button class="b" data-gen="' + side + '" type="button">Generate INSERTs for these…</button></div><div class="sy-scroll sy-cap"><table class="sy-t"><tbody>' + rows.map(recLine).join('') + '</tbody></table></div>' : '<p class="mut">None.</p>');
      $('cmpBody').innerHTML = sect('Only in ' + esc(d.a.label), d.only_a, 'a') + sect('Only in ' + esc(d.b.label), d.only_b, 'b') +
        '<h4>Changed (' + d.changed.length + ')</h4>' + (d.changed.length ? '<div class="sy-scroll sy-cap"><table class="sy-t"><thead><tr><th>' + esc(d.a.label) + '</th><th>' + esc(d.b.label) + '</th><th>Result</th><th>Differences</th></tr></thead><tbody>' +
          d.changed.map(c => '<tr><td>#' + c.key_a + '</td><td>#' + c.key_b + '</td><td>' + esc(nm(c.name)) + '</td><td class="sy-src">' + Object.entries(c.diff).map(([k, v]) => esc(k) + ': ' + esc(JSON.stringify(v[0])) + ' → ' + esc(JSON.stringify(v[1]))).join('<br>') + '</td></tr>').join('') + '</tbody></table></div>' : '<p class="mut">None.</p>') +
        '<h4>Item id sanity</h4><p class="sy-src">Same id, different name: ' + (d.item_name_mismatch.length ? d.item_name_mismatch.map(m => '#' + m.item_id + ' ' + esc(nm(m.a)) + ' / ' + esc(nm(m.b))).join('; ') : 'none') +
        '<br>Item ids missing in ' + esc(d.a.label) + ': ' + (d.items_absent_in_a.length ? d.items_absent_in_a.join(', ') : 'none') + '<br>Item ids missing in ' + esc(d.b.label) + ': ' + (d.items_absent_in_b.length ? d.items_absent_in_b.join(', ') : 'none') + '</p>' +
        '<textarea id="cmpSql" class="sy-sql" rows="10" readonly style="display:none"></textarea><div id="cmpWarn" class="mut"></div>';
    } catch (e) { $('cmpBody').innerHTML = '<div class="sy-err">' + esc(e.message) + '</div>'; }
  };
  $('cmpBody').onclick = async e => {
    const g = e.target.closest('button[data-gen]');
    if (!g || !cmp) return;
    const fromA = g.dataset.gen === 'a', rows = fromA ? cmp.only_a : cmp.only_b;
    const target = prompt('Generate INSERTs in which table layout? (dsp / topaz / lsb)', fromA ? 'lsb' : 'dsp'); if (!target) return;
    try {
      const d = await post('/synth/compare-sql.json', {flavor: target.trim().toLowerCase(), ids: rows.map(r => r.id), source_profile: fromA ? null : +$('cmpOther').value});
      $('cmpSql').style.display = 'block'; $('cmpSql').value = d.sql; $('cmpWarn').innerHTML = d.count + ' statement(s). ' + d.warnings.map(esc).join('<br>');
    } catch (err) { $('cmpWarn').innerHTML = '<span class="sy-err">' + esc(err.message) + '</span>'; }
  };

  $('ecoRun').onclick = async () => {
    $('ecoBody').innerHTML = '<div class="ahc-empty">Analyzing…</div>';
    try {
      const d = await req('/synth/economy.json?limit=300');
      tiles('ecoTiles', [['Recipes priced', d.priced], ['Profit vs NPC sell', d.profitable], ['Item cycles', d.loops.length]]);
      $('ecoBody').innerHTML = '<p class="mut">' + esc(d.note) + '</p><h4>Craft-and-sell-to-NPC profit</h4>' + (d.exploits.length ? '<div class="sy-scroll sy-cap"><table class="sy-t"><thead><tr><th>Recipe</th><th>Result</th><th class="n">Cost</th><th class="n">NPC value</th><th class="n">Profit</th></tr></thead><tbody>' +
        d.exploits.map(r => '<tr><td><a href="#" data-rid="' + r.id + '">#' + r.id + '</a></td><td>' + ico(r.result) + ' ' + esc(nm(r.name)) + ' ×' + r.qty + '</td><td class="n">' + fmt(r.cost) + '</td><td class="n">' + fmt(r.npc_value) + '</td><td class="n sy-warn">+' + fmt(r.profit) + '</td></tr>').join('') + '</tbody></table></div>' : '<p class="sy-pill ok">No recipe sells for more than its vendor-priced inputs cost</p>') +
        '<h4>Ingredient cycles</h4>' + (d.loops.length ? '<ul>' + d.loops.map(l => '<li>' + l.names.map(n => esc(nm(n))).join(' → ') + ' → (back)</li>').join('') + '</ul>' : '<p class="mut">None found (depth ≤ 4).</p>');
    } catch (e) { $('ecoBody').innerHTML = '<div class="sy-err">' + esc(e.message) + '</div>'; }
  };
  $('ecoBody').onclick = openRecipe;

  /* ---- export / port ---- */
  $('pxGo').onclick = async () => {
    const a = +$('pxFrom').value, b = +$('pxTo').value || a;
    if (!a) { $('pxWarn').textContent = 'Enter a starting recipe ID.'; return; }
    if (b - a > 499) { $('pxWarn').textContent = 'At most 500 recipes at a time.'; return; }
    try {
      const d = await post('/synth/export.json', {flavor: $('pxFlavor').value, ids: Array.from({length: b - a + 1}, (_, i) => a + i)});
      $('pxOut').value = d.sql; $('pxWarn').innerHTML = d.count + ' recipe(s). ' + d.warnings.slice(0, 6).map(esc).join('<br>');
    } catch (e) { $('pxWarn').textContent = e.message; }
  };
  $('pxCopy').onclick = () => { $('pxOut').select(); document.execCommand('copy'); };

  loadProfiles();
  /* ---- boot ---- */
  (async () => {
    try { const d = await req('/auction-house/capability-status.json'); st.env = (d.environment && d.environment.name) || ''; $('syEnv').textContent = (st.env || 'server') + (d.scoped_test_write_ready ? ' · writes enabled' : ' · read only'); $('syEnv').classList.add(d.scoped_test_write_ready ? 'warn' : 'ok'); } catch (e) { $('syEnv').textContent = 'no server'; }
    load(true);
  })();
})();
