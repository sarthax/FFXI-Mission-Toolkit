(() => {
  const root = document.getElementById('ahSeeder');
  if (!root) return;
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = new Intl.NumberFormat();
  let lastSyntheticPreview = null;

  async function request(url, options = {}) {
    const response = await fetch(url, {
      headers: {Accept: 'application/json', 'Content-Type': 'application/json'},
      ...options,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `${response.status} ${response.statusText}`);
    return data;
  }

  function showResult(target, title, data, failed = false) {
    target.classList.remove('muted');
    target.innerHTML = `<strong>${esc(title)}</strong><pre>${esc(failed ? String(data) : JSON.stringify(data, null, 2))}</pre>`;
  }

  async function loadCategories() {
    const data = await request('/auction-house/categories.json');
    for (const row of data.rows || []) {
      const option = document.createElement('option');
      option.value = row.category_id;
      option.textContent = `${row.path || row.label || `Category ${row.category_id}`} (${fmt.format(row.item_count || 0)})`;
      $('seedSyntheticCategory').appendChild(option);
    }
  }

  function playerPayload() {
    return {
      seller_id: Number($('seedPlayerSeller').value || 0),
      inventory_slot: Number($('seedPlayerSlot').value || 0),
      item_id: Number($('seedPlayerItem').value || 0),
      price: Number($('seedPlayerPrice').value || 0),
      stack: $('seedPlayerStack').checked,
    };
  }

  async function checkPlayerReadiness() {
    try {
      const data = await request('/auction-house/test-write/player-listing-readiness.json');
      showResult($('seedPlayerResult'), data.ready_for_direct_transaction ? 'Player listing ready' : 'Player listing blocked by storage engine', data);
    } catch (error) {
      showResult($('seedPlayerResult'), 'Readiness check failed', error.message, true);
    }
  }

  async function postPlayerListing() {
    const payload = playerPayload();
    const confirmation = window.prompt('Type the active Test profile name exactly to post this player-backed listing:');
    if (!confirmation) return;
    try {
      const data = await request('/auction-house/test-write/player-listing.json', {
        method: 'POST',
        body: JSON.stringify({...payload, confirmation}),
      });
      showResult($('seedPlayerResult'), 'Player listing committed', data);
    } catch (error) {
      showResult($('seedPlayerResult'), 'Player listing blocked', error.message, true);
    }
  }

  function syntheticPayload() {
    return {
      seller_id: Number($('seedSyntheticSeller').value || 0),
      category_id: Number($('seedSyntheticCategory').value || 0),
      price: Number($('seedSyntheticPrice').value || 0),
      stack_mode: $('seedSyntheticStackMode').value,
      copies_per_item: Number($('seedSyntheticCopies').value || 1),
      limit_items: Number($('seedSyntheticLimit').value || 100),
    };
  }

  function renderSyntheticPreview(data) {
    const items = data.items || [];
    const sample = items.slice(0, 50);
    const rows = sample.map(row => `<tr><td>${row.item_id}</td><td>${esc(row.item_name)}</td><td>${row.stack ? `Stack ×${fmt.format(row.stack_size)}` : 'Single'}</td><td>${fmt.format(row.copies)}</td><td>${fmt.format(row.price)}g</td></tr>`).join('');
    $('seedSyntheticResult').classList.remove('muted');
    $('seedSyntheticResult').innerHTML = `
      <strong>Preview: ${fmt.format(data.listing_rows || 0)} listing rows · ${fmt.format(data.supply_units || 0)} supply units</strong>
      <p>${fmt.format(data.item_count || 0)} distinct items matched. ${items.length > sample.length ? `Showing first ${sample.length}.` : ''}</p>
      <table class="seed-preview-table"><thead><tr><th>ID</th><th>Item</th><th>Mode</th><th>Copies</th><th>Price</th></tr></thead><tbody>${rows}</tbody></table>`;
  }

  async function previewSynthetic() {
    const payload = syntheticPayload();
    try {
      const data = await request('/auction-house/test-write/synthetic-category-preview.json', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      lastSyntheticPreview = payload;
      renderSyntheticPreview(data);
      $('seedSyntheticExecute').disabled = !(data.listing_rows > 0);
    } catch (error) {
      lastSyntheticPreview = null;
      $('seedSyntheticExecute').disabled = true;
      showResult($('seedSyntheticResult'), 'Category seed preview failed', error.message, true);
    }
  }

  async function executeSynthetic() {
    if (!lastSyntheticPreview) return;
    const current = syntheticPayload();
    if (JSON.stringify(current) !== JSON.stringify(lastSyntheticPreview)) {
      lastSyntheticPreview = null;
      $('seedSyntheticExecute').disabled = true;
      showResult($('seedSyntheticResult'), 'Preview stale', 'Inputs changed after preview. Preview the seed again before executing.', true);
      return;
    }
    const confirmation = window.prompt(`Create the previewed synthetic category seed?\nThis injects admin supply without removing player Inventory or charging AH fees.\nType the active Test profile name exactly to continue:`);
    if (!confirmation) return;
    try {
      const data = await request('/auction-house/test-write/synthetic-category-seed.json', {
        method: 'POST',
        body: JSON.stringify({...current, confirmation}),
      });
      showResult($('seedSyntheticResult'), `Synthetic seed ${data.status || 'completed'}`, data);
      lastSyntheticPreview = null;
      $('seedSyntheticExecute').disabled = true;
    } catch (error) {
      showResult($('seedSyntheticResult'), 'Synthetic seed blocked', error.message, true);
    }
  }

  $('seedPlayerReadiness').addEventListener('click', checkPlayerReadiness);
  $('seedPlayerPost').addEventListener('click', postPlayerListing);
  $('seedSyntheticPreview').addEventListener('click', previewSynthetic);
  $('seedSyntheticExecute').addEventListener('click', executeSynthetic);
  for (const id of ['seedSyntheticCategory','seedSyntheticPrice','seedSyntheticStackMode','seedSyntheticCopies','seedSyntheticLimit','seedSyntheticSeller']) {
    $(id).addEventListener('change', () => {
      if (lastSyntheticPreview) {
        lastSyntheticPreview = null;
        $('seedSyntheticExecute').disabled = true;
      }
    });
  }
  loadCategories().catch(error => showResult($('seedSyntheticResult'), 'Category load failed', error.message, true));
})();
