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
})();
