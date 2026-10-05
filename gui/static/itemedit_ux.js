// Item Editor UX refresh: tile/list search results with filter chips and hover cards,
// and the editor pane regrouped into tabs. Pure overlay: every existing element id and
// handler in itemedit.html keeps working.
(() => {
  if (typeof renderSearchResults !== 'function' || !document.getElementById('editorWrap')) return;
  const G = window.CEGear;
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const store = {get: (k, d) => { try { return localStorage.getItem(k) || d; } catch (e) { return d; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} }};

  const css = document.createElement('style');
  css.textContent = `
    #itemResults{margin:8px 0}
    #itemResults .ie-bar{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:6px}
    #itemResults .ie-chip{border:1px solid var(--border,#555);border-radius:12px;padding:2px 10px;font-size:11.5px;cursor:pointer;background:transparent;color:inherit}
    #itemResults .ie-chip.on{background:rgba(106,169,255,.22);border-color:#6aa9ff}
    #itemResults .ie-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:6px;max-height:340px;overflow:auto}
    #itemResults .ie-list{display:flex;flex-direction:column;gap:2px;max-height:340px;overflow:auto}
    #itemResults .ie-tile{display:flex;align-items:center;gap:8px;padding:5px 8px;border:1px solid var(--border,#555);border-radius:6px;cursor:pointer;min-width:0}
    #itemResults .ie-tile:hover{border-color:#6aa9ff;background:rgba(106,169,255,.12)}
    #itemResults .ie-tile.sel{border-color:#6aa9ff;background:rgba(106,169,255,.2)}
    #itemResults .ie-tile img{width:32px;height:32px;object-fit:contain;flex:none}
    #itemResults .ie-tile .nm{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    #itemResults .ie-tile .sub{font-size:11px;opacity:.7;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    #itemResults .ie-tile .tx{min-width:0;flex:1}
    #itemResults .ie-badge{font-size:10px;padding:0 6px;border-radius:8px;border:1px solid currentColor;flex:none}
    #itemResults .ie-badge.dat-only{color:#e0a030}#itemResults .ie-badge.mismatch{color:#e06060}#itemResults .ie-badge.server-only{color:#9aa}
    #ieTabs{display:flex;gap:2px;border-bottom:1px solid var(--border,#555);margin:12px 0 8px;flex-wrap:wrap}
    #ieTabs button{border:1px solid transparent;border-bottom:0;border-radius:6px 6px 0 0;padding:5px 14px;background:transparent;color:inherit;cursor:pointer;opacity:.7}
    #ieTabs button.on{opacity:1;font-weight:600;border-color:var(--border,#555);background:rgba(106,169,255,.12)}
    #ieTabs button .dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#f5c542;margin-left:5px}
    .ie-pane{display:none}.ie-pane.on{display:block}`;
  document.head.appendChild(css);

  // ---------- search / browse ----------
  const host = document.createElement('div');
  host.id = 'itemResults';
  host.style.display = 'none';
  const oldResults = document.getElementById('results');
  oldResults.parentNode.insertBefore(host, oldResults);
  oldResults.remove();
  // keep the old element id alive for setItemServer() etc.
  const stub = document.createElement('div');
  stub.id = 'results'; stub.style.display = 'none';
  host.appendChild(stub);

  let view = store.get('ieView', 'tiles');
  let classFilter = '';
  let selectedId = null;
  const stateNote = {'dat-only': 'DAT only', 'server-only': 'server only'};  // "mismatch" is too common to badge every tile; the editor's status bar shows it

  const sortedRows = () => {
    const key = document.getElementById('searchSort').value, dir = document.getElementById('searchDir').value === 'desc' ? -1 : 1;
    const val = (r) => key === 'id' ? Number(r.itemid) : key === 'class' ? (r.type_name || '') : key === 'level' ? Number(r.level ?? -1) : key === 'client' ? (r.client_state || '') : (r.name || '').toLowerCase();
    return [...lastSearchRows].sort((a, b) => ((val(a) > val(b)) - (val(a) < val(b))) * dir || Number(a.itemid) - Number(b.itemid));
  };
  const detail = r => [r.type_name, r.level ? 'Lv ' + r.level : '', r.dmg ? 'DMG ' + r.dmg : '', r.delay ? 'Delay ' + r.delay : ''].filter(Boolean).join(' · ');

  function draw() {
    const all = sortedRows();
    host.style.display = lastSearchRows.length ? '' : 'none';
    if (!lastSearchRows.length) return;
    const classes = [...new Set(lastSearchRows.map(r => r.type_name).filter(Boolean))].sort();
    if (classFilter && !classes.includes(classFilter)) classFilter = '';
    const rows = classFilter ? all.filter(r => r.type_name === classFilter) : all;
    const tiles = rows.map(r => `<div class="ie-tile${r.itemid === selectedId ? ' sel' : ''}" data-id="${r.itemid}" data-st="${esc(r.client_state)}">
      <img src="/itemedit/${r.itemid}/icon.png" loading="lazy" onerror="this.style.visibility='hidden'" alt="">
      <div class="tx"><div class="nm">${esc(r.name || '(unnamed)')}</div><div class="sub">#${r.itemid}${view === 'tiles' || true ? ' · ' + esc(detail(r)) : ''}</div></div>
      ${stateNote[r.client_state] ? `<span class="ie-badge ${esc(r.client_state)}">${stateNote[r.client_state]}</span>` : ''}</div>`).join('');
    host.innerHTML = `<div class="ie-bar">
        <strong>${rows.length}${classFilter ? ' of ' + all.length : ''} item${rows.length === 1 ? '' : 's'}</strong>
        <button class="ie-chip${classFilter ? '' : ' on'}" data-class="">All</button>
        ${classes.map(c => `<button class="ie-chip${c === classFilter ? ' on' : ''}" data-class="${esc(c)}">${esc(c)}</button>`).join('')}
        <span style="flex:1"></span>
        <button class="ie-chip${view === 'tiles' ? ' on' : ''}" data-view="tiles">Tiles</button>
        <button class="ie-chip${view === 'list' ? ' on' : ''}" data-view="list">List</button>
      </div><div class="${view === 'list' ? 'ie-list' : 'ie-grid'}">${tiles || '<div class="muted">No items match this filter.</div>'}</div>`;
    const s = document.createElement('div'); s.id = 'results'; s.style.display = 'none'; host.appendChild(s);
  }
  renderSearchResults = draw;
  document.getElementById('searchSort').onchange = draw;
  document.getElementById('searchDir').onchange = draw;

  host.addEventListener('click', e => {
    const chip = e.target.closest('.ie-chip');
    if (chip) {
      if (chip.dataset.view) { view = chip.dataset.view; store.set('ieView', view); }
      else classFilter = chip.dataset.class;
      return draw();
    }
    const t = e.target.closest('.ie-tile');
    if (!t) return;
    G.hideTip();
    selectedId = Number(t.dataset.id);
    host.querySelectorAll('.ie-tile.sel').forEach(x => x.classList.remove('sel'));
    t.classList.add('sel');
    if (t.dataset.st === 'dat-only') inspectDatOnlyItem(selectedId);
    else { document.getElementById('datOnlyPreview').style.display = 'none'; loadItem(selectedId); }
  });
  G.bindTips(host, '.ie-tile', el => {
    const r = lastSearchRows.find(x => String(x.itemid) === el.dataset.id);
    return r && {id: r.itemid, name: r.name || '(unnamed)', where: detail(r), action: r.client_state === 'dat-only' ? 'preview the client record' : 'edit'};
  });

  const origSetServer = setItemServer;
  setItemServer = async function () { await origSetServer(); lastSearchRows = []; host.style.display = 'none'; };

  // ---------- editor tabs ----------
  const wrap = document.getElementById('editorWrap');
  const byId = id => document.getElementById(id);
  const tabsDef = [
    ['props', 'Properties', ['decodedSummary', 'itemCompareResult']],
    ['effects', 'Effects', ['effectStagingTools']],
    ['client', 'Client record', ['datInfoCard']],
    ['history', 'History & safety', ['selectedItemHistory', 'itemBackupsCard', 'itemUsagePanel', 'itemDeleteCard']],
  ];
  // tag the two cards that have no id
  [...wrap.querySelectorAll(':scope > .edit-card')].forEach(c => {
    const h = c.querySelector('h3')?.textContent || '';
    if (h.startsWith('Backups')) c.id = 'itemBackupsCard';
    if (h.startsWith('Delete this item')) c.id = 'itemDeleteCard';
  });
  const bar = document.createElement('div'); bar.id = 'ieTabs';
  const panes = {};
  const anchor = byId('decodedSummary');
  anchor.parentNode.insertBefore(bar, anchor);
  let after = bar;
  for (const [key, label] of tabsDef) {
    const b = document.createElement('button'); b.type = 'button'; b.dataset.tab = key; b.textContent = label;
    bar.appendChild(b);
    const p = document.createElement('div'); p.className = 'ie-pane'; p.dataset.pane = key;
    after.after(p); after = p; panes[key] = p;
  }
  // Properties pane also takes the editor-mode toolbar, the tables grid and the lists row
  const toolbar = wrap.querySelector('.editor-toolbar');
  const put = (key, el) => el && panes[key].appendChild(el);
  put('props', toolbar);
  for (const [key, , ids] of tabsDef) for (const id of ids) put(key, byId(id));
  panes.props.insertBefore(byId('decodedSummary'), panes.props.firstChild);
  put('props', byId('editorTables'));
  put('effects', byId('editorLists'));
  // Effects: show the lists first, the bulk staging tools after
  panes.effects.insertBefore(byId('editorLists'), panes.effects.firstChild);

  const pick = key => {
    store.set('ieTab', key);
    bar.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.tab === key));
    Object.entries(panes).forEach(([k, p]) => p.classList.toggle('on', k === key));
  };
  bar.addEventListener('click', e => { const b = e.target.closest('button'); if (b) pick(b.dataset.tab); });
  pick(panes[store.get('ieTab', 'props')] ? store.get('ieTab', 'props') : 'props');

  // mark tabs that hold unsaved edits
  const markDirty = () => {
    const tbl = typeof changedTables === 'function' ? Object.keys(changedTables()).length > 0 : false;
    const fx = typeof effectsDirty === 'function' ? effectsDirty() : false;
    for (const [key, dirty] of [['props', tbl], ['effects', fx]]) {
      const b = bar.querySelector(`[data-tab="${key}"]`);
      b.querySelector('.dot')?.remove();
      if (dirty) b.insertAdjacentHTML('beforeend', '<span class="dot" title="Unsaved changes"></span>');
    }
  };
  const origDirty = updateDirtySummary;
  updateDirtySummary = function () { const r = origDirty.apply(this, arguments); markDirty(); return r; };

  // ---------- plain-language labels ----------
  const L = {
    'item_basic.name': ['Name', 'The item\'s internal (server) name.'],
    'item_basic.sortname': ['Sort name', 'Name used for sorting and searching.'],
    'item_basic.subid': ['Variant ID', 'Legacy sub-record number. Leave alone unless copying a known item.'],
    'item_basic.stackSize': ['Max stack size', 'How many of this item fit in one inventory slot.'],
    'item_basic.flags': ['Item properties', 'Rare, Ex, can\'t be sold/traded and similar permission flags.'],
    'item_basic.aH': ['Auction category', 'Which Auction House category the item is listed under (0 = not sellable).'],
    'item_basic.NoSale': ['Vendor sale', 'Whether NPC vendors will buy this item.'],
    'item_basic.BaseSell': ['Sell price (gil)', 'What an NPC vendor pays for this item.'],
    'item_equipment.name': ['Name', 'The item\'s internal (server) name.'],
    'item_equipment.level': ['Required level', 'Minimum character level needed to equip.'],
    'item_equipment.ilevel': ['Item level', 'Item level shown on the item; does not affect who can equip it.'],
    'item_equipment.jobs': ['Usable by jobs', 'Which jobs can equip this item.'],
    'item_equipment.slot': ['Equips in', 'Which equipment slot(s) it goes in. Rings and earrings link both sides together.'],
    'item_equipment.rslot': ['Slot restriction', 'Related slot data; normally leave unchanged.'],
    'item_equipment.MId': ['Appearance (model ID)', 'Which model the client draws when worn.'],
    'item_equipment.shieldSize': ['Shield size', 'Shield size class (affects block rate).'],
    'item_equipment.scriptType': ['Special equip behavior', 'Which equip script category applies.'],
    'item_weapon.name': ['Name', 'The item\'s internal (server) name.'],
    'item_weapon.skill': ['Weapon type', 'The combat skill this weapon uses (Hand-to-Hand, Sword, ...).'],
    'item_weapon.subskill': ['Weapon sub-type', 'Secondary skill/subtype, e.g. for ranged ammo.'],
    'item_weapon.dmg': ['Damage', 'Base weapon damage (DMG).'],
    'item_weapon.delay': ['Delay', 'Weapon delay between attacks. Lower is faster.'],
    'item_weapon.dmgType': ['Damage type', 'Slashing, piercing, blunt or H2H.'],
    'item_weapon.hit': ['Max hits per attack ("occasionally attacks twice")', 'Not a fixed count. 1 = always one hit. 2 = "occasionally attacks twice" (about 55% one hit, 45% two hits). 3 = one to three hits, 4+ = more. Weapons like Joyeuse get their multi-hit text from this field, not from an effect.'],
    'item_weapon.ilvl_skill': ['Item-level skill bonus', 'Skill bonus granted by item level.'],
    'item_weapon.ilvl_parry': ['Item-level parry bonus', 'Parry bonus granted by item level.'],
    'item_weapon.ilvl_macc': ['Item-level magic accuracy bonus', 'Magic accuracy bonus granted by item level.'],
    'item_weapon.unlock_points': ['Points to unlock', 'Points needed for unlock-style weapons.'],
    'item_usable.name': ['Name', 'The item\'s internal (server) name.'],
    'item_usable.validTargets': ['Can be used on', 'Who the item may be used on (self, party, enemy...).'],
    'item_usable.activation': ['Effect when used (ID)', 'Which use effect fires. Raw ID from the server.'],
    'item_usable.animation': ['Use animation', 'Animation played when used.'],
    'item_usable.animationTime': ['Animation length', 'How long the use animation lasts.'],
    'item_usable.maxCharges': ['Charges', 'Number of uses stored on the item.'],
    'item_usable.useDelay': ['Delay before use (s)', 'Seconds before the effect takes place.'],
    'item_usable.reuseDelay': ['Reuse timer (s)', 'Seconds before the item can be used again.'],
    'item_usable.aoe': ['Area effect', 'Whether the effect hits an area.'],
    'item_puppet.name': ['Name', 'The item\'s internal (server) name.'],
    'item_puppet.slot': ['Attachment slot', 'Which automaton attachment slot it fits.'],
    'item_puppet.element': ['Element', 'Elemental capacity / cost of the attachment.'],
    'item_furnishing.name': ['Name', 'The item\'s internal (server) name.'],
    'item_furnishing.storage': ['Storage added', 'Mog House storage this furnishing provides.'],
    'item_furnishing.moghancement': ['Moghancement', 'Moghancement type.'],
    'item_furnishing.element': ['Element', 'Furnishing element.'],
    'item_furnishing.aura': ['Aura strength', 'Elemental aura strength.'],
  };
  for (const [k, v] of Object.entries(L)) FIELD_HELP[k] = v[1];
  Object.assign(TABLE_LABELS, {item_basic: 'General', item_equipment: 'Equipment', item_weapon: 'Weapon', item_usable: 'Usable item', item_puppet: 'Automaton attachment', item_furnishing: 'Furnishing'});
  const GROUPS = {Identity: 'Name', Inventory: 'Stacking & flags', Economy: 'Price & auction', Requirements: 'Who can equip', Placement: 'Slots', Presentation: 'Appearance & behavior',
    Combat: 'Combat stats', ItemLevel: 'Item-level bonuses', Unlock: 'Unlocking', Targeting: 'Targets', Timing: 'Timing', Charges: 'Charges', Attachment: 'Attachment', Furnishing: 'Furnishing', Fields: 'Fields', Other: 'Other'};
  const origField = itemFieldHtml;
  itemFieldHtml = function (table, row, f, schema) {
    const lab = L[table + '.' + f]?.[0];
    const html = origField.apply(this, arguments);
    return lab ? html.replace('">' + f + '</span>', '">' + lab + '</span>') : html;
  };
  const origGrid = buildTablesGrid;
  buildTablesGrid = function (w) {
    const r = origGrid.apply(this, arguments);
    w.querySelectorAll('.logical-group-title').forEach(t => {
      const n = [...t.childNodes].find(x => x.nodeType === 3);
      if (n && GROUPS[n.textContent.trim()]) n.textContent = GROUPS[n.textContent.trim()];
    });
    w.querySelectorAll('.edit-card > h3 .hint').forEach(h => { if (/^item_/.test(h.textContent)) h.remove(); });
    return r;
  };
  const modeSel = byId('itemEditorMode');
  if (modeSel) { modeSel.options[0].textContent = 'Common fields'; modeSel.options[1].textContent = 'All fields'; modeSel.previousSibling && (modeSel.closest('label').firstChild.textContent = 'Show '); }
  const modeHint = modeSel?.closest('.editor-toolbar')?.querySelector('span.muted');
  if (modeHint) modeHint.textContent = 'Common fields covers everyday gameplay values; All fields shows every raw server column.';

  // the draft editor reuses the editor's field styling, which the page scopes to #editorWrap
  try {
    const copies = [];
    for (const sheet of document.styleSheets) for (const r of sheet.cssRules) if (r.selectorText && r.selectorText.includes('#editorWrap')) copies.push(r.cssText.replace(/#editorWrap/g, '#draftWrap'));
    const s = document.createElement('style'); s.textContent = copies.join('\n'); document.head.appendChild(s);
  } catch (e) { console.warn('draft styles', e); }

  // ---------- fixed navigation: Find & edit / Create new / Batch edit ----------
  const css2 = document.createElement('style');
  css2.textContent = `
    #ieNav{display:flex;gap:4px;border-bottom:2px solid var(--border,#555);margin:6px 0 8px}
    #ieNav button{border:1px solid transparent;border-bottom:0;border-radius:6px 6px 0 0;padding:7px 18px;background:transparent;color:inherit;cursor:pointer;font-size:13px;opacity:.7}
    #ieNav button.on{opacity:1;font-weight:700;border-color:var(--border,#555);background:rgba(106,169,255,.14)}
    .ie-section{display:none}.ie-section.on{display:grid;grid-template-columns:360px minmax(0,1fr);gap:12px;overflow:hidden}
    .ie-section.single.on{display:block;overflow:auto}
    .ie-col{overflow:auto;min-height:0;padding-right:4px}
    #ieFind .ie-grid{grid-template-columns:1fr;max-height:none;overflow:visible}
    #ieFind form.search{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 8px}
    #ieFind form.search input[type=text]{min-width:0;width:100%;flex:1 1 100%}
    #ieFind .ie-more{flex:1 1 100%}
    #ieFind .ie-more summary{cursor:pointer;opacity:.8;font-size:12px}
    #ieFind .ie-more>div{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
    .ie-empty{padding:40px 20px;text-align:center;opacity:.6;border:1px dashed var(--border,#555);border-radius:8px}
    #ieEditHead,#ieDraftHead{position:sticky;top:0;z-index:6;background:var(--bg,#1e1e1e);padding-bottom:4px;border-bottom:1px solid var(--border,#555)}
    #ieEditHead>*,#ieDraftHead>*{margin-top:4px!important}
    #ieEditHead #ieTabs{margin:4px 0 0;border-bottom:0}
    #ieEditHead #itemStatusBar{padding:3px 8px!important;font-size:11px;border-width:1px!important}
    #ieEditHead #dirtySummary{padding:2px 8px!important;font-size:11px}
    #ieEditHead #itemSessionHistory{margin:0!important;padding:0!important;font-size:11px}
    #ieEditHead #editorTitle{font-size:16px}
    #ieEditHead #editComment{min-width:140px}
    #ieCreateTabs{display:flex;gap:2px;border-bottom:1px solid var(--border,#555);margin-bottom:8px;flex-wrap:wrap}
    #ieCreateTabs button{border:1px solid transparent;border-bottom:0;border-radius:6px 6px 0 0;padding:5px 10px;background:transparent;color:inherit;cursor:pointer;opacity:.7}
    #ieCreateTabs button.on{opacity:1;font-weight:600;border-color:var(--border,#555);background:rgba(106,169,255,.12)}
    #ieCreate .ie-cpane{display:none;flex-direction:column;gap:8px}#ieCreate .ie-cpane.on{display:flex}
    #ieCreate .ie-cpane input[type=text],#ieCreate .ie-cpane select{width:100%}`;
  document.head.appendChild(css2);

  const mk = (tag, id, cls) => { const e = document.createElement(tag); if (id) e.id = id; if (cls) e.className = cls; return e; };
  const topBar = byId('itemEditorTop');
  const nav = mk('div', 'ieNav');
  const secs = {find: mk('div', 'ieFind', 'ie-section'), create: mk('div', 'ieCreate', 'ie-section'), batch: mk('div', 'ieBatch', 'ie-section single')};
  const navDef = [['find', 'Find & edit'], ['create', 'Create new item'], ['batch', 'Batch edit']];
  navDef.forEach(([k, t]) => { const b = mk('button'); b.type = 'button'; b.dataset.sec = k; b.textContent = t; nav.appendChild(b); });
  topBar.after(nav);
  let prev = nav;
  for (const s of Object.values(secs)) { prev.after(s); prev = s; }

  // -- Find & edit: search + results left, editor right
  const form = document.querySelector('form.search');
  const left = mk('div', 'ieFindLeft', 'ie-col'), right = mk('div', 'ieFindRight', 'ie-col');
  secs.find.append(left, right);
  const more = mk('details', null, 'ie-more');
  more.innerHTML = '<summary>More filters &amp; sorting</summary><div></div>';
  for (const id of ['searchMinLevel', 'searchMaxLevel', 'searchJob', 'searchSkill', 'searchClientState', 'searchSort', 'searchDir']) more.lastChild.appendChild(byId(id));
  form.insertBefore(more, form.querySelector('button[type=submit]'));
  left.append(form, byId('datOnlyPreview'), host);
  const empty = mk('div', 'ieEmpty', 'ie-empty');
  empty.innerHTML = '<h3>No item open</h3><p>Search on the left, then click an item to edit it. Hover a result to preview its details.</p>';
  right.append(empty, wrap);
  wrap.style.marginTop = '0';

  const head = mk('div', 'ieEditHead');
  const titleRow = wrap.querySelector(':scope > .dense-toolbar');
  wrap.prepend(head);
  head.append(titleRow, byId('itemSessionHistory'), byId('itemStatusBar'), byId('dirtySummary'), bar);
  byId('itemSessionHistory').style.margin = '0';
  panes.props.prepend(byId('clientMismatch'), byId('itemValidation'));  // issues belong with the fields they concern

  // -- Create new: start options left (tabbed), draft right
  const cl = byId('cloneSourceId').parentNode, nw = byId('newName').parentNode;
  const slot = byId('slotBrowser').closest('.edit-card'), draft = byId('draftWrap');
  const h2 = [...document.querySelectorAll('h2')].find(h => h.textContent.trim() === 'Create New Item');
  const intro = h2 && h2.nextElementSibling;
  const cLeft = mk('div', 'ieCreateLeft', 'ie-col'), cRight = mk('div', 'ieCreateRight', 'ie-col');
  secs.create.append(cLeft, cRight);
  const ctabs = mk('div', 'ieCreateTabs');
  const cpanes = {};
  for (const [k, t, el, blurb] of [
    ['blank', 'Blank item', nw, 'Start an empty item of a chosen type, then fill in the fields.'],
    ['clone', 'Copy an item', cl, 'Use an existing item as the starting point. Pick which of its effects come along.'],
    ['slots', 'Free ID slots', slot, 'Browse which item IDs are free, taken, or mismatched. Observational only.'],
  ]) {
    const b = mk('button'); b.type = 'button'; b.dataset.c = k; b.textContent = t; ctabs.appendChild(b);
    const p = mk('div', null, 'ie-cpane'); p.dataset.c = k;
    p.innerHTML = `<div class="muted" style="font-size:12px">${blurb}</div>`;
    el.style.flexWrap = 'wrap'; p.appendChild(el); cpanes[k] = p;
  }
  cLeft.append(ctabs, ...Object.values(cpanes));
  if (intro) { intro.style.fontSize = '11px'; cLeft.append(intro); }
  cLeft.append(byId('createStatus'), byId('createPreview'));
  if (h2) h2.style.display = 'none';
  const pickC = k => { store.set('ieCTab', k); ctabs.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.c === k)); Object.entries(cpanes).forEach(([n, p]) => p.classList.toggle('on', n === k)); };
  ctabs.addEventListener('click', e => { const b = e.target.closest('button'); if (b) pickC(b.dataset.c); });
  pickC(cpanes[store.get('ieCTab', 'blank')] ? store.get('ieCTab', 'blank') : 'blank');
  const dEmpty = mk('div', 'ieDraftEmpty', 'ie-empty');
  dEmpty.innerHTML = '<h3>No draft yet</h3><p>Choose a starting point on the left. Nothing is saved until you press Save on the draft.</p>';
  const dHead = mk('div', 'ieDraftHead');
  dHead.append(draft.firstElementChild);
  draft.prepend(dHead);
  draft.style.marginTop = '0';
  cRight.append(dEmpty, draft);

  // -- Batch edit
  secs.batch.append(byId('itemBatchEditor'));
  byId('itemBatchEditor').open = true;

  // empty-state toggles follow the old show/hide of the editor/draft blocks
  const sync = () => { empty.style.display = wrap.style.display === 'none' ? '' : 'none'; dEmpty.style.display = draft.style.display === 'none' ? '' : 'none'; };
  new MutationObserver(sync).observe(wrap, {attributes: true, attributeFilter: ['style']});
  new MutationObserver(sync).observe(draft, {attributes: true, attributeFilter: ['style']});
  sync();

  const sizeSections = () => Object.values(secs).forEach(s => {
    if (!s.classList.contains('on')) return;
    const top = s.getBoundingClientRect().top + scrollY;
    s.style.height = Math.max(420, innerHeight - (top - scrollY) - 12) + 'px';
  });
  window.showSection = key => {
    store.set('ieSection', key);
    nav.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.sec === key));
    Object.entries(secs).forEach(([k, s]) => s.classList.toggle('on', k === key));
    sizeSections();
  };
  nav.addEventListener('click', e => { const b = e.target.closest('button'); if (b) showSection(b.dataset.sec); });
  addEventListener('resize', sizeSections);
  showSection(secs[store.get('ieSection', 'find')] ? store.get('ieSection', 'find') : 'find');
  setTimeout(sizeSections, 300);

  // ---------- Effects tab: current effects on the left, add / copy tools pinned on the right ----------
  const css3 = document.createElement('style');
  css3.textContent = `
    .ie-pane[data-pane=effects]{container-type:inline-size}
    .ie-pane[data-pane=effects].on{display:block;overflow:hidden}
    #ieFxWrap{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:12px;height:100%}
    @container (max-width:640px){#ieFxWrap{grid-template-columns:1fr;grid-template-rows:auto minmax(0,1fr);height:100%}#ieFxSide{order:-1;overflow:visible}#ieFxSide>.ie-side-card:first-child{display:grid;grid-template-columns:1fr 1fr 110px;gap:4px 8px;align-items:end}#ieFxSide>.ie-side-card:first-child>h4{display:none}#ieFxSide>.ie-side-card:first-child>.ie-seg,#ieFxSide>.ie-side-card:first-child>#ieFxMsg{grid-column:1/-1;margin-bottom:2px}#ieFxSide>.ie-side-card:first-child>label{margin-bottom:0}#ieFxSide>.ie-side-card:first-child>label:first-of-type{grid-column:1/3}#ieFxSide>.ie-side-card:first-child>#ieAddBtn{grid-column:3}}
    .ie-fx .nm,.ie-fx .sub{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    #ieFx{overflow:auto;min-height:0;padding-right:4px}
    #ieFxSide{overflow:auto;min-height:0;display:flex;flex-direction:column;gap:10px}
    .ie-fxgroup{margin-bottom:12px}
    .ie-fxgroup h4{margin:0 0 6px;font-size:12px;text-transform:uppercase;letter-spacing:.04em;opacity:.75;display:flex;gap:6px;align-items:baseline}
    .ie-fxgroup h4 small{text-transform:none;letter-spacing:0;opacity:.8;font-weight:400}
    .ie-fx{display:flex;align-items:center;gap:10px;padding:6px 10px;border:1px solid var(--border,#555);border-radius:6px;margin-bottom:4px}
    .ie-fx.new{border-color:#5fb760}.ie-fx.chg{border-color:#f5c542}
    .ie-fx .tx{flex:1;min-width:0}.ie-fx .nm{font-weight:600}.ie-fx .sub{font-size:11px;opacity:.7}
    .ie-fx input[type=number]{width:72px}
    .ie-fx .tag{font-size:10px;padding:0 6px;border-radius:8px;border:1px solid currentColor;color:#f5c542}
    .ie-fx.new .tag{color:#5fb760}
    .ie-fx button.rm{padding:1px 8px}
    .ie-none{opacity:.55;font-size:12px;padding:4px 2px}
    .ie-side-card{border:1px solid var(--border,#555);border-radius:8px;padding:10px}
    .ie-side-card h4{margin:0 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:.04em;opacity:.75}
    .ie-seg{display:flex;gap:4px;margin-bottom:8px}
    .ie-seg button{flex:1;padding:4px 6px;border:1px solid var(--border,#555);border-radius:12px;background:transparent;color:inherit;cursor:pointer;font-size:12px}
    .ie-seg button.on{background:rgba(106,169,255,.22);border-color:#6aa9ff}
    .ie-side-card label{display:flex;flex-direction:column;gap:2px;font-size:11.5px;margin-bottom:6px;opacity:.95}
    .ie-side-card input{width:100%}
    #ieFxMsg{font-size:11.5px;min-height:16px;margin-top:4px;color:#f5c542}
    #ieFxSide details summary{cursor:pointer;font-size:12px;opacity:.85}
    #ieFxSide #effectStagingTools{border:0;padding:6px 0 0;margin:0!important}
    #ieFxSide #effectStagingTools>h3{display:none}
    #ieFxSide #weaponEffectsPresetCard{border:0;padding:0;margin:0}
    #ieFxSide #weaponEffectsPresetCard>h3{font-size:12px;margin:0 0 6px}
    #ieFxSide #weaponEffectsPresetCard label{display:flex;flex-direction:column;gap:2px;font-size:11.5px}
    #ieFxSide #weaponEffectsPresetCard input,#ieFxSide #weaponEffectsPresetCard select{max-width:100%}`;
  document.head.appendChild(css3);

  const fx = mk('div', 'ieFx'), side = mk('div', 'ieFxSide');
  const fxList = byId('editorLists');
  fxList.style.display = 'block';
  fx.append(fxList);
  side.innerHTML = `<div class="ie-side-card"><h4>Add an effect</h4>
      <div class="ie-seg"><button type="button" data-k="mods" class="on" title="Always-on stat bonus">Bonus</button><button type="button" data-k="pet_mods" title="Bonus given to your pet">Pet bonus</button><button type="button" data-k="latents" title="Bonus only while a condition is met">Conditional</button></div>
      <label>Effect<input type="text" id="ieAddMod" list="dl_mods" placeholder="type to search, e.g. Attack"></label>
      <label>Amount<input type="number" id="ieAddVal" value="1"></label>
      <label data-for="pet_mods" style="display:none">Pet type<input type="text" id="ieAddPet" list="dl_pettypes" placeholder="type to search"></label>
      <label data-for="latents" style="display:none">Active when<input type="text" id="ieAddLat" list="dl_latents" placeholder="type to search, e.g. HP below X%"></label>
      <label data-for="latents" style="display:none">Condition value<input type="number" id="ieAddLatP" value="0"></label>
      <button type="button" id="ieAddBtn" class="primary">Add to item</button><div id="ieFxMsg"></div></div>
    <div class="ie-side-card" id="ieFxMore"><h4>More ways to add effects</h4>
      <div class="ie-seg" id="ieFxMoreTabs"><button type="button" data-t="proc" title="Extra effect that can trigger when a weapon hits (fire damage, drain, ...)">Weapon proc</button><button type="button" data-t="copy" title="Copy effects from another item, or paste a list of rows">Copy / paste</button></div>
      <div data-tp="proc"><div id="ieFxProcNote" class="ie-none" style="display:none">Weapon procs only apply to weapons. This item has no weapon record.</div><div id="ieFxProc"></div></div>
      <div data-tp="copy" style="display:none"><div id="ieFxBulk"></div></div></div>`;
  const fxWrap = mk('div', 'ieFxWrap');
  fxWrap.append(fx, side);
  panes.effects.append(fxWrap);
  side.querySelector('#ieFxBulk').append(byId('effectStagingTools'));
  { const early = byId('weaponEffectsPresetCard'); if (early) byId('ieFxProc').append(early); }  // card may have been built before this panel existed
  const moreTab = t => {
    store.set('ieFxMore', t);
    side.querySelectorAll('#ieFxMoreTabs button').forEach(b => b.classList.toggle('on', b.dataset.t === t));
    side.querySelectorAll('#ieFxMore [data-tp]').forEach(d => d.style.display = d.dataset.tp === t ? '' : 'none');
  };
  side.querySelector('#ieFxMoreTabs').addEventListener('click', e => { const b = e.target.closest('button'); if (b) moreTab(b.dataset.t); });
  const syncProc = () => {
    const isWeapon = !!(typeof loadedServerState !== 'undefined' && loadedServerState && loadedServerState.item_weapon);
    byId('ieFxProcNote').style.display = isWeapon ? 'none' : '';
    const card = byId('weaponEffectsPresetCard'); if (card) card.style.display = isWeapon ? '' : 'none';
    moreTab(isWeapon ? 'proc' : 'copy');
  };
  moreTab('copy'); syncProc();
  const loadItemForFx = loadItem;
  loadItem = async function () { const r = await loadItemForFx.apply(this, arguments); syncProc(); return r; };

  let addKind = 'mods';
  side.querySelector('.ie-seg').addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    addKind = b.dataset.k;
    side.querySelectorAll('.ie-seg button').forEach(x => x.classList.toggle('on', x === b));
    side.querySelectorAll('[data-for]').forEach(l => l.style.display = l.dataset.for === addKind ? '' : 'none');
    byId('ieFxMsg').textContent = '';
  });
  const fxMsg = t => { byId('ieFxMsg').textContent = t; };
  byId('ieAddBtn').onclick = () => {
    const modId = pickerValue('ieAddMod', MOD_NAMES);
    if (modId === null) return fxMsg('Pick an effect from the list first.');
    const value = Number(byId('ieAddVal').value) || 0;
    let row;
    if (addKind === 'mods') {
      if (stagedEffects.mods.some(x => Number(x.modId) === modId)) return fxMsg('That effect is already on the item. Edit its amount instead.');
      row = {modId, value};
    } else if (addKind === 'pet_mods') {
      const petType = pickerValue('ieAddPet', PET_TYPE_NAMES);
      if (petType === null) return fxMsg('Pick a pet type.');
      if (stagedEffects.pet_mods.some(x => Number(x.modId) === modId && Number(x.petType) === petType)) return fxMsg('That pet effect is already on the item.');
      row = {modId, petType, value};
    } else {
      const latentId = pickerValue('ieAddLat', LATENT_NAMES);
      if (latentId === null) return fxMsg('Pick the condition when this applies.');
      row = {modId, value, latentId, latentParam: Number(byId('ieAddLatP').value) || 0};
      const key = effectSortKey('latents', row);
      if (stagedEffects.latents.some(x => effectSortKey('latents', x) === key)) return fxMsg('That conditional effect is already on the item.');
    }
    stagedEffects[addKind].push(row);
    fxMsg('');
    byId('ieAddMod').value = '';
    rerenderEffects();
  };

  const isScriptFlag = id => Number(id) === 431 && /^ADDITIONAL_EFFECT/.test(MOD_NAMES[431] || '');
  const mName = id => isScriptFlag(id) ? 'Runs an item script (additional effect)' : (MOD_NAMES[id] || `Effect #${id}`);
  let procScript = null, procScriptKey = '';
  const HOOK_TEXT = { onAdditionalEffect: 'extra effect when it hits (proc)', onItemUse: 'what happens when the item is used', onItemCheck: 'extra rules for using/equipping it', onEffectGain: 'applies bonuses while the effect it grants is active (food, medicine, buffs)', onEffectLose: 'removes those bonuses when the effect ends', onEffectTick: 'repeating effect while active' };
  const scriptBanner = () => {
    const flag = (stagedEffects.mods || []).some(r => isScriptFlag(r.modId) && Number(r.value) > 0);
    const nm = (typeof loadedServerState !== 'undefined' && loadedServerState && loadedServerState.item_basic && loadedServerState.item_basic.name) || '';
    const c = procScript && procScriptKey === nm && procScript.candidates && procScript.candidates[0];
    if (!flag && !(c && c.exists)) return '';
    let state = '<span class="muted">checking server for the script...</span>', hooks = '';
    if (c) {
      if (c.exists) {
        state = '<b>Script found.</b>';
        hooks = (c.hooks || []).map(h => `<li><code>${esc(h)}</code> - ${esc(HOOK_TEXT[h] || 'custom hook')}</li>`).join('');
        if (flag && !c.has_additional_effect) state += ' <b>But it has no onAdditionalEffect, so the proc switch does nothing.</b>';
      } else state = '<b>No script found</b> - the proc switch does nothing until this file is created.';
    }
    const src = c && c.exists ? `<details><summary>View script source${c.truncated ? ' (first 6000 characters)' : ''}</summary><pre class="mono" style="max-height:260px;overflow:auto;font-size:11px;white-space:pre-wrap">${esc(c.source || '')}</pre></details>` : '';
    return `<div class="ie-fxgroup"><h4>Item script <small>effects written in Lua, not stored as numbers on the item</small></h4>
      <div class="ie-fx"><div class="tx"><div class="nm">${flag ? 'Effect 431 switches on a scripted proc.' : 'This item has a server script.'}</div>
      <div class="sub">File: <code>${esc(c ? c.path : 'scripts/.../items/' + (nm || '&lt;item&gt;') + '.lua')}</code>. Chance, damage, duration and food/use bonuses live there, so the fields here cannot edit them. ${state}</div>${hooks ? `<ul class="sub" style="margin:4px 0 0 16px">${hooks}</ul>` : ''}${src}</div></div></div>`;
  };
  const loadProcScript = () => {
    const nm = (typeof loadedServerState !== 'undefined' && loadedServerState && loadedServerState.item_basic && loadedServerState.item_basic.name) || '';
    if (!nm || procScriptKey === nm) return;
    procScript = null;
    procScriptKey = nm;
    fetch('/itemedit/proc-script.json?item_id=' + (currentItemId || 0) + '&name=' + encodeURIComponent(nm)).then(r => r.json()).then(j => { procScript = j; rerenderEffects(); }).catch(() => {});
  };
  const sv = n => (n > 0 ? '+' : '') + n;
  const status = (kind, row) => {
    const k = effectSortKey(kind, row), was = (loadedEffects[kind] || []).find(x => effectSortKey(kind, x) === k);
    if (!was) return 'new';
    return Number(was.value) !== Number(row.value) ? 'chg' : '';
  };
  const fxRow = (kind, row, title, sub) => {
    const st = status(kind, row);
    return `<div class="ie-fx ${st}" data-kind="${kind}"><div class="tx"><div class="nm" title="${esc(title)}">${esc(title)}</div>${sub ? `<div class="sub" title="${esc(sub)}">${esc(sub)}</div>` : ''}</div>
      ${st ? `<span class="tag">${st === 'new' ? 'new' : 'edited'}</span>` : ''}
      <input type="number" value="${row.value}" title="Amount"><button type="button" class="rm" title="Remove this effect">✕</button></div>`;
  };
  rerenderEffects = function () {
    const sections = [
      ['mods', 'Bonuses', 'always active while worn', stagedEffects.mods, r => fxRow('mods', r, mName(r.modId), modMetaLine(r.modId))],
      ['pet_mods', 'Pet bonuses', 'apply to your pet', stagedEffects.pet_mods, r => fxRow('pet_mods', r, mName(r.modId), PET_TYPE_NAMES[r.petType] || 'pet ' + r.petType)],
      ['latents', 'Conditional bonuses', 'only while the condition is met', stagedEffects.latents, r => fxRow('latents', r, mName(r.modId), 'When: ' + (LATENT_NAMES[r.latentId] || 'condition ' + r.latentId) + (r.latentParam ? ' (' + r.latentParam + ')' : ''))],
    ];
    fxList.innerHTML = '';
    loadProcScript();
    { const w = (typeof loadedServerState !== 'undefined' && loadedServerState && loadedServerState.item_weapon) || null, h = w ? Number(w.hit) : 0;
      if (h > 1) {
        const dist = { 2: '1 hit 55%, 2 hits 45%', 3: '1 hit 30%, 2 hits 50%, 3 hits 20%', 4: '1 hit 20%, 2 hits 30%, 3 hits 30%, 4 hits 20%' }[h] || ('up to ' + h + ' hits per attack');
        fxList.insertAdjacentHTML('beforeend', `<div class="ie-fxgroup"><h4>Multi-hit <small>built into the weapon, not an effect row</small></h4><div class="ie-fx"><div class="tx"><div class="nm">${h === 2 ? 'Occasionally attacks twice' : 'Occasionally attacks up to ' + h + ' times'}</div><div class="sub">Weapon stat Max hits = ${h} (${esc(dist)}). Change it under Weapon combat → Max hits per attack.</div></div></div></div>`);
      } }
    { const sb = scriptBanner(); if (sb) fxList.insertAdjacentHTML('beforeend', sb); }
    for (const [kind, title, hint, rows, render] of sections) {
      const g = mk('div', null, 'ie-fxgroup');
      g.innerHTML = `<h4>${title} (${rows.length}) <small>${hint}</small></h4>` + (rows.length ? rows.map(render).join('') : '<div class="ie-none">None.</div>');
      g.querySelectorAll('.ie-fx').forEach((el, i) => {
        const row = rows[i];
        el.querySelector('input').oninput = e => { row.value = Number(e.target.value) || 0; updateDirtySummary(); renderDecodedSummary(); };
        el.querySelector('input').onchange = () => rerenderEffects();
        el.querySelector('.rm').onclick = () => { stagedEffects[kind] = stagedEffects[kind].filter(x => x !== row); rerenderEffects(); };
      });
      fxList.appendChild(g);
    }
    updateDirtySummary();
    renderDecodedSummary();
  };
  // loadItem() draws the three lists through these; route them to the single combined view
  renderMods = () => rerenderEffects();
  renderPetMods = renderLatents = () => {};
  if (currentItemId) rerenderEffects();

  // the Effects tab fills the visible area under the pinned header so nothing needs page scrolling
  const fitEffects = () => {
    const h = right.clientHeight - head.offsetHeight - 14;
    panes.effects.style.height = Math.max(260, h) + 'px';
  };
  new ResizeObserver(fitEffects).observe(head);
  new ResizeObserver(fitEffects).observe(right);
  bar.addEventListener('click', () => setTimeout(fitEffects, 0));

  // ---------- Client record + History tabs: one sub-section at a time inside a fixed-height pane ----------
  const css4 = document.createElement('style');
  css4.textContent = `
    .ie-pane[data-pane=client].on,.ie-pane[data-pane=history].on{display:flex;flex-direction:column;overflow:hidden}
    .ie-sub{display:flex;gap:6px;flex-wrap:wrap;margin:2px 0 8px;flex:none}
    .ie-sub button{padding:4px 12px;border:1px solid var(--border,#555);border-radius:14px;background:transparent;color:inherit;cursor:pointer;font-size:12px}
    .ie-sub button.on{background:rgba(106,169,255,.22);border-color:#6aa9ff}
    .ie-subbody{flex:1;min-height:0;overflow:auto;padding-right:4px}
    .ie-subpane{display:none}.ie-subpane.on{display:block}
    .ie-pane[data-pane=client] #datInfoCard,.ie-pane[data-pane=history]>.edit-card{margin-top:0!important}
    .ie-pane[data-pane=client] #datInfoCard{display:flex;flex-direction:column;min-height:0;flex:1;border:0;padding:0}
    .ie-pane[data-pane=client] #datInfoCard>h3{display:none}
    #clientRecordGrid *,#datInfoCard .mono{overflow-wrap:anywhere;word-break:break-all;min-width:0}
    #clientRecordGrid{max-width:100%}
    .ie-pane[data-pane=history]>.edit-card>h3 .hint{display:block;font-weight:400}`;
  document.head.appendChild(css4);

  // groups = [[label, [nodes]]]; builds a chip bar + panes inside `host` and moves the nodes in
  const subTabs = (host, key, groups) => {
    const sb = document.createElement('div'); sb.className = 'ie-sub';
    const body = document.createElement('div'); body.className = 'ie-subbody';
    const subs = groups.map(([label, nodes], i) => {
      const b = document.createElement('button'); b.type = 'button'; b.textContent = label; sb.appendChild(b);
      const p = document.createElement('div'); p.className = 'ie-subpane'; body.appendChild(p);
      nodes.forEach(n => n && p.appendChild(n));
      return {b, p, i};
    });
    const show = i => {
      store.set('ieSub_' + key, String(i));
      subs.forEach(s => { s.b.classList.toggle('on', s.i === i); s.p.classList.toggle('on', s.i === i); });
    };
    sb.addEventListener('click', e => { const b = e.target.closest('button'); const s = subs.find(x => x.b === b); if (s) show(s.i); });
    host.append(sb, body);
    const saved = parseInt(store.get('ieSub_' + key, '0'), 10);
    show(subs[saved] ? saved : 0);
    return {show, subs};
  };

  const dat = byId('datInfoCard');
  const dk = [...dat.children].filter(c => c.tagName !== 'H3');
  if (dk.length === 15) {
    subTabs(dat, 'client', [
      ['Overview', dk.slice(0, 6)],
      ['DAT backups', [...dk.slice(8, 12), dk[12]]],
      ['Live ↔ Xi-Pivot', [dk[6], dk[7], dk[13], dk[14]]],
    ]);
  }
  const hk = ['selectedItemHistory', 'itemBackupsCard', 'itemUsagePanel', 'itemDeleteCard'].map(byId);
  if (hk.every(Boolean)) {
    const hostH = document.createElement('div');
    hostH.style.cssText = 'display:flex;flex-direction:column;flex:1;min-height:0';
    panes.history.appendChild(hostH);
    subTabs(hostH, 'history', [
      ['Changes', [hk[0]]], ['Backups', [hk[1]]], ['Where it\'s used', [hk[2]]], ['Delete', [hk[3]]],
    ]);
  }

  const fitPanes = () => {
    const h = Math.max(260, right.clientHeight - head.offsetHeight - 14) + 'px';
    panes.client.style.height = h; panes.history.style.height = h;
  };
  new ResizeObserver(fitPanes).observe(head);
  new ResizeObserver(fitPanes).observe(right);
  bar.addEventListener('click', () => setTimeout(fitPanes, 0));

  // opening a draft (new / clone) jumps to the Create section
  const origStartDraft = startDraft;
  startDraft = function () { const r = origStartDraft.apply(this, arguments); showSection('create'); return r; };
  // the batch / item pickers used elsewhere on the page need the right section visible
  const origLoadItem = loadItem;
  loadItem = function () { showSection('find'); return origLoadItem.apply(this, arguments); };
})();
