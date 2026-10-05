(() => {
  const $ = (id) => document.getElementById(id);
  const text = (value) => value === null || value === undefined || value === '' ? '—' : String(value);
  const utc = (value) => value ? new Date(value).toLocaleString() : '—';

  function query() {
    const params = new URLSearchParams();
    const mapping = {
      aaEnvironment: 'environment_name', aaOperation: 'operation', aaStatus: 'status',
      aaCharacter: 'character_id', aaItem: 'item_id', aaLimit: 'limit'
    };
    Object.entries(mapping).forEach(([id, name]) => {
      const value = $(id).value.trim();
      if (value) params.set(name, value);
    });
    const since = $('aaSince').value;
    const until = $('aaUntil').value;
    if (since) params.set('since_utc', new Date(since).toISOString());
    if (until) params.set('until_utc', new Date(until).toISOString());
    params.set('include_evidence', $('aaEvidence').checked ? 'true' : 'false');
    params.set('include_campaigns', $('aaCampaigns').checked ? 'true' : 'false');
    return params;
  }

  function detailCell(row) {
    const wrapper = document.createElement('div');
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'View';
    const pre = document.createElement('pre');
    pre.className = 'activity-detail';
    pre.hidden = true;
    pre.textContent = JSON.stringify(row.payload || {}, null, 2);
    button.addEventListener('click', () => {
      pre.hidden = !pre.hidden;
      button.textContent = pre.hidden ? 'View' : 'Hide';
    });
    wrapper.append(button, pre);
    return wrapper;
  }

  function render(data) {
    $('aaSummary').textContent = `${data.count || 0} activity row(s) shown. Read-only unified audit view.`;
    const tbody = $('aaRows');
    tbody.innerHTML = '';
    const rows = data.rows || [];
    if (!rows.length) {
      const tr = document.createElement('tr');
      tr.innerHTML = '<td colspan="9" class="muted">No matching activity.</td>';
      tbody.appendChild(tr);
      return;
    }
    rows.forEach((row) => {
      const tr = document.createElement('tr');
      [
        utc(row.occurred_at_utc), text(row.source), text(row.operation), text(row.status),
        text(row.environment_name), text(row.character_id), text(row.item_id), text(row.auction_id)
      ].forEach((value) => {
        const td = document.createElement('td');
        td.textContent = value;
        tr.appendChild(td);
      });
      const detail = document.createElement('td');
      detail.appendChild(detailCell(row));
      tr.appendChild(detail);
      tbody.appendChild(tr);
    });
  }

  async function load() {
    $('aaSummary').textContent = 'Loading…';
    try {
      const response = await fetch(`/auction-house/activity.json?${query().toString()}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Activity request failed');
      render(data);
    } catch (error) {
      $('aaSummary').textContent = `Error: ${error.message || error}`;
    }
  }

  function clear() {
    ['aaEnvironment','aaOperation','aaStatus','aaCharacter','aaItem','aaSince','aaUntil'].forEach((id) => { $(id).value = ''; });
    $('aaLimit').value = '200';
    $('aaEvidence').checked = true;
    $('aaCampaigns').checked = true;
    load();
  }

  $('aaLoad').addEventListener('click', load);
  $('aaClear').addEventListener('click', clear);
  load();
})();
