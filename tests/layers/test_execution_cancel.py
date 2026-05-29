from __future__ import annotations

import threading
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from m_agent.layers.execution.core import ExecutionAgent
from m_agent.layers.execution.errors import ExecutionCancelledError


class _FakeStreamAgent:
    def __init__(self, steps: int = 3) -> None:
        self._steps = steps

    def stream(self, payload: Dict[str, Any], config: Dict[str, Any]):
        for i in range(self._steps):
            yield {"step": i, "messages": []}


def test_invoke_cooperative_raises_when_cancelled() -> None:
    agent = MagicMock(spec=ExecutionAgent)
    agent._invoke_cooperative = ExecutionAgent._invoke_cooperative.__get__(agent, ExecutionAgent)
    cancel = threading.Event()
    cancel.set()

    def _check() -> None:
        if cancel.is_set():
            raise ExecutionCancelledError("cancelled")

    with pytest.raises(ExecutionCancelledError):
        agent._invoke_cooperative(
            _FakeStreamAgent(),
            payload={"messages": []},
            config={},
            check_cancel=_check,
        )


def test_invoke_cooperative_streams_until_done() -> None:
    agent = MagicMock(spec=ExecutionAgent)
    agent._invoke_cooperative = ExecutionAgent._invoke_cooperative.__get__(agent, ExecutionAgent)
    result = agent._invoke_cooperative(
        _FakeStreamAgent(steps=2),
        payload={"messages": []},
        config={},
        check_cancel=lambda: False,
    )
    assert result == {"step": 1, "messages": []}
