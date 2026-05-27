"""ExecutionAgent: the controller-style worker of the three-layer architecture.

The execution layer:

* Owns the LangChain agent that runs the LLM-with-tools loop.
* Holds the capability registry, but is persona-less; instructions are
  natural-language messages from the thinking layer above.
* Exposes :py:meth:`describe_capabilities` so the thinking layer can build a
  capability boundary into its own system prompt.
* Accepts per-invocation WM entries via :class:`~m_agent.systems.wm.WMDisplay`
  for its own system prompt (recent tail, same policy as the thinking layer).
* Returns a structured :class:`~m_agent.layers.execution.contracts.ExecutionResult`
  (the final NL summary + the raw tool call history) instead of the
  controller-level ``ChatAgentResponse``.

This module deliberately keeps the same LangChain agent factory and retry
policy as the legacy :mod:`m_agent.agents.chat_controller_agent` so that the
behavioral parity tests in Phase 5 can compare like-for-like.
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langgraph.errors import GraphRecursionError

from m_agent.systems.tools import (
    ControllerCapabilityContext,
    ControllerCapabilityRegistry,
    build_controller_tools,
    get_default_capability_registry,
    resolve_enabled_controller_capability_names,
)
from m_agent.systems.episodic import EpisodeQueryModule
from m_agent.layers.execution.contracts import (
    CapabilityDescriptor,
    ExecutionRequest,
    ExecutionResult,
)
from m_agent.layers.execution.errors import ExecutionCancelledError
from m_agent.layers.execution.model_provider import ModelProvider
from m_agent.systems.wm import WMDisplay
from m_agent.utils.api_error_utils import is_network_api_error


logger = logging.getLogger(__name__)


_CONTROLLER_LIMIT_KEY = "__controller__"


@dataclass
class _ExecutionAnswer:
    """Internal LangChain structured-output schema.

    The execution layer still uses LangChain's ``ToolStrategy`` to force the
    LLM to emit a final summary string; this dataclass mirrors the legacy
    ``ChatAgentResponse`` but is private to the execution layer because the
    thinking layer never sees it.
    """

    answer: str


class ExecutionAgent:
    """Persona-less controller that turns NL instructions into tool calls + a summary."""

    def __init__(
        self,
        *,
        model_provider: ModelProvider,
        enabled_capability_names: List[str],
        capability_descriptions: Dict[str, str],
        tool_defaults: Dict[str, Dict[str, Any]],
        email_agent_provider: Optional[Callable[[], Any]] = None,
        schedule_agent_provider: Optional[Callable[[], Any]] = None,
        registry: Optional[ControllerCapabilityRegistry] = None,
        episode_query_module: Optional[EpisodeQueryModule] = None,
        episodic_backend: Any = None,
        system_prompt_base: str = "",
        tool_policy_prompt: str = "",
        prompt_language: str = "zh",
        capability_block_header: str = "",
        fallback_system_prompt: str = "",
        wm_display: Optional[WMDisplay] = None,
    ) -> None:
        self.model_provider = model_provider
        self.tool_defaults = dict(tool_defaults or {})
        self.email_agent_provider = email_agent_provider
        self.schedule_agent_provider = schedule_agent_provider
        self.registry = registry or get_default_capability_registry()
        self.episode_query_module = episode_query_module or EpisodeQueryModule(enabled=True)
        self.episodic_backend = episodic_backend
        self.system_prompt_base = str(system_prompt_base or "").strip()
        self.tool_policy_prompt = str(tool_policy_prompt or "").strip()
        self.prompt_language = str(prompt_language or "zh").strip().lower() or "zh"
        self._capability_block_header_override = str(capability_block_header or "").strip()
        self._fallback_system_prompt_override = str(fallback_system_prompt or "").strip()
        self.wm_display = wm_display

        # Apply the episode-query switch BEFORE storing the active capability set.
        all_enabled = list(enabled_capability_names or [])
        self.enabled_capability_names: List[str] = self.episode_query_module.filter_capability_names(
            all_enabled
        )
        self.capability_descriptions: Dict[str, str] = {
            name: str(capability_descriptions.get(name, "") or "").strip()
            for name in self.enabled_capability_names
        }
        # Pre-compute the capability boundary block for the thinking layer.
        self._capability_block_cache = self._build_capability_block()

    # ------------------------------------------------------------------
    # Public API exposed to the thinking layer
    # ------------------------------------------------------------------

    def describe_capabilities(self) -> List[CapabilityDescriptor]:
        """Return the list of capability descriptors visible upward.

        Capabilities disabled via :class:`EpisodeQueryModule` are not present.
        """
        descriptors: List[CapabilityDescriptor] = []
        for name in self.enabled_capability_names:
            descriptors.append(
                CapabilityDescriptor(
                    name=name,
                    category=self._capability_category(name),
                    short_description=self.capability_descriptions.get(name, "") or f"Top-level tool: {name}",
                )
            )
        return descriptors

    def describe_capabilities_block(self) -> str:
        """Return the human-readable capability list for prepending to thinking-layer prompts."""
        return self._capability_block_cache

    def execute(
        self,
        request: ExecutionRequest,
        *,
        wm_entries: Optional[List[Dict[str, Any]]] = None,
        wm_writer_callback: Optional[Callable[[ExecutionResult], None]] = None,
        think_life_hooks: Optional[Dict[str, Any]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> ExecutionResult:
        """Run one LLM-with-tools loop over ``request.instruction`` and return a structured result."""

        instruction = str(request.instruction or "").strip()
        if not instruction:
            raise ValueError("ExecutionRequest.instruction must be a non-empty string")
        active_thread_id = str(request.thread_id or "").strip()
        if not active_thread_id:
            raise ValueError("ExecutionRequest.thread_id must be a non-empty string")

        # Per-execution mutable state (closed-over by capability tools)
        recall_state: Dict[str, Any] = {"mode": None, "result": None, "history": []}
        controller_state: Dict[str, Any] = {"history": [], "call_seq": 0}
        if think_life_hooks:
            controller_state["think_life"] = dict(think_life_hooks)

        capability_context = ControllerCapabilityContext(
            active_thread_id=active_thread_id,
            recall_state=recall_state,
            controller_state=controller_state,
            tool_defaults=self.tool_defaults,
            logger=logger,
            email_agent_provider=self.email_agent_provider,
            schedule_agent_provider=self.schedule_agent_provider,
            episodic_backend=self.episodic_backend,
        )
        tools = build_controller_tools(
            context=capability_context,
            enabled_tool_names=self.enabled_capability_names,
            tool_descriptions=self.capability_descriptions,
            registry=self.registry,
        )
        system_prompt = self._build_execution_system_prompt(wm_entries=wm_entries)
        agent = create_agent(
            model=self.model_provider.model,
            system_prompt=system_prompt,
            tools=tools,
            response_format=ToolStrategy(_ExecutionAnswer),
        )

        response = self._invoke_with_retries(
            agent,
            instruction=instruction,
            active_thread_id=active_thread_id,
            correlation_id=request.correlation_id or "",
            cancel_event=cancel_event,
        )

        summary = self._extract_summary(response)
        tool_history = list(controller_state.get("history", []) or [])

        # Surface explicit failure modes for the thinking-layer summarize pass.
        insufficient = False
        limit_reached = False
        for item in tool_history:
            if not isinstance(item, dict):
                continue
            result = item.get("result")
            if isinstance(result, dict):
                if bool(result.get("limit_reached")):
                    limit_reached = True
                if bool(result.get("insufficient")):
                    insufficient = True
        recall_result = recall_state.get("result") if isinstance(recall_state, dict) else None
        if not summary and isinstance(recall_result, dict):
            summary = str(recall_result.get("answer", "") or "").strip()

        execution_result = ExecutionResult(
            summary=summary,
            tool_history=tool_history,
            success=True,
            insufficient=insufficient,
            limit_reached=limit_reached,
            raw={
                "recall_state": recall_state,
                "instruction": instruction,
                "correlation_id": request.correlation_id or "",
            },
        )

        if wm_writer_callback is not None:
            try:
                wm_writer_callback(execution_result)
            except Exception:
                logger.exception("ExecutionAgent wm_writer_callback failed")

        return execution_result

    # ------------------------------------------------------------------
    # System-prompt assembly (no persona)
    # ------------------------------------------------------------------

    def _build_execution_system_prompt(
        self,
        *,
        wm_entries: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        sections: List[str] = []
        if self.system_prompt_base:
            sections.append(self.system_prompt_base)
        if self.tool_policy_prompt:
            sections.append(self.tool_policy_prompt)
        if self.wm_display is not None and wm_entries:
            wm_block = self.wm_display.render(list(wm_entries), language=self.prompt_language)
            if wm_block:
                sections.append(wm_block)
        if self._capability_block_cache:
            sections.append(self._capability_block_cache)
        if not sections:
            # Fall back to a minimal task-executor framing so the model is never
            # left with an empty system prompt.
            if self._fallback_system_prompt_override:
                sections.append(self._fallback_system_prompt_override)
            else:
                sections.append(
                    "你是一个工具执行助手，请严格按照工具说明完成上层提出的指令。"
                    if self.prompt_language == "zh"
                    else "You are a tool-executing assistant. Follow the instruction precisely using the tools below."
                )
        return "\n\n".join(section for section in sections if section).strip()

    def _build_capability_block(self) -> str:
        if not self.enabled_capability_names:
            return ""
        if self._capability_block_header_override:
            header = self._capability_block_header_override
        else:
            header = "[可用顶层工具]" if self.prompt_language == "zh" else "[Available Top-Level Tools]"
        lines = [header]
        for name in self.enabled_capability_names:
            description = self.capability_descriptions.get(name, "") or f"Top-level tool: {name}"
            lines.append(f"- `{name}`: {description}")
        return "\n".join(lines)

    @staticmethod
    def _capability_category(name: str) -> str:
        if name in {"shallow_recall", "deep_recall"}:
            return "episode_query"
        if name in {"email_ask", "email_read", "email_send"}:
            return "email"
        if name in {"schedule_manage", "schedule_query"}:
            return "schedule"
        if name == "get_current_time":
            return "time"
        return "general"

    # ------------------------------------------------------------------
    # Invocation with recursion + network retries
    # ------------------------------------------------------------------

    def _invoke_with_retries(
        self,
        agent: Any,
        *,
        instruction: str,
        active_thread_id: str,
        correlation_id: str,
        cancel_event: Optional[threading.Event] = None,
    ) -> Dict[str, Any]:
        total_attempts = max(int(self.model_provider.network_retry_attempts), 1)
        last_exc: Optional[BaseException] = None
        for attempt in range(1, total_attempts + 1):
            try:
                tid_attempt = (
                    active_thread_id if attempt == 1 else f"{active_thread_id}:netretry:{attempt}"
                )
                return self._invoke_once(
                    agent,
                    instruction=instruction,
                    active_thread_id=tid_attempt,
                    correlation_id=correlation_id,
                    cancel_event=cancel_event,
                )
            except Exception as exc:
                last_exc = exc
                if not is_network_api_error(exc) or attempt >= total_attempts:
                    raise
                delay = self.model_provider.compute_network_retry_delay(attempt)
                logger.warning(
                    "ExecutionAgent invoke hit network/API error on attempt %d/%d: %s; retrying in %.2fs",
                    attempt,
                    total_attempts,
                    exc,
                    delay,
                )
                if delay > 0:
                    threading.Event().wait(delay)
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("ExecutionAgent invoke exhausted retry attempts unexpectedly")

    def _invoke_once(
        self,
        agent: Any,
        *,
        instruction: str,
        active_thread_id: str,
        correlation_id: str,
        cancel_event: Optional[threading.Event] = None,
    ) -> Dict[str, Any]:
        invoke_config = {
            "configurable": {"thread_id": f"{active_thread_id}:exec"},
            "recursion_limit": self.model_provider.recursion_limit,
        }
        payload = {"messages": [{"role": "user", "content": instruction}]}

        def _check_cancel() -> None:
            if cancel_event is not None and cancel_event.is_set():
                raise ExecutionCancelledError("execution preempted")

        try:
            return self._invoke_cooperative(
                agent,
                payload=payload,
                config=invoke_config,
                check_cancel=_check_cancel,
            )
        except GraphRecursionError:
            retry_config = {
                "configurable": {"thread_id": f"{active_thread_id}:exec:retry"},
                "recursion_limit": self.model_provider.retry_recursion_limit,
            }
            return self._invoke_cooperative(
                agent,
                payload=payload,
                config=retry_config,
                check_cancel=_check_cancel,
            )

    def _invoke_cooperative(
        self,
        agent: Any,
        *,
        payload: Dict[str, Any],
        config: Dict[str, Any],
        check_cancel: Callable[[], None],
    ) -> Dict[str, Any]:
        check_cancel()
        stream_fn = getattr(agent, "stream", None)
        if stream_fn is None:
            check_cancel()
            return agent.invoke(payload, config=config)

        last_chunk: Any = None
        for chunk in stream_fn(payload, config=config):
            check_cancel()
            if isinstance(chunk, dict):
                last_chunk = chunk
            elif last_chunk is None:
                last_chunk = chunk
        check_cancel()
        if last_chunk is None:
            return agent.invoke(payload, config=config)
        if isinstance(last_chunk, dict):
            return last_chunk
        return {"messages": [], "structured_response": last_chunk}

    @staticmethod
    def _extract_summary(response: Any) -> str:
        if not isinstance(response, dict):
            return str(response or "").strip()
        structured = response.get("structured_response")
        if structured is None:
            messages = response.get("messages")
            if isinstance(messages, list) and messages:
                last = messages[-1]
                text = getattr(last, "content", None)
                if text is None and isinstance(last, dict):
                    text = last.get("content")
                if isinstance(text, str):
                    return text.strip()
            return ""
        if hasattr(structured, "answer"):
            return str(getattr(structured, "answer", "") or "").strip()
        if isinstance(structured, dict):
            return str(structured.get("answer", "") or "").strip()
        return str(structured or "").strip()
