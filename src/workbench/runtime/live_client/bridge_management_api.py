"""Opt-in same-origin read-only Live Client bridge setup and status routes.

Routes are not auto-registered: the Toolkit application must deliberately mount
them. Provisioning reveals a local secret only in the direct POST response.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .bridge_managed import ManagedLiveReceiver


class ClientSelection(BaseModel):
    client_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


def create_bridge_management_router(manager: ManagedLiveReceiver) -> APIRouter:
    router = APIRouter(prefix="/live-client/bridge", tags=["Live Client Bridge"])

    def require_same_origin(request: Request) -> None:
        if request.client is None or request.client.host not in ("127.0.0.1", "::1", "testclient"):
            raise HTTPException(status_code=403, detail="bridge control requires local browser")
        origin = request.headers.get("origin")
        if not origin or origin != str(request.base_url).rstrip("/"):
            raise HTTPException(status_code=403, detail="same-origin request required")

    @router.get("/console", response_class=HTMLResponse)
    def console(request: Request) -> HTMLResponse:
        if request.client is None or request.client.host not in ("127.0.0.1", "::1", "testclient"):
            raise HTTPException(status_code=403, detail="bridge setup requires local browser")
        return HTMLResponse("""<!doctype html><html lang="en"><meta charset="utf-8">
<title>Live Client Bridge</title>
<style>body{font:16px system-ui;max-width:800px;margin:2rem auto;padding:1rem}
button,input{font:inherit;padding:.5rem;margin:.25rem}pre{white-space:pre-wrap;overflow-wrap:anywhere}
#status{border:1px solid #999;padding:1rem;border-radius:.5rem}
label{display:block}</style>
<h1>Live Client — Direct Telemetry</h1>
<p>Local read-only connection. No recording files or game writes.</p>
<label>Ashita client ID <input id="client" value="ashita-a" list="clients" pattern="[a-zA-Z0-9_-]+"></label><datalist id="clients"></datalist>
<button onclick="action('start')">Start receiver</button>
<button onclick="provision()">Configure client</button>
<button onclick="action('stop')">Stop receiver</button>
<p>Provisioning creates a new session and invalidates earlier connection credentials.
Keep the displayed configuration private.</p>
<pre id="config" aria-live="polite"></pre>
<h2>Live dashboard</h2>
<div id="health" role="status">Waiting for telemetry</div>
<div id="metrics" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem;margin:1rem 0"></div>
<h3>Nearby observed entities</h3><div id="entities">No observations yet</div>
<details><summary>Technical details</summary><pre id="status" aria-live="polite">Not connected</pre></details>
<script>
const root='/live-client/bridge/';
const client=()=>document.getElementById('client').value;
const statusEl=document.getElementById('status');
async function request(path,data){const opts={method:'POST',headers:{'Content-Type':'application/json'}};
 if(data)opts.body=JSON.stringify(data);
 const response=await fetch(root+path,opts);const result=await response.json();
 if(!response.ok)throw Error(result.detail||response.status);
 return result;}
async function action(name){try{const result=await request(name);statusEl.textContent=JSON.stringify(result,null,2);
 if(name==='stop')document.getElementById('config').textContent='';}
 catch(error){statusEl.textContent=String(error)}}
async function provision(){try{const value=client();
 if(!/^[a-zA-Z0-9_-]{1,64}$/.test(value))throw Error('Invalid client ID');
 const result=await request('provision',{client_id:value});
 const lua='-- Private workbench_bridge_settings.lua; do not commit this file.\\n'
 +'local socket = require("socket")\\nreturn {\\n'
 +'  enabled = true, host = "127.0.0.1",\\n'
 +'  port = '+result.port+',\\n'
 +'  session_id = '+JSON.stringify(result.session_id)+',\\n'
 +'  generation = '+JSON.stringify(result.generation)+',\\n'
 +'  token = '+JSON.stringify(result.token)+',\\n'
 +'  connect = function(host, port)\\n'
 +'    local peer = assert(socket.tcp())\\n'
 +'    peer:settimeout(0.1)\\n'
 +'    local ok, err = peer:connect(host, port)\\n'
 +'    if not ok then peer:close(); error(err) end\\n'
 +'    return peer\\n  end,\\n}\\n';
 document.getElementById('config').textContent='Save locally as addons/workbench_live/workbench_bridge_settings.lua (private):\\n\\n'+lua;
 }catch(error){statusEl.textContent=String(error)}}
