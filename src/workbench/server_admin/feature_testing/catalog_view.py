"""#1410: display-only description of a stored catalog revision for the browse pages.

Pure. It reads a stored specification and lists what is in it in plain sections; it never evaluates, validates or
promotes anything, and it tolerates fields that are missing or the wrong shape (shown as absent, never a crash).
"""
from __future__ import annotations


def _texts(value: object, limit: int = 50) -> list[str]:
    return [str(item)[:400] for item in value[:limit] if isinstance(item, (str, int, float))] if isinstance(value, list) else []


def _words(key: str) -> str:
    return key.replace("_", " ")


def _text(value: object) -> str:
    return value if isinstance(value, str) else __import__("json").dumps(value)


def native_step_lines(native_steps: object) -> list[dict]:
    """When / Then / And reading of saved native steps (an action is When, a check is Then, repeats are And)."""
    steps = native_steps.get("steps") if isinstance(native_steps, dict) else None
    lines, last = [], None
    for step in steps if isinstance(steps, list) else []:
        if not isinstance(step, dict):
            continue
        timeout = step.get("timeout_ms")
        timeout_text = f" (timeout {timeout} ms)" if type(timeout) is int else ""
        for side, keyword in (("do", "When"), ("expect", "Then")):
            part = step.get(side)
            if not isinstance(part, dict) or len(part) != 1:
                continue
            key = next(iter(part))
            body = _words(key) + (" " if side == "do" else " is ") + _text(part[key])
            if side == "expect":
                body += timeout_text  # the timeout bounds the check's polling window
            lines.append({"keyword": "And" if last == keyword else keyword, "text": body[:400], "step": str(step.get("name", ""))[:100]})
            last = keyword
    return lines


def describe_spec(spec: object) -> dict:
    """Plain sections of a stored specification for display."""
    spec = spec if isinstance(spec, dict) else {}
    behavior = spec.get("behavior") if isinstance(spec.get("behavior"), dict) else {}
    assertions = spec.get("assertions") if isinstance(spec.get("assertions"), list) else []
    authoring = spec.get("authoring") if isinstance(spec.get("authoring"), dict) else {}
    return {
        "name": spec.get("name") if isinstance(spec.get("name"), str) else None,
        "purpose": spec.get("purpose") if isinstance(spec.get("purpose"), str) else None,
        "rationale": spec.get("rationale") if isinstance(spec.get("rationale"), str) else None,
        "preconditions": _texts(spec.get("preconditions")),
        "behavior": {phase: _texts(behavior.get(phase)) for phase in ("given", "when", "then")},
        "assertion_ids": [a["id"] for a in assertions if isinstance(a, dict) and isinstance(a.get("id"), str)][:100],
        "steps": native_step_lines(spec.get("native_steps")),
        "cleanup": _texts(spec.get("cleanup")),
        "blocking_gaps": _texts(authoring.get("blocking_gaps")),
        "runner": spec.get("runner") if isinstance(spec.get("runner"), str) else None,
        "execution_status": spec.get("execution_status") if isinstance(spec.get("execution_status"), str) else None,
    }
