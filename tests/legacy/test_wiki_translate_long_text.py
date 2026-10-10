"""Long unstructured pages and oversize blocks are chunked instead of failing the 5000-char limit."""
import io, json, os, sqlite3, sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from workbench.devtools.reference import wiki_jobs, wiki_ollama_translate as t


class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def fake(req, timeout=0):
    prompt = json.loads(req.data)["prompt"]
    assert len(prompt) < 6500, len(prompt)
    return Resp(json.dumps({"response": "translated chunk"}).encode())


text = "\n".join("メデューサの説明文です。" * 20 for _ in range(60))  # >5000 chars
assert len(text) > 5000
with patch.dict(os.environ, {"WIKI_TRANSLATE_OLLAMA_MODEL": "m"}), \
        patch.object(t.urllib.request, "urlopen", side_effect=fake):
    con = sqlite3.connect(":memory:")
    r = wiki_jobs.translate_cached(con, "WikiWikiJP", "Medusa", "h", text)
    assert r["status"] == "OK", r
    assert len(r["blocks"]) > 1
    assert "".join(b["original"].replace("\n", "") for b in r["blocks"]) == text.replace("\n", "")
    con.close()
print("ok: long text chunked")
