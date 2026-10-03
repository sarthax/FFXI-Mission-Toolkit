(() => {
  const svg = document.getElementById('behavior-graph');
  const dataEl = document.getElementById('behavior-data');
  if (!svg || !dataEl) return;

  let data;
  try { data = JSON.parse(dataEl.textContent || '{}'); } catch { return; }

  const filter = document.getElementById('behavior-filter');
  const resetSelection = document.getElementById('behavior-reset');
  const status = document.getElementById('behavior-status');
  const controls = document.querySelector('.behavior-inspector .behavior-controls');
  const detail = document.getElementById('behavior-detail');
  const canvasWrap = svg.closest('.behavior-canvas-wrap');
  const BASE_VIEW = {x: 0, y: 0, w: 1480, h: 760};
  let view = {...BASE_VIEW};
  let selected = null;
  let dragging = null;
  let applying = false;
  let mode = 'plain';

  const nodes = new Map((data.nodes || []).map(node => [node.id, node]));
  const outgoing = new Map();
  const incoming = new Map();
  for (const edge of (data.edges || [])) {
    (outgoing.get(edge.source) || outgoing.set(edge.source, []).get(edge.source)).push(edge);
    (incoming.get(edge.target) || incoming.set(edge.target, []).get(edge.target)).push(edge);
  }
  const edgeKey = edge => `${edge.source}|${edge.kind || ''}|${edge.target}`;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

  const style = document.createElement('style');
  style.id = 'behaviorGraphInteractionStyles';
  style.textContent = `
    .behavior-mode-tabs{display:flex;gap:4px;margin:.55rem 0 .7rem;align-items:center;flex-wrap:wrap}
    .behavior-mode-tabs button{background:var(--surface);color:var(--ink);border-color:var(--border)}
    .behavior-mode-tabs button.active{background:var(--accent);color:#fff;border-color:var(--accent)}
    .behavior-mode-tabs .muted{font-size:11px;margin-left:4px}
    .behavior-workspace{display:grid;grid-template-columns:minmax(0,1fr) minmax(320px,380px);gap:12px;align-items:stretch;margin-top:.6rem}
    .behavior-workspace.inspector-collapsed{grid-template-columns:minmax(0,1fr) 42px}
    .behavior-canvas-wrap{overflow:hidden;min-height:620px;position:relative;margin:0}
    #behavior-graph{width:100%;height:clamp(620px,70vh,820px);min-width:0;min-height:620px;touch-action:none;cursor:grab;user-select:none}
    #behavior-graph.behavior-panning{cursor:grabbing}
    .behavior-inspector-pane{min-width:0;height:clamp(620px,70vh,820px);display:flex;flex-direction:column;border:1px solid var(--border);border-radius:6px;background:var(--card,var(--surface));overflow:hidden;position:sticky;top:8px}
    .behavior-inspector-pane-header{display:flex;align-items:center;gap:8px;padding:8px 9px;border-bottom:1px solid var(--border);background:var(--surface);flex:none}
    .behavior-inspector-pane-header strong{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
    .behavior-inspector-pane-header .sp{flex:1}.behavior-inspector-pane-header button{min-width:30px;padding:3px 7px;font-size:11px}
    .behavior-inspector-pane .behavior-detail{margin:0;border:0;border-radius:0;background:transparent;overflow:auto;flex:1;min-height:0;padding:12px}
    .behavior-workspace.inspector-collapsed .behavior-inspector-pane{width:42px}.behavior-workspace.inspector-collapsed .behavior-inspector-pane-header{height:100%;padding:6px;flex-direction:column}.behavior-workspace.inspector-collapsed .behavior-inspector-pane-header strong{writing-mode:vertical-rl;transform:rotate(180deg);margin-top:6px}.behavior-workspace.inspector-collapsed .behavior-inspector-pane-header .sp{display:none}.behavior-workspace.inspector-collapsed .behavior-detail{display:none}
    .behavior-plain{height:clamp(620px,70vh,820px);overflow:auto;border:1px solid var(--border);border-radius:6px;background:var(--surface);padding:12px}
    .behavior-plain[hidden],.behavior-canvas-wrap[hidden],.behavior-legend[hidden],#behavior-status[hidden]{display:none!important}
    .plain-intro{display:flex;gap:8px;align-items:flex-start;justify-content:space-between;margin-bottom:10px;padding-bottom:10px;border-bottom:1px solid var(--border)}
    .plain-intro strong{font-size:15px}.plain-intro p{margin:3px 0 0;color:var(--muted);font-size:12px}
    .plain-flow{border:1px solid var(--border);border-radius:7px;margin:0 0 12px;background:var(--bg)}
    .plain-flow>header{height:auto;min-height:0;padding:8px 10px;border-bottom:1px solid var(--border);background:var(--code-bg);font-weight:700}
    .plain-lanes{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:8px;padding:9px}
    .plain-lane{min-width:0}.plain-lane-title{font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin:0 0 5px}
    .plain-card{display:block;width:100%;text-align:left;background:var(--surface);color:var(--ink);border:1px solid var(--border);border-radius:6px;padding:7px 8px;margin:0 0 6px;cursor:pointer;line-height:1.25}
    .plain-card:hover{border-color:var(--accent);opacity:1}.plain-card strong{display:block;font-size:12px}.plain-card small{display:block;color:var(--muted);font-size:10px;margin-top:3px;word-break:break-word}.plain-card.selected{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
    .plain-empty{font-size:11px;color:var(--muted);padding:7px 4px}.plain-arrow{display:none}
    .behavior-edge.path-active{stroke:#38bdf8;stroke-width:3;opacity:1}.behavior-edge.path-dim{opacity:.10}.behavior-node.path-active{opacity:1}.behavior-node.path-active rect{stroke:#67e8f9;stroke-width:2.4}.behavior-node.path-dim{opacity:.16}.behavior-node.selected.path-active rect{stroke:#fff;stroke-width:3.2}.behavior-view-hint{font-size:11px;color:var(--muted)}
    @media(max-width:1200px){.plain-lanes{grid-template-columns:repeat(2,minmax(180px,1fr))}}
    @media(max-width:1000px){.behavior-workspace,.behavior-workspace.inspector-collapsed{grid-template-columns:1fr}.behavior-inspector-pane,.behavior-workspace.inspector-collapsed .behavior-inspector-pane{width:auto;height:auto;max-height:420px;position:static}.behavior-workspace.inspector-collapsed .behavior-inspector-pane{display:none}.behavior-workspace.inspector-collapsed .behavior-detail{display:block}.plain-lanes{grid-template-columns:1fr 1fr}}
    @media(max-width:650px){.plain-lanes{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);

  let workspace = null;
  let plainView = null;
  if (canvasWrap && detail && !document.getElementById('behavior-workspace')) {
    const tabs = document.createElement('div');
    tabs.className = 'behavior-mode-tabs';
    tabs.innerHTML = '<button type="button" id="behavior-mode-plain" class="active">Plain Behavior</button><button type="button" id="behavior-mode-technical">Technical Graph</button><span class="muted">Plain Behavior summarizes the same extracted evidence; use Technical Graph for Lua-level detail.</span>';
    canvasWrap.parentElement.insertBefore(tabs, canvasWrap);

    workspace = document.createElement('div');
    workspace.id = 'behavior-workspace';
    workspace.className = 'behavior-workspace';
    canvasWrap.parentElement.insertBefore(workspace, canvasWrap);

    plainView = document.createElement('div');
    plainView.id = 'behavior-plain-view';
    plainView.className = 'behavior-plain';
    workspace.appendChild(plainView);
    workspace.appendChild(canvasWrap);
    canvasWrap.hidden = true;

    const pane = document.createElement('aside');
    pane.className = 'behavior-inspector-pane';
    pane.setAttribute('aria-label', 'Selected behavior inspector');
    const paneHeader = document.createElement('div');
    paneHeader.className = 'behavior-inspector-pane-header';
    paneHeader.innerHTML = '<strong>Behavior Details</strong><span class="sp"></span>';
    const toggle = document.createElement('button');
    toggle.type = 'button'; toggle.id = 'behavior-inspector-toggle'; toggle.textContent = 'Collapse';
    paneHeader.appendChild(toggle); pane.appendChild(paneHeader); pane.appendChild(detail); workspace.appendChild(pane);
    toggle.addEventListener('click', () => {
      const collapsed = workspace.classList.toggle('inspector-collapsed');
      toggle.textContent = collapsed ? '›' : 'Collapse';
      toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    });

    document.getElementById('behavior-mode-plain').addEventListener('click', () => setMode('plain'));
    document.getElementById('behavior-mode-technical').addEventListener('click', () => setMode('technical'));
  }

  const legend = document.querySelector('.behavior-legend');
  function setMode(next) {
    mode = next;
    const plainButton = document.getElementById('behavior-mode-plain');
    const techButton = document.getElementById('behavior-mode-technical');
    if (plainButton) plainButton.classList.toggle('active', next === 'plain');
    if (techButton) techButton.classList.toggle('active', next === 'technical');
    if (plainView) plainView.hidden = next !== 'plain';
    if (canvasWrap) canvasWrap.hidden = next !== 'technical';
    if (legend) legend.hidden = next !== 'technical';
    if (status) status.hidden = next !== 'technical';
    if (controls) {
      [...controls.querySelectorAll('#behavior-zoom-in,#behavior-zoom-out,#behavior-fit-view,#behavior-reset-view,.behavior-view-hint')].forEach(el => el.style.display = next === 'technical' ? '' : 'none');
    }
    if (next === 'plain') renderPlain(); else { setViewBox(); applyFocus(); }
  }

  function humanHook(node) {
    const raw = String(node?.label || node?.id || 'Behavior');
    const low = raw.toLowerCase();
    if (low.includes('ontrigger')) return 'Player interacts with this actor';
    if (low.includes('ontrade')) return 'Player trades an item';
    if (low.includes('onmobdeath') || low.includes('ondeath')) return 'Actor is defeated';
    if (low.includes('onmobspawn') || low.includes('onspawn')) return 'Actor spawns';
    if (low.includes('onmobfight') || low.includes('onfight')) return 'During combat';
    if (low.includes('onmobengaged') || low.includes('onengaged')) return 'Combat starts';
    if (low.includes('onmobdisengage') || low.includes('ondisengage')) return 'Combat ends';
    if (low.includes('oneventfinish')) return 'A cutscene or event finishes';
    if (low.includes('oneventupdate')) return 'A cutscene or event updates';
    if (low.includes('timer')) return 'A timer or delayed action fires';
    if (low.includes('listener')) return 'A registered game event fires';
    return raw.replace(/^.*[:.]/, '').replace(/[_-]+/g, ' ');
  }

  function humanNode(node) {
    const meta = node?.meta || {};
    const raw = String(node?.label || meta.value || node?.id || 'Behavior step');
    const low = raw.toLowerCase();
    const value = meta.value != null ? String(meta.value) : '';
    if (node?.kind === 'state') return `Character/game state: ${raw.replace(/^.*:/, '')}`;
    if (low.includes('getcharvar')) return `Check character progress${value ? `: ${value}` : ''}`;
    if (low.includes('setcharvar')) return `Update character progress${value ? `: ${value}` : ''}`;
    if (low.includes('haskeyitem')) return `Requires a key item${value ? `: ${value}` : ''}`;
    if (low.includes('givekeyitem') || low.includes('addkeyitem')) return `Give key item${value ? `: ${value}` : ''}`;
    if (low.includes('delkeyitem')) return `Remove key item${value ? `: ${value}` : ''}`;
    if (low.includes('hasitem')) return `Requires an item${value ? `: ${value}` : ''}`;
    if (low.includes('giveitem') || low.includes('additem')) return `Give item${value ? `: ${value}` : ''}`;
    if (low.includes('delitem')) return `Remove item${value ? `: ${value}` : ''}`;
    if (low.includes('startevent')) return `Play cutscene / event${value ? ` ${value}` : ''}`;
    if (low.includes('completemission')) return 'Complete mission';
    if (low.includes('addmission')) return 'Start / advance mission';
    if (low.includes('completequest')) return 'Complete quest';
    if (low.includes('addquest')) return 'Start quest';
    if (low.includes('title')) return `Change title${value ? `: ${value}` : ''}`;
    if (low.includes('gil')) return `Change gil${value ? `: ${value}` : ''}`;
    if (low.includes('spawn')) return 'Spawn or enable an actor';
    if (low.includes('despawn')) return 'Despawn or disable an actor';
    if (low.includes('status')) return `Change actor status${value ? `: ${value}` : ''}`;
    return raw.replace(/^.*[:.]/, '').replace(/[_-]+/g, ' ');
  }

  function laneFor(node, edge = null) {
    const kind = node?.kind || '';
    const text = `${node?.label || ''} ${node?.meta?.effect || ''} ${node?.meta?.value || ''}`.toLowerCase();
    const edgeKind = String(edge?.kind || '').toLowerCase();
    if (kind === 'hook' || kind === 'callback' || kind === 'subject') return 'trigger';
    if (kind === 'condition' || kind === 'helper_input' || edgeKind.includes('read') || text.includes('getcharvar') || text.includes('hasitem') || text.includes('haskeyitem') || text.includes('getquest') || text.includes('getcurrentmission')) return 'requirements';
    if (kind === 'state' || edgeKind.includes('write') || text.includes('setcharvar') || text.includes('give') || text.includes('additem') || text.includes('delitem') || text.includes('addmission') || text.includes('completemission') || text.includes('addquest') || text.includes('completequest') || text.includes('title') || kind === 'target') return 'results';
    return 'actions';
  }

  function descendants(seed) {
    const found = [];
    const seen = new Set([seed]);
    const queue = [seed];
    while (queue.length) {
      const current = queue.shift();
      for (const edge of (outgoing.get(current) || [])) {
        if (seen.has(edge.target)) continue;
        seen.add(edge.target); queue.push(edge.target);
        const node = nodes.get(edge.target); if (node) found.push({node, edge});
      }
    }
    return found;
  }

  function triggerNodes() {
    const hooks = (data.nodes || []).filter(node => node.kind === 'hook' || node.kind === 'callback');
    return hooks.length ? hooks : (data.nodes || []).filter(node => node.kind === 'subject').slice(0, 1);
  }

  function card(node, lane) {
    const technical = node.id || node.label || '';
    return `<button type="button" class="plain-card${selected === node.id ? ' selected' : ''}" data-plain-node="${esc(node.id)}"><strong>${esc(lane === 'trigger' ? humanHook(node) : humanNode(node))}</strong><small>${esc(technical)}</small></button>`;
  }

  function renderPlain() {
    if (!plainView) return;
    const triggers = triggerNodes();
    let html = `<div class="plain-intro"><div><strong>What this behavior does</strong><p>Read left to right: what starts it, what must be true, what it does, and what changes afterward.</p></div><button type="button" id="plain-open-technical">Open technical graph</button></div>`;
    if (!triggers.length) html += '<div class="plain-empty">No trigger chain was identified in this source.</div>';
    for (const trigger of triggers) {
      const lanes = {requirements: [], actions: [], results: []};
      for (const item of descendants(trigger.id)) {
        const lane = laneFor(item.node, item.edge);
        if (lane !== 'trigger' && !lanes[lane].some(existing => existing.id === item.node.id)) lanes[lane].push(item.node);
      }
      html += `<section class="plain-flow"><header>${esc(humanHook(trigger))}</header><div class="plain-lanes">`;
      html += `<div class="plain-lane"><div class="plain-lane-title">Trigger</div>${card(trigger, 'trigger')}</div>`;
      for (const [lane, title] of [['requirements','Requirements'],['actions','Actions / Events'],['results','Results / State Changes']]) {
        html += `<div class="plain-lane"><div class="plain-lane-title">${title}</div>${lanes[lane].length ? lanes[lane].map(node => card(node, lane)).join('') : '<div class="plain-empty">No explicit steps identified</div>'}</div>`;
      }
      html += '</div></section>';
    }
    plainView.innerHTML = html;
    plainView.querySelector('#plain-open-technical')?.addEventListener('click', () => setMode('technical'));
    plainView.querySelectorAll('[data-plain-node]').forEach(button => button.addEventListener('click', () => selectPlainNode(button.dataset.plainNode)));
  }

  function selectPlainNode(id) {
    selected = id;
    const node = nodes.get(id);
    if (!node || !detail) return;
    const meta = node.meta || {};
    const ins = incoming.get(id) || [], outs = outgoing.get(id) || [];
    const rows = Object.entries(meta).filter(([,v]) => v !== null && v !== '' && !(Array.isArray(v) && !v.length)).map(([k,v]) => `<dt>${esc(k)}</dt><dd><code>${esc(typeof v === 'string' ? v : JSON.stringify(v,null,2))}</code></dd>`).join('');
    detail.innerHTML = `<strong>${esc(humanNode(node))}</strong> <span class="chip">${esc(node.kind)}</span><p class="muted">${esc(node.label || node.id)}</p><dl>${rows || '<dt>Technical metadata</dt><dd class="muted">No additional metadata</dd>'}</dl><p><strong>Feeds from:</strong> ${esc(ins.map(e => nodes.get(e.source)?.label || e.kind).join(', ') || 'none')}<br><strong>Leads to:</strong> ${esc(outs.map(e => nodes.get(e.target)?.label || e.kind).join(', ') || 'none')}</p>`;
    renderPlain();
  }

  if (controls && !document.getElementById('behavior-fit-view')) {
    const spacer = document.createElement('span'); spacer.className = 'behavior-view-hint'; spacer.textContent = 'Wheel to zoom · drag empty graph space to pan'; controls.appendChild(spacer);
    for (const [id,label,title] of [['behavior-zoom-in','+','Zoom in'],['behavior-zoom-out','−','Zoom out'],['behavior-fit-view','Fit','Fit visible graph'],['behavior-reset-view','Reset view','Reset pan and zoom']]) {
      const button = document.createElement('button'); button.type = 'button'; button.id = id; button.textContent = label; button.title = title; controls.appendChild(button);
    }
  }

  function causalPath(id) {
    const nodeIds = new Set(), edgeIds = new Set(); if (!id) return {nodeIds, edgeIds}; nodeIds.add(id);
    const walk = (seed, adjacency, nextId) => { const seen = new Set([seed]), queue = [seed]; while (queue.length) { const current = queue.shift(); for (const edge of (adjacency.get(current) || [])) { edgeIds.add(edgeKey(edge)); const next = nextId(edge); nodeIds.add(next); if (!seen.has(next)) { seen.add(next); queue.push(next); } } } };
    walk(id, incoming, edge => edge.source); walk(id, outgoing, edge => edge.target); return {nodeIds, edgeIds};
  }
  function matches(node, query) { if (!query) return true; return [node.id,node.kind,node.label,JSON.stringify(node.meta||{})].join(' ').toLowerCase().includes(query); }
  function visibleEdges() { const q=(filter?.value||'').trim().toLowerCase(), ids=new Set((data.nodes||[]).filter(n=>matches(n,q)).map(n=>n.id)); return (data.edges||[]).filter(e=>ids.has(e.source)&&ids.has(e.target)); }
  function setViewBox(){ svg.setAttribute('viewBox',`${view.x} ${view.y} ${view.w} ${view.h}`); }
  function applyFocus(){ if(applying)return; applying=true; try{ setViewBox(); const path=causalPath(selected), edges=visibleEdges(); [...svg.querySelectorAll('.behavior-edge')].forEach((el,i)=>{const edge=edges[i],active=!selected||(edge&&path.edgeIds.has(edgeKey(edge)));el.classList.toggle('path-active',!!(selected&&active));el.classList.toggle('path-dim',!!(selected&&!active));el.classList.toggle('dim',!!(selected&&!active));}); svg.querySelectorAll('.behavior-node').forEach(el=>{const active=!selected||path.nodeIds.has(el.dataset.id);el.classList.toggle('path-active',!!(selected&&active));el.classList.toggle('path-dim',!!(selected&&!active));el.classList.toggle('dim',!!(selected&&!active));}); if(selected&&status){const base=(status.textContent||'').replace(/ · Selected causal chain:.*$/,'');status.textContent=`${base} · Selected causal chain: ${path.nodeIds.size} nodes / ${path.edgeIds.size} edges.`;} } finally{applying=false;} }
  function scaleAt(factor,cx=null,cy=null){const r=svg.getBoundingClientRect(),px=cx==null?.5:Math.max(0,Math.min(1,(cx-r.left)/Math.max(1,r.width))),py=cy==null?.5:Math.max(0,Math.min(1,(cy-r.top)/Math.max(1,r.height)));let w=view.w*factor,h=view.h*factor;if(w<320){const a=320/w;w*=a;h*=a}if(w>7000){const a=7000/w;w*=a;h*=a}view.x+=(view.w-w)*px;view.y+=(view.h-h)*py;view.w=w;view.h=h;setViewBox();}
  function fitVisible(){const groups=[...svg.querySelectorAll('.behavior-node')];if(!groups.length){view={...BASE_VIEW};setViewBox();return}let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;for(const group of groups){let box;try{box=group.getBBox()}catch{continue}const t=group.transform?.baseVal?.consolidate?.(),tx=t?.matrix?.e||0,ty=t?.matrix?.f||0;minX=Math.min(minX,tx+box.x);minY=Math.min(minY,ty+box.y);maxX=Math.max(maxX,tx+box.x+box.width);maxY=Math.max(maxY,ty+box.y+box.height)}if(!Number.isFinite(minX)){view={...BASE_VIEW};setViewBox();return}view={x:minX-110,y:minY-80,w:Math.max(480,maxX-minX+220),h:Math.max(360,maxY-minY+160)};setViewBox();}

  svg.addEventListener('wheel',e=>{if(mode!=='technical')return;e.preventDefault();scaleAt(e.deltaY>0?1.14:.875,e.clientX,e.clientY)},{passive:false});
  svg.addEventListener('pointerdown',e=>{if(mode!=='technical'||e.button!==0||e.target.closest?.('.behavior-node'))return;dragging={clientX:e.clientX,clientY:e.clientY,x:view.x,y:view.y};svg.classList.add('behavior-panning');try{svg.setPointerCapture(e.pointerId)}catch{}});
  svg.addEventListener('pointermove',e=>{if(!dragging)return;view.x=dragging.x-(e.clientX-dragging.clientX)*view.w/Math.max(1,svg.clientWidth);view.y=dragging.y-(e.clientY-dragging.clientY)*view.h/Math.max(1,svg.clientHeight);setViewBox()});
  const endPan=e=>{dragging=null;svg.classList.remove('behavior-panning');try{svg.releasePointerCapture(e.pointerId)}catch{}};svg.addEventListener('pointerup',endPan);svg.addEventListener('pointercancel',endPan);
  svg.addEventListener('click',e=>{const node=e.target.closest?.('.behavior-node');if(node)selected=node.dataset.id||null},true);
  filter?.addEventListener('input',()=>{queueMicrotask(applyFocus);if(mode==='plain')renderPlain()});
  resetSelection?.addEventListener('click',()=>{selected=null;queueMicrotask(applyFocus);if(mode==='plain')renderPlain()});
  document.getElementById('behavior-zoom-in')?.addEventListener('click',()=>scaleAt(.8));document.getElementById('behavior-zoom-out')?.addEventListener('click',()=>scaleAt(1.25));document.getElementById('behavior-fit-view')?.addEventListener('click',fitVisible);document.getElementById('behavior-reset-view')?.addEventListener('click',()=>{view={...BASE_VIEW};setViewBox()});
  const observer=new MutationObserver(()=>queueMicrotask(applyFocus));observer.observe(svg,{childList:true});
  setMode('plain'); renderPlain(); setViewBox(); applyFocus();
})();
