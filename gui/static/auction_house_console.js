(() => {
  const root = document.getElementById('ahConsole');
  if (!root) return;
  const $ = id => document.getElementById(id);
  const fmt = n => n == null ? '—' : new Intl.NumberFormat().format(Math.round(n));
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const days = d => d == null ? '—' : (d < 1 ? '<1d' : d.toFixed(d < 10 ? 1 : 0) + 'd');
  const nm = s => (s || '').replace(/_/g, ' ');
  const state = {agg: null, env: null, ready: false, selItem: null, selSeller: null, rows: [], restock: [], rsSellers: [],
                 rsPlan: null, bundle: [], recips: [], tpls: []};

  async function req(url, body) {
    const r = await fetch(url, body === undefined ? {headers: {Accept: 'application/json'}} :
      {method: 'POST', headers: {Accept: 'application/json', 'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail || r.statusText));
    return d;
  }
  let toastT;
  function toast(msg) { const t = $('ahcToast'); t.textContent = msg; t.style.display = 'block'; clearTimeout(toastT); toastT = setTimeout(() => t.style.display = 'none', 4000); }
  function debounce(fn, ms = 250) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

  /* ---------- tabs & embedded tools ---------- */
  const TOOLS = {economy: ['Economy Intelligence', '/auction-house/economy'], listings: ['Listing Manager', '/auction-house/listing-manager'],
    seeder: ['Player listing & market history', '/auction-house/seeder'],
    activity: ['Activity', '/auction-house/activity'], 'reward-history': ['Reward history', '/auction-house/reward-history'],
    overview: ['Readiness & item history', '/auction-house/overview'], help: ['Status & help', '/auction-house/help']};
  function tab(name) {
    const tool = TOOLS[name];
    document.querySelectorAll('#ahcTabs button').forEach(b => b.classList.toggle('on', b.dataset.t === name));
    document.querySelectorAll('.ahc-pane').forEach(p => p.classList.toggle('on', p.id === 'p-' + (tool ? 'tool' : name)));
    const inMenu = tool && !document.querySelector('#ahcTabs [data-t="' + name + '"]'), m = $('ahcMenu'); m.classList.toggle('on', !!inMenu); m.open = false;
    $('ahcMenuLabel').textContent = inMenu ? tool[0] + ' ▾' : 'More tools ▾';
    if (tool) { const f = $('ahcFrame'), src = tool[1] + '?embed=1'; if (f.dataset.src !== src) { f.dataset.src = src; f.src = src; } }
    try { history.replaceState(null, '', '#' + name); } catch (e) {}
    if (name === 'buyers' && !state.buyers && window.loadBuyers) window.loadBuyers();
    if (name === 'arbitrage' && !state.arb && window.loadArb) window.loadArb();
  }
  window.addEventListener('hashchange', () => { const h = location.hash.slice(1); if (TOOLS[h] || $('p-' + h)) tab(h); });
  $('ahcTabs').addEventListener('click', e => { if (e.target.dataset.t) tab(e.target.dataset.t); });

  /* ---------- action drawer (single guarded confirm path) ---------- */
  let drawerRun = null;
  function drawer({title, html, confirm = true, label = 'Execute', run}) {
    $('dwTitle').textContent = title; $('dwBody').innerHTML = html; $('dwMsg').textContent = '';
    $('dwConf').value = ''; $('dwConfName').textContent = state.env ? '"' + state.env + '"' : ''; $('dwConf').placeholder = state.env || ''; $('dwConfWrap').style.display = confirm ? '' : 'none';
    $('dwGo').textContent = label; drawerRun = run; $('ahcDrawer').classList.add('on'); $('ahcBackdrop').classList.add('on');
    syncGo();
  }
  function syncGo() { $('dwGo').disabled = !drawerRun || ($('dwConfWrap').style.display !== 'none' && !$('dwConf').value.trim()); }
  $('dwConf').addEventListener('input', syncGo);
  $('dwClose').addEventListener('click', () => { $('ahcDrawer').classList.remove('on'); $('ahcBackdrop').classList.remove('on'); drawerRun = null; });
  $('ahcBackdrop').addEventListener('click', () => $('dwClose').click());
  $('dwGo').addEventListener('click', async () => {
    if (!drawerRun) return;
    const run = drawerRun, conf = $('dwConf').value.trim();
    $('dwGo').disabled = true; $('dwMsg').textContent = 'Working…';
    try { const out = await run(conf); drawerRun = null; $('dwMsg').textContent = ''; $('dwBody').insertAdjacentHTML('afterbegin', out || ''); $('dwGo').disabled = true; }
    catch (e) { $('dwMsg').textContent = ''; $('dwBody').insertAdjacentHTML('afterbegin', '<pre style="color:#d55">' + esc(e.message) + '</pre>'); drawerRun = run; syncGo(); }
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') $('dwClose').click(); });

  function listingTable(rows, withSeller = true, withItem = true) {
    return '<table><thead><tr><th>#</th>' + (withItem ? '<th>Item</th>' : '') + (withSeller ? '<th>Seller</th>' : '') +
      '<th class="n">Qty</th><th class="n">Price</th><th class="n">Age</th></tr></thead><tbody>' + rows.map(r =>
      '<tr><td>' + r.auction_id + '</td>' + (withItem ? '<td>' + esc(nm(r.item_name)) + '</td>' : '') +
      (withSeller ? '<td>' + esc(r.seller_name || '#' + r.seller_id) + '</td>' : '') +
      '<td class="n">' + r.quantity + '</td><td class="n">' + fmt(r.asking_price) + 'g</td><td class="n">' + days(ageOf(r)) + '</td></tr>').join('') + '</tbody></table>';
  }
  const ageOf = r => r.listed_at ? (Date.now() / 1000 - r.listed_at) / 86400 : null;

  // Buy a listing as a specific character (moves the item into their Inventory, debits their gil).
  function buyAs(r) {
    if (!r) return;
    let buyer = null;
    drawer({
      title: 'Buy as a player — #' + r.auction_id + ' ' + nm(r.item_name),
      label: 'Purchase for ' + fmt(r.asking_price) + 'g',
      html: '<p style="padding:6px 8px;margin:0"><b>' + esc(nm(r.item_name)) + '</b> ×' + r.quantity + ' from ' + esc(r.seller_name || '#' + r.seller_id) + ' at <b>' + fmt(r.asking_price) + 'g</b>. The buyer must be offline with enough gil and a free Inventory slot.</p>' +
        '<div style="padding:6px 8px"><input id="pbQ" placeholder="Search buyer character…" style="width:100%"><div id="pbSug" class="ahc-sug" hidden></div><div id="pbSel" class="mut" style="margin-top:4px">No character chosen.</div><button class="b" id="pbPrev" disabled style="margin-top:6px">Preview</button><div id="pbOut"></div></div>',
      run: async conf => {
        if (!buyer) throw new Error('Choose a buyer character first.');
        const d = await req('/auction-house/test-write/player-purchase.json', {auction_id: r.auction_id, expected_price: r.asking_price, buyer_id: buyer.char_id, confirmation: conf});
        loadAll(true);
        return '<pre>PURCHASED for ' + esc(buyer.char_name) + '\n' + esc(JSON.stringify(d, null, 1).slice(0, 800)) + '</pre>';
      }
    });
    const q = $('pbQ'), sug = $('pbSug');
    const go = debounce(async () => {
      const s = q.value.trim(); if (!s) { sug.hidden = true; return; }
      try {
        const rows = (await req(CHAR_URL + encodeURIComponent(s))).rows || [];
        sug.innerHTML = rows.slice(0, 20).map((c, i) => '<div data-i="' + i + '">' + esc(c.char_name) + ' <small>#' + c.char_id + '</small></div>').join('') || '<div class="mut">no matches</div>'; sug.hidden = false;
        sug.onclick = e => { const dv = e.target.closest('[data-i]'); if (!dv) return; buyer = rows[+dv.dataset.i]; sug.hidden = true; q.value = buyer.char_name;
          $('pbSel').textContent = 'Buyer: ' + buyer.char_name + ' #' + buyer.char_id; $('pbPrev').disabled = false; $('pbOut').innerHTML = ''; };
      } catch (e) { sug.innerHTML = '<div>' + esc(e.message) + '</div>'; sug.hidden = false; }
    });
    $('dwBody').oninput = e => { if (e.target.id === 'pbQ') go(); };
    $('pbPrev').onclick = async () => {
      try { const d = await req('/auction-house/admin/purchase/preview.json', {auction_id: r.auction_id, buyer_id: buyer.char_id, mode: 'normal_purchase'});
        $('pbOut').innerHTML = '<pre>' + esc(JSON.stringify(d, null, 1).slice(0, 1500)) + '</pre>'; } catch (e) { $('pbOut').innerHTML = '<pre style="color:#d55">' + esc(e.message) + '</pre>'; }
    };
  }

  function bulk(action, rows, scope) {
    if (!rows.length) return toast('Nothing to ' + (action === 'admin_buy' ? 'buy' : 'return'));
    const buy = action === 'admin_buy', total = rows.reduce((s, r) => s + r.asking_price, 0);
    drawer({
      title: (buy ? 'Admin Buy ' : 'Return ') + rows.length + ' listing(s) — ' + scope,
      html: '<p style="padding:6px 8px;margin:0">' + (buy ? 'Closes each listing as an administrative sale; total <b>' + fmt(total) + 'g</b>.'
        : 'Returns each item to its seller (Inventory when safe, otherwise delivery box). Listing fees are not refunded.') +
        ' Each listing commits independently; partial success is possible.</p>' + listingTable(rows),
      label: (buy ? 'Buy ' : 'Return ') + rows.length,
      run: async conf => {
        let committed = 0, failed = 0; const errs = [];
        for (let i = 0; i < rows.length; i += 100) {
          const chunk = rows.slice(i, i + 100);
          try {
            const d = await req('/auction-house/test-write/batch-listings.json', {action, confirmation: conf,
              targets: chunk.map(r => ({auction_id: r.auction_id, expected_price: r.asking_price}))});
            committed += d.committed; failed += d.failed;
            (d.results || []).filter(x => x.status === 'failed').forEach(x => errs.push('#' + x.auction_id + ': ' + x.error));
          } catch (e) { if (!committed && !failed) throw e; failed += chunk.length; errs.push(e.message); break; }
        }
        loadAll(true);
        return '<pre>' + (failed ? 'PARTIAL/FAILED' : 'COMPLETED') + ': ' + committed + ' committed, ' + failed + ' failed\n' + esc(errs.join('\n')) + '</pre>';
      }
    });
  }

  /* ---------- data ---------- */
  async function loadAll(quiet) {
    $('ahcFresh').textContent = 'loading…';
    try {
      state.agg = await req('/auction-house/console/aggregate.json');
      $('ahcFresh').textContent = 'updated ' + new Date().toLocaleTimeString();
    } catch (e) { $('ahcFresh').textContent = 'failed: ' + e.message; return; }
    state.catalog = null; if ($('itStatus').value !== 'active') await ensureCatalog();
    drawItems(); drawSellers();
    if (state.selItem) showItem(state.selItem, true);
    if (state.selSeller) showSeller(state.selSeller, true);
  }
  $('ahcRefresh').addEventListener('click', () => loadAll());

  async function loadEnv() {
    try {
      const d = await req('/auction-house/capability-status.json');
      state.env = (d.environment || {}).name || null; state.ready = !!d.scoped_test_write_ready;
      const c = $('ahcEnv'); c.textContent = (state.env || 'no environment') + ' · ' + (state.ready ? 'test writes ready' : 'read-only');
      c.classList.add(state.ready ? 'ok' : 'warn'); c.title = (d.blockers || []).join('\n');
      if (!state.ready) { c.style.cursor = 'pointer'; c.title += ' Click to open Settings > Auction House and enable test writes.'; c.onclick = () => window.open('/settings#auction-house-settings', '_top'); }
    } catch (e) { $('ahcEnv').textContent = 'status unavailable'; }
  }

  /* ---------- items tab ---------- */
  function sorted(rows, key) {
    const k = key === 'name' ? null : key, s = [...rows];
    if (!k) return s.sort((a, b) => (a.item_name || a.seller_name || '').toLowerCase().localeCompare((b.item_name || b.seller_name || '').toLowerCase()));
    return s.sort((a, b) => key === 'min_price' ? a[k] - b[k] : (b[k] ?? -1) - (a[k] ?? -1));
  }
  const SEP = ' → ';
  const inCat = (path, cat) => !cat || path === cat || (path || '').startsWith(cat + SEP);
  function drawTree() {
    const counts = new Map();
    itemPool().forEach(i => { const parts = (i.category_path || 'Uncategorised').split(SEP); for (let n = 1; n <= parts.length; n++) { const k = parts.slice(0, n).join(SEP); counts.set(k, (counts.get(k) || 0) + 1); } });
    const sel = state.cat || '';
    const parentOf = k => k.includes(SEP) ? k.slice(0, k.lastIndexOf(SEP)) : '';
    // top level always shown; a deeper node shows once its parent is the selection or one of its ancestors
    const rows = [...counts.keys()].sort((a, b) => a.localeCompare(b)).filter(k => { const p = parentOf(k); return !p || sel === p || sel.startsWith(p + SEP); });
    $('itTree').innerHTML = '<div class="ct' + (!sel ? ' sel' : '') + '" data-c="">All items <small>(' + fmt(itemPool().length) + ')</small></div>' + rows.map(k => {
      const d = k.split(SEP), open = sel === k || sel.startsWith(k + SEP);
      return '<div class="ct' + (sel === k ? ' sel' : '') + '" data-c="' + esc(k) + '" style="padding-left:' + (8 + (d.length - 1) * 14) + 'px">' + (open ? '▾ ' : '▸ ') + esc(d[d.length - 1]) + ' <small>(' + counts.get(k) + ')</small></div>';
    }).join('');
  }
  $('itTree').addEventListener('click', e => { const c = e.target.closest('[data-c]'); if (c) { state.cat = c.dataset.c; drawItems(); } });
  const IT_COLS = [['Item', 'name', ''], ['Listed', 'listings', 'n'], ['Low', 'min_price', 'n'], ['Median', 'median_price', 'n'], ['High', 'max_price', 'n'], ['Sellers', 'seller_count', 'n'], ['Oldest', 'oldest_days', 'n']];
  const IT_EXTRA = [['Sold', 'sales', 'n'], ['Avg sale', 'avg_sale', 'n']];
  state.itSort = 'name'; state.itDir = 1; state.cat = '';
  function drawItems() {
    drawTree();
    const q = $('itQ').value.trim().toLowerCase(), k = state.itSort, dir = state.itDir;
    const rows = itemPool().filter(i => inCat(i.category_path, state.cat) && (!q || nm(i.item_name).toLowerCase().includes(q) || String(i.item_id) === q));
    rows.sort((a, b) => (k === 'name' ? nm(a.item_name).toLowerCase().localeCompare(nm(b.item_name).toLowerCase()) : ((a[k] ?? -1) - (b[k] ?? -1))) * dir);
    $('itCatLbl').textContent = (state.cat || 'All items') + ' · ' + fmt(rows.length);
    $('itList').innerHTML = rows.length ? '<table><thead><tr>' + IT_COLS.concat($('itStatus').value === 'active' ? [] : IT_EXTRA).map(c => '<th class="' + c[2] + ' srt" data-s="' + c[1] + '">' + c[0] + (k === c[1] ? (dir > 0 ? ' ▲' : ' ▼') : '') + '</th>').join('') + '</tr></thead><tbody>' +
      rows.slice(0, 800).map(i => '<tr class="clk' + (i.item_id === state.selItem ? ' sel' : '') + '" data-id="' + i.item_id + '"><td><b>' + esc(nm(i.item_name)) + '</b> <small>#' + i.item_id + '</small></td><td class="n">' + i.listings + '</td><td class="n">' + fmt(i.min_price) + '</td><td class="n">' + fmt(i.median_price) + '</td><td class="n">' + fmt(i.max_price) + '</td><td class="n">' + i.seller_count + '</td><td class="n">' + days(i.oldest_days) + '</td>' + ($('itStatus').value === 'active' ? '' : '<td class="n">' + (i.sales ?? 0) + '</td><td class="n">' + fmt(i.avg_sale) + '</td>') + '</tr>').join('') + '</tbody></table>' : '<div class="ahc-empty">No items in this view.</div>';
  }
  $('itList').addEventListener('click', e => {
    const th = e.target.closest('th[data-s]');
    if (th) { if (state.itSort === th.dataset.s) state.itDir *= -1; else { state.itSort = th.dataset.s; state.itDir = th.dataset.s === 'name' || th.dataset.s === 'min_price' ? 1 : -1; } drawItems(); return; }
    const tr = e.target.closest('tr[data-id]'); if (tr) showItem(+tr.dataset.id);
  });
  $('itQ').addEventListener('input', debounce(drawItems, 120));

  const median = a => { const v = a.filter(x => x > 0).sort((x, y) => x - y); if (!v.length) return null; const m = v.length >> 1; return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2; };
  const isStack = r => r.stack != null ? !!r.stack : r.quantity > 1;
  function markupChip(pct) {
    if (pct == null) return '<span class="mut">—</span>';
    const cls = pct > 50 ? 'hi' : pct > 15 ? 'mid' : pct < -15 ? 'lo' : 'ok';
    return '<span class="mk ' + cls + '" title="Price vs the median of recent sales">' + (pct > 0 ? '+' : '') + Math.round(pct) + '%</span>';
  }
  const link = (kind, id, text) => '<a href="#" class="lk" data-' + kind + '="' + id + '">' + esc(text) + '</a>';
  function goBack() { const b = state.back; state.back = null; if (!b) return; tab(b.tab); b.tab === 'items' ? showItem(b.id) : showSeller(b.id); }
  const backBtn = () => state.back ? '<button class="b" data-x="back">← Back to ' + esc(state.back.label) + '</button> ' : '';

  function detail(el, head, rows, opts) {
    const sel = new Set(), f = {q: '', min: '', max: '', type: '', mk: ''};
    const ref = r => { if (opts.refs) { const x = opts.refs[r.item_id]; if (!x) return null; const k = isStack(r) ? 'stack' : 'single'; return (x[k + '_n'] >= 3 ? x[k] : x.all) || null; } const sl = opts.sales || [], same = sl.filter(x => x.stack === isStack(r)).map(x => x.sale_price); return median(same.length >= 3 ? same : sl.map(x => x.sale_price)); };
    const mkOf = r => { const m = ref(r); return m ? (r.asking_price / m - 1) * 100 : null; };
    const sellerSalesHtml = () => {
      const sl = opts.sellerSales; if (!sl) return '';
      return '<div class="ahc-sales"><div class="ahc-sh"><b>Recent sales</b> <span class="mut">' + sl.length + ' shown</span></div>' +
        (sl.length ? '<div class="ahc-sbody"><table><thead><tr><th>Sold</th><th>Item</th><th class="n">Price</th><th class="n">Asked</th><th>Buyer</th></tr></thead><tbody>' +
        sl.map(x => '<tr><td>' + esc(new Date(x.sold_at * 1000).toISOString().replace('T', ' ').slice(0, 16)) + '</td><td>' + link('item', x.item_id, nm(x.item_name)) + (x.stack ? ' <small>(stack)</small>' : '') + '</td><td class="n">' + fmt(x.sale_price) + 'g</td><td class="n">' + fmt(x.asking_price) + 'g</td><td>' + esc(x.buyer_name || '—') + '</td></tr>').join('') +
        '</tbody></table></div>' : '<div class="ahc-empty" style="padding:8px">No sales by this seller in the window.</div>') + '</div>';
    };
    const salesHtml = () => {
      const sl = opts.sales; if (!sl) return sellerSalesHtml();
      const rm = median(sl.map(x => x.sale_price));
      return '<div class="ahc-sales"><div class="ahc-sh"><b>Recent sales</b> <span class="mut">' + sl.length + ' shown' + (rm ? ' · median ' + fmt(rm) + 'g' : '') + '</span></div>' +
        (sl.length ? '<div class="ahc-sbody"><table><thead><tr><th>Sold</th><th class="n">Price</th><th>Type</th><th>Seller</th><th>Buyer</th><th class="n">vs median</th></tr></thead><tbody>' +
        sl.map(x => '<tr><td>' + esc((x.sold_at_iso || '').replace('T', ' ').slice(0, 16)) + '</td><td class="n">' + fmt(x.sale_price) + 'g</td><td>' + (x.stack ? 'stack' : 'single') + '</td><td>' +
          (x.seller_id ? link('seller', x.seller_id, x.seller_name || '#' + x.seller_id) : '—') + '</td><td>' + esc(x.buyer_name || '—') + '</td><td class="n">' + markupChip(rm ? (x.sale_price / rm - 1) * 100 : null) + '</td></tr>').join('') +
        '</tbody></table></div>' : '<div class="ahc-empty" style="padding:8px">No completed sales recorded for this item.</div>') + '</div>';
    };
    const showMk = !!(opts.sales || opts.refs);
    el.innerHTML = '<header style="display:block">' + backBtn() + head + '</header>' + salesHtml() + '<div class="ahc-sh"><b>Active listings</b></div><div class="ahc-acts"></div>' +
      '<div class="ahc-filt"><input data-f="q" placeholder="' + (opts.item ? 'Filter by item…' : 'Filter by seller…') + '"><input data-f="min" type="number" min="0" placeholder="Min price"><input data-f="max" type="number" min="0" placeholder="Max price">' +
      '<select data-f="type"><option value="">Any type</option><option value="single">Single</option><option value="stack">Stack</option></select>' +
      (showMk ? '<select data-f="mk"><option value="">Any markup</option><option value="over">Overpriced (&gt;+15%)</option><option value="fair">Fair (±15%)</option><option value="under">Underpriced (&lt;−15%)</option></select>' : '') +
      '<button class="b" data-x="clr">Clear</button></div><div class="ahc-scroll ahc-listing"></div>';
    const acts = el.querySelector('.ahc-acts'), body = el.querySelector('.ahc-listing');
    const vis = () => rows.filter(r => {
      if (f.q && !((opts.item ? nm(r.item_name) : (r.seller_name || '#' + r.seller_id)).toLowerCase().includes(f.q))) return false;
      if (f.min !== '' && r.asking_price < +f.min) return false;
      if (f.max !== '' && r.asking_price > +f.max) return false;
      if (f.type && (f.type === 'stack') !== isStack(r)) return false;
      if (f.mk) { const m = mkOf(r); if (m == null) return false; if (f.mk === 'over' ? m <= 15 : f.mk === 'under' ? m >= -15 : Math.abs(m) > 15) return false; }
      return true;
    });
    const draw = () => {
      const v = vis(), filtered = v.length !== rows.length;
      body.innerHTML = '<table><thead><tr><th><input type="checkbox" class="all"></th><th>#</th>' + (opts.item ? '<th>Item</th>' : '') + (opts.seller ? '<th>Seller</th>' : '') +
        '<th class="n">Qty</th><th class="n">Price</th>' + (showMk ? '<th class="n" title="Asking price vs the median of recent sales">Markup</th>' : '') + '<th class="n">Age</th><th></th></tr></thead><tbody>' + v.map(r => '<tr><td><input type="checkbox" data-a="' + r.auction_id + '"' + (sel.has(r.auction_id) ? ' checked' : '') + '></td><td>' + r.auction_id + '</td>' +
        (opts.item ? '<td>' + link('item', r.item_id, nm(r.item_name)) + '</td>' : '') + (opts.seller ? '<td>' + link('seller', r.seller_id, r.seller_name || '#' + r.seller_id) + '</td>' : '') +
        '<td class="n">' + r.quantity + '</td><td class="n">' + fmt(r.asking_price) + 'g</td>' + (showMk ? '<td class="n">' + markupChip(mkOf(r)) + '</td>' : '') + '<td class="n">' + days(ageOf(r)) + '</td><td><button class="b" data-buy="' + r.auction_id + '">Buy</button> <button class="b" data-ret="' + r.auction_id + '">Return</button> <button class="b" data-pbuy="' + r.auction_id + '">Buy as…</button></td></tr>').join('') + '</tbody></table>' +
        (v.length ? '' : '<div class="ahc-empty">No listings match the filters.</div>');
      const ch = [...sel].map(id => rows.find(r => r.auction_id === id)).filter(Boolean), lbl = filtered ? ' (filtered)' : '';
      acts.innerHTML = '<b>' + (filtered ? v.length + ' of ' : '') + rows.length + ' listing(s)</b><span class="mut">' + fmt(v.reduce((s, r) => s + r.asking_price, 0)) + 'g</span>' +
        '<button class="b" data-x="buy-sel"' + (ch.length ? '' : ' disabled') + '>Buy selected (' + ch.length + ')</button><button class="b" data-x="ret-sel"' + (ch.length ? '' : ' disabled') + '>Return selected</button>' +
        '<button class="b" data-x="buy-all"' + (v.length ? '' : ' disabled') + '>Buy all' + lbl + '</button><button class="b" data-x="ret-all"' + (v.length ? '' : ' disabled') + '>Return all' + lbl + '</button>' + (opts.extra || '');
    };
    el.oninput = el.onchange = e => { const k = e.target.dataset.f; if (k) { f[k] = e.target.value.trim().toLowerCase(); draw(); } };
    el.onclick = e => {
      const t = e.target, one = id => rows.filter(r => r.auction_id === id);
      const lk = t.closest && t.closest('a.lk');
      if (lk) {
        e.preventDefault();
        if (lk.dataset.seller) { state.back = {tab: 'items', id: state.selItem, label: 'item'}; tab('sellers'); showSeller(+lk.dataset.seller); }
        else { state.back = {tab: 'sellers', id: state.selSeller, label: 'seller'}; tab('items'); showItem(+lk.dataset.item); }
        return;
      }
      if (t.dataset.pbuy) buyAs(rows.find(r => r.auction_id === +t.dataset.pbuy)); else if (t.dataset.buy) bulk('admin_buy', one(+t.dataset.buy), 'single'); else if (t.dataset.ret) bulk('return_to_seller', one(+t.dataset.ret), 'single');
      else if (t.dataset.a) { t.checked ? sel.add(+t.dataset.a) : sel.delete(+t.dataset.a); draw(); }
      else if (t.classList.contains('all')) { vis().forEach(r => t.checked ? sel.add(r.auction_id) : sel.delete(r.auction_id)); draw(); }
      else if (t.dataset.x) {
        const ch = rows.filter(r => sel.has(r.auction_id)), x = t.dataset.x, v = vis(), sc = opts.scope + (v.length !== rows.length ? ' (filtered)' : '');
        if (x === 'back') goBack();
        else if (x === 'clr') { Object.keys(f).forEach(k => f[k] = ''); el.querySelectorAll('[data-f]').forEach(i => i.value = ''); draw(); }
        else if (x === 'buy-sel') bulk('admin_buy', ch, 'selected'); else if (x === 'ret-sel') bulk('return_to_seller', ch, 'selected');
        else if (x === 'buy-all') bulk('admin_buy', v, sc); else if (x === 'ret-all') bulk('return_to_seller', v, sc);
        else if (x === 'topoff') opts.topoff && opts.topoff();
      }
    };
    draw();
  }

  async function showItem(id, keep) {
    const it = state.agg.items.find(i => i.item_id === id) || itemPool().find(i => i.item_id === id), el = $('itDetail');
    state.selItem = id; if (it && !keep && !inCat(it.category_path, state.cat)) state.cat = it.category_path; drawItems();
    if (!it) { el.innerHTML = '<div class="ahc-empty">Item #' + id + ' is not an Auction House item.</div>'; return; }
    if (!keep) el.innerHTML = '<div class="ahc-empty">Loading…</div>';
    try {
      const [d, h] = await Promise.all([req('/auction-house/console/listings.json?item_id=' + id + '&limit=5000'),
        req('/auction-house/items/' + id + '/history.json?limit=50').catch(() => ({rows: []}))]);
      detail(el, '<b>' + esc(nm(it.item_name)) + '</b> <small>#' + id + ' · ' + esc(it.category_path || '') + ' · stack ' + it.stack_size + ' · ' + it.seller_count + ' seller(s) · low ' + fmt(it.min_price) + 'g · median ' + fmt(it.median_price) + 'g · high ' + fmt(it.max_price) + 'g</small>',
        d.rows, {seller: true, sales: h.rows || [], scope: nm(it.item_name), extra: '<button class="b pri" data-x="topoff">Top off…</button>',
          topoff: () => { addRestock({item_id: id, item_name: it.item_name, target: Math.max(it.listings + 1, 5), price: Math.round(it.min_price || it.avg_sale || 100), stack: false}); tab('restock'); }});
    } catch (e) { el.innerHTML = '<div class="ahc-empty">' + esc(e.message) + '</div>'; }
  }

  /* ---------- sellers tab ---------- */
  function drawSellers() {
    const q = $('seQ').value.trim().toLowerCase(), key = $('seSort').value;
    let rows = state.agg.sellers.filter(s => !q || (s.seller_name || '').toLowerCase().includes(q) || String(s.seller_id) === q);
    rows = key === 'name' ? sorted(rows.map(r => ({...r, item_name: r.seller_name})), 'name') : sorted(rows, key);
    $('seList').innerHTML = rows.length ? '<table><tbody>' + rows.slice(0, 600).map(s => '<tr class="clk' + (s.seller_id === state.selSeller ? ' sel' : '') + '" data-id="' + s.seller_id + '"><td><b>' + esc(s.seller_name || '#' + s.seller_id) +
      '</b><br><small>#' + s.seller_id + ' · ' + s.item_count + ' item(s) · oldest ' + days(s.oldest_days) + '</small></td><td class="n">' + s.listings + '×<br><small>' + fmt(s.value) + 'g</small></td></tr>').join('') + '</tbody></table>' : '<div class="ahc-empty">No sellers match.</div>';
  }
  $('seQ').addEventListener('input', debounce(drawSellers, 120)); $('seSort').addEventListener('change', drawSellers);
  $('seList').addEventListener('click', e => { const tr = e.target.closest('tr[data-id]'); if (tr) showSeller(+tr.dataset.id); });
  async function showSeller(id, keep) {
    state.selSeller = id; drawSellers();
    const s = state.agg.sellers.find(x => x.seller_id === id), el = $('seDetail');
    if (!s) { el.innerHTML = '<div class="ahc-empty">Seller #' + id + ' has no active listings.</div>'; return; }
    if (!keep) el.innerHTML = '<div class="ahc-empty">Loading…</div>';
    try {
      const [d, st] = await Promise.all([req('/auction-house/console/listings.json?seller_id=' + id + '&limit=5000'),
        req('/auction-house/console/seller-stats.json?seller_id=' + id).catch(() => null)]);
      d.rows.sort((a, b) => a.item_name.localeCompare(b.item_name) || a.asking_price - b.asking_price);
      const kpi = st ? ' · ' + st.sales + ' sold / ' + fmt(st.gil) + 'g in ' + st.days + 'd · sell-through ' + (st.sell_through == null ? '—' : st.sell_through + '%') +
        (st.median_hours_to_sale != null ? ' · median ' + st.median_hours_to_sale + 'h to sell' : '') : '';
      detail(el, '<b>' + esc(s.seller_name || '#' + id) + '</b> <small>#' + id + ' · ' + s.listings + ' listing(s) · ' + s.item_count + ' item(s) · ' + fmt(s.value) + 'g asking' + kpi + '</small>',
        d.rows, {item: true, scope: s.seller_name || '#' + id, sellerSales: st && st.recent, refs: st && st.refs});
    } catch (e) { el.innerHTML = '<div class="ahc-empty">' + esc(e.message) + '</div>'; }
  }

  /* ---------- item / character pickers ---------- */
  function picker(input, sug, url, fmtRow, onPick) {
    const run = debounce(async () => {
      const q = input.value.trim(); if (q.length < 2 && !/^\d+$/.test(q)) { sug.hidden = true; return; }
      try {
        const d = await req(url + encodeURIComponent(q)); const rows = d.rows || [];
        sug.innerHTML = rows.map((r, i) => '<div data-i="' + i + '">' + fmtRow(r) + '</div>').join('') || '<div class="mut">no matches</div>'; sug.hidden = false;
        sug.onclick = e => { const d2 = e.target.closest('[data-i]'); if (!d2) return; onPick(rows[+d2.dataset.i]); input.value = ''; sug.hidden = true; };
      } catch (e) { sug.innerHTML = '<div>' + esc(e.message) + '</div>'; sug.hidden = false; }
    });
    input.addEventListener('input', run);
  }
  const itemRow = r => (Array.isArray(r) ? esc(nm(r[1])) + ' <small>#' + r[0] + '</small>' : esc(nm(r.name || r.item_name)) + ' <small>#' + (r.item_id ?? r.id) + '</small>');

  /* ---------- shared character picker (Restock sellers + Inbox recipients) ---------- */
  const CHAR_URL = '/auction-house/console/characters.json?q=';
  function charPicker(root, list, onChange) {
    root.innerHTML = '<div class="ahc-chips cp-chips"></div><div class="ahc-bar"><input class="cp-q" placeholder="type a name or id, press Enter to add" autocomplete="off" style="flex:1"><button class="b cp-browse" type="button">Browse…</button><button class="b cp-clear" type="button">Clear all</button></div>' +
      '<div class="ahc-sug cp-sug" hidden></div><div class="cp-browser" hidden><div class="ahc-bar"><input class="cp-bq" placeholder="filter characters (name, id or account)" style="flex:1"><button class="b cp-addall" type="button">Add all shown</button></div><div class="ahc-scroll cp-blist"></div></div>';
    const q = root.querySelector('.cp-q'), sug = root.querySelector('.cp-sug'), chips = root.querySelector('.cp-chips'), br = root.querySelector('.cp-browser'), bq = root.querySelector('.cp-bq'), bl = root.querySelector('.cp-blist');
    let shown = [], suggest = [];
    const has = id => list.some(x => x.char_id === id);
    const add = r => { if (r && !has(r.char_id)) list.push(r); changed(); };
    const del = id => { const i = list.findIndex(x => x.char_id === id); if (i >= 0) list.splice(i, 1); changed(); };
    function draw() {
      chips.innerHTML = list.map(r => '<span class="ahc-chip2">' + esc(r.char_name) + ' #' + r.char_id + ' <button type="button" data-rm="' + r.char_id + '" title="Remove">✕</button></span>').join('') || '<small class="mut">No characters selected.</small>';
      bl.innerHTML = shown.length ? '<table><tbody>' + shown.map(r => '<tr><td><input type="checkbox" data-c="' + r.char_id + '"' + (has(r.char_id) ? ' checked' : '') + '></td><td>' + esc(r.char_name) + '</td><td class="mut">#' + r.char_id + '</td><td class="mut">' + esc(r.login || '') + '</td></tr>').join('') + '</tbody></table>' : '<div class="ahc-empty">No characters match.</div>';
    }
    const changed = () => { draw(); onChange && onChange(); };
    async function find(term, limit) { return (await req(CHAR_URL + encodeURIComponent(term) + '&limit=' + limit)).rows || []; }
    chips.onclick = e => { if (e.target.dataset.rm) del(+e.target.dataset.rm); };
    root.querySelector('.cp-clear').onclick = () => { list.length = 0; changed(); };
    q.addEventListener('input', debounce(async () => {
      const t = q.value.trim(); if (!t) { sug.hidden = true; return; }
      try { suggest = await find(t, 25); sug.innerHTML = suggest.map((r, i) => '<div data-i="' + i + '">' + esc(r.char_name) + ' <small>#' + r.char_id + '</small></div>').join('') || '<div class="mut">no matches</div>'; sug.hidden = false; } catch (e) { sug.hidden = true; }
    }, 150));
    q.addEventListener('keydown', e => { if (e.key === 'Enter' && suggest.length) { e.preventDefault(); const t = q.value.trim().toLowerCase(); add(suggest.find(r => r.char_name.toLowerCase() === t || String(r.char_id) === t) || suggest[0]); q.value = ''; sug.hidden = true; } });
    sug.onclick = e => { const d = e.target.closest('[data-i]'); if (d) { add(suggest[+d.dataset.i]); q.value = ''; sug.hidden = true; q.focus(); } };
    async function browse() { try { shown = await find(bq.value.trim(), 100); } catch (e) { shown = []; } draw(); }
    root.querySelector('.cp-browse').onclick = () => { br.hidden = !br.hidden; if (!br.hidden) browse(); };
    bq.addEventListener('input', debounce(browse, 200));
    bl.onchange = e => { const id = +e.target.dataset.c; if (!id) return; e.target.checked ? add(shown.find(r => r.char_id === id)) : del(id); };
    root.querySelector('.cp-addall').onclick = () => { shown.forEach(r => { if (!has(r.char_id)) list.push(r); }); changed(); };
    draw();
    return {draw};
  }
  const rsPick = charPicker($('rsChars'), state.rsSellers, () => { state.rsPlan = null; });
  const ibPick = charPicker($('ibChars'), state.recips);

  /* ---------- restock tab ---------- */
  function addRestock(e) {
    const i = state.restock.findIndex(x => x.item_id === e.item_id);
    if (i >= 0) state.restock[i] = {...state.restock[i], ...e}; else state.restock.push(e);
    state.rsPlan = null; drawRestock();
  }
  function drawRestock() {
    $('rsRows').innerHTML = state.restock.map((r, i) => {
      const cur = (state.agg && state.agg.items.find(x => x.item_id === r.item_id)) || {};
      return '<tr><td>' + esc(nm(r.item_name)) + '<br><small>#' + r.item_id + '</small></td><td class="n">' + (cur.listings || 0) + '</td><td class="n"><input type="number" min="1" data-k="target" data-i="' + i + '" value="' + r.target + '"></td><td class="n"><input type="number" min="1" data-k="price" data-i="' + i + '" value="' + r.price + '"></td>' +
        '<td><input type="checkbox" data-k="stack" data-i="' + i + '"' + (r.stack ? ' checked' : '') + '></td><td><button class="b" data-rm="' + i + '">✕</button></td></tr>';
    }).join('') || '<tr><td colspan="6" class="ahc-empty">Search for items above, or use “Top off…” from an item.</td></tr>';
  }
  $('rsRows').addEventListener('input', e => { const t = e.target, i = t.dataset.i; if (i == null) return; state.restock[i][t.dataset.k] = t.dataset.k === 'stack' ? t.checked : +t.value; state.rsPlan = null; });
  $('rsRows').addEventListener('click', e => { if (e.target.dataset.rm) { state.restock.splice(+e.target.dataset.rm, 1); state.rsPlan = null; drawRestock(); } });
  picker($('rsItemQ'), $('rsSug'), '/auction-house/console/item-search.json?q=', r => itemRow(r),
    r => { const id = Array.isArray(r) ? r[0] : (r.item_id ?? r.id), name = Array.isArray(r) ? r[1] : (r.name || r.item_name); addRestock({item_id: id, item_name: name, target: 5, price: 100, stack: false}); });
  req('/auction-house/categories.json').then(d => { $('rsCat').innerHTML += (d.rows || []).map(r => '<option value="' + r.category_id + '">' + esc(r.path || r.label || 'Category ' + r.category_id) + ' (' + (r.item_count || 0) + ')</option>').join(''); }).catch(() => {});
  $('rsCatAdd').addEventListener('click', async () => {
    const cat = $('rsCat').value; if (!cat) return toast('Choose a category');
    try {
      const d = await req('/auction-house/console/item-search.json?category_id=' + cat + '&limit=' + (+$('rsCatLimit').value || 50));
      const price = +$('rsCatPrice').value, target = +$('rsCatTarget').value || 3; let n = 0, skipped = 0;
      (d.rows || []).forEach(r => { const p = price || Math.round(r.average_sale_price || 0); if (p <= 0) { skipped++; return; } addRestock({item_id: r.item_id, item_name: r.name, target, price: p, stack: false}); n++; });
      toast('Added ' + n + ' item(s)' + (skipped ? '; ' + skipped + ' skipped (no sale history and no price set)' : ''));
    } catch (e) { toast(e.message); }
  });
  const rsBody = () => ({seller_ids: state.rsSellers.map(c => c.char_id), entries: state.restock.map(r => ({item_id: r.item_id, target: r.target, price: r.price, stack: r.stack}))});
  $('rsPreview').addEventListener('click', async () => {
    if (!state.restock.length) return toast('Add at least one item');
    try {
      const body = rsBody(), d = await req('/auction-house/console/restock/preview.json', body); state.rsPlan = d;
      $('rsPlan').innerHTML = '<p class="mut" style="margin:0 0 6px">' + d.listing_rows + ' listing(s) to create across ' + d.sellers.length + ' seller(s): ' + d.sellers.map(x => '<b>' + esc(x.char_name) + '</b> (' + x.listings + ')').join(', ') + '</p><table><thead><tr><th>Item</th><th class="n">Now</th><th class="n">Target</th><th class="n">Add</th><th class="n">Price</th></tr></thead><tbody>' +
        d.plan.map(p => '<tr><td>' + esc(nm(p.item_name)) + (p.stack ? ' <small>(stack of ' + p.stack_size + ')</small>' : '') + '</td><td class="n">' + p.current + '</td><td class="n">' + p.target + '</td><td class="n"><b>' + p.needed + '</b></td><td class="n">' + fmt(p.price) + 'g</td></tr>').join('') + '</tbody></table>' +
        '<div class="ahc-bar" style="margin-top:8px"><button class="b pri" id="rsGo"' + (d.listing_rows ? '' : ' disabled') + '>Create ' + d.listing_rows + ' listing(s)…</button></div>';
      $('rsGo').onclick = () => drawer({title: 'Restock ' + d.listing_rows + ' listing(s)', html: '<p style="padding:6px 8px;margin:0">Creates synthetic listings for ' + d.sellers.map(x => esc(x.char_name)).join(', ') + '. ' + esc(d.note) + '</p>', label: 'Create listings',
        run: async conf => { const r = await req('/auction-house/test-write/restock.json', {...body, preview_token: d.preview_token, confirmation: conf}); loadAll(true); state.rsPlan = null; return '<pre>' + r.status.toUpperCase() + ': ' + r.committed + ' created, ' + r.failed + ' failed\n' + esc(r.results.filter(x => x.status === 'failed').map(x => '#' + x.item_id + ': ' + x.error).join('\n')) + '</pre>'; }});
    } catch (e) { $('rsPlan').innerHTML = '<div class="ahc-empty">' + esc(e.message) + '</div>'; }
  });

  /* ---------- inbox tab ---------- */
  function drawBundle() {
    $('ibRows').innerHTML = state.bundle.map((b, i) => '<tr><td>' + esc(nm(b.name)) + ' <small>#' + b.item_id + '</small></td><td class="n"><input type="number" min="1" data-i="' + i + '" value="' + b.quantity + '"></td><td><button class="b" data-rm="' + i + '">✕</button></td></tr>').join('') || '<tr><td colspan="3" class="ahc-empty">Search for items to build a bundle, or pick a template.</td></tr>';
  }
  const drawChips = () => ibPick.draw();
  $('ibRows').addEventListener('input', e => { if (e.target.dataset.i != null) state.bundle[e.target.dataset.i].quantity = Math.max(1, +e.target.value || 1); });
  $('ibRows').addEventListener('click', e => { if (e.target.dataset.rm) { state.bundle.splice(+e.target.dataset.rm, 1); drawBundle(); } });
  $('ibGilAdd').addEventListener('click', () => {
    const amt = Math.min(999999999, Math.floor(+$('ibGil').value || 0));
    if (amt < 1) return;
    const ex = state.bundle.find(b => b.item_id === 65535);
    if (ex) ex.quantity = Math.min(999999999, ex.quantity + amt); else state.bundle.push({item_id: 65535, name: 'Gil', quantity: amt});
    $('ibGil').value = ''; drawBundle();
  });
  picker($('ibItemQ'), $('ibSug'), '/auction-house/console/item-search.json?q=', r => itemRow(r), r => {
    const id = Array.isArray(r) ? r[0] : (r.item_id ?? r.id), name = Array.isArray(r) ? r[1] : (r.name || r.item_name);
    const ex = state.bundle.find(b => b.item_id === id); if (ex) ex.quantity++; else state.bundle.push({item_id: id, name, quantity: 1}); drawBundle(); });
  async function loadTpls() {
    try {
      state.tpls = (await req('/auction-house/rewards/templates.json')).rows || [];
      const cur = $('ibTpl').value; $('ibTpl').innerHTML = '<option value="">Ad hoc bundle</option>' + state.tpls.map(t => '<option value="' + esc(t.template_id) + '">' + esc(t.name) + ' (' + t.items.length + ')</option>').join(''); $('ibTpl').value = cur;
    } catch (e) {}
  }
  $('ibTpl').addEventListener('change', async () => {
    const t = state.tpls.find(x => x.template_id === $('ibTpl').value); if (!t) return;
    $('ibName').value = t.name; state.bundle = t.items.map(i => ({item_id: i.item_id, name: '#' + i.item_id, quantity: i.quantity})); drawBundle();
    state.bundle.forEach(async b => { try { const d = await req('/auction-house/console/item-search.json?q=' + b.item_id); const r = (d.rows || []).find(x => (Array.isArray(x) ? x[0] : (x.item_id ?? x.id)) === b.item_id); if (r) { b.name = Array.isArray(r) ? r[1] : (r.name || r.item_name); drawBundle(); } } catch (e) {} });
  });
  const bundleItems = () => state.bundle.map(b => ({item_id: b.item_id, quantity: b.quantity}));
  $('ibSave').addEventListener('click', async () => {
    try { const r = await req('/auction-house/rewards/templates/save.json', {template_id: $('ibTpl').value || null, name: $('ibName').value, items: bundleItems()}); await loadTpls(); if (r.template_id) $('ibTpl').value = r.template_id; toast('Template saved'); } catch (e) { toast(e.message); }
  });
  $('ibDel').addEventListener('click', async () => {
    const id = $('ibTpl').value; if (!id) return toast('Select a saved template first');
    try { await req('/auction-house/rewards/templates/delete.json', {template_id: id}); $('ibTpl').value = ''; await loadTpls(); toast('Template deleted'); } catch (e) { toast(e.message); }
  });
  $('ibPreview').addEventListener('click', async () => {
    const mode = document.querySelector('input[name=ibMode]:checked').value;
    if (!state.bundle.length) return toast('Add items to the bundle');
    if (mode === 'selected' && !state.recips.length) return toast('Select recipients (or choose All characters)');
    const body = {recipient_mode: mode, character_ids: state.recips.map(r => r.char_id), items: bundleItems(), template_id: $('ibTpl').value || null};
    try {
      const d = (await req('/auction-house/rewards/preview.json', body)).preview;
      drawer({title: 'Send ' + d.item_count + ' item(s) to ' + d.recipient_count + ' character(s)', label: 'Deliver',
        html: '<p style="padding:6px 8px;margin:0">' + d.delivery_rows + ' delivery row(s) will be created.</p><table><thead><tr><th>Item</th><th class="n">Qty</th></tr></thead><tbody>' +
          d.items.map(i => '<tr><td>' + esc(nm(i.name || i.item_name || '#' + i.item_id)) + '</td><td class="n">' + i.quantity + '</td></tr>').join('') + '</tbody></table><table><thead><tr><th>Recipients</th></tr></thead><tbody>' +
          d.recipients.slice(0, 200).map(r => '<tr><td>' + esc(r.char_name) + ' <small>#' + r.char_id + '</small></td></tr>').join('') + (d.recipients.length > 200 ? '<tr><td>… +' + (d.recipients.length - 200) + ' more</td></tr>' : '') + '</tbody></table>',
        run: async conf => { const r = (await req('/auction-house/rewards/execute.json', {...body, preview_token: d.preview_token, preview_id: d.preview_id, replay_id: d.replay_id, confirmation: conf})).result;
          return '<pre>' + r.status.toUpperCase() + ': ' + r.committed_recipients + ' delivered, ' + r.failed_recipients + ' failed\n' + esc(r.results.filter(x => x.status === 'failed').map(x => x.char_name + ': ' + x.error).join('\n')) + '</pre>'; }});
    } catch (e) { toast(e.message); }
  });

  /* ---------- presets (shared by Restock, Cleanup and the Presets tab) ---------- */
  state.presets = []; state.cats = []; state.pzSel = null; state.pzBack = null; state.pzDraft = null; state.pzSellers = []; state.pzSellerNames = {};
  async function loadCats() { try { state.cats = (await req('/auction-house/categories.json')).rows || []; } catch (e) {} $('cuCategory').innerHTML = '<option value="">Any category</option>' + state.cats.map(r => '<option value="' + r.category_id + '">' + esc(r.path || r.label) + '</option>').join(''); }
  async function loadPresets() {
    try { state.presets = (await req('/auction-house/presets.json')).rows || []; } catch (e) { toast(e.message); }
    const opts = kind => '<option value="">Load a preset…</option>' + state.presets.filter(p => p.kind === kind).map(p => '<option value="' + esc(p.preset_id) + '">' + esc(p.name) + '</option>').join('');
    const r = $('rsPreset').value, c = $('cuPreset').value;
    $('rsPreset').innerHTML = opts('restock'); $('cuPreset').innerHTML = opts('cleanup'); $('rsPreset').value = r; $('cuPreset').value = c;
    drawPresetList();
  }
  const byId = id => state.presets.find(p => p.preset_id === id);

  /* jump between a tool and the preset editor */
  function newDraft(kind) { return kind === 'cleanup' ? {kind, name: '', config: {min_age_days: 30, default_action: 'return_to_seller', limit: 100}} : {kind: 'restock', name: '', config: {price_source: 'market', target: 3, max_items: 50, stack_mode: 'single', fallback_mult: 1.5, price_mult: 1}}; }
  function editPreset(id, back, kind) { state.pzBack = back; state.pzSel = id || null; state.pzDraft = id ? null : newDraft(kind); tab('presets'); drawPresetList(); drawEditor(); }
  [['rs', 'restock'], ['cu', 'cleanup']].forEach(([p, kind]) => {
    $(p + 'PresetEdit').onclick = () => { const id = $(p + 'Preset').value; id ? editPreset(id, kind) : toast('Pick a preset to edit first'); };
    $(p + 'PresetNew').onclick = () => editPreset(null, kind, kind);
  });

  function drawPresetList() {
    const q = $('pzQ').value.trim().toLowerCase(), k = $('pzKind').value;
    const rows = state.presets.filter(p => (!k || p.kind === k) && (!q || p.name.toLowerCase().includes(q)));
    $('pzList').innerHTML = rows.map(p => '<div class="pz-item' + (p.preset_id === state.pzSel ? ' sel' : '') + '" data-id="' + esc(p.preset_id) + '"><span><span class="pz-kind">' + esc(p.kind === 'synthetic_seed' ? 'seed' : p.kind) + '</span><b>' + esc(p.name) + '</b></span><small>' + esc(p.config.description || '') + '</small></div>').join('') || '<div class="ahc-empty">No presets match.</div>';
  }
  $('pzQ').addEventListener('input', drawPresetList); $('pzKind').addEventListener('change', drawPresetList);
  $('pzList').addEventListener('click', e => { const d = e.target.closest('[data-id]'); if (d) { state.pzSel = d.dataset.id; state.pzDraft = null; drawPresetList(); drawEditor(); } });
  $('pzNewRestock').onclick = () => { state.pzSel = null; state.pzDraft = newDraft('restock'); drawPresetList(); drawEditor(); };
  $('pzNewCleanup').onclick = () => { state.pzSel = null; state.pzDraft = newDraft('cleanup'); drawPresetList(); drawEditor(); };

  const numv = id => { const v = $(id).value.trim(); return v === '' ? null : +v; };

  /* ---------- preset editor: grouped categories + include/exclude items ---------- */
  state.pzInc = []; state.pzExc = []; state.pzNames = {};
  function catTree(sel) {
    const groups = new Map();
    state.cats.forEach(r => { const g = (r.path || r.label).split(' → ')[0]; if (!groups.has(g)) groups.set(g, []); groups.get(g).push(r); });
    return '<input id="pzCatQ" placeholder="filter categories" autocomplete="off"><div class="pz-catlist" id="pzCats">' + [...groups].map(([g, rs]) =>
      '<div class="pz-grp" data-g="' + esc(g) + '"><label class="pz-gh"><input type="checkbox" data-gall="1"> <b>' + esc(g) + '</b> <small class="mut" data-gcount="1"></small></label>' +
      rs.map(r => '<label class="pz-c" data-n="' + esc((r.path || r.label).toLowerCase()) + '"><input type="checkbox" data-c="1" value="' + r.category_id + '"' + (sel.has(r.category_id) ? ' checked' : '') + '> ' + esc(r.label || r.path) + '</label>').join('') + '</div>').join('') + '</div>' +
      '<div class="ahc-bar"><button class="b" id="pzCatClear" type="button">Clear categories</button><button class="b" id="pzCatGear" type="button" title="Every weapon and armor category">Select all weapons &amp; armor</button></div>';
  }
  function wireCats() {
    const root = $('pzCats');
    const sync = () => {
      let total = 0;
      root.querySelectorAll('.pz-grp').forEach(g => {
        const cs = [...g.querySelectorAll('input[data-c]')], on = cs.filter(c => c.checked).length; total += on;
        const all = g.querySelector('input[data-gall]'); all.checked = on === cs.length; all.indeterminate = on > 0 && on < cs.length;
        g.querySelector('[data-gcount]').textContent = on + '/' + cs.length;
      });
      $('pzCatSum').textContent = total ? total + ' categor' + (total === 1 ? 'y' : 'ies') + ' selected' : 'none selected';
    };
    root.onchange = e => {
      if (e.target.dataset.gall) e.target.closest('.pz-grp').querySelectorAll('.pz-c input[data-c]').forEach(c => { if (c.closest('.pz-c').style.display !== 'none') c.checked = e.target.checked; });
      sync();
    };
    $('pzCatQ').oninput = () => {
      const q = $('pzCatQ').value.toLowerCase();
      root.querySelectorAll('.pz-c').forEach(l => { l.style.display = l.dataset.n.includes(q) ? '' : 'none'; });
      root.querySelectorAll('.pz-grp').forEach(g => { g.style.display = [...g.querySelectorAll('.pz-c')].some(l => l.style.display !== 'none') ? '' : 'none'; });
    };
    $('pzCatClear').onclick = () => { root.querySelectorAll('input[data-c]').forEach(c => { c.checked = false; }); sync(); };
    $('pzCatGear').onclick = () => { root.querySelectorAll('.pz-grp').forEach(g => { if (/weapon|armor/i.test(g.dataset.g)) g.querySelectorAll('input[data-c]').forEach(c => { c.checked = true; }); }); sync(); };
    sync();
  }
  function itemsBox() {
    return '<div class="ahc-bar"><input id="pzItQ" placeholder="search items to add or exclude…" autocomplete="off" style="flex:1"></div><div class="pz-itres" id="pzItRes"></div>' +
      '<div class="pz-two"><div><small><b>Always include</b></small><div class="pz-chips" id="pzInc"></div></div><div><small><b>Never include</b></small><div class="pz-chips" id="pzExc"></div></div></div>';
  }
  function pzName(id) {
    if (state.pzNames[id]) return state.pzNames[id];
    const c = state.catalog && state.catalog.find(x => x.item_id === id); return c ? c.item_name : '#' + id;
  }
  function pzChips() {
    [['pzInc', state.pzInc], ['pzExc', state.pzExc]].forEach(([id, list]) => {
      $(id).innerHTML = list.length ? list.map(x => '<span class="pz-chip">' + esc(x.item_name) + ' <a href="#" data-rm="' + x.item_id + '" title="Remove">×</a></span>').join('') : '<small class="mut">none</small>';
      $(id).onclick = e => { const a = e.target.closest('[data-rm]'); if (!a) return; e.preventDefault(); const k = +a.dataset.rm, i = list.findIndex(x => x.item_id === k); if (i >= 0) list.splice(i, 1); pzChips(); };
    });
  }
  function wireItems(c) {
    const mk = ids => (ids || []).map(id => ({item_id: id, item_name: pzName(id)}));
    state.pzInc.length = 0; mk(c.item_ids).forEach(x => state.pzInc.push(x));
    state.pzExc.length = 0; mk(c.exclude_item_ids).forEach(x => state.pzExc.push(x));
    pzChips();
    ensureCatalog().then(() => { [...state.pzInc, ...state.pzExc].forEach(x => { x.item_name = pzName(x.item_id); }); if ($('pzInc')) pzChips(); });
    const run = debounce(async () => {
      const q = $('pzItQ').value.trim(); if (q.length < 2) { $('pzItRes').innerHTML = ''; return; }
      try {
        const rows = (await req('/auction-house/console/item-search.json?q=' + encodeURIComponent(q) + '&limit=15')).rows || [];
        $('pzItRes').innerHTML = rows.length ? rows.map(r => '<div class="pz-ir"><span>' + esc(r.item_name || r.name) + ' <small class="mut">#' + r.item_id + '</small></span><span><button class="b" data-inc="' + r.item_id + '" type="button">+ Include</button><button class="b" data-exc="' + r.item_id + '" type="button">− Exclude</button></span></div>').join('') : '<small class="mut">No matching AH items.</small>';
        $('pzItRes').onclick = e => {
          const b = e.target.closest('button'); if (!b) return;
          const id = +(b.dataset.inc || b.dataset.exc), r = rows.find(x => x.item_id === id), nm0 = r.item_name || r.name;
          state.pzNames[id] = nm0;
          const to = b.dataset.inc ? state.pzInc : state.pzExc, from = b.dataset.inc ? state.pzExc : state.pzInc, fi = from.findIndex(x => x.item_id === id);
          if (fi >= 0) from.splice(fi, 1);
          if (!to.some(x => x.item_id === id)) to.push({item_id: id, item_name: nm0});
          pzChips();
        };
      } catch (e) { toast(e.message); }
    }, 300);
    $('pzItQ').oninput = run;
  }

  function drawEditor() {
    const cur = state.pzDraft || byId(state.pzSel), box = $('pzEditor');
    if (!cur) { box.innerHTML = '<div class="ahc-empty">Pick a preset to edit, or create a new one.</div>'; return; }
    if (cur.kind === 'synthetic_seed') { box.innerHTML = '<div class="ahc-empty">Legacy seeding presets are kept as-is. Category seeding now lives in Restock; create a Restock preset instead.</div>'; return; }
    const c = cur.config || {}, back = state.pzBack ? '<button class="b" id="pzBack" type="button">← Back to ' + (state.pzBack === 'restock' ? 'Restock' : 'Cleanup') + '</button>' : '';
    const head = '<div class="ahc-bar">' + back + '<h3 style="margin:0;flex:1">' + (cur.preset_id ? 'Edit' : 'New') + ' ' + cur.kind + ' preset</h3></div><label>Name <input id="pzName" value="' + esc(cur.name) + '"></label><label>Description <input id="pzDesc" value="' + esc(c.description || '') + '"></label>';
    if (cur.kind === 'restock') {
      const sel = new Set(c.category_ids || []);
      state.pzSellers.length = 0; (c.seller_ids || []).forEach(id => state.pzSellers.push({char_id: id, char_name: state.pzSellerNames[id] || ('#' + id)}));
      box.innerHTML = head + '<b>Categories</b> <small class="mut" id="pzCatSum"></small>' + catTree(sel) +
        '<div class="ahc-grid2"><label>Min level <input id="pzMinL" type="number" min="1" value="' + (c.min_level ?? '') + '"></label><label>Max level <input id="pzMaxL" type="number" min="1" value="' + (c.max_level ?? '') + '"></label>' +
        '<label>Name contains <input id="pzName2" value="' + esc(c.name_contains || '') + '"></label><label>No activity for (days) <input id="pzIdle" type="number" min="0" value="' + (c.no_activity_days ?? '') + '"></label>' +
        '<label class="wide" style="flex-direction:row;gap:6px"><input type="checkbox" id="pzRare"' + (c.rare_only ? ' checked' : '') + '> Rare items only</label></div>' +
        '<b>Specific items</b> <small class="mut">add single items on top of the filters, or exclude items the filters would pick up</small>' + itemsBox() +
        '<b>Pricing and quantity</b><div class="ahc-grid2"><label>Price source <select id="pzSrc"><option value="market">Market average (fallback: base value)</option><option value="base_sell">Base value</option><option value="fixed">Fixed price</option></select></label>' +
        '<label>Fixed price <input id="pzPrice" type="number" min="1" value="' + (c.price ?? '') + '"></label><label>Price multiplier <input id="pzMult" type="number" step="0.05" min="0.05" value="' + (c.price_mult ?? 1) + '"></label><label>Fallback × base value <input id="pzFb" type="number" step="0.1" min="0.1" value="' + (c.fallback_mult ?? 1.5) + '"></label>' +
        '<label>Target listings per item <input id="pzTarget" type="number" min="1" max="99" value="' + (c.target ?? 3) + '"></label><label>Max items (up to 50) <input id="pzMax" type="number" min="1" max="50" value="' + (c.max_items ?? 50) + '"></label>' +
        '<label>Listing type <select id="pzStack"><option value="single">Single items</option><option value="stack">Full stacks</option></select></label></div>' +
        '<b>Sellers</b> <small class="mut">leave empty to use the default seller</small><div class="ahc-charpick" id="pzChars"></div>';
      $('pzSrc').value = c.price_source || 'market'; $('pzStack').value = c.stack_mode || 'single';
      charPicker($('pzChars'), state.pzSellers, () => state.pzSellers.forEach(s => { state.pzSellerNames[s.char_id] = s.char_name; }));
      wireCats(); wireItems(c);
    } else {
      box.innerHTML = head + '<div class="ahc-grid2"><label>Seller ID <input id="pzSid" type="number" value="' + (c.seller_id ?? '') + '"></label><label>Seller name contains <input id="pzSname" value="' + esc(c.seller_name || '') + '"></label>' +
        '<label>Category <select id="pzCat"><option value="">Any category</option>' + state.cats.map(r => '<option value="' + r.category_id + '">' + esc(r.path || r.label) + '</option>').join('') + '</select></label><label>Item ID <input id="pzItem" type="number" value="' + (c.item_id ?? '') + '"></label>' +
        '<label>Min price <input id="pzMinP" type="number" value="' + (c.min_price ?? '') + '"></label><label>Max price <input id="pzMaxP" type="number" value="' + (c.max_price ?? '') + '"></label>' +
        '<label>Older than (days) <input id="pzAge" type="number" step="0.1" value="' + (c.min_age_days ?? '') + '"></label><label title="1 = below NPC buy-back value">Below vendor value × <input id="pzVend" type="number" step="0.05" min="0" value="' + (c.max_vendor_ratio ?? '') + '"></label><label>Limit (up to 100) <input id="pzLim" type="number" max="100" value="' + (c.limit ?? 100) + '"></label>' +
        '<label class="wide">Suggested action <select id="pzAct"><option value="return_to_seller">Return to seller</option><option value="admin_buy">Admin buy</option></select></label></div>';
      $('pzCat').value = c.category_id ?? ''; $('pzAct').value = c.default_action || 'return_to_seller';
    }
    box.insertAdjacentHTML('beforeend', '<div class="ahc-bar ahc-bar-bottom"><button class="b pri" id="pzSave" type="button">Save</button>' + (cur.kind === 'restock' ? '<button class="b" id="pzTest" type="button">Test (show matches)</button>' : '') +
      (cur.preset_id ? '<button class="b" id="pzDup" type="button">Duplicate</button><button class="b" id="pzDel" type="button">Delete</button>' : '') + '<button class="b" id="pzUse" type="button">Use in ' + (cur.kind === 'restock' ? 'Restock' : 'Cleanup') + ' →</button></div><div class="ahc-scroll" id="pzOut"></div>');
    $('pzSave').onclick = () => savePreset(); $('pzUse').onclick = () => useAfterSave();
    if ($('pzBack')) $('pzBack').onclick = () => { const b = state.pzBack; state.pzBack = null; tab(b); };
    if ($('pzTest')) $('pzTest').onclick = testPreset;
    if ($('pzDup')) $('pzDup').onclick = () => { const c2 = collect(); state.pzSel = null; state.pzDraft = {kind: cur.kind, name: c2.name + ' (copy)', config: c2.config}; drawPresetList(); drawEditor(); };
    if ($('pzDel')) $('pzDel').onclick = async () => { if (!confirm('Delete preset "' + cur.name + '"?')) return; try { await req('/auction-house/presets/delete.json', {preset_id: cur.preset_id}); state.pzSel = null; await loadPresets(); drawEditor(); toast('Preset deleted'); } catch (e) { toast(e.message); } };
  }
  function collect() {
    const cur = state.pzDraft || byId(state.pzSel), clean = o => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== null && v !== '' && v !== undefined));
    if (cur.kind === 'restock') return {name: $('pzName').value.trim(), kind: 'restock', config: clean({description: $('pzDesc').value.trim(),
      category_ids: [...$('pzCats').querySelectorAll('input[data-c]:checked')].map(i => +i.value), item_ids: state.pzInc.map(x => x.item_id), exclude_item_ids: state.pzExc.map(x => x.item_id), min_level: numv('pzMinL'), max_level: numv('pzMaxL'), name_contains: $('pzName2').value.trim(), rare_only: $('pzRare').checked,
      no_activity_days: numv('pzIdle'), price_source: $('pzSrc').value, price: numv('pzPrice'), price_mult: numv('pzMult'), fallback_mult: numv('pzFb'), target: numv('pzTarget'), max_items: numv('pzMax'),
      stack_mode: $('pzStack').value, seller_ids: state.pzSellers.map(s => s.char_id)})};
    return {name: $('pzName').value.trim(), kind: 'cleanup', config: clean({description: $('pzDesc').value.trim(), seller_id: numv('pzSid'), seller_name: $('pzSname').value.trim(), category_id: numv('pzCat'), item_id: numv('pzItem'),
      min_price: numv('pzMinP'), max_price: numv('pzMaxP'), min_age_days: numv('pzAge'), max_vendor_ratio: numv('pzVend'), limit: numv('pzLim'), default_action: $('pzAct').value})};
  }
  async function savePreset() {
    const cur = state.pzDraft || byId(state.pzSel), body = collect();
    try { const r = await req('/auction-house/presets/save.json', {...body, preset_id: cur.preset_id || null}); state.pzSel = r.preset_id; state.pzDraft = null; await loadPresets(); drawEditor(); toast('Preset saved'); return r; } catch (e) { toast(e.message); return null; }
  }
  async function useAfterSave() {
    const r = await savePreset(); if (!r) return;
    state.pzBack = null; tab(r.kind);
    if (r.kind === 'restock') { $('rsPreset').value = r.preset_id; loadRestockPreset(); } else { $('cuPreset').value = r.preset_id; loadCleanupPreset(); }
  }
  const resolveNote = d => '<p class="mut" style="margin:4px 0">' + d.entries.length + ' item(s) shown' + (d.matched_capped ? ' (more match than the search window)' : ', ' + d.matched + ' matched') + (d.truncated ? '; list capped at ' + d.config.max_items : '') + (d.skipped.length ? '; ' + d.skipped.length + ' skipped (no price or cannot stack)' : '') + '.</p>';
  async function testPreset() {
    try {
      const d = await req('/auction-house/console/restock/preset-test.json', {config: collect().config});
      $('pzOut').innerHTML = resolveNote(d) + '<table><thead><tr><th>Item</th><th class="n">Lv</th><th class="n">Price</th></tr></thead><tbody>' + d.entries.map(e => '<tr><td>' + esc(nm(e.item_name)) + '</td><td class="n">' + (e.level ?? '') + '</td><td class="n">' + fmt(e.price) + 'g</td></tr>').join('') + '</tbody></table>';
    } catch (e) { $('pzOut').innerHTML = '<div class="ahc-empty">' + esc(e.message) + '</div>'; }
  }

  /* default seller card */
  async function loadDefault() { try { const d = await req('/auction-house/console/restock/default-seller.json'); $('pzDefName').value = d.char_name; $('pzDefId').value = d.char_id; $('rsSellerHint').textContent = 'none selected → listings go to the default seller ' + d.char_name; } catch (e) {} }
  $('pzDefSave').onclick = async () => { try { await req('/auction-house/console/restock/default-seller.json', {char_id: +$('pzDefId').value, char_name: $('pzDefName').value.trim()}); await loadDefault(); toast('Default seller saved'); } catch (e) { toast(e.message); } };

  /* restock: load a preset into the table */

  function describePreset(d) {
    const c = d.config || {}, nm = id => (state.cats.find(r => r.category_id === id) || {}).path || ('#' + id), L = [];
    const groups = {}; (c.category_ids || []).forEach(id => { const p = nm(id).split(' → '); (groups[p[0]] = groups[p[0]] || []).push(p[p.length - 1]); });
    if (Object.keys(groups).length) L.push('<b>Categories:</b> ' + Object.entries(groups).map(([g, v]) => esc(g) + ' (' + v.length + (v.length <= 4 ? ': ' + esc(v.join(', ')) : '') + ')').join('; '));
    if (c.min_level || c.max_level) L.push('<b>Level:</b> ' + (c.min_level || 1) + '–' + (c.max_level || '99'));
    if (c.name_contains) L.push('<b>Name contains:</b> ' + esc(c.name_contains));
    if (c.rare_only) L.push('<b>Rare only</b>');
    if (c.no_activity_days) L.push('<b>Idle:</b> ' + c.no_activity_days + '+ days');
    if ((c.item_ids || []).length) L.push('<b>Always include:</b> ' + c.item_ids.length + ' item(s)');
    if ((c.exclude_item_ids || []).length) L.push('<b>Excluding:</b> ' + c.exclude_item_ids.length + ' item(s)');
    L.push('<b>Price:</b> ' + (c.price_source === 'fixed' ? fmt(c.price) + 'g fixed' : c.price_source === 'base_sell' ? 'base value' : 'market average') + (c.price_mult && c.price_mult !== 1 ? ' ×' + c.price_mult : '') + ' · target ' + c.target + ' · ' + (c.stack_mode === 'stack' ? 'stacks' : 'singles'));
    L.push(esc(d.preset.name) + ' → <b>' + d.entries.length + ' item(s)</b>' + (d.matched_capped ? ', more match than the search window' : ', ' + d.matched + ' matched') + (d.truncated ? ', capped at ' + c.max_items : '') + (d.skipped.length ? ', ' + d.skipped.length + ' skipped (no price / cannot stack)' : ''));
    return L.join('<br>');
  }
  $('rsPresetDel').onclick = async () => {
    const id = $('rsPreset').value; if (!id) return toast('Pick a preset to delete first');
    const p = state.presets.find(x => x.preset_id === id); if (!confirm('Delete preset "' + (p ? p.name : id) + '"?')) return;
    try { await req('/auction-house/presets/delete.json', {preset_id: id}); $('rsPreset').value = ''; $('rsPresetInfo').textContent = ''; await loadPresets(); toast('Preset deleted'); } catch (e) { toast(e.message); }
  };
  async function loadRestockPreset() {
    const id = $('rsPreset').value; if (!id) return toast('Pick a preset to load');
    try {
      const d = await req('/auction-house/console/restock/from-preset.json', {preset_id: id});
      state.restock.length = 0; d.entries.forEach(e => state.restock.push(e)); state.rsPlan = null; drawRestock();
      state.rsSellers.length = 0; (d.sellers || []).forEach(s => state.rsSellers.push(s)); rsPick.draw();
      $('rsPresetInfo').innerHTML = describePreset(d);
    } catch (e) { toast(e.message); }
  }
  $('rsPresetLoad').onclick = loadRestockPreset;

  /* cleanup tab */
  const CU = {SellerId: 'seller_id', SellerName: 'seller_name', Category: 'category_id', ItemId: 'item_id', MinPrice: 'min_price', MaxPrice: 'max_price', AgeDays: 'min_age_days', Vendor: 'max_vendor_ratio', Limit: 'limit'};
  function cuClear() {
    $('cuSellerQ').value = $('cuItemQ').value = '';
    Object.keys(CU).forEach(k => { $('cu' + k).value = ''; }); $('cuAgeDays').value = 30; $('cuLimit').value = 100;
    state.cuRows = []; state.cuAction = null; $('cuAction').textContent = ''; $('cuSummary').textContent = ''; $('cuBuy').disabled = $('cuReturn').disabled = true;
    $('cuRows').innerHTML = '<div class="ahc-empty">Set rules and preview to see exactly which listings match.</div>';
  }
  function loadCleanupPreset() {
    const p = byId($('cuPreset').value); if (!p) return toast('Pick a preset to load');
    cuClear(); Object.entries(CU).forEach(([k, f]) => { if (p.config[f] != null) $('cu' + k).value = p.config[f]; }); cuShowFields();
    state.cuAction = p.config.default_action || null; $('cuPresetInfo').textContent = p.name + (p.config.description ? ': ' + p.config.description : '');
    $('cuAction').textContent = state.cuAction ? 'Preset suggests: ' + (state.cuAction === 'admin_buy' ? 'Admin Buy' : 'Return') : ''; cuPreview();
  }
  async function cuPreview() {
    cuSyncFields(); const body = {}; Object.entries(CU).forEach(([k, f]) => { const v = $('cu' + k).value.trim(); if (v !== '') body[f] = f === 'seller_name' ? v : +v; });
    try {
      const d = await req('/auction-house/cleanup/preview.json', body);
      state.cuRows = (d.targets || []).map(t => ({...t, quantity: t.quantity ?? t.stack_quantity ?? 1}));
      $('cuSummary').textContent = state.cuRows.length + ' listing(s), ' + fmt(d.aggregate_asking_value) + 'g asking';
      $('cuBuy').disabled = $('cuReturn').disabled = !state.cuRows.length;
      $('cuBuy').classList.toggle('pri', state.cuAction === 'admin_buy'); $('cuReturn').classList.toggle('pri', state.cuAction === 'return_to_seller');
      $('cuRows').innerHTML = state.cuRows.length ? listingTable(state.cuRows) : '<div class="ahc-empty">Nothing matches these rules.' + (state.agg && state.agg.oldest_days != null ? ' The oldest active listing is ' + days(state.agg.oldest_days) + ' old — lower “Older than” to catch more.' : '') + '</div>';
    } catch (e) { $('cuRows').innerHTML = '<div class="ahc-empty">' + esc(e.message) + '</div>'; }
  }
  $('cuPresetLoad').onclick = loadCleanupPreset; $('cuClear').onclick = cuClear; $('cuPreview').onclick = cuPreview;
  $('cuBuy').onclick = () => bulk('admin_buy', state.cuRows, 'cleanup rules'); $('cuReturn').onclick = () => bulk('return_to_seller', state.cuRows, 'cleanup rules');

  /* ---------- items: active / unlisted / all ---------- */
  state.catalog = null;
  async function ensureCatalog() {
    if (state.catalog) return;
    try { state.catalog = (await req('/auction-house/console/catalog.json')).rows; } catch (e) { toast(e.message); state.catalog = []; }
  }
  function itemPool() {
    const st = $('itStatus').value, active = state.agg ? state.agg.items : [];
    if (st === 'active' || !state.catalog) return active;
    const have = new Map(active.map(i => [i.item_id, i]));
    const all = state.catalog.map(c => have.get(c.item_id) ? {...have.get(c.item_id), sales: c.sales, last_sold_at: c.last_sold_at, avg_sale: c.avg_sale}
      : {item_id: c.item_id, item_name: c.item_name, category_path: c.category_path, stack_size: c.stack_size, listings: 0, min_price: null, median_price: null, max_price: null, seller_count: 0, oldest_days: null, sales: c.sales, last_sold_at: c.last_sold_at, avg_sale: c.avg_sale});
    return st === 'unlisted' ? all.filter(i => !i.listings) : all;
  }
  $('itStatus').addEventListener('change', async () => { if ($('itStatus').value !== 'active') await ensureCatalog(); drawItems(); });

  /* ---------- cleanup: seller / item search ---------- */
  function cuSearch(input, sug, url, fmtRow, onPick) {
    const run = debounce(async () => {
      const q = input.value.trim(); if (!q) { sug.hidden = true; return; }
      try {
        const rows = (await req(url + encodeURIComponent(q))).rows || [];
        sug.innerHTML = rows.slice(0, 25).map((r, i) => '<div data-i="' + i + '">' + fmtRow(r) + '</div>').join('') || '<div class="mut">no matches — the text is used as a name filter</div>'; sug.hidden = false;
        sug.onclick = e => { const d = e.target.closest('[data-i]'); if (d) { onPick(rows[+d.dataset.i]); sug.hidden = true; } };
      } catch (e) { sug.hidden = true; }
    });
    input.addEventListener('input', run);
  }
  cuSearch($('cuSellerQ'), $('cuSellerSug'), '/auction-house/console/characters.json?include_sellers=1&limit=25&q=', r => esc(r.char_name) + ' <small>#' + r.char_id + (r.source === 'auction-only' ? ' · AH seller' : '') + '</small>',
    r => { $('cuSellerId').value = r.char_id; $('cuSellerName').value = ''; $('cuSellerQ').value = r.char_name + ' #' + r.char_id; $('cuSellerQ').dataset.picked = $('cuSellerQ').value; });
  cuSearch($('cuItemQ'), $('cuItemSug'), '/auction-house/console/item-search.json?q=', r => itemRow(r),
    r => { const id = Array.isArray(r) ? r[0] : (r.item_id ?? r.id), name = Array.isArray(r) ? r[1] : (r.name || r.item_name); $('cuItemId').value = id; $('cuItemQ').value = nm(name) + ' #' + id; $('cuItemQ').dataset.picked = $('cuItemQ').value; });
  $('cuSellerQ').addEventListener('input', () => { if ($('cuSellerQ').value !== $('cuSellerQ').dataset.picked) $('cuSellerId').value = ''; });
  $('cuItemQ').addEventListener('input', () => { if ($('cuItemQ').value !== $('cuItemQ').dataset.picked) $('cuItemId').value = ''; });
  // translate the visible search boxes into the criteria the API wants
  function cuSyncFields() {
    const sq = $('cuSellerQ').value.trim(), iq = $('cuItemQ').value.trim();
    if (!sq) { $('cuSellerId').value = ''; $('cuSellerName').value = ''; }
    else if (!$('cuSellerId').value) { if (/^\d+$/.test(sq)) $('cuSellerId').value = sq; else $('cuSellerName').value = sq; }
    if (!iq) $('cuItemId').value = ''; else if (!$('cuItemId').value && /^\d+$/.test(iq)) $('cuItemId').value = iq;
  }
  function cuShowFields() {
    $('cuSellerQ').dataset.picked = $('cuItemQ').dataset.picked = '';
    $('cuSellerQ').value = $('cuSellerName').value || ($('cuSellerId').value ? '#' + $('cuSellerId').value : '');
    $('cuItemQ').value = $('cuItemId').value ? '#' + $('cuItemId').value : '';
  }

  /* ---------- buyers tab ---------- */
  state.buyers = null; state.selBuyer = null;
  async function loadBuyers() {
    $('buList').innerHTML = '<div class="ahc-empty">Loading…</div>';
    try { state.buyers = await req('/auction-house/console/buyers.json?days=' + $('buDays').value); } catch (e) { $('buList').innerHTML = '<div class="ahc-empty">' + esc(e.message) + '</div>'; return; }
    drawBuyers();
  }
  function drawBuyers() {
    const d = state.buyers; if (!d) return;
    const q = $('buQ').value.trim().toLowerCase(), k = $('buSort').value;
    const rows = d.buyers.filter(b => !q || (b.buyer_name || '').toLowerCase().includes(q)).sort((a, b) => (b[k] ?? -1e9) - (a[k] ?? -1e9));
    $('buSummary').textContent = d.count + ' buyer(s) · ' + fmt(d.total_purchases) + ' purchases · ' + fmt(d.total_spent) + 'g in ' + d.days + 'd · overpaid = ≥' + d.overpaid_threshold_pct + '% above median';
    $('buList').innerHTML = rows.length ? '<table><tbody>' + rows.slice(0, 600).map(b => '<tr class="clk' + (b.buyer_key === state.selBuyer ? ' sel' : '') + '" data-id="' + esc(b.buyer_key) + '"><td><b>' + esc(b.buyer_name || b.buyer_key) + '</b><br><small>' + b.purchases + ' buys · ' + b.distinct_items + ' item(s) · ' + b.distinct_sellers + ' seller(s)' +
      (b.overpaid_count ? ' · <span class="mk hi">' + b.overpaid_count + ' overpaid (' + fmt(b.overpaid_gil) + 'g)</span>' : '') + '</small></td><td class="n">' + fmt(b.spent) + 'g<br><small>' + (b.avg_markup_pct == null ? '' : (b.avg_markup_pct > 0 ? '+' : '') + b.avg_markup_pct + '% avg') + '</small></td></tr>').join('') + '</tbody></table>' : '<div class="ahc-empty">No buyers match.</div>';
  }
  $('buQ').addEventListener('input', debounce(drawBuyers, 120)); $('buSort').addEventListener('change', drawBuyers); $('buDays').addEventListener('change', () => { loadBuyers(); if (state.selBuyer) showBuyer(state.selBuyer); });
  $('buList').addEventListener('click', e => { const tr = e.target.closest('tr[data-id]'); if (tr) showBuyer(tr.dataset.id); });
  const fmtTime = s => s ? new Date(s * 1000).toISOString().replace('T', ' ').slice(0, 16) : '—';
  async function showBuyer(id) {
    state.selBuyer = id; drawBuyers(); const el = $('buDetail'); el.innerHTML = '<div class="ahc-empty">Loading…</div>';
    try {
      const d = await req('/auction-house/console/buyer.json?buyer=' + encodeURIComponent(id) + '&days=' + $('buDays').value);
      const over = d.rows.filter(r => r.markup_pct != null && r.markup_pct >= d.overpaid_threshold_pct && r.overpaid_by > 0), sel = new Set();
      const draw = () => {
        const chosen = d.rows.filter(r => sel.has(r.auction_id)), sum = chosen.reduce((s, r) => s + (r.overpaid_by || 0), 0);
        el.innerHTML = '<header style="display:block"><b>' + esc(d.buyer_name || id) + '</b> <small>' + d.purchases + ' purchase(s) · ' + fmt(d.spent) + 'g in ' + d.days + 'd · ' + d.overpaid_count + ' overpaid (' + fmt(d.overpaid_gil) + 'g above median)</small></header>' +
          '<div class="ahc-acts"><button class="b" data-x="refund-sel"' + (chosen.length ? '' : ' disabled') + '>Refund selected overpay (' + fmt(sum) + 'g)</button><button class="b" data-x="refund-all"' + (over.length ? '' : ' disabled') + '>Refund all overpaid (' + fmt(over.reduce((s, r) => s + r.overpaid_by, 0)) + 'g)</button><button class="b" data-x="pick-over"' + (over.length ? '' : ' disabled') + '>Select overpaid</button></div>' +
          '<div class="ahc-sales"><div class="ahc-sh"><b>Top items</b> <span class="mut">' + d.top_items.map(i => esc(nm(i.item_name)) + ' ×' + i.count).slice(0, 5).join(', ') + '</span></div><div class="ahc-sh"><b>Top sellers</b> <span class="mut">' + d.top_sellers.map(s => esc(s.seller_name || '#' + s.seller_id) + ' ×' + s.count).slice(0, 5).join(', ') + '</span></div></div>' +
          '<div class="ahc-scroll"><table><thead><tr><th><input type="checkbox" class="all"></th><th>Bought</th><th>Item</th><th>Seller</th><th class="n">Paid</th><th class="n">Median</th><th class="n">Markup</th></tr></thead><tbody>' +
          d.rows.map(r => '<tr><td>' + (r.overpaid_by > 0 && r.markup_pct != null ? '<input type="checkbox" data-a="' + r.auction_id + '"' + (sel.has(r.auction_id) ? ' checked' : '') + '>' : '') + '</td><td>' + esc(fmtTime(r.sold_at)) + '</td><td>' + link('item', r.item_id, nm(r.item_name)) + (r.stack ? ' <small>(stack)</small>' : '') + '</td><td>' + link('seller', r.seller_id, r.seller_name || '#' + r.seller_id) +
            '</td><td class="n">' + fmt(r.price) + 'g</td><td class="n">' + (r.median == null ? '—' : fmt(r.median) + 'g') + '</td><td class="n">' + markupChip(r.markup_pct) + '</td></tr>').join('') + '</tbody></table></div>';
      };
      el.onclick = e => {
        const t = e.target, lk = t.closest && t.closest('a.lk');
        if (lk) { e.preventDefault(); if (lk.dataset.seller) { tab('sellers'); showSeller(+lk.dataset.seller); } else { tab('items'); showItem(+lk.dataset.item); } return; }
        if (t.dataset.a) { t.checked ? sel.add(+t.dataset.a) : sel.delete(+t.dataset.a); draw(); }
        else if (t.classList.contains('all')) { d.rows.filter(r => r.overpaid_by > 0 && r.markup_pct != null).forEach(r => t.checked ? sel.add(r.auction_id) : sel.delete(r.auction_id)); draw(); }
        else if (t.dataset.x === 'pick-over') { over.forEach(r => sel.add(r.auction_id)); draw(); }
        else if (t.dataset.x === 'refund-sel') refundBuyer(d, d.rows.filter(r => sel.has(r.auction_id)));
        else if (t.dataset.x === 'refund-all') refundBuyer(d, over);
      };
      draw();
    } catch (e) { el.innerHTML = '<div class="ahc-empty">' + esc(e.message) + '</div>'; }
  }
  // Refund = deliver the overpaid difference as gil to the buyer's delivery box via the guarded reward path.
  async function refundBuyer(d, rows) {
    const amount = Math.min(999999999, rows.reduce((s, r) => s + (r.overpaid_by || 0), 0));
    if (!rows.length || amount < 1) return toast('Nothing to refund');
    let chars;
    try { chars = (await req('/auction-house/console/characters.json?q=' + encodeURIComponent(d.buyer_name || d.buyer_key))).rows || []; } catch (e) { return toast(e.message); }
    const ch = chars.find(c => (c.char_name || '').toLowerCase() === (d.buyer_name || '').toLowerCase());
    if (!ch) return toast('Cannot refund: "' + (d.buyer_name || d.buyer_key) + '" has no character record on this server, so there is no delivery box to send gil to.');
    const body = {recipient_mode: 'selected', character_ids: [ch.char_id], items: [{item_id: 65535, quantity: amount}]};
    try {
      const p = (await req('/auction-house/rewards/preview.json', body)).preview;
      drawer({title: 'Refund ' + fmt(amount) + 'g to ' + (d.buyer_name || d.buyer_key), label: 'Send ' + fmt(amount) + 'g',
        html: '<p style="padding:6px 8px;margin:0">Delivers <b>' + fmt(amount) + 'g</b> to the buyer\'s delivery box: the amount paid above the median sale price for ' + rows.length + ' purchase(s). The sales themselves are not reversed.</p><table><thead><tr><th>Item</th><th class="n">Paid</th><th class="n">Median</th><th class="n">Refund</th></tr></thead><tbody>' +
          rows.map(r => '<tr><td>' + esc(nm(r.item_name)) + '</td><td class="n">' + fmt(r.price) + 'g</td><td class="n">' + fmt(r.median) + 'g</td><td class="n">' + fmt(r.overpaid_by) + 'g</td></tr>').join('') + '</tbody></table>',
        run: async conf => { const r = (await req('/auction-house/rewards/execute.json', {...body, preview_token: p.preview_token, preview_id: p.preview_id, replay_id: p.replay_id, confirmation: conf})).result;
          return '<pre>' + r.status.toUpperCase() + ': ' + r.committed_recipients + ' delivered, ' + r.failed_recipients + ' failed\n' + esc(r.results.filter(x => x.status === 'failed').map(x => x.char_name + ': ' + x.error).join('\n')) + '</pre>'; }});
    } catch (e) { toast(e.message); }
  }

  window.loadBuyers = loadBuyers; window.loadArb = loadArb;

  /* ---------- Arbitrage: AH vs NPC vendor prices ---------- */
  state.arb = null; state.arbView = 'listings'; state.arbSel = new Set();
  async function loadArb() {
    const mp = Math.max(0, +$('arMin').value || 0);
    $('arBody').innerHTML = '<div class="ahc-empty">Scanning shops and listings…</div>';
    try { state.arb = await req('/auction-house/console/arbitrage.json?min_profit=' + mp); state.arbSel.clear(); drawArb(); } catch (e) { $('arBody').innerHTML = '<div class="ahc-empty">' + esc(e.message) + '</div>'; }
  }
  function drawArb() {
    const d = state.arb, v = state.arbView; if (!d) return;
    const s = d.summary;
    document.querySelectorAll('#arViews button').forEach(b => b.classList.toggle('pri', b.dataset.v === v));
    $('arCnt_listings').textContent = s.listing_count; $('arCnt_post').textContent = s.post_count; $('arCnt_loops').textContent = s.loop_count;
    $('arSummary').textContent = d.vendor_items + ' vendor items known' + (v === 'listings' ? ' · ' + fmt(s.listing_profit) + 'g total vendor profit across listings' : '');
    const bar = $('arActions'); bar.innerHTML = '';
    let h = '';
    if (v === 'listings') {
      const rows = d.listings;
      bar.innerHTML = '<button class="b pri" id="arClean" type="button">Clean up via Cleanup rules…</button><button class="b" id="arBuy" type="button">Admin Buy selected</button><button class="b" id="arRet" type="button">Return selected</button>' +
        '<small class="mut">Cleanup loads the “below vendor value” rule so you can preview and run it with a preset.</small>';
      h = rows.length ? '<table><thead><tr><th><input type="checkbox" class="all"></th><th>#</th><th>Item</th><th>Seller</th><th class="n">Qty</th><th class="n">Price</th><th class="n">Vendor pays</th><th class="n">Profit</th><th class="n">Age</th><th></th></tr></thead><tbody>' +
        rows.map(r => '<tr><td><input type="checkbox" data-a="' + r.auction_id + '"' + (state.arbSel.has(r.auction_id) ? ' checked' : '') + '></td><td>' + r.auction_id + '</td><td>' + esc(nm(r.item_name)) + '</td><td>' + esc(r.seller_name || '#' + r.seller_id) + '</td><td class="n">' + r.quantity + '</td><td class="n">' + fmt(r.asking_price) + 'g</td><td class="n">' + fmt(r.vendor_value) + 'g</td><td class="n"><b>+' + fmt(r.profit) + 'g</b></td><td class="n">' + days(ageOf(r)) + '</td><td><button class="b" data-pbuy="' + r.auction_id + '" type="button">Buy as…</button></td></tr>').join('') + '</tbody></table>'
        : '<div class="ahc-empty">No active listing is priced under its NPC buy-back value (min profit ' + fmt(d.min_profit) + 'g).</div>';
    } else if (v === 'post') {
      bar.innerHTML = '<small class="mut">Items an NPC sells for less than they fetch on the AH (30-day average sale when there are 2+ sales, otherwise the lowest single-item listing). “Add to Restock” queues them for posting.</small>';
      h = d.post.length ? '<table><thead><tr><th>Item</th><th>Vendor</th><th class="n">Vendor price</th><th class="n">AH low</th><th class="n">Avg sale</th><th class="n">Sales 30d</th><th class="n">Profit</th><th class="n">Margin</th><th></th></tr></thead><tbody>' +
        d.post.map(r => '<tr><td>' + esc(nm(r.item_name)) + '</td><td>' + esc((r.vendor || '') + (r.zone ? ' · ' + r.zone.replace(/_/g, ' ') : '')) + '</td><td class="n">' + fmt(r.vendor_price) + 'g</td><td class="n">' + (r.ah_low == null ? '—' : fmt(r.ah_low) + 'g') + '</td><td class="n">' + (r.avg_sale == null ? '—' : fmt(r.avg_sale) + 'g') + '</td><td class="n">' + r.sales_30d + '</td><td class="n"><b>+' + fmt(r.profit) + 'g</b></td><td class="n">' + r.margin_pct + '%</td><td><button class="b" data-radd="' + r.item_id + '" type="button">Add to Restock</button></td></tr>').join('') + '</tbody></table>'
        : '<div class="ahc-empty">No vendor-sold item currently has an AH price above its NPC price.</div>';
    } else {
      bar.innerHTML = '<small class="mut">Data check (the old <code>price_checker</code> rule): an NPC sells an item for less than any NPC pays for it, so a player can loop vendor → vendor for free gil. Fix in the shop script or <code>item_basic.BaseSell</code>.</small>';
      h = d.loops.length ? '<table><thead><tr><th>Item</th><th>Sold by</th><th class="n">NPC sells for</th><th class="n">NPC pays</th><th class="n">Loop profit</th></tr></thead><tbody>' +
        d.loops.map(r => '<tr><td>' + esc(nm(r.item_name)) + ' <small class="mut">#' + r.item_id + '</small></td><td>' + esc((r.vendor || '') + (r.zone ? ' · ' + r.zone.replace(/_/g, ' ') : '')) + '</td><td class="n">' + fmt(r.vendor_price) + 'g</td><td class="n">' + fmt(r.base_sell) + 'g</td><td class="n"><b>+' + fmt(r.profit) + 'g</b></td></tr>').join('') + '</tbody></table>'
        : '<div class="ahc-empty">No vendor loops found.</div>';
    }
    $('arBody').innerHTML = h;
    if ($('arClean')) $('arClean').onclick = () => { cuClear(); $('cuAgeDays').value = ''; $('cuVendor').value = '1'; tab('cleanup'); cuPreview(); };
    const picked = () => d.listings.filter(r => state.arbSel.has(r.auction_id));
    if ($('arBuy')) { $('arBuy').onclick = () => bulk('admin_buy', picked(), 'below vendor value'); $('arRet').onclick = () => bulk('return_to_seller', picked(), 'below vendor value'); }
  }
  $('arViews').onclick = e => { const b = e.target.closest('button[data-v]'); if (b) { state.arbView = b.dataset.v; drawArb(); } };
  $('arRefresh').onclick = loadArb;
  $('arBody').onclick = e => {
    const t = e.target;
    if (t.dataset.a) { t.checked ? state.arbSel.add(+t.dataset.a) : state.arbSel.delete(+t.dataset.a); }
    else if (t.classList.contains('all')) { state.arb.listings.forEach(r => t.checked ? state.arbSel.add(r.auction_id) : state.arbSel.delete(r.auction_id)); drawArb(); }
    else if (t.dataset.pbuy) { const r = state.arb.listings.find(x => x.auction_id === +t.dataset.pbuy); if (r) buyAs(r); }
    else if (t.dataset.radd) {
      const r = state.arb.post.find(x => x.item_id === +t.dataset.radd); if (!r) return;
      if (!state.restock.some(x => x.item_id === r.item_id)) state.restock.push({item_id: r.item_id, item_name: r.item_name, target: 3, price: r.reference, stack: false, level: null, category_id: r.category_id});
      state.rsPlan = null; drawRestock(); toast(nm(r.item_name) + ' added to Restock');
    }
  };
  /* ---------- boot ---------- */
  loadCats(); loadPresets(); loadDefault();
  drawRestock(); drawBundle(); drawChips();
  loadEnv(); loadTpls(); loadAll();
  { const h = location.hash.slice(1); tab(TOOLS[h] || $('p-' + h) ? h : 'economy'); }
  window.ahcOpen = (k, id, cat) => { if (cat != null) { state.cat = cat; drawItems(); } if (id) return k === 'items' ? showItem(id) : showSeller(id); };
})();

/* Embedded tools can ask the hub to jump to the Sellers tab pre-filtered (e.g. Economy -> Manage listings). */
window.addEventListener('message', e => {
  const m = e.data || {};
  if (e.origin !== location.origin || !['items', 'sellers'].includes(m.ahTab) || (!m.id && m.cat == null)) return;
  document.querySelector('#ahcTabs button[data-t="' + m.ahTab + '"]').click();
  window.ahcOpen && window.ahcOpen(m.ahTab, m.id ? +m.id : 0, m.cat);
});
