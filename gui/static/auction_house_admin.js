(() => {
  const root = document.getElementById('ahAdmin');
  if (!root) return;
  const $ = (id) => document.getElementById(id);
  const fmt = new Intl.NumberFormat();
  const money = (v) => v == null ? '—' : `${fmt.format(Number(v))}g`;
  const when = (v) => v ? new Date(v).toLocaleString() : '—';
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  async function api(url) {
    const response = await fetch(url, {headers:{Accept:'application/json'}});
    let payload = null;
    try { payload = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(payload?.detail || `${response.status} ${response.statusText}`);
    return payload;
  }

  async function loadStatus() {
    const data = await api('/auction-house/status.json');
    const db = data.database || {};
    const ah = data.auction_house || {};
    $('ahStatus').innerHTML = `<strong>${esc(db.database || 'database')}</strong> · ${esc(ah.family_hint || 'unknown schema')} · ${esc(db.host || '')}<br><small>${esc(db.server_root || '')}</small>`;
  }

  async function loadOverview() {
    const data = await api('/auction-house/overview.json?days=30');
    const values = [fmt.format(data.active_listings || 0), fmt.format(data.sales || 0), money(data.gil_transacted), `${fmt.format(data.unique_buyers || 0)} / ${fmt.format(data.unique_sellers || 0)}`];
    document.querySelectorAll('#ahMetrics .metric strong').forEach((node, i) => node.textContent = values[i]);
  }

  async function loadCategories() {
    const data = await api('/auction-house/categories.json');
    const select = $('ahCategory');
    for (const row of data.rows || []) {
      const option = document.createElement('option');
      option.value = row.category_id;
      option.textContent = `Category ${row.category_id} (${fmt.format(row.item_count)})`;
      select.appendChild(option);
    }
  }

  async function loadItems() {
    const qs = new URLSearchParams();
    const term = $('ahSearch').value.trim();
    const category = $('ahCategory').value;
    if (term) qs.set('q', term);
    if (category) qs.set('category_id', category);
    qs.set('limit', '200');
    const box = $('ahItems');
    box.innerHTML = '<p class="muted">Loading…</p>';
    try {
      const data = await api(`/auction-house/items.json?${qs}`);
      if (!(data.rows || []).length) {
        box.innerHTML = '<p class="muted">No auctionable items matched.</p>';
        return;
      }
      box.innerHTML = (data.rows || []).map(row => `
        <button type="button" class="ah-item" data-item-id="${row.item_id}">
          <img src="/auction-house/items/${row.item_id}/icon.png" alt="" loading="lazy" onerror="this.style.visibility='hidden'">
          <span><strong>${esc(row.name)}</strong><small>ID ${row.item_id} · AH ${row.category_id} · stack ${row.stack_size}</small></span>
          <span class="ah-count"><strong>${fmt.format(row.active_listings)}</strong> listed<br>${row.average_sale_price == null ? 'no sales' : money(row.average_sale_price)}</span>
        </button>`).join('');
      box.querySelectorAll('[data-item-id]').forEach(button => button.addEventListener('click', () => loadDetail(Number(button.dataset.itemId))));
    } catch (error) {
      box.innerHTML = `<p>${esc(error.message)}</p>`;
    }
  }

  function historyTable(rows) {
    if (!rows.length) return '<p class="muted">No completed sale history found.</p>';
    return `<table class="ah-table"><thead><tr><th>Date</th><th>Seller</th><th>Buyer</th><th>Lot</th><th class="ah-price">Sale</th></tr></thead><tbody>${rows.map(r => `<tr><td>${esc(when(r.sold_at_iso))}</td><td>${esc(r.seller_name || `#${r.seller_id}`)}</td><td>${esc(r.buyer_name || (r.buyer_id ? `#${r.buyer_id}` : '—'))}</td><td>${r.stack ? 'Stack' : 'Single'}</td><td class="ah-price">${money(r.sale_price)}</td></tr>`).join('')}</tbody></table>`;
  }

  function listingTable(rows) {
    if (!rows.length) return '<p class="muted">No current listings.</p>';
    return `<table class="ah-table"><thead><tr><th>Listed</th><th>Seller</th><th>Lot</th><th class="ah-price">Asking</th></tr></thead><tbody>${rows.map(r => `<tr><td>${esc(when(r.listed_at_iso))}</td><td>${esc(r.seller_name || `#${r.seller_id}`)}</td><td>${r.stack ? 'Stack' : 'Single'}</td><td class="ah-price">${money(r.asking_price)}</td></tr>`).join('')}</tbody></table>`;
  }

  function trendCard(days, rows) {
    const sales = rows.reduce((n, r) => n + Number(r.sales || 0), 0);
    const weighted = rows.reduce((n, r) => n + Number(r.average_price || 0) * Number(r.sales || 0), 0);
    const avg = sales ? weighted / sales : null;
    const low = rows.length ? Math.min(...rows.map(r => Number(r.min_price))) : null;
    const high = rows.length ? Math.max(...rows.map(r => Number(r.max_price))) : null;
    return `<div class="ah-trend"><strong>${days} days</strong><br>${fmt.format(sales)} sales<br>avg ${money(avg == null ? null : Math.round(avg))}<br><small>${money(low)} – ${money(high)}</small></div>`;
  }

  async function loadDetail(itemId) {
    const box = $('ahDetail');
    box.innerHTML = '<h2>Item detail</h2><p class="muted">Loading…</p>';
    try {
      const data = await api(`/auction-house/items/${itemId}.json?history_limit=100`);
      const item = data.item;
      box.innerHTML = `
        <div class="page-head"><div><h2>${esc(item.name)}</h2><div class="muted">Item ${item.item_id} · AH category ${item.category_id} · stack ${item.stack_size}</div></div><img class="ah-icon" src="/auction-house/items/${item.item_id}/icon.png" alt=""></div>
        <h3>Price & volume</h3><div class="ah-trends">${trendCard(7, data.trends['7'] || [])}${trendCard(30, data.trends['30'] || [])}${trendCard(90, data.trends['90'] || [])}</div>
        <h3>Current listings (${fmt.format((data.active_listings || []).length)})</h3>${listingTable(data.active_listings || [])}
        <h3>Recent sales</h3>${historyTable(data.history || [])}`;
    } catch (error) {
      box.innerHTML = `<h2>Item detail</h2><p>${esc(error.message)}</p>`;
    }
  }

  $('ahSearchButton').addEventListener('click', loadItems);
  $('ahSearch').addEventListener('keydown', e => { if (e.key === 'Enter') loadItems(); });
  $('ahCategory').addEventListener('change', loadItems);
  Promise.all([loadStatus(), loadOverview(), loadCategories()]).then(loadItems).catch(error => {
    $('ahStatus').textContent = error.message;
    $('ahItems').innerHTML = '<p class="muted">Auction House data unavailable.</p>';
  });
})();
