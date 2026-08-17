"""Optional OpenAI orchestration for the Irene Energy Agent.

The remote model can select and combine approved tools, but every project
number is produced by the deterministic local engine. API keys are accepted
only at runtime and are never persisted by this module.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import replace
from typing import Callable, Mapping, Sequence

from .energy_agent import (
    AgentResponse,
    OPENAI_TOOL_DEFINITIONS,
    ToolResult,
    answer_energy_question,
    compose_enhanced_response,
    execute_energy_tool,
)


DEFAULT_MODEL = "gpt-5.6-terra"
ALLOWED_MODELS = ("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol")
ALLOWED_EFFORTS = ("low", "medium", "high")
MAX_TOOL_ROUNDS = 3
MAX_TOOL_CALLS = 6

Transport = Callable[[dict[str, object], dict[str, str]], dict[str, object]]


SYSTEM_INSTRUCTIONS = """You are the energy-decision orchestrator for the anonymized Ningbo reference case in Project Irene.
Call at least one provided Irene project tool before answering. You may combine tools, but do not call the same tool more than once.
The model is responsible only for understanding, planning and expression. Every project number must come directly from tool output; never calculate or invent project values independently.
Clearly distinguish APPROVED AGGREGATE, SYNTHETIC PUBLIC DEMO, DERIVED, ASSUMED and SANDBOX evidence. The reference case currently has no battery storage. Its approved aggregate PV capacity is 106.14 kWp.
The Ningbo reference-case electricity-billing rule is kWh × CNY 0.538 only. Never claim to connect to, control or modify the BMS, and never make procurement commitments. Treat the Malaysia carbon factor as a parameterized scenario assumption, not a field result.
Answer in clear competition-ready English. Lead with the direct answer, then state the evidence boundary and recommended next action."""


def _safe_model(model: str) -> str:
    return model if model in ALLOWED_MODELS else DEFAULT_MODEL


def _safe_effort(effort: str) -> str:
    return effort if effort in ALLOWED_EFFORTS else "medium"


def _history_items(history: Sequence[str] | None) -> list[dict[str, str]]:
    clean = [str(item).strip()[:1200] for item in (history or ()) if str(item).strip()][-6:]
    return [{"role": "user", "content": item} for item in clean]


def _post_json(
    base_url: str,
    payload: dict[str, object],
    api_key: str,
    timeout: float,
    transport: Transport | None,
) -> dict[str, object]:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if transport:
        return transport(payload, headers)
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/responses",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Never include response bodies: they may contain request diagnostics.
        raise RuntimeError(f"OpenAI service returned HTTP {exc.code}") from None
    except urllib.error.URLError:
        raise RuntimeError("OpenAI service is unreachable") from None


def _output_items(response: Mapping[str, object]) -> list[dict[str, object]]:
    output = response.get("output", [])
    return [item for item in output if isinstance(item, dict)] if isinstance(output, list) else []


def _tool_calls(response: Mapping[str, object]) -> list[dict[str, object]]:
    return [item for item in _output_items(response) if item.get("type") == "function_call"]


def _output_text(response: Mapping[str, object]) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    parts: list[str] = []
    for item in _output_items(response):
        content = item.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "output_text" and isinstance(block.get("text"), str):
                parts.append(str(block["text"]))
    return "\n".join(parts).strip()


def _usage(response: Mapping[str, object]) -> tuple[int, int]:
    usage = response.get("usage", {})
    if not isinstance(usage, Mapping):
        return 0, 0
    return int(usage.get("input_tokens", 0) or 0), int(usage.get("output_tokens", 0) or 0)


def _tool_payload(result: ToolResult) -> str:
    return json.dumps(
        {
            "intent": result.intent,
            "tool": result.tool,
            "title": result.title,
            "answer": result.body,
            "evidence": result.evidence,
            "sources": list(result.sources),
            "next_steps": list(result.actions),
            "calculations": list(result.calculations),
        },
        ensure_ascii=False,
    )


def _local_fallback(
    question: str,
    context: Mapping[str, object] | None,
    history: Sequence[str] | None,
    reason: str,
) -> AgentResponse:
    local = answer_energy_question(question, context, history)
    return replace(
        local,
        engine="fallback",
        provider="Local deterministic engine",
        model_mode="LOCAL FALLBACK · 9 AUDITABLE TOOLS",
        fallback_reason=reason,
    )


def answer_energy_question_hybrid(
    question: str,
    context: Mapping[str, object] | None = None,
    history: Sequence[str] | None = None,
    *,
    mode: str = "local",
    api_key: str = "",
    model: str = DEFAULT_MODEL,
    effort: str = "medium",
    base_url: str = "https://api.openai.com/v1",
    timeout: float = 35.0,
    safety_identifier: str = "db-energy-session",
    transport: Transport | None = None,
) -> AgentResponse:
    """Run local mode or OpenAI-enhanced tool orchestration with safe fallback."""
    if mode != "openai":
        return answer_energy_question(question, context, history)
    if not api_key.strip():
        return _local_fallback(question, context, history, "No OpenAI API key is configured, so the auditable local mode was used automatically.")

    safe_model = _safe_model(model)
    input_items: list[dict[str, object]] = [*_history_items(history), {"role": "user", "content": (question or "").strip()[:1200]}]
    seen_tools: set[str] = set()
    results: list[ToolResult] = []
    total_input = 0
    total_output = 0
    try:
        for round_index in range(MAX_TOOL_ROUNDS):
            payload: dict[str, object] = {
                "model": safe_model,
                "instructions": SYSTEM_INSTRUCTIONS,
                "input": input_items,
                "tools": list(OPENAI_TOOL_DEFINITIONS),
                "tool_choice": "required" if round_index == 0 else "auto",
                "parallel_tool_calls": True,
                "reasoning": {"effort": _safe_effort(effort)},
                "text": {"verbosity": "medium"},
                "max_output_tokens": 1000,
                "store": False,
                "safety_identifier": safety_identifier[:64],
            }
            response = _post_json(base_url, payload, api_key.strip(), timeout, transport)
            in_tokens, out_tokens = _usage(response)
            total_input += in_tokens
            total_output += out_tokens
            calls = _tool_calls(response)
            if not calls:
                if not results:
                    raise RuntimeError("OpenAI response did not select an Irene tool")
                return compose_enhanced_response(question, results, _output_text(response), safe_model, total_input, total_output)

            input_items.extend(_output_items(response))
            for call in calls:
                name = str(call.get("name", ""))
                call_id = str(call.get("call_id", ""))
                if not name or not call_id:
                    raise RuntimeError("OpenAI returned an incomplete tool call")
                if name in seen_tools:
                    output = json.dumps({"status": "skipped", "reason": "tool already executed"}, ensure_ascii=False)
                elif len(results) >= MAX_TOOL_CALLS:
                    output = json.dumps({"status": "skipped", "reason": "tool call limit reached"}, ensure_ascii=False)
                else:
                    result = execute_energy_tool(name, question, context, history)
                    seen_tools.add(name)
                    results.append(result)
                    output = _tool_payload(result)
                input_items.append({"type": "function_call_output", "call_id": call_id, "output": output})

        if results:
            return compose_enhanced_response(question, results, "", safe_model, total_input, total_output)
        raise RuntimeError("OpenAI tool orchestration ended without a result")
    except Exception as exc:  # Safe user experience: retain the deterministic engine.
        reason = "OpenAI enhancement is temporarily unavailable, so local mode was used automatically."
        if isinstance(exc, RuntimeError) and str(exc).startswith("OpenAI service returned HTTP"):
            reason = f"{str(exc)}; local mode was used automatically."
        return _local_fallback(question, context, history, reason)


def test_openai_connection(
    api_key: str,
    model: str = DEFAULT_MODEL,
    effort: str = "low",
    *,
    base_url: str = "https://api.openai.com/v1",
    timeout: float = 20.0,
    transport: Transport | None = None,
) -> tuple[bool, str]:
    """Test server-side connectivity without exposing or storing the key."""
    if not api_key.strip():
        return False, "No API key was detected."
    payload: dict[str, object] = {
        "model": _safe_model(model),
        "instructions": "Reply with exactly: OK",
        "input": "Connection test",
        "reasoning": {"effort": _safe_effort(effort)},
        "max_output_tokens": 16,
        "store": False,
    }
    try:
        response = _post_json(base_url, payload, api_key.strip(), timeout, transport)
        return bool(response.get("id") or _output_text(response)), "Connection succeeded; the key was used only for this server-side request."
    except Exception:
        return False, "Connection failed. Check the key, network, model access and API account quota."
