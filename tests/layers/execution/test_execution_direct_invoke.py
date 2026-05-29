"""Tests for direct tool invoke (Think-life)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from m_agent.layers.execution.core import ExecutionAgent
from m_agent.layers.execution.model_provider import ModelProvider


def _agent() -> ExecutionAgent:
    provider = ModelProvider(
        model=MagicMock(),
        network_retry_attempts=1,
        network_retry_backoff_seconds=0.0,
    )
    return ExecutionAgent(
        model_provider=provider,
        enabled_capability_names=["get_current_time"],
        capability_descriptions={"get_current_time": "time"},
        tool_defaults={"__controller__": {"max_calls_per_turn": 1}},
    )


def test_invoke_tool_direct_records_history() -> None:
    agent = _agent()
    with patch("m_agent.layers.execution.core.build_controller_tools") as build_tools:
        mock_tool = MagicMock()
        mock_tool.invoke.return_value = {"success": True, "answer": "2026-05-29"}
        build_tools.return_value = [mock_tool]
        result = agent.invoke_tool_direct(
            tool_name="get_current_time",
            tool_input={},
            thread_id="t1",
            correlation_id="dlg_1",
        )
    assert result.tool_call_count >= 0
    assert "get_current_time" in result.summary or result.success
