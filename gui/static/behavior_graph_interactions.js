(() => {
  const COLLAPSED_HELPER_KINDS = new Set(['helper_call', 'shared_helper_callee']);

  function plainSummary(flow) {
    const lanes = [...flow.querySelectorAll('.plain-lane')];
    if (!lanes.length) return '';
    const trigger = flow.querySelector('header')?.textContent?.trim() || 'Behavior';
    const labels = lane => [...lane.querySelectorAll('.plain-card:not([hidden]) strong')].map(el => el.textContent.trim()).filter(Boolean);
    const parts = [`${trigger.replace(/[.]$/, '')}.`];
    const append = (prefix, rows) => {
      if (!rows.length) return;
      const shown = rows.slice(0, 2);
      const suffix = rows.length > 2 ? ` (+${rows.length - 2} more)` : '';
      parts.push(`${prefix} ${shown.join('; ')}${suffix}.`);
    };
    append('Checks', labels(lanes[1]));
    append('Then', labels(lanes[2]));
    append('Results:', labels(lanes[3]));
    return parts.join(' ');
  }

  function applyHelperParity() {
    const plain = document.getElementById('behavior-plain-view');
    const dataEl = document.getElementById('behavior-data');
    if (!plain || !dataEl) return;

    let graph;
    try { graph = JSON.parse(dataEl.textContent || '{}'); } catch { return; }
    const kinds = new Map((graph.nodes || []).map(node => [node.id, node.kind]));

    for (const flow of plain.querySelectorAll('.plain-flow')) {
      let collapsedHelpers = 0;
      for (const card of flow.querySelectorAll('[data-plain-node]')) {
        const kind = kinds.get(card.dataset.plainNode);
        const shouldCollapse = COLLAPSED_HELPER_KINDS.has(kind);
        card.hidden = shouldCollapse;
        if (shouldCollapse) collapsedHelpers += 1;
      }

      const summary = flow.querySelector('.plain-summary');
      if (!summary) continue;
      const text = plainSummary(flow);
      const existingRuleChip = [...summary.querySelectorAll('.chip')].find(chip => /internal rule/.test(chip.textContent || ''));
      const ruleChip = existingRuleChip ? existingRuleChip.outerHTML : '';
      const helperChip = collapsedHelpers
        ? `<span class="chip">${collapsedHelpers} helper plumbing node${collapsedHelpers === 1 ? '' : 's'} collapsed</span>`
        : '';
      summary.innerHTML = `${text}${ruleChip}${helperChip}`;
    }
  }

  const core = document.createElement('script');
  core.src = '/static/behavior_graph_interactions_core.js';
  core.onload = () => {
    const plain = document.getElementById('behavior-plain-view');
    if (!plain) return;
    let queued = false;
    const queueParity = () => {
      if (queued) return;
      queued = true;
      queueMicrotask(() => {
        queued = false;
        applyHelperParity();
      });
    };
    const observer = new MutationObserver(queueParity);
    observer.observe(plain, { childList: true, subtree: true });
    applyHelperParity();
  };
  document.head.appendChild(core);
})();
