(() => {
  const root = document.getElementById('ahCleanup');
  if (!root) return;
  const $ = id => document.getElementById(id);
  const fmt = new Intl.NumberFormat();
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let preview = null;

  async function request(url, options = {}) {
    const response = await fetch(url, {headers:{Accept:'application/json','Content-Type':'application/json'}, ...options});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `${response.status} ${response.statusText}`);
    return data;
  }

  function criteria() {
    const out = {};
    const map = {
      seller_id:'cuSellerId', seller_name:'cuSellerName', category_id:'cuCategoryId', item_id:'cuItemId',
      min_price:'cuMinPrice', max_price:'cuMaxPrice', min_age_days:'cuAgeDays', limit:'cuLimit'
    };
    for (const [key,id] of Object.entries(map)) {
      const value = $(id).value.trim();
      if (value !== '') out[key] = value;
    }
    return out;
  }

  function invalidate() {
    preview = null;
    $('cuAdminBuy').disabled = true;
    $('cuReturn').disabled = true;
    $('cuToken').textContent = 'unbound';
  }

  function render(data) {
    preview = data;
    $('cuSummary').textContent = `${fmt.format(data.count || 0)} listing(s), ${fmt.format(data.aggregate_asking_value || 0)}g aggregate asking value. Oldest ${data.oldest_age_days == null ? '—' : data.oldest_age_days.toFixed(1)+'d'}.`;
    $('cuToken').textContent = data.preview_token ? data.preview_token.slice(0,12) : 'unbound';
    const rows = data.targets || [];
    $('cuResults').innerHTML = rows.length ? `<table class="cu-table"><thead><tr><th>Auction</th><th>Item</th><th>Seller</th><th>Listed</th><th>Age</th><th class="price">Asking</th></tr></thead><tbody>${rows.map(r => {
      const age = r.listed_at ? Math.max(0,(data.generated_at-r.listed_at)/86400) : null;
      return `<tr><td>#${r.auction_id}</td><td>${esc(r.item_name)}<br><small>ID ${r.item_id}</small></td><td>${esc(r.seller_name || `#${r.seller_id}`)}</td><td>${r.listed_at ? new Date(r.listed_at*1000).toLocaleString() : '—'}</td><td>${age==null?'—':age.toFixed(1)+'d'}</td><td class="price">${fmt.format(r.asking_price)}g</td></tr>`;
    }).join('')}</tbody></table>` : '<p class="muted">No active listings matched.</p>';
    $('cuAdminBuy').disabled = rows.length === 0;
    $('cuReturn').disabled = rows.length === 0;
  }

  async function runPreview() {
    invalidate();
    $('cuSummary').textContent = 'Resolving exact live target set…';
    try { render(await request('/auction-house/cleanup/preview.json',{method:'POST',body:JSON.stringify(criteria())})); }
    catch (error) { $('cuSummary').textContent = error.message; $('cuResults').innerHTML = ''; }
  }

  async function execute(action) {
    if (!preview) return;
    const confirmation = window.prompt(`${action === 'admin_buy' ? 'Admin Buy' : 'Return'} ${preview.count} previewed listing(s)?\nThe exact preview fingerprint must still match live state.\nType the active Test profile name exactly:`);
    if (!confirmation) return;
    try {
      const data = await request('/auction-house/test-write/cleanup.json',{method:'POST',body:JSON.stringify({criteria:preview.criteria,preview_token:preview.preview_token,action,confirmation})});
      $('cuAction').innerHTML = `<div class="action-result"><strong>${esc(data.status || 'completed')}</strong><pre>${esc(JSON.stringify(data,null,2))}</pre></div>`;
      await runPreview();
    } catch (error) {
      $('cuAction').innerHTML = `<div class="action-result"><strong>Cleanup blocked</strong><pre>${esc(error.message)}</pre></div>`;
    }
  }

  $('cuPreview').addEventListener('click', runPreview);
  $('cuPreset30').addEventListener('click', () => { $('cuAgeDays').value='30'; runPreview(); });
  $('cuPreset90').addEventListener('click', () => { $('cuAgeDays').value='90'; runPreview(); });
  $('cuAdminBuy').addEventListener('click', () => execute('admin_buy'));
  $('cuReturn').addEventListener('click', () => execute('return_to_seller'));
  root.querySelectorAll('input').forEach(input => input.addEventListener('input', invalidate));
})();
