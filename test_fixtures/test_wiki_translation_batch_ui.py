"""Static regression guard for Wiki translation batch endpoints and tab."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
host=(ROOT/"src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
ui=(ROOT/"gui/templates/wiki.html").read_text(encoding="utf-8")
for method,path in [
    ("get","/wiki/translation/jobs"),
    ("post","/wiki/translation/start"),
    ("post","/wiki/translation/retry"),
    ("post","/wiki/translation/cancel"),
]:
    assert '@app.'+method+'("'+path+'")' in host, path
    assert path in ui,path
assert "{% if tab == 'translation' %}" in ui
assert 'id="wiki-translation-batch-form"' in ui
assert 'id="wiki-translation-job-list"' in ui
assert "setInterval(showJobs,4000)" in ui
assert "response.ok" in ui
print("ok: Wiki translation batch route/tab contracts")
