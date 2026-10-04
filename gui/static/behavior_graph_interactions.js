(() => {
  const CONTRACT_VERSION = '2';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

  function installBranchStyles() {
    if (document.getElementById('behavior-branch-flow-styles')) return;
    const style = document.createElement('style');
    style.id = 'behavior-branch-flow-styles';
    style.textContent = `
      #behavior-plain-view .plain-branch-intro{margin:0 0 8px;padding:8px 10px;border:1px solid var(--border);border-radius:7px;background:var(--surface)}
      #behavior-plain-view .plain-branch-group{margin:10px 0;border:1px solid var(--border);border-radius:8px;background:var(--surface);overflow:hidden}
      #behavior-plain-view .plain-branch-trigger{display:flex;gap:8px;align-items:center;padding:9px 10px;background:var(--code-bg);border-bottom:1px solid var(--border)}
      #behavior-plain-view .plain-branch-trigger button{font-weight:700}
      #behavior-plain-view .plain-branch-tree{padding:10px 12px 12px}
      #behavior-plain-view .plain-branch{position:relative;margin:7px 0 7px 18px;padding:8px 9px 8px 12px;border-left:3px solid var(--border);border-radius:0 6px 6px 0;background:var(--code-bg)}
      #behavior-plain-view .plain-branch::before{content:'';position:absolute;left:-18px;top:18px;width:15px;border-top:2px solid var(--border)}
      #behavior-plain-view .plain-branch.root{margin-left:4px;border-left-color:var(--accent,#5684a5)}
      #behavior-plain-view .plain-branch.root::before{display:none}
      #behavior-plain-view .plain-branch-gate{display:flex;align-items:flex-start;gap:6px;flex-wrap:wrap;margin-bottom:7px}
      #behavior-plain-view .plain-branch-gate-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);padding-top:5px}
      #behavior-plain-view .plain-guard{display:inline-flex;text-align:left;border:1px solid var(--border);border-radius:999px;padding:4px 8px;background:var(--surface);color:var(--text);cursor:pointer}
      #behavior-plain-view .plain-guard:hover,#behavior-plain-view .plain-effect:hover,#behavior-plain-view .plain-trigger-button:hover{border-color:var(--accent,#5684a5)}
      #behavior-plain-view .plain-branch-effects{display:flex;gap:6px;flex-wrap:wrap;align-items:stretch}
      #behavior-plain-view .plain-branch-arrow{display:flex;align-items:center;color:var(--muted);font-weight:700;padding:0 1px}
      #behavior-plain-view .plain-effect{display:flex;flex-direction:column;gap:2px;min-width:150px;max-width:320px;text-align:left;border:1px solid var(--border);border-radius:6px;padding:6px 8px;background:var(--surface);color:var(--text);cursor:pointer}
      #behavior-plain-view .plain-effect small{color:var(--muted);font-family:ui-monospace,Consolas,monospace;overflow-wrap:anywhere}
      #behavior-plain-view .plain-branch-children{margin-top:8px;padding-left:7px;border-left:1px dashed var(--border)}
      #behavior-plain-view .plain-branch-empty{color:var(--muted);font-size:12px;padding:4px 0}
      #behavior-plain-view .plain-event-handoffs{margin:12px 0;border:1px dashed var(--border);border-radius:8px;padding:9px 10px;background:var(--surface)}
      #behavior-plain-view .plain-event-handoff{display:grid;grid-template-columns:minmax(140px,1fr) auto minmax(160px,1fr);gap:8px;align-items:center;padding:7px 0;border-top:1px dotted var(--border)}
      #behavior-plain-view .plain-event-handoff:first-of-type{border-top:0}
      #behavior-plain-view .plain-handoff-middle{text-align:center;color:var(--muted);font-size:11px}
      #behavior-plain-view .plain-handoff-dots{display:block;font-size:18px;letter-spacing:2px;line-height:1}
      #behavior-plain-view .plain-handoff-side{display:flex;gap:5px;flex-wrap:wrap}
      #behavior-plain-view .plain-handoff-side button{font-size:11px}
      #behavior-plain-view .plain-trigger-button{border:1px solid var(--border);border-radius:6px;background:var(--surface);color:var(--text);padding:5px 8px;cursor:pointer;text-align:left}
      @media(max-width:760px){#behavior-plain-view .plain-event-handoff{grid-template-columns:1fr}.plain-handoff-middle{text-align:left!important}}
    `;
    document.head.appendChild(style);
  }

  function applyPlainContract() {
    const plain = document.getElementById('behavior-plain-view');
    const dataEl = document.getElementById('behavior-data');
    if (!plain || !dataEl || plain.dataset.plainContractVersion === CONTRACT_VERSION) return;

    let graph;
    try { graph = JSON.parse(dataEl.textContent || '{}'); } catch { return; }
    const contract = graph.plain_behavior;
    if (!contract || !Array.isArray(contract.flows)) return;

    const originalButtons = new Map();
    for (const button of plain.querySelectorAll('[data-plain-node]')) {
      if (!originalButtons.has(button.dataset.plainNode)) originalButtons.set(button.dataset.plainNode, button);
    }

    const selectNode = nodeId => {
      if (!nodeId) return;
      const sourceButton = originalButtons.get(String(nodeId));
      if (sourceButton) {
        sourceButton.click();
        return;
      }
      document.getElementById('behavior-mode-technical')?.click();
      queueMicrotask(() => {
        const graphNode = [...document.querySelectorAll('.behavior-node')]
          .find(node => node.dataset.id === String(nodeId));
        graphNode?.dispatchEvent(new MouseEvent('click', {bubbles: true}));
      });
    };

    const cardButton = (row, className) => (
      `<button type="button" class="${className}" data-contract-node="${esc(row.node_id)}">` +
      `<strong>${esc(row.label)}</strong>${row.technical_label ? `<small>${esc(row.technical_label)}</small>` : ''}</button>`
    );

    const branchGroups = Array.isArray(contract.branch_groups) ? contract.branch_groups : [];
    if (contract.presentation === 'branch_tree_v1' && branchGroups.length) {
      installBranchStyles();

      const renderBranch = (branch, depth = 0) => {
        const requirements = branch.display_requirements || branch.direct_requirements || branch.requirements || [];
        const effects = branch.effects || [];
        const children = branch.children || [];
        const gate = requirements.length
          ? `<div class="plain-branch-gate"><span class="plain-branch-gate-label">${depth ? 'And if' : 'If / when'}</span>${requirements.map(row => cardButton(row, 'plain-guard')).join('')}</div>`
          : `<div class="plain-branch-gate"><span class="plain-branch-gate-label">${depth ? 'Then' : 'Direct behavior'}</span></div>`;
        const effectHtml = effects.length
          ? `<div class="plain-branch-effects"><span class="plain-branch-arrow">→</span>${effects.map(row => cardButton(row, 'plain-effect')).join('')}</div>`
          : '<div class="plain-branch-empty">No direct effect at this branch; it only gates more-specific behavior.</div>';
        const childHtml = children.length
          ? `<div class="plain-branch-children">${children.map(row => renderBranch(row, depth + 1)).join('')}</div>`
          : '';
        return `<div class="plain-branch${depth === 0 ? ' root' : ''}" data-branch-id="${esc(branch.branch_id)}">${gate}${effectHtml}${childHtml}</div>`;
      };

      const groupsHtml = branchGroups.map(group => {
        const trigger = group.trigger || {};
        const branches = group.branches || [];
        return `<section class="plain-branch-group">` +
          `<div class="plain-branch-trigger"><span class="chip">Trigger</span>${cardButton(trigger, 'plain-trigger-button')}<span class="muted">${Number(group.branch_count || 0)} branch${Number(group.branch_count || 0) === 1 ? '' : 'es'}</span></div>` +
          `<div class="plain-branch-tree">${branches.length ? branches.map(row => renderBranch(row)).join('') : '<div class="plain-branch-empty">No explicit guarded branches identified.</div>'}</div>` +
          `</section>`;
      }).join('');

      const handoffs = Array.isArray(contract.event_handoffs) ? contract.event_handoffs : [];
      const handoffHtml = handoffs.length ? (
        `<section class="plain-event-handoffs"><strong>Cross-hook event identity</strong>` +
        `<p class="muted">Dotted handoffs mean the same literal event/CSID is started and handled in different hooks. They do not assert runtime execution order.</p>` +
        handoffs.map(row => {
          const starts = (row.start_branches || []).map(ref => `<button type="button" class="plain-trigger-button" data-contract-node="${esc(ref.branch_id)}">${esc(ref.trigger_label)}</button>`).join('');
          const handlers = (row.handler_branches || []).map(ref => `<button type="button" class="plain-trigger-button" data-contract-node="${esc(ref.branch_id)}">${esc(ref.trigger_label)}</button>`).join('');
          return `<div class="plain-event-handoff"><div class="plain-handoff-side">${starts}</div>` +
            `<div class="plain-handoff-middle"><strong>Event ${esc(row.event_id)}</strong><span class="plain-handoff-dots">·····►</span>${esc(row.ordering || 'UNPROVEN')} ordering</div>` +
            `<div class="plain-handoff-side">${handlers}</div></div>`;
        }).join('') + `</section>`
      ) : '';

      plain.innerHTML = `<div class="plain-branch-intro"><strong>Branch-preserving behavior flow</strong><div class="muted">Solid branch connectors preserve source-proven guard → effect relationships. Sibling effects are not shown as ordered unless source evidence proves ordering.</div></div>${groupsHtml}${handoffHtml}`;
      for (const button of plain.querySelectorAll('[data-contract-node]')) {
        button.addEventListener('click', () => selectNode(button.dataset.contractNode));
      }
      plain.dataset.plainContractVersion = CONTRACT_VERSION;
      return;
    }

    const flows = [...plain.querySelectorAll('.plain-flow')];
    for (let index = 0; index < flows.length; index += 1) {
      const flow = flows[index];
      const expected = contract.flows[index];
      if (!expected || flow.dataset.plainContractVersion === CONTRACT_VERSION) continue;
      const laneElements = [...flow.querySelectorAll('.plain-lane')];
      const laneRows = [[expected.trigger].filter(Boolean), expected.requirements || [], expected.actions || [], expected.results || []];
      laneElements.forEach((lane, laneIndex) => {
        const title = lane.querySelector('.plain-lane-title')?.outerHTML || '';
        const rows = laneRows[laneIndex] || [];
        lane.innerHTML = title + (rows.length ? rows.map(row => cardButton(row, 'plain-card')).join('') : '<div class="plain-empty">No explicit steps identified</div>');
      });
      for (const button of flow.querySelectorAll('[data-contract-node]')) {
        button.addEventListener('click', () => selectNode(button.dataset.contractNode));
      }
      const summary = flow.querySelector('.plain-summary');
      if (summary) {
        const collapsedCount = Number(expected.collapsed_count || 0);
        const collapsedChip = collapsedCount ? `<span class="chip">${collapsedCount} implementation node${collapsedCount === 1 ? '' : 's'} collapsed</span>` : '';
        summary.innerHTML = `${esc(expected.summary || '')}${collapsedChip}`;
      }
      flow.dataset.plainContractVersion = CONTRACT_VERSION;
    }
    plain.dataset.plainContractVersion = CONTRACT_VERSION;
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
