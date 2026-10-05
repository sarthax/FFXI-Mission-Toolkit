(() => {
  const root = document.getElementById('ahRewardHistory');
  if (!root) return;
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let rows = [];

  async function request(url, options = {}) {
    const response = await fetch(url, {headers: {Accept: 'application/json', 'Content-Type': 'application/json'}, ...options});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `${response.status} ${response.statusText}`);
    return data;
  }

  async function loadHistory() {
    const params = new URLSearchParams();
    const status = $('rhStatus').value;
    const template = $('rhTemplate').value.trim();
    if (status) params.set('status', status);
    if (template) params.set('template_id', template);
    params.set('limit', $('rhLimit').value || '100');
    const data = await request(`/auction-house/reward-history.json?${params}`);
    rows = data.rows || [];
    $('rhList').innerHTML = rows.length ? `<table class="history-table"><thead><tr><th>Created</th><th>Status</th><th>Template</th><th>Recipients</th><th>Completed</th><th>Failed</th><th></th></tr></thead><tbody>${rows.map((row, i) => `<tr><td>${esc(row.created_at_utc)}</td><td>${esc(row.overall_status)}</td><td>${esc(row.template_name || row.template_id || 'Ad hoc')}</td><td>${row.recipient_count}</td><td>${row.completed_count ?? 0}</td><td>${row.failed_count ?? 0}</td><td><button data-index="${i}">Inspect</button></td></tr>`).join('')}</tbody></table>` : '<p class="muted">No reward campaigns match the filters.</p>';
    $('rhList').querySelectorAll('button[data-index]').forEach(button => button.addEventListener('click', () => inspect(rows[Number(button.dataset.index)])));
  }

  async function inspect(row) {
    try {
      const detail = await request(`/auction-house/reward-history/${encodeURIComponent(row.campaign_id)}.json`);
      $('rhDetail').innerHTML = `<h3>${esc(detail.campaign_id)}</h3><p>${detail.completed_count} completed · ${detail.failed_count} failed</p><button id="rhRetry" type="button" ${detail.failed_count ? '' : 'disabled'}>Preview failed-recipient retry</button><pre class="preview-json">${esc(JSON.stringify(detail, null, 2))}</pre>`;
      const retry = $('rhRetry');
      if (retry) retry.addEventListener('click', () => retryPreview(detail.campaign_id));
    } catch (error) {
      $('rhDetail').innerHTML = `<pre class="preview-json">${esc(error.message)}</pre>`;
    }
  }

  async function retryPreview(campaignId) {
    try {
      const data = await request(`/auction-house/reward-history/${encodeURIComponent(campaignId)}/retry-preview.json`, {method: 'POST', body: '{}'});
      $('rhDetail').innerHTML = `<h3>Retry preview</h3><p class="muted">Only failed recipients are included. Execute from Rewards using the fresh preview values and Test confirmation.</p><pre class="preview-json">${esc(JSON.stringify(data, null, 2))}</pre>`;
    } catch (error) {
      $('rhDetail').innerHTML = `<pre class="preview-json">${esc(error.message)}</pre>`;
    }
  }

  $('rhLoad').addEventListener('click', () => loadHistory().catch(error => { $('rhList').innerHTML = `<pre>${esc(error.message)}</pre>`; }));
  loadHistory().catch(error => { $('rhList').innerHTML = `<pre>${esc(error.message)}</pre>`; });
})();
