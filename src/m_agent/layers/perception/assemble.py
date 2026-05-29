"""Helpers that turn runtime/chat inputs into :class:`PerceptionInput`."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from m_agent.layers.perception.contracts import PerceptionInput


def normalize_history_messages(
    history: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    if not isinstance(history, list):
        return out
    for item in history:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "") or "").strip().lower()
        content = str(item.get("content", "") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        out.append({"role": role, "content": content})
    return out


def build_perception_input(
    *,
    message: str,
    thread_id: str,
    conversation_id: str,
    history_messages: Optional[List[Dict[str, Any]]] = None,
    source: str = "user",
    system_context: Optional[Dict[str, Any]] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
) -> PerceptionInput:
    return PerceptionInput(
        thread_id=thread_id,
        conversation_id=conversation_id,
        user_message=message,
        history_messages=normalize_history_messages(history_messages),
        source=str(source or "user").strip().lower() or "user",
        system_context=dict(system_context or {}),
        attachments=attachments,
    )
