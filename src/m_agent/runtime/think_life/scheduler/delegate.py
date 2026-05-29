"""Resolve Think-life delegate targets (one tool per delegate)."""
from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Tuple

from m_agent.layers.thinking.state import ThinkingDecision
from m_agent.runtime.think_life.scheduler.tool_runner import REPLY_TOOL_NAME, build_tool_input


def resolve_tool_name(
    decision: ThinkingDecision,
    *,
    enabled_tools: Sequence[str],
    for_user_reply: bool = False,
) -> Optional[str]:
    """Pick exactly one capability name for the next delegate, or None if invalid."""
    enabled = {str(n or "").strip() for n in enabled_tools if str(n or "").strip()}
    if not enabled:
        return None

    if for_user_reply:
        return REPLY_TOOL_NAME if REPLY_TOOL_NAME in enabled else None

    if str(decision.mode or "").strip().lower() != "execute":
        return None

    name = str(decision.tool_name or "").strip()
    if name and name in enabled:
        return name

    hints = decision.capability_hint or []
    if isinstance(hints, list):
        for item in hints:
            hint = str(item or "").strip()
            if hint in enabled:
                return hint

    return None


def plan_delegate(
    decision: ThinkingDecision,
    *,
    enabled_tools: Sequence[str],
    for_user_reply: bool = False,
    user_reply_text: Optional[str] = None,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Return (tool_name, tool_input) for one direct registry invoke, or None."""
    tool_name = resolve_tool_name(
        decision,
        enabled_tools=enabled_tools,
        for_user_reply=for_user_reply,
    )
    if not tool_name:
        return None
    tool_input = build_tool_input(
        tool_name,
        instruction=str(decision.instruction or "").strip(),
        user_reply_text=user_reply_text,
    )
    return tool_name, tool_input
