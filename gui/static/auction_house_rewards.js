(() => {
  const root = document.getElementById('ahRewards');
  if (!root) return;
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let templates = [];
  let preview = null;

  async function request(url, options = {}) {
    const response = await fetch(url, {headers: {Accept: 'application/json', 'Content-Type': 'application/json'}, ...options});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `${response.status} ${response.statusText}`);
    return data;
  }

  function parseItems() {
    const lines = $('arItems').value.split(/\r?\n/).map(v => v.trim()).filter(Boolean);
    return lines.map(line => {
      const [itemId, quantity] = line.split(':').map(v => v.trim());
      return {item_id: Number(itemId), quantity: Number(quantity)};
    });
  }

  function parseRecipients() {
    return $('arRecipients').value.split(/[\s,]+/).map(v => v.trim()).filter(Boolean).map(Number);
  }

  function invalidatePreview() {
    preview = null;
    $('arExecute').disabled = true;
  }

  async function loadTemplates() {
    const data = await request('/auction-house/rewards/templates.json');
    templates = data.rows || [];
    const selected = $('arTemplate').value;
    $('arTemplate').innerHTML = '<option value="">Ad hoc bundle</option>' + templates.map(row => `<option value="${esc(row.template_id)}">${esc(row.name)}</option>`).join('');
    if (templates.some(row => row.template_id === selected)) $('arTemplate').value = selected;
  }

  function selectedTemplate() {
    return templates.find(row => row.template_id === $('arTemplate').value) || null;
  }

  $('arTemplate').addEventListener('change', () => {
    const row = selectedTemplate();
    if (row) {
      $('arName').value = row.name;
      $('arItems').value = row.items.map(item => `${item.item_id}:${item.quantity}`).join('\n');
    }
    invalidatePreview();
  });

  $('arMode').addEventListener('change', () => {
    $('arRecipients').disabled = $('arMode').value === 'all';
    invalidatePreview();
  });
  $('arRecipients').addEventListener('input', invalidatePreview);
  $('arItems').addEventListener('input', invalidatePreview);

  $('arSave').addEventListener('click', async () => {
    try {
      const current = selectedTemplate();
      const saved = await request('/auction-house/rewards/templates/save.json', {
        method: 'POST',
        body: JSON.stringify({template_id: current?.template_id || null, name: $('arName').value.trim(), items: parseItems()}),
      });
      await loadTemplates();
      $('arTemplate').value = saved.template_id;
      $('arOutput').innerHTML = `<pre class="preview-json">Saved template ${esc(saved.name)}</pre>`;
      invalidatePreview();
    } catch (error) {
      $('arOutput').innerHTML = `<pre class="preview-json">${esc(error.message)}</pre>`;
    }
  });

  $('arDelete').addEventListener('click', async () => {
    const row = selectedTemplate();
    if (!row || !window.confirm(`Delete reward template “${row.name}”?`)) return;
    try {
      await request('/auction-house/rewards/templates/delete.json', {method: 'POST', body: JSON.stringify({template_id: row.template_id})});
      $('arTemplate').value = '';
      $('arName').value = '';
      $('arItems').value = '';
      invalidatePreview();
      await loadTemplates();
    } catch (error) {
      $('arOutput').innerHTML = `<pre class="preview-json">${esc(error.message)}</pre>`;
    }
  });

  $('arPreview').addEventListener('click', async () => {
    try {
      const row = selectedTemplate();
      const payload = {
        template_id: row?.template_id || null,
        items: row ? undefined : parseItems(),
        recipient_mode: $('arMode').value,
        character_ids: $('arMode').value === 'all' ? [] : parseRecipients(),
      };
      const data = await request('/auction-house/rewards/preview.json', {method: 'POST', body: JSON.stringify(payload)});
      preview = data.preview;
      $('arExecute').disabled = false;
      $('arOutput').innerHTML = `<pre class="preview-json">${esc(JSON.stringify(data, null, 2))}</pre>`;
    } catch (error) {
      invalidatePreview();
      $('arOutput').innerHTML = `<pre class="preview-json">${esc(error.message)}</pre>`;
    }
  });

  $('arExecute').addEventListener('click', async () => {
    if (!preview) return;
    const confirmation = window.prompt('Type the active Test profile name exactly to deliver this bundle:');
    if (!confirmation) return;
    try {
      const row = selectedTemplate();
      const payload = {
        template_id: row?.template_id || null,
        items: row ? undefined : parseItems(),
        recipient_mode: preview.recipient_mode,
        character_ids: preview.recipient_mode === 'all' ? [] : preview.recipients.map(r => r.char_id),
        preview_token: preview.preview_token,
        preview_id: preview.preview_id,
        replay_id: preview.replay_id,
        confirmation,
      };
      const data = await request('/auction-house/rewards/execute.json', {method: 'POST', body: JSON.stringify(payload)});
      invalidatePreview();
      $('arOutput').innerHTML = `<pre class="preview-json">${esc(JSON.stringify(data, null, 2))}</pre>`;
    } catch (error) {
      invalidatePreview();
      $('arOutput').innerHTML = `<pre class="preview-json">${esc(error.message)}</pre>`;
    }
  });

  loadTemplates().catch(error => { $('arOutput').innerHTML = `<pre class="preview-json">${esc(error.message)}</pre>`; });
})();
