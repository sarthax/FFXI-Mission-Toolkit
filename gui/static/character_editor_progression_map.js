(() => {
  window.CharacterProgressionMap = {
    render(payload) {
      const progression = payload?.progression || {};
      const bounded = progression.bounded || {};
      if (!bounded.available) return '<div class="ce-muted">Bounded progression map unavailable.</div>';

      const esc = window.esc || (v => String(v ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])));
      const effect = row => {
        const name = String(row?.effect || '').replaceAll('_',' ').toLowerCase();
        return `${name}${row?.subject ? ' · '+row.subject : ''}${row?.value !== null && row?.value !== undefined ? ' → '+row.value : ''}`;
      };
      const route = action => {
        const event = action?.event || {};
        const where = [event.zone, event.actor, event.event_id !== undefined ? 'event '+event.event_id : ''].filter(Boolean).join(' · ');
        const effects = (action?.effects || []).map(row => `<li>${esc(effect(row))}</li>`).join('');
        return `<article class="ce-map-route"><div class="ce-map-route-head"><strong>${esc(String(action?.trigger || 'Progression action').replaceAll('_',' '))}</strong><span>${esc(action?.eligibility || 'UNKNOWN')}</span></div>${where ? `<div class="ce-muted">${esc(where)}</div>` : ''}${effects ? `<ul>${effects}</ul>` : ''}<div class="ce-map-traces"><button type="button" data-map-trace="implementation" data-transition="${esc(action?.transition_id || '')}">Trace implementation</button><button type="button" data-map-trace="behavior" data-transition="${esc(action?.transition_id || '')}">Trace behavior</button></div></article>`;
      };
      const layer = step => {
        if (!step) return '<section class="ce-map-layer ce-map-empty"><h4>Not modeled</h4></section>';
        const actions = step.actions || (step.primary_action ? [step.primary_action] : []);
        const title = step.relation === 'previous' ? 'Previous' : step.relation === 'next' ? 'Next' : 'Current';
        return `<section class="ce-map-layer ce-map-${esc(step.relation)}"><header><h4>${title} layer</h4><span>Section ${esc(step.section_index)}</span></header>${actions.map(route).join('') || '<div class="ce-muted">No progression action modeled.</div>'}${actions.length > 1 ? `<div class="ce-map-alt">${actions.length} valid routes preserved in this layer</div>` : ''}</section>`;
      };

      return `<section class="ce-progression-map"><div class="ce-map-head"><div><strong>Progression Map</strong><div class="ce-muted">Parallel bounded view · same inspector payload</div></div><span class="ce-map-count">${bounded.blocked_alternatives || 0} off-layer blocked path(s) collapsed</span></div><div class="ce-map-layers">${layer(bounded.previous)}${layer(bounded.current)}${layer(bounded.next)}</div></section>`;
    }
  };

  const style = document.createElement('style');
  style.textContent = `
    .ce-progression-map{margin:10px 0;border:1px solid var(--border,#444);border-radius:8px;padding:10px;background:rgba(255,255,255,.018)}
    .ce-map-head,.ce-map-layer>header,.ce-map-route-head{display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap}
    .ce-map-count,.ce-map-alt{font-size:.82em;opacity:.78}.ce-map-layers{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin-top:9px}
    .ce-map-layer{border:1px solid var(--border,#444);border-radius:8px;padding:9px;min-width:0}.ce-map-layer h4{margin:0}.ce-map-previous{border-top:3px solid #4a8}.ce-map-current{border-top:3px solid #58a6ff}.ce-map-next{border-top:3px solid #8b7fd6}
    .ce-map-route{border:1px solid var(--border,#3b3b3b);border-radius:6px;padding:8px;margin-top:7px;background:rgba(0,0,0,.12)}.ce-map-route ul{margin:5px 0;padding-left:18px;font-size:.86em}
    .ce-map-traces{display:flex;gap:5px;flex-wrap:wrap;margin-top:7px}.ce-map-traces button{font-size:.82em}.ce-map-alt{margin-top:7px;padding-top:6px;border-top:1px solid var(--border,#333)}
    @media(max-width:900px){.ce-map-layers{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);
})();