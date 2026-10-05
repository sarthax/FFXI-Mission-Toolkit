(() => {
  const root = document.getElementById('ahListingManager');
  if (!root) return;
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = new Intl.NumberFormat();
  const gil = value => `${fmt.format(Number(value || 0))}g`;
  const when = value => value ? new Date(Number(value) * 1000).toLocaleString() : '—';

  async function request(url, options = {}) {
    const response = await fetch(url, {
      headers: {Accept: 'application/json', 'Content-Type': 'application/json'},
      ...options,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `${response.status} ${response.statusText}`);
    return data;
  }

  async function loadCategories() {
    const data = await request('/auction-house/categories.json');
    for (const row of data.rows || []) {
      const option = document.createElement('option');
      option.value = row.category_id;
      option.textContent = `${row.path || row.label || `Category ${row.category_id}`} (${fmt.format(row.item_count || 0)})`;
      $('lmCategory').appendChild(option);
    }
  }

  function queryString() {
    const qs = new URLSearchParams();
    const values = {
      seller_id: $('lmSellerId').value,
      seller_name: $('lmSellerName').value.trim(),
      category_id: $('lmCategory').value,
      item_id: $('lmItemId').value,
      q: $('lmQuery').value.trim(),
      limit: $('lmLimit').value,
    };
    for (const [key, value] of Object.entries(values)) if (value) qs.set(key, value);
    return qs;
  }

  function showAction(title, data, failed = false) {
    $('lmAction').innerHTML = `<div class="action-result"><strong>${esc(title)}</strong><pre>${esc(failed ? String(data) : JSON.stringify(data, null, 2))}</pre></div>`;
  }

  async function adminClose(row) {
    const confirmation = window.prompt(`Close auction #${row.auction_id} as an administrative sale at ${gil(row.asking_price)}?\nType the active Test profile name exactly to continue:`);
    if (!confirmation) return;
    try {
      const data = await request('/auction-house/test-write/admin-buy.json', {
        method: 'POST',
        body: JSON.stringify({auction_id: row.auction_id, expected_price: row.asking_price, confirmation}),
      });
      showAction('Administrative sale committed', data);
      await loadListings();
    } catch (error) {
      showAction('Administrative sale blocked', error.message, true);
    }
  }

  async function returnListing(row) {
    const confirmation = window.prompt(`Return auction #${row.auction_id} to ${row.seller_name || `seller #${row.seller_id}`}?\nThe item returns to Inventory. The original listing fee is not restored.\nType the active Test profile name exactly to continue:`);
    if (!confirmation) return;
    try {
      const data = await request('/auction-house/test-write/return-to-seller.json', {
        method: 'POST',
        body: JSON.stringify({auction_id: row.auction_id, confirmation}),
      });
      showAction('Return committed', data);
      await loadListings();
    } catch (error) {
      showAction('Return blocked', error.message, true);
    }
  }

  async function playerPreview(row) {
    const buyerId = window.prompt(`Character ID to preview against auction #${row.auction_id}:`);
    if (!buyerId) return;
    try {
      const data = await request('/auction-house/admin/purchase/preview.json', {
        method: 'POST',
        body: JSON.stringify({auction_id: row.auction_id, buyer_id: Number(buyerId), mode: 'normal_purchase'}),
      });
      showAction('Player purchase preview', data);
    } catch (error) {
      showAction('Player purchase preview failed', error.message, true);
    }
  }

  function render(rows) {
    if (!rows.length) {
      $('lmResults').innerHTML = '<p class="muted">No active listings matched.</p>';
      return;
    }
    $('lmResults').innerHTML = `<table class="lm-table"><thead><tr><th>Auction</th><th>Item</th><th>Category</th><th>Seller</th><th>Lot</th><th>Listed</th><th class="price">Asking</th><th>Actions</th></tr></thead><tbody>${rows.map((row, index) => `
      <tr>
        <td>#${row.auction_id}</td>
        <td><strong>${esc(row.item_name)}</strong><br><small>ID ${row.item_id}</small></td>
        <td>${esc(row.category_path || row.category_id)}</td>
        <td>${esc(row.seller_name || `#${row.seller_id}`)}<br><small>ID ${row.seller_id}</small></td>
        <td>${row.stack ? `Stack ×${fmt.format(row.quantity)}` : 'Single'}</td>
        <td>${esc(when(row.listed_at))}</td>
        <td class="price">${gil(row.asking_price)}</td>
        <td><div class="lm-actions">
          <button type="button" data-action="admin" data-index="${index}">Admin Buy</button>
          <button type="button" data-action="player" data-index="${index}">Player Buy Preview</button>
          <button type="button" data-action="return" data-index="${index}">Return</button>
        </div></td>
      </tr>`).join('')}</tbody></table>`;

    $('lmResults').querySelectorAll('button[data-action]').forEach(button => {
      button.addEventListener('click', () => {
        const row = rows[Number(button.dataset.index)];
        if (button.dataset.action === 'admin') adminClose(row);
        else if (button.dataset.action === 'return') returnListing(row);
        else playerPreview(row);
      });
    });
  }

  async function loadListings() {
    $('lmSummary').textContent = 'Loading active listings…';
    try {
      const data = await request(`/auction-house/listings.json?${queryString()}`);
      $('lmSummary').textContent = `${fmt.format(data.count || 0)} active listing(s) returned.`;
      render(data.rows || []);
    } catch (error) {
      $('lmSummary').textContent = error.message;
      $('lmResults').innerHTML = '';
    }
  }

  $('lmRefresh').addEventListener('click', loadListings);
  for (const id of ['lmSellerId', 'lmSellerName', 'lmItemId', 'lmQuery']) {
    $(id).addEventListener('keydown', event => {
      if (event.key === 'Enter') {
        event.preventDefault();
        loadListings();
      }
    });
  }
  $('lmCategory').addEventListener('change', loadListings);
  loadCategories().finally(loadListings);
})();
