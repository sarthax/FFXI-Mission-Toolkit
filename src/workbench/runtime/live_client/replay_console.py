"""Standalone read-only replay browser console; mount explicitly with the registry router."""
from __future__ import annotations

import re

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse


def create_replay_console_router(render=None) -> APIRouter:
    router = APIRouter(prefix="/live-client/replay", tags=["Live Client Replay"])

    @router.get("/console", response_class=HTMLResponse)
    def console(request: Request):
        html = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Live Client — Replay Console</title>
<style>
body{font:15px system-ui,sans-serif;max-width:none;margin:2rem auto;padding:0 1rem;color:#ddd;background:#161b22}
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
<button id="refresh" type="button">Refresh</button><button id="poll" type="button" disabled>Poll file feed</button><button id="previous" type="button" disabled>Previous</button><button id="restart" type="button" disabled>Restart</button><button id="step" type="button" disabled>Next recorded frame</button><button id="play" type="button" disabled>Play</button>
<label for="speed">Speed</label><select id="speed"><option value="0.25">0.25×</option><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option><option value="4">4×</option></select>
<label for="timeline">Frame</label><input id="timeline" type="range" min="1" max="1" value="1" disabled>
<button id="unload" type="button" disabled>Unload selected</button><button id="replace" type="button" disabled>Replace selected with chosen file</button>
<label for="compare">Compare</label><select id="compare"><option value="">No comparison</option></select><p id="comparison" role="status"></p><p id="state" role="status">Not connected</p></section>
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
let rows=[],playing=false,timer=null,generation=0;
const controls=['step','poll','previous','restart','play','timeline','unload','replace'];
function reset(){for(const id of ['character','zone','xyz','heading','observed','entities'])show(id,'—');document.getElementById('trace').replaceChildren();show('trace-status','Select a recorded session.');}
function pause(){playing=false;clearTimeout(timer);timer=null;generation++;show('play','Play');}
async function request(url,options={}){
 const response=await fetch(url,{cache:'no-store',...options});
 const data=await response.json();
 if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Request failed ('+response.status+')');
 return data;
}
function selectedRow(){return rows.find(row=>row.client_id===client.value);}
async function projection(row){
 return request('/live-client/replay/projection?'+new URLSearchParams({client_id:row.client_id,zone_id:String(row.zone_id)}));
}
async function drawTrace(clientId,zoneId,instanceHint){
 const svg=document.getElementById('trace');svg.replaceChildren();
 const result=await fetch('/live-client/replay/trace?'+new URLSearchParams({client_id:clientId,max_points:'500'}),{cache:'no-store'});
 if(!result.ok){show('trace-status','Trace only available for recorded sessions.');return;}
 const all=(await result.json()).points||[];
 const points=all.filter(p=>p.zone_id===zoneId&&(p.instance_hint??null)===(instanceHint??null));
 if(!points.length){show('trace-status','No trace points in this zone.');return;}
 const minX=Math.min(...points.map(p=>p.x)),maxX=Math.max(...points.map(p=>p.x));
 const minZ=Math.min(...points.map(p=>p.z)),maxZ=Math.max(...points.map(p=>p.z));
 const scale=Math.min(540/Math.max(maxX-minX,1),220/Math.max(maxZ-minZ,1));
 const coords=points.map(p=>({x:300+(p.x-(minX+maxX)/2)*scale,y:140-(p.z-(minZ+maxZ)/2)*scale,segment:p.segment}));
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
 rows=(await request('/live-client/replay/clients')).clients||[];
 const prior=client.value,compare=document.getElementById('compare'),priorCompare=compare.value;
 client.replaceChildren(new Option('Choose recording',''));compare.replaceChildren(new Option('No comparison',''));
 for(const row of rows){
  const label=(row.label||row.client_id)+(row.recorded_client_id?' · '+row.recorded_client_id+' · '+row.client_id.slice(-8):'');
  client.add(new Option(label,row.client_id));compare.add(new Option(label,row.client_id));
 }
 client.value=rows.some(r=>r.client_id===prior)?prior:'';
 compare.value=rows.some(r=>r.client_id===priorCompare)?priorCompare:'';
 const row=selectedRow();
 for(const id of controls)document.getElementById(id).disabled=true;
 if(!row){pause();reset();state.textContent=rows.length?'Select a recording':'Open a recording to begin';show('comparison','');return;}
 const recording=Number.isInteger(row.total_frames);
 document.getElementById('poll').disabled=row.source!=='file_feed';
 for(const id of ['timeline','unload','replace'])document.getElementById(id).disabled=!recording;
 for(const id of ['step','play'])document.getElementById(id).disabled=!row.remaining_frames;
 for(const id of ['previous','restart'])document.getElementById(id).disabled=!(row.frame_position>1);
 const timeline=document.getElementById('timeline');timeline.max=row.total_frames||1;timeline.value=row.frame_position||1;
 state.textContent=row.observed?(recording?'Frame '+row.frame_position+' of '+row.total_frames:'Observation available'):'Waiting for telemetry';
 if(!row.observed||!Number.isInteger(row.zone_id)){reset();return;}
 const data=await projection(row);
 if(!data.visible||!data.player){reset();throw Error('Observation outside selected zone');}
 const p=data.player.position;
 show('character',data.player.character);show('zone',String(data.zone_id));show('xyz',[p.x,p.y,p.z].join(', '));
 show('heading',String(p.heading));show('observed',String(data.observed_at));show('entities',String(data.entities.length));
 await drawTrace(client.value,data.zone_id,data.instance_hint);
 const other=rows.find(r=>r.client_id===compare.value);
 if(other&&other.observed){
  const second=await projection(other),q=second.player?.position;
  show('comparison',q?'Comparison: '+second.player.character+' · zone '+second.zone_id+' · XYZ '+[q.x,q.y,q.z].join(', ')+' · observed '+second.observed_at:'Comparison observation unavailable');
 }else show('comparison','');
}
async function safeRefresh(){try{await refresh();}catch(error){pause();reset();for(const id of controls)document.getElementById(id).disabled=true;state.textContent=error.message;}}
async function mutate(action,params={}){
 const selected=client.value;if(!selected)return false;
 await request('/live-client/replay/'+action+'?'+new URLSearchParams({client_id:selected,...params}),{method:'POST'});
 await refresh();return true;
}
async function manual(action,params={}){pause();try{await mutate(action,params);}catch(error){state.textContent=error.message;}}
function schedule(){
 const row=selectedRow();if(!playing||!row?.remaining_frames){pause();return;}
 const token=generation,selected=client.value,speed=Number(document.getElementById('speed').value);
 // Preserve observed timing; browser playback has no effect on file feeds or game clients.
 const delay=Math.min(2147483647,Math.max(10,(row.next_frame_delay??0)*1000/speed));
 timer=setTimeout(async()=>{
  if(!playing||token!==generation||selected!==client.value)return;
  try{await mutate('advance');if(playing&&token===generation)schedule();}
  catch(error){pause();state.textContent=error.message;}
 },delay);
}
document.getElementById('play').addEventListener('click',()=>{if(playing){pause();return;}playing=true;generation++;show('play','Pause');schedule();});
document.getElementById('speed').addEventListener('change',()=>{if(playing){clearTimeout(timer);generation++;schedule();}});
document.getElementById('timeline').addEventListener('change',event=>manual('seek',{position:event.target.value}));
document.getElementById('step').addEventListener('click',()=>manual('advance'));
document.getElementById('previous').addEventListener('click',()=>manual('navigate',{action:'previous'}));
document.getElementById('restart').addEventListener('click',()=>manual('navigate',{action:'restart'}));
document.getElementById('poll').addEventListener('click',()=>manual('poll-feed'));
document.getElementById('unload').addEventListener('click',()=>manual('unload'));
async function openRecording(replace){
 pause();const file=document.getElementById('recording').files[0],status=document.getElementById('import-status');
 if(!file){status.textContent='Choose a .jsonl recording first';return;}
 const button=document.getElementById(replace?'replace':'open-recording');button.disabled=true;
 try{
  const params=new URLSearchParams({open_session:'true'});if(replace)params.set('replace_session',client.value);
  const form=new FormData();form.append('recording',file);
  const data=await request('/live-client/upload-recording?'+params,{method:'POST',body:form});
  status.textContent='Loaded '+data.frames+' frames for '+data.client_id;
  await refresh();client.value=data.session_id;await refresh();
 }catch(error){status.textContent=error.message;}
 finally{button.disabled=false;}
}
document.getElementById('open-recording').addEventListener('click',()=>openRecording(false));
document.getElementById('replace').addEventListener('click',()=>openRecording(true));
client.addEventListener('change',()=>{pause();safeRefresh();});
document.getElementById('compare').addEventListener('change',safeRefresh);
document.getElementById('refresh').addEventListener('click',()=>{pause();safeRefresh();});
document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});
window.addEventListener('pagehide',pause);
safeRefresh();
</script></body></html>"""

        if render is not None:
            style = html.split("<style>", 1)[1].split("</style>", 1)[0]
            # Scope the standalone console styles to its shared-shell container.
            for selector in ("body", "header", "section", "select", "button", "input", "dl", "dt", "dd", "pre"):
                style = re.sub(r"(?<![\w-])" + selector + r"(?=[,{])",
                               ".live-client-console" if selector == "body" else ".live-client-console " + selector,
                               style)
            body = html.split("<body>", 1)[1].rsplit("</body>", 1)[0]
            return render(request, style, body)
        return html

    return router
