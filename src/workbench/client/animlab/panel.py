"""Standalone Anim Lab test panel (stdlib http.server; independent of gui_server.py).

Run: python -m workbench.client.animlab.panel [--port 8765] [--bridge-dir DIR]
Pick a mob, play/sweep anim ids through the Ashita bridge, record a verdict per id.
SQL export only includes ids marked "correct".
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from workbench.client.animlab import observations
from workbench.client.animlab.bridge import Bridge

PAGE = """<!doctype html><meta charset=utf-8><title>Anim Lab</title>
<style>body{font:14px sans-serif;margin:16px;max-width:900px}input{width:6em}
td,th{border:1px solid #888;padding:2px 8px}button{margin:2px}</style>
<h2>Anim Lab</h2>
<p>Mob <input id=mob value=Mumor style="width:10em"> <button onclick="cmd('find',{name:mob.value})">Find</button>
Skill <input id=skill value=2899> Anim <input id=anim value=2037>
<button onclick="cmd('play',{anim:+anim.value,skill:+skill.value})">Play</button>
Sweep to <input id=hi value=2042> gap <input id=gap value=8>
<button onclick="cmd('sweep',{lo:+anim.value,hi:+hi.value,gap:+gap.value,skill:+skill.value})">Sweep</button>
<button onclick="cmd('stop',{})">Stop</button></p>
<p>Verdict for mob/anim/skill above:
<button onclick="note('correct')">correct</button><button onclick="note('wrong')">wrong</button>
<button onclick="note('unknown')">unknown</button> note <input id=text style="width:20em"></p>
<pre id=log style="height:8em;overflow:auto;border:1px solid #888"></pre>
<table id=obs></table><p><a href="/export.sql">SQL export (confirmed only)</a></p>
<script>
async function cmd(c,a){await fetch('/api/'+c,{method:'POST',body:JSON.stringify(a)});}
async function note(v){await fetch('/api/note',{method:'POST',body:JSON.stringify(
 {mob:mob.value,anim:+anim.value,skill:+skill.value,verdict:v,note:text.value})});refresh();}
async function refresh(){
 const r=await (await fetch('/api/state')).json();
 log.textContent=r.results.map(x=>x.stamp+' '+x.kind+' '+x.args.join(' ')).join('\\n');
 obs.innerHTML='<tr><th>mob<th>anim<th>skill<th>verdict<th>note</tr>'+r.obs.map(o=>
  `<tr><td>${o.mob}<td>${o.anim}<td>${o.skill}<td>${o.verdict}<td>${o.note}</tr>`).join('');}
setInterval(refresh,1500);refresh();
</script>"""


def export_sql(rows: list[dict]) -> str:
    out = ["-- Anim Lab export: operator-confirmed (mob, anim, skill) only. Review before applying."]
    for r in rows:
        out.append(f"-- {r['mob']}: skill {r['skill']} -> anim {r['anim']} ({r['note']})")
    return "\n".join(out) + "\n"


def make_handler(bridge: Bridge):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body: bytes, ctype: str):
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self._send(PAGE.encode(), "text/html; charset=utf-8")
            elif self.path == "/api/state":
                res = [{"stamp": r.stamp, "kind": r.kind, "args": r.args} for r in bridge.results()[-40:]]
                self._send(json.dumps({"results": res, "obs": observations.load()}).encode(), "application/json")
            elif self.path == "/export.sql":
                self._send(export_sql(observations.confirmed()).encode(), "text/plain; charset=utf-8")
            else:
                self.send_error(404)

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            a = json.loads(self.rfile.read(n) or b"{}")
            cmd = self.path.rsplit("/", 1)[-1]
            try:
                if cmd == "find":
                    bridge.find(a["name"])
                elif cmd == "play":
                    bridge.play(a["anim"], a["skill"])
                elif cmd == "sweep":
                    bridge.sweep(a["lo"], a["hi"], a["gap"], a["skill"])
                elif cmd == "stop":
                    bridge.stop()
                elif cmd == "note":
                    observations.record(a["mob"], a["anim"], a["skill"], a["verdict"], a.get("note", ""))
                else:
                    return self.send_error(404)
                self._send(b"{}", "application/json")
            except (ValueError, KeyError) as exc:
                self.send_error(400, str(exc))

    return H


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--bridge-dir")
    a = ap.parse_args(argv)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(Bridge(a.bridge_dir)))
    print(f"Anim Lab panel: http://127.0.0.1:{a.port}/")
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
