(() => {
  const boxes = Array.from(document.querySelectorAll('[data-ah-shared-status]'));
  if (!boxes.length) return;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  fetch('/auction-house/status.json', {headers:{Accept:'application/json'}})
    .then(async response => {
      const payload = await response.json().catch(() => ({}));
      if (!response.ok && !payload) throw new Error(`${response.status} ${response.statusText}`);
      return payload;
    })
    .then(data => {
      const env = data.environment || {};
      const name = env.name || 'unconfigured';
      const family = env.family || data.schema_family || 'unknown';
      const kind = env.environment || env.kind || 'unknown';
      let state = 'READ ONLY';
      let detail = data.capability_note || '';
      if (!data.configured) {
        state = 'NO ACTIVE ENVIRONMENT';
      } else if (data.scoped_test_write_ready) {
        state = 'SCOPED TEST WRITES READY';
      } else if (data.read_only_ready) {
        state = 'READ ONLY · TEST WRITES BLOCKED';
      } else {
        state = 'UNAVAILABLE';
      }
      const engineNote = (data.player_listing_transactional === false || data.player_purchase_transactional === false)
        ? ' Player-backed listing/purchase may be blocked by non-transactional legacy tables (for example MyISAM).'
        : '';
      const blockers = (data.blockers || []).slice(0, 2).join(' · ');
      const html = `<strong>Auction House:</strong> <span class="${data.scoped_test_write_ready ? 'ok' : 'warn'}">${esc(state)}</span> · ${esc(name)} · ${esc(family)} · ${esc(kind)}<small>${esc(detail + engineNote)}${blockers ? ` Blockers: ${esc(blockers)}` : ''}</small>`;
      boxes.forEach(box => { box.innerHTML = html; });
    })
    .catch(error => boxes.forEach(box => { box.innerHTML = `<strong>Auction House:</strong> status unavailable<small>${esc(error.message)}</small>`; }));
})();
