"""Bounded GUI/runtime orchestration for ResearchSession execution and replay."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .domain_tools import WorkbenchDomainReader
from .graph_tools import CanonicalGraphReader
from .providers.factory import create_provider
from .runner import ResearchRunner
from .session import ResearchSessionStore
from .tools import ResearchToolRegistry, register_domain_tools, register_graph_tools


class ResearchExecutionError(ValueError):
    pass


def build_runtime_registry(db_path: Path) -> ResearchToolRegistry:
    """Build the conservative canonical read-tool set available to GUI research runs."""
    db_path=Path(db_path)
    if not db_path.is_file():
        raise ResearchExecutionError(f"Workbench database does not exist: {db_path}")
    registry=ResearchToolRegistry()
    register_graph_tools(registry,CanonicalGraphReader(db_path))
    register_domain_tools(registry,WorkbenchDomainReader(db_path))
    return registry


def _run_metadata(
    *,
    max_tool_calls: int,
    max_provider_calls: int,
    timeout: float,
    temperature: float,
    provider_base_url: str | None,
) -> dict[str,Any]:
    return {
        "max_tool_calls":int(max_tool_calls),
        "max_provider_calls":int(max_provider_calls),
        "timeout":float(timeout),
        "temperature":float(temperature),
        "provider_base_url":provider_base_url or None,
    }


def validate_run_controls(
    *,
    provider: str,
    model: str,
    max_tool_calls: int,
    max_provider_calls: int,
    timeout: float,
    temperature: float,
) -> None:
    if not str(provider or "").strip():
        raise ResearchExecutionError("Provider is required.")
    if not str(model or "").strip():
        raise ResearchExecutionError("Model is required.")
    if max_tool_calls < 0 or max_tool_calls > 100:
        raise ResearchExecutionError("Max tool calls must be between 0 and 100.")
    if max_provider_calls < 1 or max_provider_calls > 100:
        raise ResearchExecutionError("Max provider calls must be between 1 and 100.")
    if timeout < 1 or timeout > 900:
        raise ResearchExecutionError("Timeout must be between 1 and 900 seconds.")
    if temperature < 0 or temperature > 2:
        raise ResearchExecutionError("Temperature must be between 0 and 2.")


def execute_session(
    db_path: Path,
    research_session_id: str,
    *,
    provider_id: str,
    model: str,
    max_tool_calls: int,
    max_provider_calls: int,
    timeout: float,
    temperature: float,
    provider_base_url: str | None = None,
    replay: bool = False,
    provider_override=None,
) -> dict[str,Any]:
    """Run once or replay as a new immutable child session."""
    validate_run_controls(
        provider=provider_id,
        model=model,
        max_tool_calls=max_tool_calls,
        max_provider_calls=max_provider_calls,
        timeout=timeout,
        temperature=temperature,
    )
    store=ResearchSessionStore(Path(db_path))
    source=store.get(research_session_id)
    if source is None:
        raise KeyError(research_session_id)

    controls=_run_metadata(
        max_tool_calls=max_tool_calls,
        max_provider_calls=max_provider_calls,
        timeout=timeout,
        temperature=temperature,
        provider_base_url=provider_base_url,
    )

    if replay:
        target=store.clone_for_replay(
            research_session_id,
            provider=provider_id,
            model=model,
            budgets={"max_tool_calls":int(max_tool_calls)},
            replay_metadata={
                **dict(source.get("replay_metadata") or {}),
                "replay_of":research_session_id,
                "run_controls":controls,
            },
        )
        target_id=target.research_session_id
    else:
        if source.get("tool_calls") or source.get("final_report"):
            raise ResearchExecutionError(
                "This session has already run. Use Replay to preserve the existing transcript."
            )
        store.update_execution_config(
            research_session_id,
            provider=provider_id,
            model=model,
            budgets={"max_tool_calls":int(max_tool_calls)},
            replay_metadata={
                **dict(source.get("replay_metadata") or {}),
                "run_controls":controls,
            },
        )
        target_id=research_session_id

    provider=provider_override or create_provider(provider_id,base_url=provider_base_url)
    runner=ResearchRunner(
        provider=provider,
        registry=build_runtime_registry(Path(db_path)),
        session_store=store,
    )
    result=runner.run(
        target_id,
        max_tool_calls=max_tool_calls,
        max_provider_calls=max_provider_calls,
        temperature=temperature,
        timeout=timeout,
    )
    return {
        **result,
        "source_research_session_id":research_session_id,
        "research_session_id":target_id,
        "replay":bool(replay),
        "run_controls":controls,
    }