function metric(label,value){const node=document.createElement('div');node.style.border='1px solid #aaa';
 node.style.padding='0.75rem';node.style.borderRadius='0.5rem';
 const heading=document.createElement('small');heading.textContent=label;
 const content=document.createElement('div');content.style.fontSize='1.25rem';content.textContent=String(value);
 node.append(heading,content);return node;}
function render(data){const health=document.getElementById('health');
 health.textContent=!data.running?'Receiver stopped':data.connected?'Connected — live telemetry':
 data.snapshot?'Stale — last known observation':'Waiting for client';
 const metrics=document.getElementById('metrics');metrics.replaceChildren();
 const snap=data.snapshot;const fields=snap?[
 ['Character',snap.character],['Zone',snap.zone_id],
 ['X',Number(snap.x).toFixed(3)],['Y',Number(snap.y).toFixed(3)],
 ['Z',Number(snap.z).toFixed(3)],['Heading',Number(snap.heading).toFixed(3)],
 ['Last update',data.age_seconds===null?'—':Number(data.age_seconds).toFixed(1)+'s'],
 ['Adapter',snap.adapter]]:[['Connection',data.running?'Waiting':'Stopped']];
 for(const [label,value] of fields)metrics.appendChild(metric(label,value));
 const entities=document.getElementById('entities');entities.replaceChildren();
 const observed=snap&&Array.isArray(snap.entities)?snap.entities:[];
 if(!observed.length){entities.textContent='No entity observations in current frame';return}
 const list=document.createElement('ul');for(const entity of observed){
 const item=document.createElement('li');
 item.textContent=(entity.name||'Unnamed')+' · index '+entity.client_index+' · '+entity.x.toFixed(2)+', '+entity.y.toFixed(2)+', '+entity.z.toFixed(2);
 list.appendChild(item);}entities.appendChild(list);}
async function poll(){const value=client();if(!/^[a-zA-Z0-9_-]{1,64}$/.test(value))return;
 try{const response=await fetch(root+'status/'+encodeURIComponent(value));
 if(response.ok){const data=await response.json();statusEl.textContent=JSON.stringify(data,null,2);render(data)}
 }catch(error){statusEl.textContent=String(error)}}
async function refreshClients(){try{const response=await fetch(root+'clients');
 if(!response.ok)return;const result=await response.json();
 const list=document.getElementById('clients');list.replaceChildren();
 for(const id of result.clients||[]){const option=document.createElement('option');option.value=id;list.appendChild(option);}
 }catch(error){}}
setInterval(poll,1500);setInterval(refreshClients,5000);refreshClients();poll();
</script></html>""")

    @router.post("/start")
    def start(request: Request) -> dict:
        require_same_origin(request)
        try:
            host, port = manager.start()
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"running": True, "host": host, "port": port}

    @router.post("/provision")
    def provision(request: Request, selection: ClientSelection) -> dict:
        require_same_origin(request)
        try:
            return manager.provision(selection.client_id)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/clients")
    def clients() -> dict:
        return {"clients": manager.clients()}

    @router.get("/status/{client_id}")
    def status(client_id: str) -> dict:
        if not 0 < len(client_id) <= 64 or not client_id.replace("_", "").replace("-", "").isalnum():
            raise HTTPException(status_code=422, detail="invalid client ID")
        result = manager.status(client_id)
        snapshot = result.pop("snapshot", None)
        frame = manager.feeds.feed(client_id)
        frame = frame._latest if frame else None
        if snapshot is None:
            result["snapshot"] = None
        else:
            pos = snapshot.position
            result["snapshot"] = {
                "client_id": snapshot.client_id, "character": snapshot.character,
                "client_version": snapshot.version, "adapter": snapshot.adapter,
                "observed_at": snapshot.observed_at,
                "zone_id": pos.zone_id, "x": pos.x, "y": pos.y, "z": pos.z,
                "heading": pos.heading,
                "entities": [
                    {"client_index": entity.client_index, "name": entity.name,
                     "kind": entity.kind,
                     "zone_id": entity.position.zone_id,
                     "x": entity.position.x, "y": entity.position.y,
                     "z": entity.position.z}
                    for entity in (frame.entities if frame else ())
                ],
            }
        return result

    @router.post("/stop")
    def stop(request: Request) -> dict:
        require_same_origin(request)
        manager.stop()
        return {"running": False}

    return router
