from __future__ import annotations

import llm_client as legacy
from workbench.devtools.research.legacy_llm import client as canonical
from workbench.runtime.paths import OPENWEBUI_KEY_PATH


def test_root_module_is_packaged_implementation():
    assert legacy is canonical
    assert canonical.KEY_FILE == OPENWEBUI_KEY_PATH


def test_multimodal_chat_keeps_openai_compatible_image_shape(monkeypatch):
    captured = {}

    def fake_request(path, payload=None, timeout=60.0, base_url=None):
        captured.update(path=path, payload=payload, timeout=timeout, base_url=base_url)
        return {"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 3}}

    monkeypatch.setattr(canonical, "_request", fake_request)
    result = canonical.chat_full(
        "inspect",
        model="vision-model",
        system="be precise",
        image_b64="YWJj",
        image_mime="image/jpeg",
        timeout=12.5,
        base_url="http://example.invalid",
    )

    assert result == {"content": "ok", "usage": {"total_tokens": 3}}
    assert captured["path"] == "/api/chat/completions"
    assert captured["timeout"] == 12.5
    assert captured["base_url"] == "http://example.invalid"
    assert captured["payload"]["model"] == "vision-model"
    assert captured["payload"]["messages"] == [
        {"role": "system", "content": "be precise"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "inspect"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,YWJj"}},
            ],
        },
    ]
