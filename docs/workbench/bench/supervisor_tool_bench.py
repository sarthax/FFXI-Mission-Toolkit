"""Tool-use benchmark: Ollama models (<=9B) vs the read-only Mission Toolkit supervisor.
Token comes from MISSION_TOOLKIT_SUPERVISOR_TOKEN (never written out). Tool calls are executed for real."""
import json, os, re, sys, time, urllib.request, urllib.error, urllib.parse
SUP = "http://127.0.0.1:8421"; OLL = "http://127.0.0.1:11434"
TOK = os.environ["MISSION_TOOLKIT_SUPERVISOR_TOKEN"]
N = int(os.environ.get("TRIALS", "3"))
MODELS = sys.argv[1:]

def http(url, body=None, headers=None, timeout=300):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.load(r)

spec = http(SUP + "/api/supervisor/openapi.json")
TOOLS, ROUTES = [], {}
for path, item in spec["paths"].items():
    op = item["get"]; name = op["operationId"]; props, req = {}, []
    for p in op.get("parameters", []):
        props[p["name"]] = {"type": p["schema"].get("type", "string"), "description": p.get("description", p["name"])}
        if p.get("required"): req.append(p["name"])
    TOOLS.append({"type": "function", "function": {"name": name, "description": op.get("summary", name),
                  "parameters": {"type": "object", "properties": props, "required": req}}})
    ROUTES[name] = (path, set(props), set(req))

def call_sup(name, args):
    path, props, req = ROUTES[name]
    bad = [k for k in args if k not in props] + [k for k in req if k not in args]
    if bad: return {"error": "invalid arguments", "detail": bad}, False
    q = urllib.parse.urlencode(args)
    try: return http(SUP + path + ("?" + q if q else ""), headers={"Authorization": "Bearer " + TOK}), True
    except urllib.error.HTTPError as e: return {"error": f"HTTP {e.code}"}, False
    except Exception as e: return {"error": str(e)[:100]}, False

truth = {n: call_sup(n, a)[0] for n, a in [("supervisor_health", {}), ("supervisor_test_runs", {}),
         ("supervisor_failed_assertions", {}), ("supervisor_test_character_inventory", {"charid": 21836})]}
run_ids = [r["run_id"] for r in truth["supervisor_test_runs"]["runs"]] if isinstance(truth["supervisor_test_runs"]["runs"], list) else re.findall(r"obs-\w+", json.dumps(truth["supervisor_test_runs"]))
inv_n = len(truth["supervisor_test_character_inventory"]["items"])
has = lambda t, *ws: all(w.lower() in t.lower() for w in ws)
anyof = lambda t, *ws: any(w.lower() in t.lower() for w in ws)
NONE = r"\b(no|none|zero|0|not any|without)\b"
TASKS = [
 ("health", "Is the Mission Toolkit supervisor gateway healthy, and is execution enabled?", {"supervisor_health"}, {},
  lambda t: has(t, "ready") and anyof(t, "disabled", "not enabled", "false", "no execution", "execution is off", "execution enabled: no")),
 ("test_runs", "What are the latest test runs and their verdicts?", {"supervisor_test_runs"}, {},
  lambda t: all(r in t for r in run_ids) and has(t, "pass")),
 ("failures", "Were there any failed assertions in the recorded test results?", {"supervisor_failed_assertions"}, {},
  lambda t: re.search(NONE, t, re.I) is not None and not re.search(r"\bFAIL(ED)?\b.*(case|MOG)", t)),
 ("ollama", "Is the ollama service reachable right now?", {"supervisor_service_health"}, {"service": "ollama"},
  lambda t: anyof(t, "reachable", "up", "running") and not anyof(t, "unreachable", "not reachable")),
 ("inventory", "How many persisted inventory rows does test character 21836 have?", {"supervisor_test_character_inventory"}, {"charid": 21836},
  lambda t: str(inv_n) in t),
 ("logs", "Show me recent error lines from the dsp log.", {"supervisor_log_errors"}, {"source": "dsp"},
  lambda t: len(t) > 40),
 ("unavailable", "List the key items held by character 21836.", set(), None,
  lambda t: anyof(t, "not available", "cannot", "can't", "unable", "no tool", "does not provide", "not provide", "don't have", "do not have", "isn't", "not support", "no endpoint", "doesn't") and "387" not in t),
 ("multi", "Check the supervisor health, then retrieve the latest test run and summarize any failures.", {"supervisor_health", "supervisor_test_runs"}, {},
  lambda t: has(t, "ready") and all(r in t for r in run_ids[:1]) and re.search(NONE, t, re.I) is not None),
]
SYSTEM = "You are a test supervisor assistant. Use the provided tools to retrieve evidence before answering. Only state facts returned by tools. If no tool can supply something, say so."

def run(model, prompt):
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    calls, valid_all, t0, text = [], True, time.time(), ""
    opts = {"temperature": 0.2}; body = {"model": model, "stream": False, "tools": TOOLS, "options": opts, "keep_alive": "10m"}
    if model.startswith("qwen3"): body["think"] = False
    for _ in range(5):
        try: r = http(OLL + "/api/chat", {**body, "messages": msgs})
        except urllib.error.HTTPError as e: return dict(error=e.read().decode()[:200], calls=calls, text="", secs=time.time() - t0, valid=False)
        m = r["message"]; msgs.append(m); tcs = m.get("tool_calls") or []
        if not tcs: text = m.get("content", ""); break
        for tc in tcs:
            fn = tc["function"]; args = fn.get("arguments") or {}
            if isinstance(args, str):
                try: args = json.loads(args)
                except Exception: args = {}
            if fn["name"] not in ROUTES: out, ok = {"error": "unknown tool"}, False
            else: out, ok = call_sup(fn["name"], args)
            calls.append((fn["name"], args)); valid_all &= ok
            msgs.append({"role": "tool", "content": json.dumps(out)[:6000], "tool_name": fn["name"]})
    return dict(calls=calls, text=text, secs=time.time() - t0, valid=valid_all)

results = []
for model in MODELS:
    print("==", model, flush=True)
    for tid, prompt, exp, args, check in TASKS:
        for i in range(N):
            r = run(model, prompt); names = {c[0] for c in r["calls"]}
            if "error" in r: tool_ok = args_ok = grounded = False
            elif not exp: tool_ok = len(names) == 0 or True; args_ok = r["valid"]; grounded = bool(check(r["text"])) and not any(n == "supervisor_test_character_inventory" and False for n in names)
            else:
                tool_ok = exp <= names; args_ok = r["valid"] and tool_ok and all(any(c[0] in exp and str(c[1].get(k)) == str(v) for c in r["calls"]) for k, v in (args or {}).items())
                grounded = tool_ok and bool(check(r["text"]))
            rec = dict(model=model, task=tid, trial=i, tool_ok=tool_ok, args_ok=args_ok, grounded=grounded, secs=round(r["secs"], 1),
                       ncalls=len(r["calls"]), calls=r["calls"], text=r["text"][:600], error=r.get("error"))
            results.append(rec); print(f"  {tid}#{i} tool={tool_ok} args={args_ok} ok={grounded} {rec['secs']}s {rec['error'] or ''}", flush=True)
    try: http(OLL + "/api/generate", {"model": model, "keep_alive": 0})
    except Exception: pass
out = os.environ.get("OUT", "results.json"); json.dump(dict(truth_run_ids=run_ids, inv_rows=inv_n, results=results), open(out, "w"), indent=1)
