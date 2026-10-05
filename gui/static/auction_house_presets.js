(() => {
  const root = document.getElementById('ahPresets');
  if (!root) return;
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let presets = [];
  let previews = new Map();

  async function request(url, options = {}) {
    const response = await fetch(url, {headers: {Accept: 'application/json', 'Content-Type': 'application/json'}, ...options});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `${response.status} ${response.statusText}`);
    return data;
  }

  function value(id) { return $(id).value.trim(); }
  function numberOrNull(id) { const v = value(id); return v === '' ? null : Number(v); }

  function toggleKind() {
    const cleanup = $('apKind').value === 'cleanup';
    $('apCleanupFields').hidden = !cleanup;
    $('apSeedFields').hidden = cleanup;
  }

  function buildConfig() {
    if ($('apKind').value === 'cleanup') {
      const config = {
        seller_id: numberOrNull('apSellerId'), seller_name: value('apSellerName') || null,
        category_id: numberOrNull('apCategoryId'), item_id: numberOrNull('apItemId'),
        min_price: numberOrNull('apMinPrice'), max_price: numberOrNull('apMaxPrice'),
        min_age_days: numberOrNull('apAgeDays'), limit: numberOrNull('apLimit'),
        default_action: $('apAction').value,
      };
      return Object.fromEntries(Object.entries(config).filter(([, v]) => v !== null && v !== ''));
    }
    return {
      seller_id: Number(value('apSeedSeller') || 0), category_id: Number(value('apSeedCategory') || 0),
      price: Number(value('apSeedPrice') || 0), stack_mode: $('apSeedStack').value,
      copies_per_item: Number(value('apSeedCopies') || 1), limit_items: Number(value('apSeedLimit') || 100),
    };
  }

  async function savePreset() {
    try {
      await request('/auction-house/presets/save.json', {
        method: 'POST',
        body: JSON.stringify({name: value('apName'), kind: $('apKind').value, config: buildConfig()}),
      });
      $('apName').value = '';
      await loadPresets();
    } catch (error) {
      $('apPreview').innerHTML = `<pre class="preview-json">${esc(error.message)}</pre>`;
    }
  }

  function render() {
    if (!presets.length) {
      $('apList').innerHTML = '<p class="muted">No saved presets yet.</p>';
      return;
    }
    $('apList').innerHTML = `<table class="preset-table"><thead><tr><th>Name</th><th>Type</th><th>Configuration</th><th>Updated</th><th>Actions</th></tr></thead><tbody>${presets.map((row, i) => `
      <tr><td><strong>${esc(row.name)}</strong></td><td>${esc(row.kind)}</td><td><code>${esc(JSON.stringify(row.config))}</code></td><td>${esc(row.updated_at_utc)}</td>
      <td><div class="row-actions"><button data-action="preview" data-index="${i}">Preview live</button><button data-action="execute" data-index="${i}" ${previews.has(row.preset_id) ? '' : 'disabled'}>${row.kind === 'cleanup' ? 'Execute cleanup' : 'Seed now'}</button><button data-action="delete" data-index="${i}">Delete</button></div></td></tr>`).join('')}</tbody></table>`;
    $('apList').querySelectorAll('button[data-action]').forEach(button => button.addEventListener('click', () => {
      const row = presets[Number(button.dataset.index)];
      if (button.dataset.action === 'preview') previewPreset(row);
      else if (button.dataset.action === 'execute') executePreset(row);
      else deletePreset(row);
    }));
  }

  async function loadPresets() {
    const data = await request('/auction-house/presets.json');
    presets = data.rows || [];
    previews = new Map([...previews].filter(([id]) => presets.some(row => row.preset_id === id)));
    render();
  }

  async function previewPreset(row) {
    try {
      const data = await request('/auction-house/presets/preview.json', {method: 'POST', body: JSON.stringify({preset_id: row.preset_id})});
      previews.set(row.preset_id, {preview: data.preview, token: data.preset_preview_token});
      $('apPreview').innerHTML = `<h3>${esc(row.name)}</h3><pre class="preview-json">${esc(JSON.stringify(data.preview, null, 2))}</pre>`;
      render();
    } catch (error) {
      previews.delete(row.preset_id);
      $('apPreview').innerHTML = `<pre class="preview-json">${esc(error.message)}</pre>`;
      render();
    }
  }

  async function executePreset(row) {
    const state = previews.get(row.preset_id);
    if (!state) return;
    const confirmation = window.prompt('Type the active Test profile name exactly to continue:');
    if (!confirmation) return;
    try {
      const data = await request('/auction-house/presets/execute.json', {
        method: 'POST',
        body: JSON.stringify({preset_id: row.preset_id, preset_preview_token: state.token, confirmation}),
      });
      previews.delete(row.preset_id);
      $('apPreview').innerHTML = `<h3>${esc(row.name)} — completed</h3><pre class="preview-json">${esc(JSON.stringify(data.result, null, 2))}</pre>`;
      render();
    } catch (error) {
      previews.delete(row.preset_id);
      $('apPreview').innerHTML = `<pre class="preview-json">${esc(error.message)}</pre>`;
      render();
    }
  }

  async function deletePreset(row) {
    if (!window.confirm(`Delete preset “${row.name}”?`)) return;
    try {
      await request('/auction-house/presets/delete.json', {method: 'POST', body: JSON.stringify({preset_id: row.preset_id})});
      previews.delete(row.preset_id);
      await loadPresets();
    } catch (error) {
      $('apPreview').innerHTML = `<pre class="preview-json">${esc(error.message)}</pre>`;
    }
  }

  $('apKind').addEventListener('change', toggleKind);
  $('apSave').addEventListener('click', savePreset);
  toggleKind();
  loadPresets().catch(error => { $('apList').innerHTML = `<pre>${esc(error.message)}</pre>`; });
})();
