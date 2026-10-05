(() => {
  const root = document.getElementById('ahEconomy');
  if (!root) return;
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = value => value == null ? '—' : Number(value).toLocaleString();
  const pct = value => value == null ? '—' : `${Number(value).toFixed(2)}%`;

  function query() {
    const params = new URLSearchParams();
    const pairs = [
      ['days','aeDays'], ['stale_days','aeStaleDays'], ['seller_id','aeSellerId'],
      ['category_id','aeCategoryId'], ['limit','aeLimit'], ['sample_limit','aeSampleLimit'],
    ];
    for (const [key,id] of pairs) { const value = $(id).value.trim(); if (value) params.set(key, value); }
    return params.toString();
  }

  function table(rows, columns) {
    if (!rows.length) return '<p class="muted">No matching data.</p>';
    return `<table><thead><tr>${columns.map(c => `<th>${esc(c[0])}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${columns.map(c => `<td>${c[2] ? c[2](row[c[1]], row) : esc(row[c[1]] ?? '—')}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  }

  function render(data) {
    const t = data.totals || {};
    $('aeSummary').innerHTML = `<h2>Economy summary</h2><div class="metric-grid">
      <div><strong>${fmt(t.active_listings)}</strong><span>Active listings</span></div>
      <div><strong>${fmt(t.active_asking_value)}</strong><span>Active asking gil</span></div>
      <div><strong>${fmt(t.sold_count)}</strong><span>Sales in window</span></div>
      <div><strong>${fmt(t.sold_gil)}</strong><span>Realized gil</span></div>
      <div><strong>${pct(t.sell_through_pct)}</strong><span>Sell-through</span></div>
      <div><strong>${fmt(t.stale_active_count)}</strong><span>Stale active</span></div>
    </div><p class="muted">Sample ${fmt(data.sample_rows)} / limit ${fmt(data.sample_limit)}${data.sample_truncated ? ' — sample limit reached' : ''}. Lookback ${fmt(data.window_days)} days; stale threshold ${fmt(data.stale_threshold_days)} days.</p>`;

    $('aeSellers').innerHTML = table(data.seller_rows || [], [
      ['Seller','seller_name',(v,r)=>`${esc(v || '(unknown)')} <span class="muted">#${fmt(r.seller_id)}</span>`],
      ['Active','active_listings',fmt], ['Exposure','active_asking_value',fmt], ['Sold','sold_count',fmt], ['Gil','sold_gil',fmt],
      ['Median ask','median_asking_price',fmt], ['Median sale','median_sale_price',fmt], ['Sell-through','sell_through_pct',pct],
      ['Oldest active','oldest_active_age_days',v=>v == null ? '—' : `${Number(v).toFixed(1)}d`], ['Stale','stale_active_count',fmt],
    ]);

    $('aeCategories').innerHTML = table(data.category_rows || [], [
      ['Category','category_path',(v,r)=>`${esc(v || 'Unknown')} <span class="muted">#${fmt(r.category_id)}</span>`],
      ['Items','distinct_items',fmt], ['Sellers','seller_count',fmt], ['Active','active_listings',fmt], ['Exposure','active_asking_value',fmt],
      ['Sold','sold_count',fmt], ['Gil','sold_gil',fmt], ['Median ask','median_asking_price',fmt], ['Median sale','median_sale_price',fmt],
      ['Sell-through','sell_through_pct',pct], ['Stale','stale_active_count',fmt], ['Supply signal','supply_signal',v=>`<code>${esc(v)}</code>`],
    ]);
  }

  async function load() {
    $('aeSummary').innerHTML = '<p class="muted">Loading…</p>';
    try {
      const response = await fetch(`/auction-house/economy.json?${query()}`, {headers:{Accept:'application/json'}});
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `${response.status} ${response.statusText}`);
      render(data);
    } catch (error) {
      $('aeSummary').innerHTML = `<pre>${esc(error.message)}</pre>`;
      $('aeSellers').innerHTML = '';
      $('aeCategories').innerHTML = '';
    }
  }

  $('aeLoad').addEventListener('click', load);
  load();
})();
