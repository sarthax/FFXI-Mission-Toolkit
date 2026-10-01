(() => {
  const root = document.getElementById('salvage-reconstruction-workspace');
  if (!root) return;

  const $ = (sel) => root.querySelector(sel);
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num = (v) => v === '' || v == null ? null : Number(v);

  function parseCsv(text) {
    const rows = [];
    let row = [], field = '', quoted = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i], n = text[i + 1];
      if (quoted) {
        if (c === '"' && n === '"') { field += '"'; i++; }
        else if (c === '"') quoted = false;
        else field += c;
      } else if (c === '"') quoted = true;
      else if (c === ',') { row.push(field); field = ''; }
      else if (c === '\n') { row.push(field.replace(/\r$/, '')); rows.push(row); row = []; field = ''; }
      else field += c;
    }
    if (field.length || row.length) { row.push(field.replace(/\r$/, '')); rows.push(row); }
    if (!rows.length) return [];
    const headers = rows.shift();
    return rows.filter(r => r.some(v => v !== '')).map(r => Object.fromEntries(headers.map((h, i) => [h, r[i] ?? ''])));
  }

  async function csvTable(table, captureId) {
    const r = await fetch(`/captures/query.csv?table=${encodeURIComponent(table)}&capture_id=${encodeURIComponent(captureId)}`);
    if (!r.ok) return [];
    return parseCsv(await r.text());
  }

  function zoneRows(rows, zone) {
    if (!zone) return rows;
    return rows.filter(r => !('zone_db' in r) || r.zone_db === zone);
  }

  function readiness(label, state) {
    return `<div class="sr-ready sr-${state.toLowerCase().replaceAll('_','-')}"><b>${esc(label)}</b><span>${esc(state)}</span></div>`;
  }

  function aggregateHistory(rows) {
    const m = new Map();
    for (const r of rows) {
      const id = String(r.entity_id ?? '');
      if (!id) continue;
      m.set(id, (m.get(id) || 0) + 1);
    }
    return m;
  }

  function aggregatePaths(rows) {
    const m = new Map();
    for (const r of rows) {
      const id = String(r.entity_id ?? '');
      if (!id) continue;
      if (!m.has(id)) m.set(id, []);
      m.get(id).push(r);
    }
    return m;
  }

  function renderMap(spatial, pcPath) {
    const host = $('#sr-map');
    const entities = spatial.entities || spatial.spatial_entities || [];
    const pts = [];
    entities.forEach(e => { if (Number.isFinite(num(e.x)) && Number.isFinite(num(e.z))) pts.push([+e.x,+e.z]); });
    pcPath.forEach(p => { if (Number.isFinite(num(p.x)) && Number.isFinite(num(p.z))) pts.push([+p.x,+p.z]); });
    if (!pts.length) { host.innerHTML = '<div class="muted sr-empty">No positioned entity/player-path evidence for this zone.</div>'; return; }
    let minX=Math.min(...pts.map(p=>p[0])), maxX=Math.max(...pts.map(p=>p[0])), minZ=Math.min(...pts.map(p=>p[1])), maxZ=Math.max(...pts.map(p=>p[1]));
    if (minX===maxX) { minX-=1; maxX+=1; } if (minZ===maxZ) { minZ-=1; maxZ+=1; }
    const W=900,H=560,pad=28;
    const sx=x=>pad+(x-minX)/(maxX-minX)*(W-pad*2), sy=z=>H-pad-(z-minZ)/(maxZ-minZ)*(H-pad*2);
    const line = pcPath.filter(p=>Number.isFinite(num(p.x))&&Number.isFinite(num(p.z))).map(p=>`${sx(+p.x).toFixed(1)},${sy(+p.z).toFixed(1)}`).join(' ');
    const marks = entities.map(e => {
      if (!Number.isFinite(num(e.x)) || !Number.isFinite(num(e.z))) return '';
      const door = num(e.door_id) && num(e.door_id) !== 0;
      const interactive = door || (num(e.act_index) && num(e.act_index)!==0) || (num(e.sub_kind)&&num(e.sub_kind)!==0);
      const x=sx(+e.x), y=sy(+e.z), id=esc(e.id), name=esc(e.n || '?');
      const shape = door
        ? `<rect x="${x-5}" y="${y-5}" width="10" height="10" class="sr-door-mark"/>`
        : interactive
          ? `<polygon points="${x},${y-6} ${x+6},${y} ${x},${y+6} ${x-6},${y}" class="sr-interactive-mark"/>`
          : `<circle cx="${x}" cy="${y}" r="4" class="sr-entity-mark"/>`;
      return `<g><a href="/captures/search?module=entities&q=${encodeURIComponent(e.id)}">${shape}<title>${name} (${id})</title></a></g>`;
    }).join('');
    host.innerHTML = `<svg class="sr-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="Capture reconstruction map">
      <rect x="0" y="0" width="${W}" height="${H}" class="sr-map-bg"/>
      ${line ? `<polyline points="${line}" class="sr-player-path"/>` : ''}
      ${marks}
    </svg><div class="sr-legend"><span>● entity</span><span>◆ interactive</span><span>■ door</span><span>— player path</span></div>`;
  }

  function renderEntities(entities, pathMap) {
    $('#sr-entities').innerHTML = entities.length ? `<div class="table-wrap"><table><tr><th>ID</th><th>Name</th><th>Model</th><th>XYZ</th><th>Dir</th><th>Runtime</th><th>Path</th></tr>${entities.map(e => {
      const id=String(e.entity_id ?? e.id ?? ''), pathCount=(pathMap.get(id)||[]).length;
      return `<tr><td><a href="/captures/search?module=entities&q=${encodeURIComponent(id)}"><code>${esc(id)}</code></a></td><td>${esc(e.name ?? e.n ?? '?')}</td><td>${esc(e.model_id ?? e.model ?? '')}</td><td>${esc(e.x)}, ${esc(e.y)}, ${esc(e.z)}</td><td>${esc(e.dir ?? '')}</td><td>door ${esc(e.door_id ?? 0)} · act ${esc(e.act_index ?? 0)} · sub ${esc(e.sub_kind ?? 0)}</td><td>${pathCount ? `${pathCount} samples` : 'fixed / no path'}</td></tr>`;
    }).join('')}</table></div>` : '<div class="muted sr-empty">No entity snapshots found.</div>';
  }

  function renderDoors(entities, historyMap) {
    const doors = entities.filter(e => num(e.door_id) && num(e.door_id)!==0);
    $('#sr-doors').innerHTML = doors.length ? doors.map(e => {
      const id=String(e.entity_id ?? e.id ?? ''), h=historyMap.get(id)||0;
      return `<div class="sr-card"><div><b>${esc(e.name ?? e.n ?? 'Door')}</b> <code>${esc(id)}</code></div><div>door_id ${esc(e.door_id)} · pos ${esc(e.x)}, ${esc(e.y)}, ${esc(e.z)} · dir ${esc(e.dir ?? '')}</div><div class="muted">${h ? `${h} state-history observations available for transition review.` : 'No state-history observations; captured state must not be treated as an open/close rule.'}</div><a href="/captures/search?module=entities&q=${encodeURIComponent(id)}">Entity evidence</a></div>`;
    }).join('') : '<div class="muted sr-empty">No door entities identified by captured door_id.</div>';
  }

  function renderEvents(events, pcPath) {
    $('#sr-events').innerHTML = events.length ? `<div class="table-wrap"><table><tr><th>Seq</th><th>Actor</th><th>Opcode</th><th>CSID/event</th><th>Option</th><th>Destination evidence</th></tr>${events.map(e => `<tr><td>${esc(e.seq)}</td><td><code>${esc(e.entity_id)}</code> ${esc(e.entity_name)}</td><td>${esc(e.opcode)} ${esc(e.opcode_name)}</td><td>${esc(e.event_hex)}</td><td>${esc(e.option)}</td><td>${pcPath.length ? 'player path available for correlation' : '<span class="muted">no player path</span>'}</td></tr>`).join('')}</table></div>` : '<div class="muted sr-empty">No EVENT/CSID observations in this zone.</div>';
  }

  function renderGaps({entities, doors, history, events, npcPath, pcPath}) {
    const gaps=[];
    if (!entities.length) gaps.push('No captured entity roster for the selected zone.');
    if (doors.length && !history.length) gaps.push('Door entities exist, but no entity-history evidence proves open/close transitions.');
    if (events.length && !pcPath.length) gaps.push('EVENT/option evidence exists, but no player path is available to correlate telepad destination.');
    if (!npcPath.length) gaps.push('No NPC/mob path samples; roaming paths must remain unresolved.');
    if (events.length) gaps.push('CSID/option observations do not prove activation conditions or Lua ownership by themselves.');
    $('#sr-gaps').innerHTML = gaps.length ? `<ul>${gaps.map(g=>`<li>${esc(g)}</li>`).join('')}</ul>` : '<div class="sr-ok">No basic capture-evidence gaps detected. Dependency/mechanics closure is still a separate review.</div>';
  }

  async function loadWorkspace(ev) {
    if (ev) ev.preventDefault();
    const captureId = $('#sr-capture-id').value.trim();
    let zone = $('#sr-zone').value.trim();
    if (!captureId || !/^\d+$/.test(captureId)) { $('#sr-status').textContent='Enter a numeric capture ID.'; return; }
    $('#sr-status').textContent='Loading reconstruction evidence…';
    try {
      let spatialResp = await fetch(`/captures/${encodeURIComponent(captureId)}/spatial.json${zone ? `?zone_db=${encodeURIComponent(zone)}` : ''}`);
      if (!spatialResp.ok) throw new Error(`capture spatial endpoint returned ${spatialResp.status}`);
      const spatial = await spatialResp.json();
      zone = zone || spatial.zone_db || '';
      $('#sr-zone').value = zone;
      const tables = await Promise.all([
        csvTable('capture_npc_entries', captureId),
        csvTable('capture_npc_history', captureId),
        csvTable('capture_events', captureId),
        csvTable('capture_npc_path', captureId),
        csvTable('capture_pc_path', captureId),
      ]);
      const entities=zoneRows(tables[0],zone), history=zoneRows(tables[1],zone), events=zoneRows(tables[2],zone), npcPath=zoneRows(tables[3],zone), pcPath=zoneRows(tables[4],zone);
      const doors=entities.filter(e=>num(e.door_id)&&num(e.door_id)!==0), historyMap=aggregateHistory(history), pathMap=aggregatePaths(npcPath);
      const ready = {
        'Entity rows': entities.length ? 'READY_FOR_REVIEW' : 'NO_EVIDENCE',
        'Door state': doors.length && history.length ? 'READY_FOR_REVIEW' : doors.length ? 'PARTIAL' : 'NO_EVIDENCE',
        'Instance registration': entities.length ? 'PARTIAL' : 'NO_EVIDENCE',
        'Mob paths': npcPath.length ? 'READY_FOR_REVIEW' : 'NO_EVIDENCE',
        'Telepad / CSID': events.length ? 'PARTIAL' : 'NO_EVIDENCE',
        'Telepad destination': events.length && pcPath.length ? 'PARTIAL' : 'NO_EVIDENCE',
      };
      $('#sr-readiness').innerHTML=Object.entries(ready).map(([k,v])=>readiness(k,v)).join('');
      $('#sr-counts').innerHTML=`<span class="chip">${entities.length} entities</span> <span class="chip">${doors.length} doors</span> <span class="chip">${events.length} events</span> <span class="chip">${npcPath.length} NPC path pts</span> <span class="chip">${pcPath.length} player path pts</span>`;
      $('#sr-handoffs').innerHTML=`<a class="chip" href="/captures/${captureId}">Capture</a> <a class="chip" href="/captures/search?module=entities&q=">Entity search</a> <a class="chip" href="/captures/search?module=events&q=">Events/CSIDs</a> <a class="chip" href="/zoneplot2?capture_id=${captureId}&zone_db=${encodeURIComponent(zone)}">Zone Editor</a> <a class="chip" href="/features/trace">Feature Trace</a> <a class="chip" href="/packages/scope">Package Scope</a>`;
      renderMap(spatial,pcPath); renderEntities(entities,pathMap); renderDoors(entities,historyMap); renderEvents(events,pcPath); renderGaps({entities,doors,history,events,npcPath,pcPath});
      $('#sr-status').textContent=`Loaded capture #${captureId}${zone ? ` · ${zone}` : ''}. Read-only evidence view.`;
    } catch (err) {
      $('#sr-status').textContent=`Unable to load reconstruction evidence: ${err.message}`;
    }
  }

  $('#sr-form').addEventListener('submit', loadWorkspace);
  const params=new URLSearchParams(location.search);
  if (params.get('capture_id')) $('#sr-capture-id').value=params.get('capture_id');
  if (params.get('zone_db')) $('#sr-zone').value=params.get('zone_db');
  if ($('#sr-capture-id').value) loadWorkspace();
})();
