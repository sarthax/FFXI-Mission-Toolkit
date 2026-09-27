#!/usr/bin/env python3
import workbench.research.providers.openwebui as ow
from workbench.research.providers import OpenWebUIProvider


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

    print("research provider abstraction self-test: PASS")


if __name__=="__main__":
    main()
