(() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

  function applyPlainContract() {
    const plain = document.getElementById('behavior-plain-view');
    const dataEl = document.getElementById('behavior-data');
    if (!plain || !dataEl) return;

    let graph;
    try { graph = JSON.parse(dataEl.textContent || '{}'); } catch { return; }
    const contract = graph.plain_behavior;
    if (!contract || !Array.isArray(contract.flows)) return;

    const originalButtons = new Map();
    for (const button of plain.querySelectorAll('[data-plain-node]')) {
      if (!originalButtons.has(button.dataset.plainNode)) originalButtons.set(button.dataset.plainNode, button);
    }

    const flows = [...plain.querySelectorAll('.plain-flow')];
    for (let index = 0; index < flows.length; index += 1) {
      const flow = flows[index];
      const expected = contract.flows[index];
      if (!expected) continue;

      const laneElements = [...flow.querySelectorAll('.plain-lane')];
      const laneRows = [
        [expected.trigger].filter(Boolean),
        expected.requirements || [],
        expected.actions || [],
        expected.results || [],
      ];

      laneElements.forEach((lane, laneIndex) => {
        const title = lane.querySelector('.plain-lane-title')?.outerHTML || '';
        const rows = laneRows[laneIndex] || [];
        lane.innerHTML = title + (rows.length ? rows.map(row => (
          `<button type="button" class="plain-card" data-contract-node="${esc(row.node_id)}">` +
          `<strong>${esc(row.label)}</strong><small>${esc(row.technical_label || row.node_id)}</small></button>`
        )).join('') : '<div class="plain-empty">No explicit steps identified</div>');
      });

      for (const button of flow.querySelectorAll('[data-contract-node]')) {
        button.addEventListener('click', () => {
          const nodeId = button.dataset.contractNode;
          const sourceButton = originalButtons.get(nodeId);
          if (sourceButton) {
            sourceButton.click();
            return;
          }
          document.getElementById('behavior-mode-technical')?.click();
          queueMicrotask(() => {
            const graphNode = [...document.querySelectorAll('.behavior-node')]
              .find(node => node.dataset.id === nodeId);
            graphNode?.dispatchEvent(new MouseEvent('click', {bubbles: true}));
          });
        });
      }

      const summary = flow.querySelector('.plain-summary');
      if (!summary) continue;
      const collapsedCount = Number(expected.collapsed_count || 0);
      const collapsedChip = collapsedCount
        ? `<span class="chip">${collapsedCount} implementation node${collapsedCount === 1 ? '' : 's'} collapsed</span>`
        : '';
      summary.innerHTML = `${esc(expected.summary || '')}${collapsedChip}`;
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
