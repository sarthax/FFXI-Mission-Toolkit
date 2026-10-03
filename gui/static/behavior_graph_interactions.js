(() => {
  const svg = document.getElementById('behavior-graph');
  const dataEl = document.getElementById('behavior-data');
  if (!svg || !dataEl) return;

  let data;
  try { data = JSON.parse(dataEl.textContent || '{}'); }
  catch { return; }

  const filter = document.getElementById('behavior-filter');
  const resetSelection = document.getElementById('behavior-reset');
  const status = document.getElementById('behavior-status');
  const controls = document.querySelector('.behavior-inspector .behavior-controls');
  const BASE_VIEW = {x: 0, y: 0, w: 1480, h: 760};
  let view = {...BASE_VIEW};
  let selected = null;
  let dragging = null;
  let applying = false;

  const style = document.createElement('style');
  style.id = 'behaviorGraphInteractionStyles';
  style.textContent = `
    .behavior-canvas-wrap{overflow:hidden;min-height:620px;position:relative}
    #behavior-graph{width:100%;height:clamp(620px,70vh,820px);min-width:0;min-height:620px;touch-action:none;cursor:grab;user-select:none}
    #behavior-graph.behavior-panning{cursor:grabbing}
    .behavior-edge.path-active{stroke:#38bdf8;stroke-width:3;opacity:1}
    .behavior-edge.path-dim{opacity:.10}
    .behavior-node.path-active{opacity:1}
    .behavior-node.path-active rect{stroke:#67e8f9;stroke-width:2.4}
    .behavior-node.path-dim{opacity:.16}
    .behavior-node.selected.path-active rect{stroke:#fff;stroke-width:3.2}
    .behavior-view-hint{font-size:11px;color:var(--muted)}
  `;
  document.head.appendChild(style);

  if (controls && !document.getElementById('behavior-fit-view')) {
    const spacer = document.createElement('span');
    spacer.className = 'behavior-view-hint';
    spacer.textContent = 'Wheel to zoom · drag empty graph space to pan';
    controls.appendChild(spacer);
    for (const [id, label, title] of [
      ['behavior-zoom-in', '+', 'Zoom in'],
      ['behavior-zoom-out', '−', 'Zoom out'],
      ['behavior-fit-view', 'Fit', 'Fit visible graph'],
      ['behavior-reset-view', 'Reset view', 'Reset pan and zoom'],
    ]) {
      const button = document.createElement('button');
      button.type = 'button';
      button.id = id;
      button.textContent = label;
      button.title = title;
      controls.appendChild(button);
    }
  }

  const outgoing = new Map();
  const incoming = new Map();
  for (const edge of (data.edges || [])) {
    (outgoing.get(edge.source) || outgoing.set(edge.source, []).get(edge.source)).push(edge);
    (incoming.get(edge.target) || incoming.set(edge.target, []).get(edge.target)).push(edge);
  }
  const edgeKey = edge => `${edge.source}|${edge.kind || ''}|${edge.target}`;

  // Unlike the old undirected connected-component walk, traverse upstream and downstream
  // independently from the selected node. That highlights the selected causal chain without
  // walking back through an ancestor and lighting unrelated sibling branches.
  function causalPath(id) {
    const nodeIds = new Set();
    const edgeIds = new Set();
    if (!id) return {nodeIds, edgeIds};
    nodeIds.add(id);

    const walk = (seed, adjacency, nextId) => {
      const seen = new Set([seed]);
      const queue = [seed];
      while (queue.length) {
        const current = queue.shift();
        for (const edge of (adjacency.get(current) || [])) {
          edgeIds.add(edgeKey(edge));
          const next = nextId(edge);
          nodeIds.add(next);
          if (!seen.has(next)) {
            seen.add(next);
            queue.push(next);
          }
        }
      }
    };
    walk(id, incoming, edge => edge.source);
    walk(id, outgoing, edge => edge.target);
    return {nodeIds, edgeIds};
  }

  function matches(node, query) {
    if (!query) return true;
    const hay = [node.id, node.kind, node.label, JSON.stringify(node.meta || {})].join(' ').toLowerCase();
    return hay.includes(query);
  }

  function currentlyVisibleEdges() {
    const query = (filter?.value || '').trim().toLowerCase();
    const ids = new Set((data.nodes || []).filter(node => matches(node, query)).map(node => node.id));
    return (data.edges || []).filter(edge => ids.has(edge.source) && ids.has(edge.target));
  }

  function setViewBox() {
    svg.setAttribute('viewBox', `${view.x} ${view.y} ${view.w} ${view.h}`);
  }

  function applyFocus() {
    if (applying) return;
    applying = true;
    try {
      setViewBox();
      const path = causalPath(selected);
      const visibleEdges = currentlyVisibleEdges();
      const edgeElements = [...svg.querySelectorAll('.behavior-edge')];
      edgeElements.forEach((element, index) => {
        const edge = visibleEdges[index];
        const active = !selected || (edge && path.edgeIds.has(edgeKey(edge)));
        element.classList.toggle('path-active', Boolean(selected && active));
        element.classList.toggle('path-dim', Boolean(selected && !active));
        // Override the legacy connected-component dimming with the directed causal path.
        element.classList.toggle('dim', Boolean(selected && !active));
      });
      svg.querySelectorAll('.behavior-node').forEach(element => {
        const active = !selected || path.nodeIds.has(element.dataset.id);
        element.classList.toggle('path-active', Boolean(selected && active));
        element.classList.toggle('path-dim', Boolean(selected && !active));
        element.classList.toggle('dim', Boolean(selected && !active));
      });
      if (selected && status) {
        const base = (status.textContent || '').replace(/ · Selected causal chain:.*$/, '');
        status.textContent = `${base} · Selected causal chain: ${path.nodeIds.size} nodes / ${path.edgeIds.size} edges.`;
      }
    } finally {
      applying = false;
    }
  }

  function scaleAt(factor, clientX = null, clientY = null) {
    const rect = svg.getBoundingClientRect();
    const px = clientX == null ? 0.5 : Math.max(0, Math.min(1, (clientX - rect.left) / Math.max(1, rect.width)));
    const py = clientY == null ? 0.5 : Math.max(0, Math.min(1, (clientY - rect.top) / Math.max(1, rect.height)));
    let newW = view.w * factor;
    let newH = view.h * factor;
    const minW = 320, maxW = 7000;
    if (newW < minW) { const adjust = minW / newW; newW *= adjust; newH *= adjust; }
    if (newW > maxW) { const adjust = maxW / newW; newW *= adjust; newH *= adjust; }
    view.x += (view.w - newW) * px;
    view.y += (view.h - newH) * py;
    view.w = newW;
    view.h = newH;
    setViewBox();
  }

  function fitVisible() {
    const groups = [...svg.querySelectorAll('.behavior-node')];
    if (!groups.length) { view = {...BASE_VIEW}; setViewBox(); return; }
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const group of groups) {
      let box;
      try { box = group.getBBox(); } catch { continue; }
      const transform = group.transform?.baseVal?.consolidate?.();
      const tx = transform?.matrix?.e || 0;
      const ty = transform?.matrix?.f || 0;
      minX = Math.min(minX, tx + box.x);
      minY = Math.min(minY, ty + box.y);
      maxX = Math.max(maxX, tx + box.x + box.width);
      maxY = Math.max(maxY, ty + box.y + box.height);
    }
    if (!Number.isFinite(minX)) { view = {...BASE_VIEW}; setViewBox(); return; }
    const padX = 110, padY = 80;
    view = {
      x: minX - padX,
      y: minY - padY,
      w: Math.max(480, maxX - minX + padX * 2),
      h: Math.max(360, maxY - minY + padY * 2),
    };
    setViewBox();
  }

  svg.addEventListener('wheel', event => {
    event.preventDefault();
    scaleAt(event.deltaY > 0 ? 1.14 : 0.875, event.clientX, event.clientY);
  }, {passive: false});

  svg.addEventListener('pointerdown', event => {
    if (event.button !== 0 || event.target.closest?.('.behavior-node')) return;
    dragging = {clientX: event.clientX, clientY: event.clientY, x: view.x, y: view.y};
    svg.classList.add('behavior-panning');
    try { svg.setPointerCapture(event.pointerId); } catch {}
  });
  svg.addEventListener('pointermove', event => {
    if (!dragging) return;
    view.x = dragging.x - (event.clientX - dragging.clientX) * view.w / Math.max(1, svg.clientWidth);
    view.y = dragging.y - (event.clientY - dragging.clientY) * view.h / Math.max(1, svg.clientHeight);
    setViewBox();
  });
  const endPan = event => {
    dragging = null;
    svg.classList.remove('behavior-panning');
    try { svg.releasePointerCapture(event.pointerId); } catch {}
  };
  svg.addEventListener('pointerup', endPan);
  svg.addEventListener('pointercancel', endPan);

  // Delegation survives the legacy renderer replacing all SVG children on every selection/filter.
  svg.addEventListener('click', event => {
    const node = event.target.closest?.('.behavior-node');
    if (!node) return;
    selected = node.dataset.id || null;
    queueMicrotask(applyFocus);
  });
  filter?.addEventListener('input', () => queueMicrotask(applyFocus));
  resetSelection?.addEventListener('click', () => {
    selected = null;
    queueMicrotask(applyFocus);
  });

  document.getElementById('behavior-zoom-in')?.addEventListener('click', () => scaleAt(0.8));
  document.getElementById('behavior-zoom-out')?.addEventListener('click', () => scaleAt(1.25));
  document.getElementById('behavior-fit-view')?.addEventListener('click', fitVisible);
  document.getElementById('behavior-reset-view')?.addEventListener('click', () => {
    view = {...BASE_VIEW};
    setViewBox();
  });

  // Re-apply view state and path focus after the legacy renderer replaces graph children.
  const observer = new MutationObserver(() => queueMicrotask(applyFocus));
  observer.observe(svg, {childList: true});
  setViewBox();
  applyFocus();
})();
