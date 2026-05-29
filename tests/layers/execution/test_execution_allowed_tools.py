"""ExecutionAgent allowed_tool_names (single-tool delegate)."""
from __future__ import annotations

from unittest.mock import MagicMock

from m_agent.layers.execution.contracts import ExecutionRequest
from m_agent.layers.execution.core import ExecutionAgent
from m_agent.layers.execution.model_provider import ModelProvider
from m_agent.systems.episodic import EpisodeQueryModule


def _agent() -> ExecutionAgent:
    provider = ModelProvider(
        model=MagicMock(),
        network_retry_attempts=1,
        network_retry_backoff_seconds=0.0,
    )
    return ExecutionAgent(
      model_provider=provider,
      enabled_capability_names=[
          "shallow_recall",
          "get_current_time",
          "reply_to_user",
      ],
      capability_descriptions={
          "shallow_recall": "recall",
          "get_current_time": "time",
          "reply_to_user": "reply",
      },
      tool_defaults={"__controller__": {"max_calls_per_turn": 12}},
      episode_query_module=EpisodeQueryModule(enabled=True),
  )


def test_enabled_names_for_request_subset() -> None:
    agent = _agent()
    names = agent._enabled_names_for_request(
        ExecutionRequest(
            instruction="x",
            thread_id="t1",
            allowed_tool_names=["get_current_time"],
        )
    )
    assert names == ["get_current_time"]


def test_tool_defaults_single_tool_delegate() -> None:
    agent = _agent()
    defaults = agent._tool_defaults_for_request(
        ExecutionRequest(instruction="x", thread_id="t1", allowed_tool_names=["shallow_recall"]),
        ["shallow_recall"],
    )
    assert defaults["__controller__"]["max_calls_per_turn"] == 1
    assert defaults["shallow_recall"]["max_calls_per_turn"] == 1
