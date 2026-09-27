#!/usr/bin/env python3
import workbench.research.providers.openwebui as ow
from workbench.research.providers import (
    OllamaDirectProvider,
    OllamaProviderError,
    OpenWebUIProvider,
    create_provider,
)


def main():
    original_list=ow.llm_client.list_models
    original_chat=ow.llm_client.chat_messages
    try:
        ow.llm_client.list_models=lambda **kwargs:[
            {
                "id":"fixture-model",
                "ollama":{
                    "capabilities":["vision","thinking"],
                    "details":{"parameter_size":"7B"},
                },
            }
        ]
        ow.llm_client.chat_messages=lambda messages,**kwargs:{
            "content":"fixture response",
            "usage":{"prompt_tokens":10,"completion_tokens":3},
        }

        provider=OpenWebUIProvider(base_url="http://fixture")
        models=provider.list_models()
        assert models[0]["id"]=="fixture-model",models

        caps=provider.capabilities("fixture-model")
        assert caps.chat is True,caps
        assert caps.vision is True,caps
        assert caps.thinking is True,caps
        assert caps.tools is False,caps

        result=provider.chat(
            [{"role":"user","content":"question"}],
            model="fixture-model",
        )
        assert result.content=="fixture response",result
        assert result.usage["completion_tokens"]==3,result
        assert result.provider_metadata["provider_id"]=="openwebui",result
    finally:
        ow.llm_client.list_models=original_list
        ow.llm_client.chat_messages=original_chat

    ollama=OllamaDirectProvider(base_url="http://ollama-fixture")
    calls=[]

    def fake_request(path,payload=None,*,timeout=60.0):
        calls.append((path,payload,timeout))
        if path=="/api/tags":
            return {
                "models":[{
                    "name":"qwen-fixture:7b",
                    "model":"qwen-fixture:7b",
                    "digest":"abc123",
                    "details":{"parameter_size":"7B","format":"gguf"},
                }]
            }
        if path=="/api/show":
            assert payload=={"model":"qwen-fixture:7b"},payload
            return {
                "capabilities":["completion","tools","thinking","vision"],
                "details":{"parameter_size":"7B"},
                "model_info":{"general.architecture":"qwen"},
            }
        if path=="/api/chat":
            assert payload["model"]=="qwen-fixture:7b",payload
            assert payload["stream"] is False,payload
            assert payload["options"]["temperature"]==0.1,payload
            return {
                "model":"qwen-fixture:7b",
                "created_at":"2026-09-27T00:00:00Z",
                "message":{
                    "role":"assistant",
                    "content":"direct ollama fixture response",
                    "thinking":"fixture thought",
                },
                "done":True,
                "done_reason":"stop",
                "total_duration":100,
                "prompt_eval_count":12,
                "prompt_eval_cached_count":4,
                "eval_count":5,
            }
        raise AssertionError(path)

    ollama._request=fake_request

    models=ollama.list_models()
    assert models==[{
        "name":"qwen-fixture:7b",
        "model":"qwen-fixture:7b",
        "digest":"abc123",
        "details":{"parameter_size":"7B","format":"gguf"},
        "id":"qwen-fixture:7b",
    }],models

    caps=ollama.capabilities("qwen-fixture:7b")
    assert caps.chat is True,caps
    assert caps.vision is True,caps
    assert caps.thinking is True,caps
    assert caps.tools is True,caps
    assert caps.metadata["details"]["parameter_size"]=="7B",caps

    result=ollama.chat(
        [{"role":"user","content":"question"}],
        model="qwen-fixture:7b",
        temperature=0.1,
        timeout=30.0,
    )
    assert result.content=="direct ollama fixture response",result
    assert result.usage["prompt_eval_count"]==12,result
    assert result.usage["prompt_eval_cached_count"]==4,result
    assert result.usage["eval_count"]==5,result
    assert result.provider_metadata["provider_id"]=="ollama",result
    assert result.provider_metadata["thinking"]=="fixture thought",result
    assert calls[-1][2]==30.0,calls

    assert isinstance(create_provider("open-webui"),OpenWebUIProvider)
    direct=create_provider("ollama-direct",base_url="http://direct-fixture")
    assert isinstance(direct,OllamaDirectProvider),direct
    assert direct.base_url=="http://direct-fixture",direct.base_url
    try:
        create_provider("unsupported")
    except ValueError:
        pass
    else:
        raise AssertionError("unsupported provider id must fail")

    fallback=OllamaDirectProvider()
    fallback._request=lambda *args,**kwargs: (_ for _ in ()).throw(
        OllamaProviderError("fixture unavailable")
    )
    caps=fallback.capabilities("missing")
    assert caps.chat is True,caps
    assert caps.metadata["capability_probe"]=="unavailable",caps

    print("research provider abstraction self-test: PASS")


if __name__=="__main__":
    main()
