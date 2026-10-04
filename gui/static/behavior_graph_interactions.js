(() => {
  const CONTRACT_VERSION = '8';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  let activateClarified = () => {};

  function installBranchStyles() {
    if (document.getElementById('behavior-branch-flow-styles')) return;
    const style = document.createElement('style');
    style.id = 'behavior-branch-flow-styles';
    style.textContent = `
      #behavior-clarified-view .plain-branch-intro{margin:0 0 8px;padding:8px 10px;border:1px solid var(--border);border-radius:7px;background:var(--surface)}
      #behavior-clarified-view .plain-stage-chain{margin:10px 0 14px;border:1px solid var(--border);border-radius:8px;background:var(--surface);overflow:hidden}
      #behavior-clarified-view .plain-stage-chain>header{padding:9px 11px;background:var(--code-bg);border-bottom:1px solid var(--border)}
      #behavior-clarified-view .plain-stage-chain>header strong,#behavior-clarified-view .plain-stage-chain>header .muted{display:block}
      #behavior-clarified-view .plain-stage-chain>header .muted{margin-top:2px;font-size:11px}
      #behavior-clarified-view .plain-stage-chain-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:10px 11px;border-top:1px dotted var(--border)}
      #behavior-clarified-view .plain-stage-chain-row:first-of-type{border-top:0}
      #behavior-clarified-view .plain-stage-chain-step{display:flex;flex-direction:column;gap:2px;min-width:115px;padding:7px 9px;border:1px solid var(--border);border-radius:7px;background:var(--code-bg)}
      #behavior-clarified-view .plain-stage-chain-step strong{font-size:13px}
      #behavior-clarified-view .plain-stage-chain-step small{color:var(--muted)}
      #behavior-clarified-view .plain-stage-chain-arrow{display:flex;flex-direction:column;align-items:center;text-align:center;color:var(--muted);font-size:10px;line-height:1.2}
      #behavior-clarified-view .plain-stage-chain-arrow b{font-size:18px;line-height:1;color:var(--text)}
      #behavior-clarified-view .plain-stage-overview{margin:10px 0 14px;border:1px solid var(--border);border-radius:8px;background:var(--surface);overflow:hidden}
      #behavior-clarified-view .plain-stage-overview>header{padding:9px 11px;background:var(--code-bg);border-bottom:1px solid var(--border)}
      #behavior-clarified-view .plain-stage-overview>header strong,#behavior-clarified-view .plain-stage-overview>header .muted{display:block}
      #behavior-clarified-view .plain-stage-overview>header .muted{margin-top:2px;font-size:11px}
      #behavior-clarified-view .plain-stage-row{display:grid;grid-template-columns:minmax(170px,.9fr) minmax(150px,.7fr) minmax(180px,1fr);gap:10px;align-items:stretch;padding:10px 11px;border-top:1px dotted var(--border)}
      #behavior-clarified-view .plain-stage-row:first-of-type{border-top:0}
      #behavior-clarified-view .plain-stage-cell{display:flex;flex-direction:column;gap:5px;min-width:0}
      #behavior-clarified-view .plain-stage-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
      #behavior-clarified-view .plain-stage-value{font-weight:700}
      #behavior-clarified-view .plain-stage-event{display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;border-left:1px dashed var(--border);border-right:1px dashed var(--border);padding:4px 10px}
      #behavior-clarified-view .plain-stage-event strong{font-size:13px}
      #behavior-clarified-view .plain-stage-event .muted{font-size:11px;margin-top:3px}
      #behavior-clarified-view .plain-lifecycle{margin:10px 0 14px;border:1px solid var(--border);border-radius:8px;background:var(--surface);overflow:hidden}
      #behavior-clarified-view .plain-lifecycle>header{padding:9px 11px;background:var(--code-bg);border-bottom:1px solid var(--border)}
      #behavior-clarified-view .plain-lifecycle>header strong{display:block}
      #behavior-clarified-view .plain-lifecycle>header .muted{display:block;margin-top:2px;font-size:11px}
      #behavior-clarified-view .plain-lifecycle-row{display:grid;grid-template-columns:minmax(180px,1fr) minmax(170px,.8fr) minmax(180px,1fr);gap:10px;align-items:stretch;padding:10px 11px;border-top:1px dotted var(--border)}
      #behavior-clarified-view .plain-lifecycle-row:first-of-type{border-top:0}
      #behavior-clarified-view .plain-lifecycle-side{display:flex;flex-direction:column;gap:5px;min-width:0}
      #behavior-clarified-view .plain-lifecycle-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
      #behavior-clarified-view .plain-lifecycle-middle{display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;color:var(--muted);font-size:11px;border-left:1px dashed var(--border);border-right:1px dashed var(--border);padding:4px 10px}
      #behavior-clarified-view .plain-lifecycle-middle strong{font-size:13px;color:var(--text);margin-bottom:3px}
      #behavior-clarified-view .plain-lifecycle-dots{font-size:18px;letter-spacing:2px;line-height:1.1;margin:2px 0}
      #behavior-clarified-view .plain-branch-group{margin:10px 0;border:1px solid var(--border);border-radius:8px;background:var(--surface);overflow:hidden}
      #behavior-clarified-view .plain-branch-trigger{display:flex;gap:8px;align-items:center;padding:9px 10px;background:var(--code-bg);border-bottom:1px solid var(--border)}
      #behavior-clarified-view .plain-branch-trigger button{font-weight:700}
      #behavior-clarified-view .plain-branch-tree{padding:10px 12px 12px}
      #behavior-clarified-view .plain-branch{position:relative;margin:7px 0 7px 18px;padding:8px 9px 8px 12px;border-left:3px solid var(--border);border-radius:0 6px 6px 0;background:var(--code-bg);transition:outline-color .15s ease,box-shadow .15s ease}
      #behavior-clarified-view .plain-branch::before{content:'';position:absolute;left:-18px;top:18px;width:15px;border-top:2px solid var(--border)}
      #behavior-clarified-view .plain-branch.root{margin-left:4px;border-left-color:var(--accent,#5684a5)}
      #behavior-clarified-view .plain-branch.root::before{display:none}
      #behavior-clarified-view .plain-branch.handoff-focus{outline:2px solid var(--accent,#5684a5);outline-offset:2px;box-shadow:0 0 0 3px color-mix(in srgb,var(--accent,#5684a5) 18%,transparent)}
      #behavior-clarified-view .plain-branch-gate{display:flex;align-items:flex-start;gap:6px;flex-wrap:wrap;margin-bottom:7px}
      #behavior-clarified-view .plain-branch-gate-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);padding-top:5px}
      #behavior-clarified-view .plain-guard{display:inline-flex;text-align:left;border:1px solid var(--border);border-radius:999px;padding:4px 8px;background:var(--surface);color:var(--text);cursor:pointer}
      #behavior-clarified-view .plain-guard:hover,#behavior-clarified-view .plain-effect:hover,#behavior-clarified-view .plain-trigger-button:hover{border-color:var(--accent,#5684a5)}
      #behavior-clarified-view .plain-branch-effects{display:flex;gap:6px;flex-wrap:wrap;align-items:stretch}
      #behavior-clarified-view .plain-branch-arrow{display:flex;align-items:center;color:var(--muted);font-weight:700;padding:0 1px}
      #behavior-clarified-view .plain-effect{display:flex;flex-direction:column;gap:2px;min-width:150px;max-width:320px;text-align:left;border:1px solid var(--border);border-radius:6px;padding:6px 8px;background:var(--surface);color:var(--text);cursor:pointer}
      #behavior-clarified-view .plain-effect small{color:var(--muted);font-family:ui-monospace,Consolas,monospace;overflow-wrap:anywhere}
      #behavior-clarified-view .plain-branch-children{margin-top:8px;padding-left:7px;border-left:1px dashed var(--border)}
      #behavior-clarified-view .plain-branch-empty{color:var(--muted);font-size:12px;padding:4px 0}
      #behavior-clarified-view .plain-trigger-button{border:1px solid var(--border);border-radius:6px;background:var(--surface);color:var(--text);padding:5px 8px;cursor:pointer;text-align:left}
      #behavior-clarified-view[hidden]{display:none!important}
      @media(max-width:820px){#behavior-clarified-view .plain-stage-chain-row{align-items:stretch}#behavior-clarified-view .plain-stage-chain-step{flex:1 1 120px}#behavior-clarified-view .plain-stage-row,#behavior-clarified-view .plain-lifecycle-row{grid-template-columns:1fr}#behavior-clarified-view .plain-stage-event,#behavior-clarified-view .plain-lifecycle-middle{align-items:flex-start;text-align:left;border-left:0;border-right:0;border-top:1px dashed var(--border);border-bottom:1px dashed var(--border)}}
    `;
    document.head.appendChild(style);
  }

  function applyClarifiedContract() {
    const clarified = document.getElementById('behavior-clarified-view');
    const plain = document.getElementById('behavior-plain-view');
    const dataEl = document.getElementById('behavior-data');
    if (!clarified || !plain || !dataEl || clarified.dataset.plainContractVersion === CONTRACT_VERSION) return;

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
        queueMicrotask(activateClarified);
        return;
      }
      const graphNode = [...document.querySelectorAll('.behavior-node')]
        .find(node => node.dataset.id === String(nodeId));
      graphNode?.dispatchEvent(new MouseEvent('click', {bubbles: true}));
      queueMicrotask(activateClarified);
    };

    const focusBranch = branchId => {
      if (!branchId) return;
      activateClarified();
      queueMicrotask(() => {
        for (const branch of clarified.querySelectorAll('[data-branch-id]')) {
          branch.classList.toggle('handoff-focus', branch.dataset.branchId === String(branchId));
        }
        const target = [...clarified.querySelectorAll('[data-branch-id]')]
          .find(branch => branch.dataset.branchId === String(branchId));
        target?.scrollIntoView({behavior: 'smooth', block: 'center'});
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
      const stageRows = Array.isArray(contract.stage_lifecycles) ? contract.stage_lifecycles : [];
      const chainLinks = Array.isArray(contract.stage_chain_links) ? contract.stage_chain_links : [];
      const chainHtml = chainLinks.length ? (
        `<section class="plain-stage-chain"><header><strong>Verified stage continuity</strong>` +
        `<span class="muted">A link appears only when one verified direct next-stage literal matches exactly one verified start literal for the same canonical state. This is value continuity across evidence, not proven runtime ordering.</span></header>` +
        chainLinks.map(link => `<div class="plain-stage-chain-row">` +
          `<div class="plain-stage-chain-step"><small>Current stage</small><strong>${esc(link.state_name)} = ${esc(link.from_value)}</strong></div>` +
          `<div class="plain-stage-chain-arrow"><b>→</b><span>Event ${esc(link.via_event_id)}</span></div>` +
          `<div class="plain-stage-chain-step"><small>Verified next value</small><strong>${esc(link.state_name)} = ${esc(link.next_value)}</strong></div>` +
          `<div class="plain-stage-chain-arrow"><b>·····►</b><span>same-state literal continuity</span><span>${esc(link.ordering || 'UNPROVEN')} ordering</span></div>` +
          `<div class="plain-stage-chain-step"><small>Unique matching start</small><strong>Event ${esc(link.next_event_id)}</strong></div>` +
        `</div>`).join('') + `</section>`
      ) : '';

      const stageHtml = stageRows.length ? (
        `<section class="plain-stage-overview"><header><strong>Stage progression</strong>` +
        `<span class="muted">Rows come from the verified stage lifecycle contract: a literal stage guard starts this Event/CSID, and a matching literal handler directly writes the same canonical state. The dotted cross-hook handoff is identity evidence only; runtime ordering remains unproven.</span></header>` +
        stageRows.map(row => {
          const handlers = (row.handler_branches || []).map(ref => `<button type="button" class="plain-trigger-button" data-contract-branch="${esc(ref.branch_id)}">${esc(ref.trigger_label)}</button>`).join('') || '<span class="muted">No handler branch indexed</span>';
          const writes = (row.handler_writes || []).map(write => `<span class="plain-stage-value">${esc(write.state_name || row.state_name)} = ${esc(write.value)}</span><span class="muted">${esc(write.hook || '')}${write.source_line ? ` · line ${esc(write.source_line)}` : ''}</span>`).join('') || '<span class="muted">No verified direct same-state write</span>';
          return `<div class="plain-stage-row">` +
            `<div class="plain-stage-cell"><span class="plain-stage-label">Current stage</span><span class="plain-stage-value">${esc(row.state_name)} = ${esc(row.from_value)}</span><span class="muted">verified source guard · ${esc(row.start_hook || '')}</span></div>` +
            `<div class="plain-stage-event"><strong>Event ${esc(row.event_id)}</strong><span class="muted">started by this stage guard</span><span class="plain-lifecycle-dots">·····►</span><span class="muted">same literal event identity · ${esc(row.ordering || 'UNPROVEN')} ordering</span></div>` +
            `<div class="plain-stage-cell"><span class="plain-stage-label">Verified next-stage write</span>${writes}${handlers}</div>` +
          `</div>`;
        }).join('') + `</section>`
      ) : '';

      const lifecycleHtml = handoffs.length ? (
        `<section class="plain-lifecycle"><header><strong>Event lifecycle</strong>` +
        `<span class="muted">These rows group the source branch that starts an Event/CSID with branches that handle the same literal Event/CSID. The dotted middle is an identity handoff only; runtime ordering remains unproven.</span></header>` +
        handoffs.map(row => {
          const starts = (row.start_branches || []).map(ref => `<button type="button" class="plain-trigger-button" data-contract-branch="${esc(ref.branch_id)}">${esc(ref.trigger_label)}</button>`).join('') || '<span class="muted">No start branch indexed</span>';
          const handlers = (row.handler_branches || []).map(ref => `<button type="button" class="plain-trigger-button" data-contract-branch="${esc(ref.branch_id)}">${esc(ref.trigger_label)}</button>`).join('') || '<span class="muted">No handler branch indexed</span>';
          return `<div class="plain-lifecycle-row">` +
            `<div class="plain-lifecycle-side"><span class="plain-lifecycle-label">Starts event</span>${starts}</div>` +
            `<div class="plain-lifecycle-middle"><strong>Event ${esc(row.event_id)}</strong><span class="plain-lifecycle-dots">·····►</span><span>same literal event identity</span><span>${esc(row.ordering || 'UNPROVEN')} ordering</span></div>` +
            `<div class="plain-lifecycle-side"><span class="plain-lifecycle-label">Handled by</span>${handlers}</div>` +
          `</div>`;
        }).join('') + `</section>`
      ) : '';

      clarified.innerHTML = `<div class="plain-branch-intro"><strong>Clarified branch flow</strong><div class="muted">Solid branch connectors preserve source-proven guard → effect relationships. Sibling effects are not shown as ordered unless source evidence proves ordering. Stage continuity, stage progression, and event lifecycle rows use backend evidence contracts without claiming runtime sequence.</div></div>${chainHtml}${stageHtml}${lifecycleHtml}${groupsHtml}`;
      for (const button of clarified.querySelectorAll('[data-contract-node]')) {
        button.addEventListener('click', () => selectNode(button.dataset.contractNode));
      }
      for (const button of clarified.querySelectorAll('[data-contract-branch]')) {
        button.addEventListener('click', () => focusBranch(button.dataset.contractBranch));
      }
      clarified.dataset.plainContractVersion = CONTRACT_VERSION;
      return;
    }

    clarified.innerHTML = '<div class="plain-branch-intro"><strong>Clarified Flow</strong><div class="muted">No branch-preserving projection is available for this script. Use Plain Behavior or Technical Graph for the extracted evidence.</div></div>';
    clarified.dataset.plainContractVersion = CONTRACT_VERSION;
  }

  const core = document.createElement('script');
  core.src = '/static/behavior_graph_interactions_core.js';
  core.onload = () => {
    const plain = document.getElementById('behavior-plain-view');
    const workspace = document.getElementById('behavior-workspace');
    const plainButton = document.getElementById('behavior-mode-plain');
    const technicalButton = document.getElementById('behavior-mode-technical');
    const canvasWrap = document.getElementById('behavior-graph')?.closest('.behavior-canvas-wrap');
    if (!plain || !workspace || !plainButton || !technicalButton || !canvasWrap) return;

    const clarified = document.createElement('div');
    clarified.id = 'behavior-clarified-view';
    clarified.className = 'behavior-plain';
    workspace.insertBefore(clarified, plain);

    const clarifiedButton = document.createElement('button');
    clarifiedButton.type = 'button';
    clarifiedButton.id = 'behavior-mode-clarified';
    clarifiedButton.textContent = 'Clarified Flow';
    plainButton.parentElement.insertBefore(clarifiedButton, plainButton);

    const legend = document.querySelector('.behavior-legend');
    const status = document.getElementById('behavior-status');
    const controls = document.querySelector('.behavior-inspector .behavior-controls');
    const technicalControls = () => controls?.querySelectorAll('#behavior-zoom-in,#behavior-zoom-out,#behavior-fit-view,#behavior-reset-view,.behavior-view-hint') || [];

    activateClarified = () => {
      clarifiedButton.classList.add('active');
      plainButton.classList.remove('active');
      technicalButton.classList.remove('active');
      clarified.hidden = false;
      plain.hidden = true;
      canvasWrap.hidden = true;
      if (legend) legend.hidden = true;
      if (status) status.hidden = true;
      [...technicalControls()].forEach(el => { el.style.display = 'none'; });
    };

    clarifiedButton.addEventListener('click', activateClarified);
    plainButton.addEventListener('click', () => {
      clarified.hidden = true;
      clarifiedButton.classList.remove('active');
    });
    technicalButton.addEventListener('click', () => {
      clarified.hidden = true;
      clarifiedButton.classList.remove('active');
    });

    applyClarifiedContract();
    activateClarified();
  };
  document.head.appendChild(core);
})();