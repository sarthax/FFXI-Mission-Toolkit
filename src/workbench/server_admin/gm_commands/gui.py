"""Copy-only Server GM command browser; no execution or chat transport."""
from __future__ import annotations

from html import escape
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from workbench.runtime.legacy_settings import get_active_server_root
from .catalog import catalog_commands

router = APIRouter(prefix="/server/gm", tags=["Server GM Command Catalog"])


def _catalog():
    root = get_active_server_root()
    if not root or not Path(root).is_dir():
        raise HTTPException(409, "Configure an active local DSP server checkout first")
    try:
        return catalog_commands(root)
    except (OSError, ValueError) as exc:
        raise HTTPException(409, "Active server checkout has no readable GM command catalog") from exc


@router.get("/commands")
def commands():
    """Read-only metadata; raw Lua and arbitrary host paths are not served."""
    return {"commands": _catalog(), "execution_enabled": False}


@router.get("", response_class=HTMLResponse)
def gm_command_page():
    """Standalone browser pending shared-shell integration."""
    return HTMLResponse("""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Server · GM Command Center</title>
<style>
:root{font-family:system-ui,sans-serif;color-scheme:dark}
body{margin:0;background:#111827;color:#e5e7eb}
main{max-width:1100px;margin:auto;padding:26px}
header{display:flex;align-items:center;justify-content:space-between}
a{color:#93c5fd}
.panel{border:1px solid #374151;border-radius:12px;padding:18px;margin-top:18px;background:#1f2937}
input,select,button{background:#111827;color:#e5e7eb;border:1px solid #4b5563;padding:10px;border-radius:8px}
input{width:100%;box-sizing:border-box}
button{cursor:pointer}
small{color:#9ca3af}
table{width:100%;border-collapse:collapse}
td,th{text-align:left;padding:10px;border-bottom:1px solid #374151}
tr[data-name]{cursor:pointer}
tr[data-name]:hover{background:#374151}
code{overflow-wrap:anywhere}
</style></head>
<body><main><header><h1>GM Command Center</h1><a href="/">Mission Toolkit home</a></header>
<p>Catalog and copy-only command previews. No command transmission is enabled.</p>
<section class="panel"><label for="search">Search GM commands</label>
<input id="search" placeholder="Name, description, parameter..." autocomplete="off">
<p id="status" aria-live="polite">Loading active server command catalog…</p>
<div style="overflow:auto"><table><thead><tr><th>Command</th><th>Description</th><th>Permission</th><th>Review</th></tr></thead><tbody id="items"></tbody></table></div></section>
<section class="panel"><h2>Command preview</h2><p id="selected">Select a command above.</p>
<label for="args">Arguments (manual text, single line)</label><input id="args" placeholder="Arguments" maxlength="512">
<p><code id="preview">—</code></p><button id="copy" disabled>Copy command</button>
<p><small>Copy only. Review the source Lua command and required GM permissions before using it. A diagnostic candidate label is not an execution approval.</small></p></section>
</main><script>
"use strict";
let all=[], selected=null;
const $=id=>document.getElementById(id);
const plain=(s)=>String(s??"");
function preview(){
  const args=$("args").value;
  const valid=selected && !/[\\r\\n\\0]/.test(args);
  const result=valid ? "!"+selected.name+(args.trim()?" "+args.trim():"") : "";
  $("preview").textContent=result||"—";
  $("copy").disabled=!result;
}
function render(){
  const q=$("search").value.trim().toLowerCase();
  $("items").replaceChildren();
  const filtered=all.filter(x=>(x.name+" "+x.description+" "+x.parameters).toLowerCase().includes(q));
  for(const item of filtered){
    const tr=document.createElement("tr");
    tr.dataset.name=item.name;
    for(const value of ["!"+item.name,item.description||"—",item.permission??"Unknown",item.classification]){
      const td=document.createElement("td");td.textContent=plain(value);tr.append(td);
    }
    tr.addEventListener("click",()=>{selected=item;$("selected").textContent="!"+item.name+" · "+(item.source_path||"");preview()});
    $("items").append(tr);
  }
  $("status").textContent=filtered.length+" of "+all.length+" commands";
}
$("search").addEventListener("input",render);
$("args").addEventListener("input",preview);
$("copy").addEventListener("click",()=>{const value=$("preview").textContent;if(value&&value!=="—")navigator.clipboard.writeText(value).catch(()=>{$("status").textContent="Clipboard unavailable; select the preview to copy manually."})});
fetch("/server/gm/commands").then(async r=>{if(!r.ok)throw Error((await r.json()).detail||"Unable to load catalog");return r.json()}).then(data=>{all=data.commands||[];render()}).catch(err=>{$("status").textContent=err.message});
</script></body></html>""")


