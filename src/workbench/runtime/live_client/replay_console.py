"""Standalone read-only replay browser console; mount explicitly with the registry router."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


def create_replay_console_router() -> APIRouter:
    router = APIRouter(prefix="/live-client/replay", tags=["Live Client Replay"])

    @router.get("/console", response_class=HTMLResponse)
    def console() -> str:
        return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Live Client — Replay Console</title>
<style>
body{font:15px system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#ddd;background:#161b22}
header{display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap}
section{background:#212833;border:1px solid #414a58;border-radius:9px;padding:1rem;margin:1rem 0}
select,button,input{background:#111923;color:#fff;padding:.5rem;border:1px solid #6b7788;border-radius:5px}
dl{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.7rem}
dt{color:#a9b8ca}dd{margin:0;overflow-wrap:anywhere}
#state{font-weight:bold}pre{white-space:pre-wrap;max-height:16rem;overflow:auto}
</style></head><body>
<header><h1>Live Client — Replay Console</h1><strong>Read-only • Offline</strong></header>
<p>Open a recording directly. No restart or Settings changes required. Game-memory controls are not available.</p>
<section><label for="recording">Open recording (.jsonl) </label><input type="file" id="recording" accept=".jsonl"><button id="open-recording" type="button">Open recording</button><p id="import-status" role="status"></p></section>
<section><label for="client">Recorded client </label><select id="client"><option value="">Choose client</option></select>
<button id="refresh" type="button">Refresh</button><button id="poll" type="button" disabled>Poll file feed</button><button id="previous" type="button" disabled>Previous</button><button id="restart" type="button" disabled>Restart</button><button id="step" type="button" disabled>Next recorded frame</button><p id="state" role="status">Not connected</p></section>
<section><h2>Player observation</h2><dl>
<div><dt>Character</dt><dd id="character">—</dd></div><div><dt>Zone</dt><dd id="zone">—</dd></div>
<div><dt>XYZ</dt><dd id="xyz">—</dd></div><div><dt>Heading</dt><dd id="heading">—</dd></div>
<div><dt>Observed at</dt><dd id="observed">—</dd></div><div><dt>Entities</dt><dd id="entities">—</dd></div>
</dl></section>
<section><h2>Recorded position trace (X/Z)</h2><p id="trace-status">Select a recording to view its observed movement.</p>
<svg id="trace" viewBox="0 0 600 280" style="width:100%;background:#101720;border:1px solid #414a58" role="img" aria-label="Recorded positions in current zone"></svg>
<p style="color:#a9b8ca">Relative X/Z positions only; this is not a calibrated zone map.</p></section>
<script>
const client=document.getElementById('client'),state=document.getElementById('state');
const show=(id,value)=>document.getElementById(id).textContent=value;
function reset(){for(const id of ['character','zone','xyz','heading','observed','entities'])show(id,'—');document.getElementById('trace').replaceChildren();show('trace-status','Select a recorded session.');}
async function drawTrace(clientId,zoneId,instanceHint){
 const svg=document.getElementById('trace');svg.replaceChildren();
 const result=await fetch('/live-client/replay/trace?'+new URLSearchParams({client_id:clientId,max_points:'500'}),{cache:'no-store'});
 if(!result.ok){show('trace-status','Trace only available for recorded sessions.');return;}
 const all=(await result.json()).points||[];
 const points=all.filter(p=>p.zone_id===zoneId&&(p.instance_hint??null)===(instanceHint??null));
 if(!points.length){show('trace-status','No trace points in this zone.');return;}
 const minX=Math.min(...points.map(p=>p.x)),maxX=Math.max(...points.map(p=>p.x));
 const minZ=Math.min(...points.map(p=>p.z)),maxZ=Math.max(...points.map(p=>p.z));
 const coords=points.map(p=>({x:30+(p.x-minX)/Math.max(maxX-minX,1)*540,y:250-(p.z-minZ)/Math.max(maxZ-minZ,1)*220,segment:p.segment}));
 const ns='http://www.w3.org/2000/svg';
 const segments=new Map();
 for(const point of coords){if(!segments.has(point.segment))segments.set(point.segment,[]);segments.get(point.segment).push(point);}
 for(const group of segments.values()){
  const line=document.createElementNS(ns,'polyline');line.setAttribute('points',group.map(p=>p.x+','+p.y).join(' '));
  line.setAttribute('fill','none');line.setAttribute('stroke','#58a6ff');line.setAttribute('stroke-width','2');svg.append(line);
 }
 const current=coords[coords.length-1];const dot=document.createElementNS(ns,'circle');dot.setAttribute('cx',current.x);dot.setAttribute('cy',current.y);dot.setAttribute('r','6');dot.setAttribute('fill','#fb923c');svg.append(dot);
 show('trace-status',points.length+' observed positions in zone '+zoneId+' (relative X/Z)');
}
async function refresh(){
 try{
  const response=await fetch('/live-client/replay/clients',{cache:'no-store'});
  if(!response.ok)throw Error('Client list unavailable ('+response.status+')');
  const rows=(await response.json()).clients||[];
  const prior=client.value;client.replaceChildren(new Option('Choose client',''));
  for(const row of rows)client.add(new Option(row.client_id,row.client_id));
  client.value=rows.some(r=>r.client_id===prior)?prior:'';
  if(!client.value){document.getElementById('step').disabled=true;document.getElementById('poll').disabled=true;document.getElementById('previous').disabled=true;document.getElementById('restart').disabled=true;reset();state.textContent=rows.length?'Select a recorded client':'No replay sessions registered';return;}
  const row=rows.find(r=>r.client_id===client.value);
  document.getElementById('step').disabled=!row.remaining_frames;
  document.getElementById('poll').disabled=row.source!=='file_feed';
  document.getElementById('previous').disabled=!(row.frame_position>1);
  document.getElementById('restart').disabled=!(row.frame_position>1);
  state.textContent=row.observed?(row.total_frames?'Frame '+row.frame_position+' of '+row.total_frames:'Observation available'):'Waiting for recorded frame';
  if(!row.observed){reset();return;}
  // Zone is read from selected client's already-observed frame via registry status.
  if(!Number.isInteger(row.zone_id)){reset();state.textContent='No zone in status; projection unavailable';return;}
  const url='/live-client/replay/projection?'+new URLSearchParams({client_id:client.value,zone_id:String(row.zone_id)});
  const result=await fetch(url,{cache:'no-store'});
  if(!result.ok)throw Error('Projection unavailable ('+result.status+')');
  const data=await result.json();if(!data.visible||!data.player){reset();state.textContent='Observation outside selected zone';return;}
  const p=data.player.position;
  show('character',data.player.character);show('zone',String(data.zone_id));
  show('xyz',[p.x,p.y,p.z].join(', '));show('heading',String(p.heading));
  show('observed',String(data.observed_at));show('entities',String(data.entities.length));
  await drawTrace(client.value,data.zone_id,data.instance_hint);
 }catch(err){reset();state.textContent=String(err.message||err);}
}
async function step(){
 const selected=client.value;if(!selected)return;
 const button=document.getElementById('step');button.disabled=true;
 try{const url='/live-client/replay/advance?'+new URLSearchParams({client_id:selected});
 const result=await fetch(url,{method:'POST',headers:{'Accept':'application/json'}});
 if(!result.ok){const detail=await result.json();throw Error(detail.detail||'Replay advance failed');}
 await refresh();
 }catch(err){state.textContent=String(err.message||err);await refresh();}
}
document.getElementById('open-recording').addEventListener('click',async()=>{
 const file=document.getElementById('recording').files[0];
 const status=document.getElementById('import-status');
 if(!file){status.textContent='Choose a .jsonl recording first';return;}
 const button=document.getElementById('open-recording');button.disabled=true;
 try{
  const form=new FormData();form.append('recording',file);
  const response=await fetch('/live-client/upload-recording?open_session=true',{method:'POST',body:form});
  const data=await response.json();
  if(!response.ok)throw Error(data.detail||'Unable to open recording');
  status.textContent='Loaded '+data.frames+' frames for '+data.client_id;
  await refresh();client.value=data.client_id;await refresh();
 }catch(error){status.textContent=String(error.message||error);}
 finally{button.disabled=false;}
});
document.getElementById('step').addEventListener('click',step);
async function navigate(action){
 if(!client.value)return;
 try{
  const url='/live-client/replay/navigate?'+new URLSearchParams({client_id:client.value,action});
  const response=await fetch(url,{method:'POST'});
  if(!response.ok){const result=await response.json();throw Error(result.detail||'Navigation failed');}
  await refresh();
 }catch(error){state.textContent=String(error.message||error);}
}
document.getElementById('previous').addEventListener('click',()=>navigate('previous'));
document.getElementById('restart').addEventListener('click',()=>navigate('restart'));
document.getElementById('poll').addEventListener('click',async()=>{
  if(!client.value)return;
  const button=document.getElementById('poll');button.disabled=true;
  try{
    const response=await fetch('/live-client/replay/poll-feed?'+new URLSearchParams({client_id:client.value}),{method:'POST'});
    const result=await response.json();
    if(!response.ok)throw Error(result.detail||'File feed polling failed');
    await refresh();
  }catch(error){state.textContent=String(error.message||error);button.disabled=false;}
});
client.addEventListener('change',refresh);document.getElementById('refresh').addEventListener('click',refresh);
refresh();
</script></body></html>"""

    return router
