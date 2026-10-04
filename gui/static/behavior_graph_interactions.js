(() => {
  function applyPlainContract() {
    const plain = document.getElementById('behavior-plain-view');
    const dataEl = document.getElementById('behavior-data');
    if (!plain || !dataEl) return;

    let graph;
    try { graph = JSON.parse(dataEl.textContent || '{}'); } catch { return; }
    const contract = graph.plain_behavior;
    if (!contract || !Array.isArray(contract.flows)) return;

    const flows = [...plain.querySelectorAll('.plain-flow')];
    for (let index = 0; index < flows.length; index += 1) {
      const flow = flows[index];
      const expected = contract.flows[index];
      if (!expected) continue;

      const visible = new Set([
        expected.trigger?.node_id,
        ...(expected.requirements || []).map(row => row.node_id),
        ...(expected.actions || []).map(row => row.node_id),
        ...(expected.results || []).map(row => row.node_id),
      ].filter(Boolean));

      for (const card of flow.querySelectorAll('[data-plain-node]')) {
        card.hidden = !visible.has(card.dataset.plainNode);
      }

      const summary = flow.querySelector('.plain-summary');
      if (!summary) continue;
      const collapsedCount = Number(expected.collapsed_count || 0);
      const collapsedChip = collapsedCount
        ? `<span class="chip">${collapsedCount} implementation node${collapsedCount === 1 ? '' : 's'} collapsed</span>`
        : '';
      summary.innerHTML = `${expected.summary || ''}${collapsedChip}`;
    }
  }

  const core = document.createElement('script');
  core.src = '/static/behavior_graph_interactions_core.js';
  core.onload = () => {
    const plain = document.getElementById('behavior-plain-view');
    if (!plain) return;
    let queued = false;
    const queueContract = () => {
      if (queued) return;
      queued = true;
      queueMicrotask(() => {
        queued = false;
        applyPlainContract();
      });
    };
    const observer = new MutationObserver(queueContract);
    observer.observe(plain, { childList: true, subtree: true });
    applyPlainContract();
  };
  document.head.appendChild(core);
})();
