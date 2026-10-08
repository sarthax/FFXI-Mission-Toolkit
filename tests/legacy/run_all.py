"""Run every tests/legacy/test_*.py script with the environment they need.

Usage: .venv\\Scripts\\python.exe tests\\legacy\\run_all.py [name_substring ...]
Sets PYTHONPATH=src (so `workbench` imports) and PYTHONIOENCODING=utf-8 (scripts print non-cp1252 glyphs).
"""
import os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
env = dict(os.environ)
env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
env["PYTHONIOENCODING"] = "utf-8"

filters = sys.argv[1:]
scripts = sorted(p for p in HERE.glob("test_*.py") if not filters or any(f in p.name for f in filters))
failed = []
for p in scripts:
    r = subprocess.run([sys.executable, str(p)], cwd=ROOT, env=env, timeout=600)
    print(f"{'PASS' if r.returncode == 0 else 'FAIL'}  {p.name}", flush=True)
    if r.returncode:
        failed.append(p.name)
print(f"\n{len(scripts) - len(failed)}/{len(scripts)} passed")
sys.exit(1 if failed else 0)
