"""Saved Wiki translation model: env override, saved setting fallback, installed-model listing."""
import os, sqlite3, sys, tempfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from workbench.devtools.reference import wiki_ollama_translate as t
from workbench.runtime import settings_store

with tempfile.TemporaryDirectory() as d:
    db = Path(d) / "s.db"
    with patch.object(settings_store, "DB_PATH", db), patch.dict(os.environ):
        os.environ.pop("WIKI_TRANSLATE_OLLAMA_MODEL", None)
        assert t.configured_model() == ""
        with closing(sqlite3.connect(str(db))) as con:
            settings_store.set_many(con, {"wiki_translate_model": "sugoi:q4"})
        assert t.configured_model() == "sugoi:q4"
        os.environ["WIKI_TRANSLATE_OLLAMA_MODEL"] = "env-model"
        assert t.configured_model() == "env-model"

with patch("urllib.request.urlopen", side_effect=OSError("down")):
    assert t.installed_models() == []
print("ok: wiki translate model setting")
