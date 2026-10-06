(() => {
  const root = document.getElementById('ahEconomy');
  if (!root) return;
  const $ = id => document.getElementById(id);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = v => v == null ? '—' : Number(v).toLocaleString();
  const pct = v => v == null ? '—' : `${Number(v).toFixed(1)}%`;
  const when = ts => ts ? new Date(ts * 1000).toLocaleString([], {dateStyle: 'medium', timeStyle: 'short'}) : '—';
  const day = ts => ts ? new Date(ts * 1000).toLocaleDateString() : '—';
  const days = () => $('aeDays').value;
  const S = {tab: 'overview', econ: null, agg: null, sellers: null, buyers: null, sel: {}, sort: {}, redraw: {}};
  const j = async url => { const r = await fetch(url, {headers: {Accept: 'application/json'}}); const d = await r.json().catch(() => ({})); if (!r.ok) throw new Error(d.detail || r.statusText); return d; };

  /* Sortable tables: a table opts into header sorting with opts.sid; column c[4] (optional) is the sort value. */
  function sortRows(rows, cols, sid, def) {
    const st = S.sort[sid] || (S.sort[sid] = {ci: def[0], dir: def[1]});
    const c = cols[st.ci], val = r => c[4] ? c[4](r) : r[c[1]];
    return rows.slice().sort((a, b) => {
      const x = val(a), y = val(b);
      const d = (typeof x === 'string' || typeof y === 'string') ? String(x ?? '').localeCompare(String(y ?? ''), undefined, {sensitivity: 'base'}) : (x ?? -Infinity) - (y ?? -Infinity);
      return d * st.dir;
    });
  }
  const arrow = (sid, i) => { const st = S.sort[sid]; return st && st.ci === i ? (st.dir > 0 ? ' \u25B2' : ' \u25BC') : ''; };
  function table(rows, cols, opts = {}) {
    if (!rows.length) return '<div class="ahc-empty">No data in this window.</div>';
    return `<table><thead><tr>${cols.map((c, i) => opts.sid ? `<th class="${c[3] || ''} srt" data-sid="${opts.sid}" data-ci="${i}">${esc(c[0])}${arrow(opts.sid, i)}</th>` : `<th class="${c[3] || ''}">${esc(c[0])}</th>`).join('')}</tr></thead><tbody>${rows.map((r, i) =>
      `<tr class="${opts.click ? 'clk' : ''} ${opts.sel && opts.sel(r) ? 'sel' : ''}" data-i="${i}">${cols.map(c => `<td class="${c[3] || ''}">${c[2] ? c[2](r[c[1]], r) : esc(r[c[1]] ?? '—')}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  }
  const tiles = t => `<div class="ahc-tiles">${t.map(x => `<div class="ahc-tile"><b>${x[1]}</b><span>${esc(x[0])}</span></div>`).join('')}</div>`;
  function bars(series) {
    if (!series.length) return '<div class="ahc-empty">No sales in this window.</div>';
    const max = Math.max(...series.map(s => s.gil), 1);
    return `<div class="ahc-spark">${series.map(s => `<i style="height:${Math.max(4, s.gil / max * 100)}%" title="${esc(s.day)}: ${s.count} sales, ${fmt(s.gil)} gil"></i>`).join('')}</div><small class="mut">${esc(series[0].day)} → ${esc(series[series.length - 1].day)} · gil per day</small>`;
  }
  const nm = v => String(v ?? '').replace(/_/g, ' ');
  const person = role => v => v ? `<a href="#" class="ae-p" data-role="${role}" data-name="${esc(v)}">${esc(v)}</a>` : '—';
  const itemLink = (v, r) => `<a href="#" class="ae-item" data-item="${r.item_id}" data-name="${esc(v)}">${esc(v)}</a> <small>#${r.item_id}</small>`;
  const avg = (v, r) => fmt(r.count ? Math.round(r.gil / r.count) : null);
  const itemCols = [['Item', 'item_name', itemLink], ['Sold', 'count', fmt, 'n'], ['Total gil', 'gil', fmt, 'n'], ['Avg', 'count', avg, 'n']];
  const cpCols = lbl => [[lbl, 'name', person(lbl.toLowerCase())], ['Deals', 'count', fmt, 'n'], ['Gil', 'gil', fmt, 'n']];
  const recentCols = [['When', 'sold_at', when], ['Item', 'item_name', (v, r) => `${esc(v)}${r.stack ? ' (stack)' : ''}`], ['Seller', 'seller', person('seller')], ['Buyer', 'buyer', person('buyer')], ['Asked', 'asking', fmt, 'n'], ['Paid', 'price', fmt, 'n']];

  function detailHtml(d, kind) {
    const s = d.summary || {};
    const lbl = kind === 'buyer' ? 'Sellers' : 'Buyers';
    const sides = kind === 'category' || kind === 'item'
      ? `<div class="ahc-card"><h3>Top sellers</h3>${table(d.top_sellers || [], cpCols('Seller'))}</div><div class="ahc-card"><h3>Top buyers</h3>${table(d.top_buyers || [], cpCols('Buyer'))}</div>`
      : `<div class="ahc-card"><h3>Top ${lbl.toLowerCase()}</h3>${table(d.counterparties || [], cpCols(lbl))}</div>`;
    const itemsCard = kind === 'item' ? '' : `<div class="ahc-card"><h3>Top items</h3>${table(d.top_items || [], itemCols)}</div>`;
    const head = kind === 'item' ? [['Sales', fmt(s.sold_count)], ['Gil traded', fmt(s.sold_gil)], ['Avg price', fmt(s.avg_price)], ['Median price', fmt(s.median_price)], ['Listed now', fmt(s.active_count)], ['Asking total', fmt(s.active_value)], ['Last sale', day(s.last)]]
      : kind === 'buyer'
      ? [['Purchases', fmt(s.sold_count)], ['Gil spent', fmt(s.sold_gil)], ['Avg price', fmt(s.avg_price)], ['Distinct items', fmt(s.distinct_items)], ['Sellers dealt with', fmt(s.counterparties)], ['Last purchase', day(s.last)]]
      : [['Sales', fmt(s.sold_count)], ['Gil sold', fmt(s.sold_gil)], ['Avg price', fmt(s.avg_price)], ['Active listings', fmt(s.active_count)], ['Active value', fmt(s.active_value)], ['Buyers', fmt(s.counterparties)], ['Last sale', day(s.last)]];
    return `${tiles(head)}<div class="ahc-card"><h3>Sales per day</h3>${bars(d.series || [])}</div>
      <div class="ahc-grid" style="margin-top:8px">${itemsCard}${sides}</div>
      <div class="ahc-card" style="margin-top:8px"><h3>Recent transactions</h3>${table(d.recent || [], recentCols)}</div>`;
  }

  async function showDetail(kind, key, label, el, extra = '') {
    el.innerHTML = '<div class="ahc-empty">Loading…</div>';
    try {
      const d = await j(`/auction-house/intel/detail.json?kind=${kind}&key=${encodeURIComponent(key)}&days=${days()}`);
      el.innerHTML = `<div style="padding:8px"><div class="ahc-bar"><h3 style="margin:0;flex:1">${esc(d.label || label)}</h3>${extra}</div>${detailHtml(d, kind)}</div>`;
      el.querySelectorAll('[data-person]').forEach(b => b.onclick = () => { tab('people'); openPerson(+b.dataset.person); });
    } catch (e) { el.innerHTML = `<div class="ahc-empty">${esc(e.message)}</div>`; }
  }

  /* ---- list panes (sellers / buyers) ---- */
  async function loadLedger(role) {
    const data = await j(`/auction-house/intel/ledger.json?role=${role}&days=${days()}&limit=1000`);
    S[role + 's'] = data.rows;
    drawLedger(role);
  }
  function selectLedger(role, r) {
    const key = role + 's';
    S.sel[role] = r.key; drawLedger(role);
    const extra = (r.accid ? `<button class="b" data-person="${r.accid}">Player profile</button>` : '') + (role === 'seller' ? `<button class="b" data-hub="sellers" data-id="${esc(r.key)}">Manage listings</button>` : '');
    showDetail(role, r.key, r.name, $(key + 'Detail'), extra);
  }
  function drawLedger(role) {
    const key = role + 's', rows = (S[key] || []).slice();
    const q = $(key + 'Q').value.trim().toLowerCase();
    const econ = new Map(((S.econ || {}).seller_rows || []).map(r => [String(r.seller_id), r]));
    const cols = role === 'seller'
      ? [['Seller', 'name', (v, r) => `${esc(v)} <small>#${r.char_id}</small>`], ['Sales', 'sold_count', fmt, 'n'], ['Gil sold', 'sold_gil', fmt, 'n'], ['Active', 'active_count', fmt, 'n'], ['Active value', 'active_value', fmt, 'n'],
         ['Sell-through', 'key', k => pct((econ.get(k) || {}).sell_through_pct), 'n', r => (econ.get(r.key) || {}).sell_through_pct], ['Stale', 'key', k => fmt((econ.get(k) || {}).stale_active_count), 'n', r => (econ.get(r.key) || {}).stale_active_count]]
      : [['Buyer', 'name'], ['Purchases', 'sold_count', fmt, 'n'], ['Gil spent', 'sold_gil', fmt, 'n'], ['Avg', 'avg_price', fmt, 'n'], ['Last', 'last', day, '', r => r.last]];
    const f = sortRows(rows.filter(r => !q || r.name.toLowerCase().includes(q) || String(r.char_id) === q), cols, key, [role === 'seller' ? 2 : 2, -1]);
    S.redraw[key] = () => drawLedger(role);
    $(key + 'List').innerHTML = (role === 'buyer' ? '<div class="ahc-acts"><small>Matched by character name — the AH table stores no buyer id.</small></div>' : '') +
      table(f, cols, {click: 1, sel: r => S.sel[role] === r.key, sid: key}) + `<div class="ahc-acts"><small>${fmt(f.length)} shown</small></div>`;
    $(key + 'List').querySelectorAll('tbody tr').forEach(tr => tr.onclick = () => selectLedger(role, f[+tr.dataset.i]));
  }
  /* jump from a name link anywhere to that seller's / buyer's page */
  async function goPerson(role, name) {
    const key = role + 's';
    tab(key);
    if (!S[key]) await loadLedger(role);
    const r = S[key].find(x => x.name.toLowerCase() === String(name).toLowerCase());
    if (r) { $(key + 'Q').value = ''; selectLedger(role, r); }
    else { $(key + 'Q').value = name; drawLedger(role); $(key + 'Detail').innerHTML = `<div class="ahc-empty">${esc(name)} has no ${role} activity in this window.</div>`; }
  }

  /* ---- categories ---- */
  function drawCategories() {
    const q = $('categoriesQ').value.trim().toLowerCase();
    const cols = [['Category', 'category_path', v => `<a href="#" class="ae-cat" data-cat="${esc(v || '')}" title="Browse every item in this category">${esc(v || 'Unknown')}</a>`],
      ['Active', 'active_listings', fmt, 'n'], ['Sold', 'sold_count', fmt, 'n'], ['Gil', 'sold_gil', fmt, 'n'],
      ['Sell-thru', 'sell_through_pct', pct, 'n'], ['Median sale', 'median_sale_price', fmt, 'n'],
      ['Time to sale', 'median_hours_to_sale', v => v == null ? '—' : v < 1 ? Math.round(v * 60) + 'm' : v < 48 ? v.toFixed(1) + 'h' : (v / 24).toFixed(1) + 'd', 'n'],
      ['Signal', 'supply_signal', v => `<small>${esc(String(v).replace(/_or_insufficient_evidence/, '').replace(/_/g, ' '))}</small>`]];
    const f = sortRows(((S.econ || {}).category_rows || []).filter(r => !q || (r.category_path || '').toLowerCase().includes(q)), cols, 'categories', [0, 1]);
    S.redraw.categories = drawCategories;
    $('categoriesList').innerHTML = table(f, cols, {click: 1, sel: r => S.sel.cat === r.category_id, sid: 'categories'});
    $('categoriesList').querySelectorAll('tbody tr').forEach(tr => tr.onclick = () => {
      const r = f[+tr.dataset.i]; S.sel.cat = r.category_id; drawCategories();
      const b = r.signal_basis || {};
      showDetail('category', r.category_id, r.category_path, $('categoriesDetail'),
        `<button class="b pri" data-cat="${esc(r.category_path || '')}">Browse items</button><span class="ahc-chip">${esc(String(r.supply_signal).replace(/_/g, ' '))}</span><small title="${esc(b.heuristic || '')}">active ${fmt(b.active_count)} · sales ${fmt(b.recent_sales)} · stale ${pct(b.stale_ratio_pct)}</small>`);
    });
  }

  /* ---- overview ---- */
  function activityChart(ser, key) {
    if (!ser.length) return '<div class="ahc-empty">No activity in this window.</div>';
    const evDay = {}; ((S.impact || {}).events || []).forEach(v => (evDay[v.day] = evDay[v.day] || []).push(v.label));
    const max = Math.max(...ser.map(s => s[key]), 1), lab = {sales: 'sales', listed: 'new listings', gil: 'gil'}[key];
    return `<div class="ahc-spark ae-big">${ser.map(s => `<i${evDay[s.day] ? ' class="ae-ev"' : ''} style="height:${Math.max(3, s[key] / max * 100)}%" title="${esc(s.day)}: ${fmt(s[key])} ${lab}${evDay[s.day] ? ' — admin: ' + esc(evDay[s.day].join(', ')) : ''}"></i>`).join('')}</div><small class="mut">${esc(ser[0].day)} → ${esc(ser[ser.length - 1].day)} · ${lab} per day (UTC) · peak ${fmt(max)}${Object.keys(evDay).length ? ' · <span class="ae-evkey">▮</span> orange bars = days with admin actions' : ''}</small>`;
  }
  function adminCard() {
    const evs = (S.impact || {}).events || [];
    const cols = [['When (UTC)', 'ts', v => new Date(v * 1000).toISOString().slice(0, 16).replace('T', ' ')], ['Action', 'label', v => esc(v)], ['Item', 'item_name', (v, r) => r.item_id ? itemLink(v, r) : '<span class="mut">—</span>'],
      ['Median before', 'before_median', v => v == null ? '—' : fmt(Math.round(v)), 'n'], ['Median after', 'after_median', v => v == null ? '—' : fmt(Math.round(v)), 'n'],
      ['Change', 'change_pct', (v, r) => v == null ? (r.item_id ? '<small class="mut">not enough sales</small>' : '<small class="mut">market-wide</small>') : `<b class="${v > 0 ? 'ae-up' : 'ae-dn'}">${v > 0 ? '▲' : '▼'} ${Math.abs(v).toFixed(1)}%</b>`, 'n']];
    S.redraw.admin = drawOverview;
    const rows = sortRows(evs, cols, 'admin', [0, -1]).slice(0, 15);
    return `<div class="ahc-card" style="margin-top:8px"><h3 style="margin:0 0 4px">Admin actions <small class="mut ae-tip" title="Seeds, restocks, Admin Buys, returns and reward deliveries made through this toolkit (completed ones only). Median before/after = the item's median sale price in the 7 days either side. Other market changes happen at the same time, so read it as a pointer, not proof.">toolkit actions vs. price</small></h3>${rows.length ? table(rows, cols, {sid: 'admin'}) : '<div class="ahc-empty">No completed admin actions in this window.</div>'}</div>`;
  }
  function baselineStrip() {
    const b = (S.snaps || {}).baselines;
    if (!b) return '';
    const names = {active_listings: 'Active listings', active_gil: 'Asking gil', sales_7d: 'Sales (7d)', sell_through_7d: 'Sell-through %'};
    if (b.points < b.min_points) return `<p class="mut" style="margin:6px 0 0"><small>Baselines: building (${b.points} of ${b.min_points} earlier snapshots). Once there are ${b.min_points} days of history each figure is compared with its usual range and flagged if it falls outside it.</small></p>`;
    return `<div class="ahc-tiles" style="margin-top:8px">${Object.entries(b.metrics).map(([k, m]) => {
      const cls = m.status === 'high' ? 'ae-up' : m.status === 'low' ? 'ae-dn' : '';
      return `<div class="ahc-tile" title="Usual range ${fmt(m.low)} – ${fmt(m.high)} (median of the previous snapshots ± 2× typical spread)"><b class="${cls}">${m.status === 'normal' ? 'Normal' : m.status === 'high' ? 'Above usual' : 'Below usual'}</b><span>${names[k]}</span><small class="mut">now ${fmt(m.latest)} · usual ${fmt(m.baseline)}${m.deviation_pct == null ? '' : ' (' + (m.deviation_pct >= 0 ? '+' : '') + m.deviation_pct + '%)'}</small></div>`;
    }).join('')}</div>`;
  }
  function supplyDeltas(sn) {
    const last = sn[sn.length - 1];
    if (!last) return '';
    const day = d => Date.parse(d + 'T00:00:00Z') / 86400000, want = day(last.day) - 7;
    // the snapshot nearest 7 days back; with a shorter history the oldest one is used and the span is stated
    const earlier = sn.slice(0, -1);
    const base = earlier.length ? earlier.reduce((b, x) => Math.abs(day(x.day) - want) < Math.abs(day(b.day) - want) ? x : b) : null;
    const span = base ? Math.round(day(last.day) - day(base.day)) : 0;
    const items = [['Active listings', 'active_listings', fmt, false, false, 'More listings = more supply. Rising is shown amber, since more supply can mean slower sales.'], ['Asking gil', 'active_gil', fmt, false, false, 'Total gil asked across all active listings.'],
      ['Sell-through %', 'sell_through_7d', v => v == null ? '—' : v + '%', true, true, 'Share of the last 7 days offered listings that sold. Change is in percentage points.'], ['Sales (7d)', 'sales_7d', fmt, false, true, 'Completed sales in the 7 days before each snapshot.']];
    return `<div class="ahc-tiles ae-kpis" style="margin:8px 0">${items.map(([label, k, f, pp, goodUp, tip]) => {
      const a = last[k], b = base ? base[k] : null;
      let d = '<small class="mut">needs a second snapshot</small>';
      if (base && a != null && b != null) {
        const diff = pp ? a - b : (b ? (a - b) / b * 100 : null);
        if (diff == null) d = '<small class="mut">no prior value</small>';
        else {
          const good = goodUp ? diff > 0 : null, cls = Math.abs(diff) < 0.5 ? 'mut' : good === null ? 'ae-warn' : good ? 'ae-up' : 'ae-dn';
          d = `<small class="${cls}">${diff > 0 ? '▲' : diff < 0 ? '▼' : '='} ${Math.abs(diff).toFixed(1)}${pp ? ' pts' : '%'} vs ${span}d ago</small>`;
        }
      }
      return `<div class="ahc-tile ae-kpi" title="${esc(tip)}"><b>${f(a)}</b><span>${label}</span>${d}</div>`;
    }).join('')}</div>`;
  }
  const ANOM = {price_shift: 'Price shift', volume_spike: 'Volume spike', listing_overpriced: 'Overpriced listing', listing_underpriced: 'Underpriced listing', seller_flood: 'Seller flood'};
  function anomalyCard() {
    const a = S.anom; if (!a) return '';
    const sev = v => `<b class="${v >= 3 ? 'ae-dn' : v === 2 ? '' : 'mut'}" title="3 = strongest, 1 = mild">${'●'.repeat(v)}</b>`;
    const who = (v, r) => r.item_id ? itemLink(r.item_name, r) + (r.seller_name ? ` <small>by ${esc(r.seller_name)}</small>` : '') : esc(r.seller_name || '—');
    const chips = Object.entries(a.by_kind).map(([k, n]) => `<span class="ahc-chip2">${esc(ANOM[k] || k)}: ${n}</span>`).join(' ') || '<span class="mut">none</span>';
    return `<div class="ahc-card"><h3 title="Each item, listing and seller is compared with its own history (median and MAD), never with other items. Items with fewer than ${a.rules.min_history_sales} earlier sales are not judged.">Anomalies <small class="mut">last ${a.days} days vs the ${a.history_days}-day history</small></h3>
      <p style="margin:0 0 6px">${a.count} finding(s) ${chips}</p>${a.findings.length ? table(a.findings, [['', 'severity', sev], ['Type', 'kind', v => esc(ANOM[v] || v)], ['What', 'item_name', who], ['Detail', 'detail', v => esc(v)]]) : '<div class="ahc-empty">Nothing unusual — prices, volume and listing behaviour are all within their normal range.</div>'}</div>`;
  }
  function supplyCard() {
    const sn = (S.snaps || {}).series || [], k = S.supplyKey || 'active_listings';
    const opts = [['active_listings', 'Active listings'], ['active_gil', 'Asking gil'], ['sell_through_7d', 'Sell-through %']];
    const vals = sn.map(x => x[k] ?? 0), max = Math.max(...vals, 1);
    const last = sn[sn.length - 1], prev = sn[sn.length - 2];
    const dl = last && prev && prev[k] != null && last[k] != null ? ` · ${last[k] - prev[k] >= 0 ? '+' : ''}${fmt(Math.round((last[k] - prev[k]) * 10) / 10)} vs previous snapshot` : '';
    const body = sn.length < 2
      ? `<div class="ahc-empty">${sn.length ? 'One snapshot so far.' : 'No snapshots yet.'} The server keeps no supply history, so it is recorded once a day from now on; a trend appears after the second day. Use "Record now" to add today's.</div>`
      : `<div class="ahc-spark ae-big">${sn.map((x, i) => `<i style="height:${Math.max(3, vals[i] / max * 100)}%" title="${esc(x.day)}: ${fmt(vals[i])}"></i>`).join('')}</div><small class="mut">${esc(sn[0].day)} → ${esc(last.day)} · ${sn.length} snapshots · latest ${fmt(last[k] ?? 0)}${dl}</small>`;
    return `<div class="ahc-card" style="margin-top:8px"><div class="ahc-bar"><h3 style="margin:0;flex:1">Supply history <small class="mut ae-tip" title="Recorded once a day by the toolkit (the game server does not keep this). Sell-through = share of the last 7 days' offered listings that sold.">daily snapshots</small></h3><span>${opts.map(o => `<button class="b${k === o[0] ? ' pri' : ''}" data-supply="${o[0]}">${o[1]}</button>`).join(' ')}</span><button class="b" id="aeSnapNow" title="Save today's supply figures now (writes only to the toolkit's own database)">Record now</button></div>${supplyDeltas(sn)}${body}${baselineStrip()}</div>`;
  }
  function drawOverview() {
    const e = S.econ || {}, t = e.totals || {}, g = S.agg;
    const top = (t.top_items_by_realized_volume || []).slice(0, 6).map(r => ({...r, gil: r.sold_value, count: r.sold_count}));
    const act = (t.top_items_by_active_exposure || []).slice(0, 6).map(r => ({...r, gil: r.active_value, count: r.active_count}));
    const tl = [['Active listings', fmt(t.active_listings)], ['Active asking gil', fmt(t.active_asking_value)], ['Sales in window', fmt(t.sold_count)], ['Gil traded', fmt(t.sold_gil)], ['Sell-through', pct(t.sell_through_pct)], ['Stale active', fmt(t.stale_active_count)], ['Median sale', fmt(t.median_sale_price)]];
    let listed = '';
    if (g) {
      const ones = g.items.filter(i => i.listings === 1).length, heavy = g.items.filter(i => i.listings >= 10).length;
      tl.push(['Distinct items', fmt(g.items.length)], ['Sellers', fmt(g.sellers.length)], ['Single-listing items', fmt(ones)], ['Deep stock (10+)', fmt(heavy)], ['Oldest listing', g.oldest_days == null ? '—' : g.oldest_days.toFixed(0) + 'd']);
      const link = i => ({item_id: i.item_id, item_name: nm(i.item_name)});
      const mostListed = [...g.items].sort((x, y) => y.listings - x.listings).slice(0, 6).map(i => ({...link(i), listings: i.listings, low: i.min_price}));
      const topSellers = g.sellers.slice(0, 6).map(s => ({name: s.seller_name || '#' + s.seller_id, listings: s.listings, value: s.value}));
      const oldest = [...g.items].filter(i => (i.oldest_days || 0) >= 1).sort((x, y) => y.oldest_days - x.oldest_days).slice(0, 6).map(i => ({...link(i), age: i.oldest_days, listings: i.listings}));
      listed = `<div class="ahc-card"><h3>Most listed items</h3>${table(mostListed, [['Item', 'item_name', itemLink], ['Listings', 'listings', fmt, 'n'], ['Lowest', 'low', fmt, 'n']])}</div>
        <div class="ahc-card"><h3>Top sellers (active)</h3>${table(topSellers, [['Seller', 'name', person('seller')], ['Listings', 'listings', fmt, 'n'], ['Asking', 'value', fmt, 'n']])}</div>
        <div class="ahc-card"><h3>Oldest listings</h3>${table(oldest, [['Item', 'item_name', itemLink], ['Age', 'age', v => v.toFixed(0) + 'd', 'n'], ['Listings', 'listings', fmt, 'n']])}</div>`;
    }
    const ag = Object.entries(t.aging_buckets || {}), mx = Math.max(1, ...ag.map(x => x[1]));
    const aging = `<div class="ahc-card"><h3>Listing age</h3>${ag.map(([k, v]) => `<div class="ae-age"><span>${esc(({lt_7d: '< 7d', '7_30d': '7–30d', '30_90d': '30–90d', '90d_plus': '90d+'})[k] || k.replace(/_/g, ' '))}</span><i style="width:${Math.max(2, v / mx * 100)}%"></i><b>${fmt(v)}</b></div>`).join('') || '<div class="ahc-empty">No listings.</div>'}</div>`;
    const tr = S.trends;
    let trendHtml = '';
    if (tr) {
      const c = tr.current, p = tr.prior, ser = tr.series;
      const dropTl = new Set(['Sales in window', 'Gil traded', 'Median sale']);
      for (let i = tl.length - 1; i >= 0; i--) if (dropTl.has(tl[i][0])) tl.splice(i, 1);
      const delta = (a, b, lowerBetter) => {
        if (a == null || !b) return '<small class="mut">no prior data</small>';
        const d = (a - b) / b * 100, good = lowerBetter ? d < 0 : d > 0;
        return `<small class="${Math.abs(d) < 0.5 ? 'mut' : good ? 'ae-up' : 'ae-dn'}">${d > 0 ? '▲' : d < 0 ? '▼' : '='} ${Math.abs(d).toFixed(1)}% vs prior ${tr.days}d</small>`;
      };
      const spark = key => ser.length > 1 ? `<div class="ahc-spark ae-mini">${ser.map(s => { const m = Math.max(...ser.map(x => x[key]), 1); return `<i style="height:${Math.max(6, s[key] / m * 100)}%"></i>`; }).join('')}</div>` : '';
      const hrs = v => v == null ? '—' : v < 1 ? Math.round(v * 60) + 'm' : v < 48 ? v.toFixed(1) + 'h' : (v / 24).toFixed(1) + 'd';
      const kpi = (label, val, d, sp) => `<div class="ahc-tile ae-kpi"><b>${val}</b><span>${esc(label)}</span>${d}${sp || ''}</div>`;
      trendHtml = `<div class="ahc-tiles ae-kpis">${kpi('Sales', fmt(c.sales), delta(c.sales, p.sales), spark('sales'))}${kpi('Gil volume', fmt(c.gil), delta(c.gil, p.gil), spark('gil'))}${kpi('New listings', fmt(c.listed), delta(c.listed, p.listed), spark('listed'))}${kpi('Unique buyers', fmt(c.unique_buyers), delta(c.unique_buyers, p.unique_buyers))}${kpi('Unique sellers', fmt(c.unique_sellers), delta(c.unique_sellers, p.unique_sellers))}${kpi('Median sale', fmt(c.median_sale), delta(c.median_sale, p.median_sale))}${kpi('Median time to sale', hrs(c.median_hours_to_sale), delta(c.median_hours_to_sale, p.median_hours_to_sale, true))}</div>
        <div class="ahc-card"><div class="ahc-bar"><h3 style="margin:0;flex:1">Market activity <small class="mut ae-tip" title="Daily totals for the selected window. Use the buttons to switch what the bars show.">per day</small></h3><span id="aeMetric">${[['sales', 'Sales'], ['listed', 'New listings'], ['gil', 'Gil volume']].map(m => `<button class="b${(S.metric || 'sales') === m[0] ? ' pri' : ''}" data-metric="${m[0]}" title="Chart ${m[1].toLowerCase()} per day">${m[1]}</button>`).join(' ')}</span></div>${activityChart(ser, S.metric || 'sales')}</div>`;
    }
    const moversHtml = (() => {
      if (!tr) return '';
      const cols = [['Item', 'item_name', itemLink], ['Change', 'change_pct', v => `<b class="${v > 0 ? 'ae-up' : 'ae-dn'}">${v > 0 ? '▲' : '▼'} ${Math.abs(v).toFixed(1)}%</b>`, 'n'], ['Median now', 'current_median', fmt, 'n'], ['Median before', 'prior_median', fmt, 'n'],
        ['Sales (now / before)', 'current_sales', (v, r) => `${r.current_sales} / ${r.prior_sales}${r.reliable ? '' : ' <small title="Too few sales to trust this change">⚠ thin</small>'}`, 'n']];
      S.redraw.movers = drawOverview;
      const rows = sortRows(tr.movers.filter(m => S.thin || m.reliable), cols, 'movers', [1, -1]).slice(0, 12);
      return `<div class="ahc-card" style="margin-top:8px"><div class="ahc-bar"><h3 style="margin:0;flex:1">Price movers <small class="mut">median sale price vs prior ${tr.days}d</small></h3><label style="flex-direction:row;gap:4px;align-items:center"><input type="checkbox" id="aeThin"${S.thin ? ' checked' : ''}> include thin evidence (&lt; ${tr.min_mover_sales} sales)</label></div>${table(rows, cols, {sid: 'movers'})}</div>`;
    })();
    const Q = e.queues;
    const queuesHtml = !Q ? '' : (() => {
      const st = v => v == null ? '—' : v.toFixed(0) + '%';
      const card = (title, key, cols, hint) => `<div class="ahc-card"><h3>${title} <span class="ahc-chip">${fmt(Q.counts[key])}</span></h3><small class="mut" title="${esc(Q.rules[key])}">${hint}</small>${Q[key].length ? table(Q[key], cols) : '<div class="ahc-empty">None right now.</div>'}</div>`;
      const item = ['Item', 'item_name', itemLink];
      return `<h3 style="margin:12px 0 4px">Where to look <small class="mut">click an item for its page; thresholds shown on hover</small></h3><div class="ahc-grid ahc-ov">` +
        card('Needs supply', 'needs_supply', [item, ['Listed', 'active', fmt, 'n'], ['Sold', 'sold', fmt, 'n']], 'Selling, but almost nothing listed') +
        card('Oversupplied', 'oversupplied', [item, ['Listed', 'active', fmt, 'n'], ['Sold', 'sold', fmt, 'n'], ['Sell-thru', 'sell_through_pct', st, 'n']], 'Lots listed, few selling') +
        card('Stagnant', 'stagnant', [item, ['Stale', 'stale', fmt, 'n'], ['Oldest', 'oldest_days', v => v.toFixed(0) + 'd', 'n']], 'Old listings, no sales in window') +
        card('Seller concentration', 'concentration', [item, ['Top seller', 'top_seller', person('seller')], ['Share', 'share_pct', v => v.toFixed(0) + '%', 'n']], 'One seller holds most of the supply') + '</div>';
    })();
    $('e-overview').innerHTML = trendHtml + anomalyCard() + supplyCard() + adminCard() + tiles(tl) + queuesHtml + moversHtml +
      `<div class="ahc-grid ahc-ov"><div class="ahc-card"><h3>Best-selling items (by gil)</h3>${table(top, itemCols)}</div><div class="ahc-card"><h3>Largest active exposure</h3>${table(act, [['Item', 'item_name', itemLink], ['Listed', 'count', fmt, 'n'], ['Asking total', 'gil', fmt, 'n'], ['Avg ask', 'count', avg, 'n']])}</div>${aging}${listed}</div>
      <p class="mut"><small>Sample ${fmt(e.sample_rows)} / ${fmt(e.sample_limit)}${e.sample_truncated ? ' — limit reached' : ''}. Stale = listed ≥ ${fmt(e.stale_threshold_days)} days. Supply signals are heuristics, not conclusions about players.</small></p>`;
  }

  /* ---- players & accounts ---- */
  async function searchPeople() {
    const q = $('peopleQ').value.trim(); if (!q) return;
    $('peopleList').innerHTML = '<div class="ahc-empty">Searching…</div>';
    try {
      const rows = (await j(`/auction-house/intel/people.json?q=${encodeURIComponent(q)}`)).rows;
      $('peopleList').innerHTML = rows.length ? `<table><tbody>${rows.map(a => `<tr class="clk" data-a="${a.accid}"><td><b>${esc(a.login || '(no login)')}</b> <small>acct #${a.accid}</small><br><small>${a.characters.map(c => esc(c.name)).join(', ') || 'no characters'}</small></td></tr>`).join('')}</tbody></table>` : '<div class="ahc-empty">No match.</div>';
      $('peopleList').querySelectorAll('tr').forEach(tr => tr.onclick = () => openPerson(+tr.dataset.a));
    } catch (e) { $('peopleList').innerHTML = `<div class="ahc-empty">${esc(e.message)}</div>`; }
  }
  async function openPerson(accid) {
    const el = $('peopleDetail'); el.innerHTML = '<div class="ahc-empty">Loading…</div>';
    try {
      const d = await j(`/auction-house/intel/person.json?accid=${accid}&days=${days()}`);
      const a = d.account, ip = d.ip;
      const chars = c => c.map(x => `${esc(x.name)} <small>#${x.char_id}</small>`).join(', ') || '—';
      const ipHtml = !ip.available ? '<div class="ahc-empty">This server has no <code>account_ip_record</code> table.</div>'
        : !ip.records.length ? '<div class="ahc-empty">No login IPs recorded for this account. Linked-account detection needs IP history, so none can be shown.</div>'
        : table(ip.records, [['IP', 'ip', v => `<code>${esc(v)}</code>`], ['Logins', 'logins', fmt, 'n'], ['First', 'first'], ['Last', 'last']]);
      const linked = ip.linked.length ? table(ip.linked, [['Account', 'login', (v, r) => `<a href="#" data-acc="${r.accid}">${esc(v)}</a> <small>#${r.accid}</small>`], ['Characters', 'characters', chars], ['Shared IPs', 'shared_ips', v => v.map(x => `<code>${esc(x)}</code>`).join(' ')]]) : '<div class="ahc-empty">No other accounts share this account\'s IPs.</div>';
      const hist = (h, title) => `<h3 style="margin:10px 0 4px">${title}</h3><div class="ahc-grid"><div class="ahc-card"><h3>Selling</h3>${tiles([['Sales', fmt(h.selling.summary.sold_count)], ['Gil earned', fmt(h.selling.summary.sold_gil)], ['Active', fmt(h.selling.summary.active_count)]])}${bars(h.selling.series)}</div>
        <div class="ahc-card"><h3>Buying</h3>${tiles([['Purchases', fmt(h.buying.summary.sold_count)], ['Gil spent', fmt(h.buying.summary.sold_gil)], ['Sellers', fmt(h.buying.summary.counterparties)]])}${bars(h.buying.series)}</div></div>
        <div class="ahc-card" style="margin-top:8px"><h3>Recent sales</h3>${table(h.selling.recent.slice(0, 15), recentCols)}</div><div class="ahc-card" style="margin-top:8px"><h3>Recent purchases</h3>${table(h.buying.recent.slice(0, 15), recentCols)}</div>`;
      el.innerHTML = `<div style="padding:8px"><div class="ahc-bar"><h3 style="margin:0;flex:1">${esc(a.login)} <small>account #${a.accid}</small></h3><select id="peopleWin"><option value="0">All time</option><option value="30">30 days</option><option value="7">7 days</option></select></div>
        <div class="ahc-card" style="margin:8px 0"><h3>Characters on this account</h3>${chars(a.characters)}</div>
        <div class="ahc-grid"><div class="ahc-card"><h3>Login IPs</h3>${ipHtml}</div><div class="ahc-card"><h3>Linked accounts (same IP)</h3>${linked}</div></div>
        ${hist(d.ah, 'AH activity — this account')}${d.ah_with_linked ? hist(d.ah_with_linked, 'AH activity — including linked accounts') : ''}</div>`;
      $('peopleWin').value = String(d.days);
      $('peopleWin').onchange = e => { $('aeDays').value = [...$('aeDays').options].some(o => o.value === e.target.value) ? e.target.value : '0'; openPerson(accid); };
      el.querySelectorAll('[data-acc]').forEach(x => x.onclick = ev => { ev.preventDefault(); openPerson(+x.dataset.acc); });
    } catch (e) { el.innerHTML = `<div class="ahc-empty">${esc(e.message)}</div>`; }
  }

  /* ---- item page (opened from any item link) ---- */
  function hub(tabName, id) {
    if (parent !== window) parent.postMessage({ahTab: tabName, id}, '*');
    else location.href = '/auction-house#' + tabName;
  }
  function hubCat(path) {
    if (parent !== window) parent.postMessage({ahTab: 'items', cat: path}, '*');
    else location.href = '/auction-house#items';
  }
  function openItem(id, name) {
    S.back = S.tab === 'item' ? S.back : S.tab;
    tab('item');
    showDetail('item', id, name, $('itemDetail'),
      `<button class="b" data-back="1">← Back</button><button class="b pri" data-hub="items" data-id="${id}">Administer listings</button>`);
  }
  /* one delegated handler, so buttons work no matter when their detail pane finishes loading */
  root.addEventListener('click', e => {
    const t = e.target;
    const it = t.closest('a.ae-item'), pe = t.closest('a.ae-p'), ca = t.closest('a.ae-cat, button[data-cat]'), bk = t.closest('[data-back]'), hb = t.closest('[data-hub]'), th = t.closest('th[data-sid]');
    if (!(it || pe || ca || bk || hb || th)) return;
    e.preventDefault(); e.stopPropagation();
    if (it) openItem(it.dataset.item, it.dataset.name);
    else if (pe) goPerson(pe.dataset.role, pe.dataset.name);
    else if (ca) hubCat(ca.dataset.cat);
    else if (bk) tab(S.back || 'overview');
    else if (hb) hub(hb.dataset.hub, hb.dataset.id);
    else if (th) {
      const st = S.sort[th.dataset.sid], ci = +th.dataset.ci;
      if (st.ci === ci) st.dir *= -1; else { st.ci = ci; st.dir = ci === 0 ? 1 : -1; }
      S.redraw[th.dataset.sid] && S.redraw[th.dataset.sid]();
    }
  }, true);

  /* ---- tabs & loading ---- */
  function tab(name) {
    S.tab = name;
    document.querySelectorAll('#aeTabs button').forEach(b => b.classList.toggle('on', b.dataset.t === name));
    document.querySelectorAll('.ahc-pane').forEach(p => p.classList.toggle('on', p.id === 'e-' + name));
    document.querySelectorAll('#aeTabs button').forEach(b => b.classList.toggle('on', b.dataset.t === (name === 'item' ? S.back : name)));
    if (name === 'sellers' && !S.sellers) loadLedger('seller').catch(e => $('sellersList').innerHTML = `<div class="ahc-empty">${esc(e.message)}</div>`);
    if (name === 'buyers' && !S.buyers) loadLedger('buyer').catch(e => $('buyersList').innerHTML = `<div class="ahc-empty">${esc(e.message)}</div>`);
  }
  async function refresh() {
    S.sellers = S.buyers = null;
    try {
      const [econ, agg] = await Promise.all([j(`/auction-house/economy.json?days=${days() === '0' ? 3650 : days()}&limit=500&sample_limit=50000`), j('/auction-house/console/aggregate.json').catch(() => null)]);
      S.econ = econ; S.agg = agg;
      S.impact = days() === '0' ? null : await j(`/auction-house/economy/admin-impact.json?days=${days()}`).catch(() => null);
      S.snaps = await j('/auction-house/economy/snapshots.json?days=365').catch(() => null);
      S.trends = days() === '0' ? null : await j(`/auction-house/economy/trends.json?days=${days()}`).catch(() => null);
      S.anom = await j('/auction-house/economy/anomalies.json?days=7').catch(() => null);
    } catch (e) { $('e-overview').innerHTML = `<div class="ahc-empty">${esc(e.message)}</div>`; return; }
    drawOverview(); drawCategories(); tab(S.tab);
    ['seller', 'buyer'].forEach(r => { if (S[r + 's'] === null && S.tab === r + 's') loadLedger(r); });
  }
  $('e-overview').addEventListener('click', e => { const m = e.target.closest('[data-metric]'); if (m) { S.metric = m.dataset.metric; drawOverview(); } });
  $('e-overview').addEventListener('click', async e => {
    const m = e.target.closest('[data-supply]'); if (m) { S.supplyKey = m.dataset.supply; drawOverview(); return; }
    if (e.target.id === 'aeSnapNow') { e.target.disabled = true; try { await fetch('/auction-house/economy/snapshot.json', {method: 'POST'}); S.snaps = await j('/auction-house/economy/snapshots.json?days=365'); } catch (x) { /* shown unchanged */ } drawOverview(); }
  });
  $('e-overview').addEventListener('change', e => { if (e.target.id === 'aeThin') { S.thin = e.target.checked; drawOverview(); } });
  $('aeTabs').onclick =e => { if (e.target.dataset.t) tab(e.target.dataset.t); };
  $('aeRefresh').onclick = $('aeDays').onchange = refresh;
  ['sellers', 'buyers'].forEach(k => { $(k + 'Q').oninput = () => drawLedger(k.slice(0, -1)); });
  $('categoriesQ').oninput = drawCategories;
  $('peopleGo').onclick = searchPeople;
  $('peopleQ').onkeydown = e => { if (e.key === 'Enter') searchPeople(); };
  refresh();
})();
