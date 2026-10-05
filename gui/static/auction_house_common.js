(() => {
  const boxes = Array.from(document.querySelectorAll('[data-ah-shared-status]'));
  if (!boxes.length) return;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  const rewriteLegacyReadiness = () => {
    const box = document.getElementById('ahWriteReadiness');
    if (!box) return;
    const first = box.firstElementChild;
    if (first && /Executor:\s*disabled/i.test(first.textContent || '')) {
      first.innerHTML = first.innerHTML.replace(
        /<strong>Executor:<\/strong>\s*disabled/i,
        '<strong>Global executor:</strong> disabled · <strong>Scoped DSP/Topaz Test executors:</strong> available when their gates pass'
      );
    }
  };
  const legacyBox = document.getElementById('ahWriteReadiness');
  if (legacyBox) {
    new MutationObserver(rewriteLegacyReadiness).observe(legacyBox, {childList:true, subtree:true});
    rewriteLegacyReadiness();
  }

  fetch('/auction-house/capability-status.json', {headers:{Accept:'application/json'}})
    .then(async response => {
      const payload = await response.json().catch(() => ({}));
      if (!response.ok && !payload) throw new Error(`${response.status} ${response.statusText}`);
      return payload;
    })
    .then(data => {
      const env = data.environment || {};
      const name = env.name || 'unconfigured';
      const family = env.family || data.schema_family || 'unknown';
      const kind = env.environment || env.environment_kind || env.kind || 'unknown';
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
