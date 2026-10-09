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
<label>Ashita client ID <input id="client" value="ashita-a" pattern="[a-zA-Z0-9_-]+"></label>
<button onclick="action('start')">Start receiver</button>
<button onclick="provision()">Configure client</button>
<button onclick="action('stop')">Stop receiver</button>
<p>Provisioning creates a new session and invalidates earlier connection credentials.
Keep the displayed configuration private.</p>
<pre id="config" aria-live="polite"></pre>
<h2>Live Status</h2><pre id="status" aria-live="polite">Not connected</pre>
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
 document.getElementById('config').textContent='Private Ashita settings (do not share):\\n'+JSON.stringify(result,null,2);
 }catch(error){statusEl.textContent=String(error)}}
async function poll(){const value=client();if(!/^[a-zA-Z0-9_-]{1,64}$/.test(value))return;
 try{const response=await fetch(root+'status/'+encodeURIComponent(value));
 if(response.ok)statusEl.textContent=JSON.stringify(await response.json(),null,2);
 }catch(error){statusEl.textContent=String(error)}}
setInterval(poll,1500);poll();
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

    @router.get("/status/{client_id}")
    def status(client_id: str) -> dict:
        if not 0 < len(client_id) <= 64 or not client_id.replace("_", "").replace("-", "").isalnum():
            raise HTTPException(status_code=422, detail="invalid client ID")
        result = manager.status(client_id)
        snapshot = result.pop("snapshot", None)
        if snapshot is not None:
            pos = snapshot.position
            result["snapshot"] = {
                "client_id": snapshot.client_id, "character": snapshot.character,
                "client_version": snapshot.version, "adapter": snapshot.adapter,
                "observed_at": snapshot.observed_at,
                "zone_id": pos.zone_id, "x": pos.x, "y": pos.y, "z": pos.z,
                "heading": pos.heading,
            }
        return result

    @router.post("/stop")
    def stop(request: Request) -> dict:
        require_same_origin(request)
        manager.stop()
        return {"running": False}

    return router
