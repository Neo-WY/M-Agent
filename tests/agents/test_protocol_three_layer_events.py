"""Whitelist coverage: three-layer streaming events must be on the SSE allow-list
and produce human-readable protocol-log summaries.

These tests are intentionally tiny: they guard against future regressions where
someone adds a new event in the thinking/execution layer without remembering to
also register it with the protocol layer, which would silently strip the event
from the FastAPI log channel (it would still reach the SSE stream, but
operators would lose tracing).
"""
from __future__ import annotations

import pytest

from m_agent.api.chat_api_protocol import (
    _PROTOCOL_SSE_EVENTS,
    _summarize_event_payload,
)


@pytest.mark.parametrize(
    "event_type",
    [
        "thinking_started",
        "thinking_plan",
        "execution_started",
        "execution_completed",
        "thinking_summary",
        "thinking_completed",
    ],
)
def test_three_layer_events_are_in_protocol_whitelist(event_type: str) -> None:
    assert event_type in _PROTOCOL_SSE_EVENTS, (
        f"{event_type!r} missing from _PROTOCOL_SSE_EVENTS; FastAPI protocol "
        f"channel will drop it from operator logs"
    )


def test_summarize_thinking_plan_returns_mode_and_instruction_excerpt() -> None:
    payload = {
        "mode": "execute",
        "instruction": "查询昨天的旅行计划安排",
        "capability_hint": ["deep_recall", "shallow_recall"],
    }
    text = _summarize_event_payload("thinking_plan", payload)
    assert "mode=execute" in text
    assert "查询昨天" in text


def test_summarize_execution_completed_includes_tool_call_count_and_flags() -> None:
    payload = {
        "tool_call_count": 3,
        "tool_names": ["deep_recall", "email_ask", "deep_recall"],
        "insufficient": False,
        "limit_reached": True,
    }
    text = _summarize_event_payload("execution_completed", payload)
    assert "tool_calls=3" in text
    assert "deep_recall" in text
    assert "limit_reached=True" in text


def test_summarize_thinking_summary_shows_answer_and_note_excerpt() -> None:
    payload = {
        "answer_excerpt": "昨天你讨论了旅行计划。",
        "episode_note": "topic: travel plans",
    }
    text = _summarize_event_payload("thinking_summary", payload)
    assert "昨天" in text
    assert "travel" in text


def test_summarize_thinking_completed_lists_phases() -> None:
    payload = {"executed": True, "phases": ["plan", "execute", "summarize"]}
    text = _summarize_event_payload("thinking_completed", payload)
    assert "executed=True" in text
    assert "plan,execute,summarize" in text
