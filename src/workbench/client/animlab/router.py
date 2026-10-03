"""FastAPI router exposing the Anim Lab panel inside the main GUI at /animlab."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse

from workbench.client.animlab import observations
from workbench.client.animlab.bridge import Bridge
from workbench.client.animlab.panel import PAGE, export_sql

router = APIRouter(prefix="/animlab")
_PAGE = PAGE.replace("'/api/", "'/animlab/api/").replace('href="/export.sql"', 'href="/animlab/export.sql"')


@router.get("/", response_class=HTMLResponse)
def page():
    return _PAGE


@router.get("/api/state")
def state():
    res = [{"stamp": r.stamp, "kind": r.kind, "args": r.args} for r in Bridge().results()[-40:]]
    return {"results": res, "obs": observations.load()}


@router.get("/export.sql", response_class=PlainTextResponse)
def export():
    return export_sql(observations.confirmed())


@router.post("/api/{cmd}")
def command(cmd: str, a: dict):
    b = Bridge()
    try:
        if cmd == "find":
            b.find(a["name"])
        elif cmd == "play":
            b.play(a["anim"], a["skill"])
        elif cmd == "sweep":
            b.sweep(a["lo"], a["hi"], a["gap"], a["skill"])
        elif cmd == "stop":
            b.stop()
        elif cmd == "note":
            observations.record(a["mob"], a["anim"], a["skill"], a["verdict"], a.get("note", ""))
        else:
            raise HTTPException(404)
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc))
    return {}
