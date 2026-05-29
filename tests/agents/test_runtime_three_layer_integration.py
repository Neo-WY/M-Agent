"""Integration test: ChatServiceRuntime drives three-layer chat + flush.

The point of this test is NOT to exercise the real LangChain agents — that
would require live LLM access. Instead it patches the chat-agent factory
with a fake stack whose ``chat()`` / ``on_flush()`` / ``snapshot_working_memory()``
behave according to the three-layer contract. This lets us assert the runtime
correctly:

* passes ``conversation_id`` into ``chat()``;
* skips its own session-side WM bookkeeping;
* sources ``thread_state.working_memory`` from the agent;
* bumps ``conversation_seq`` and calls ``on_flush()`` on a successful flush.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest

from m_agent.api.chat_api_runtime import ChatServiceRuntime
from m_agent.chat.working_memory import WorkingMemoryConfig


class _FakeMemoryPersistence:
    """Minimal stand-in for ChatMemoryPersistence.persist_dialogue."""

    def __init__(self) -> None:
        self.workflow_id = "fake-workflow"
        self.calls: List[Dict[str, Any]] = []

    def persist_dialogue(self, **kwargs: Any) -> Dict[str, Any]:
        self.calls.append(kwargs)
        return {
            "success": True,
            "workflow_id": self.workflow_id,
            "dialogue_id": f"dlg_{len(self.calls):03d}",
            "episode_id": "ep_001",
            "episode_ids": ["ep_001"],
            "round_count": len(kwargs.get("rounds", []) or []),
            "turn_count": len(kwargs.get("rounds", []) or []) * 2,
            "import_result": {"success": True},
            "error": None,
        }

    def persist_round(self, **_: Any) -> Dict[str, Any]:
        return {"success": True, "workflow_id": self.workflow_id}


class _FakeThreeLayerAgent:
    """A drop-in three-layer chat agent for runtime-level wiring tests."""

    arch_mode = "three_layer"

    def __init__(self) -> None:
        self.default_thread_id = "test-thread"
        self.user_name = "user"
        self.assistant_name = "assistant"
        self.persist_memory = True
        self.working_memory_config = WorkingMemoryConfig(enable=True)
        self.memory_persistence = _FakeMemoryPersistence()
        self.chat_calls: List[Dict[str, Any]] = []
        self.on_flush_calls: List[Dict[str, Any]] = []
        # Per-conversation WM snapshot (keyed by conversation_id)
        self._wm_by_conv: Dict[str, List[Dict[str, Any]]] = {}

    def chat(
        self,
        *,
        message: str,
        thread_id: str,
        history_messages: Optional[List[Dict[str, Any]]] = None,
        persist_memory: Optional[bool] = None,
        source: str = "user",
        system_context: Optional[Dict[str, Any]] = None,
        working_memory_prompt: Optional[str] = None,
        conversation_id: Optional[str] = None,
        event_emitter: Optional[Any] = None,
    ) -> Dict[str, Any]:
        # Record the call so the test can assert on payload shape.
        self.chat_calls.append(
            {
                "message": message,
                "thread_id": thread_id,
                "conversation_id": conversation_id,
                "source": source,
                "working_memory_prompt": working_memory_prompt,
                "event_emitter": event_emitter,
            }
        )

        # Simulate the thinking layer publishing intermediate events.
        if event_emitter is not None:
            event_emitter(
                "thinking_plan",
                {
                    "conversation_id": conversation_id,
                    "mode": "execute",
                    "instruction": message,
                    "reasoning": "fake reasoning",
                    "capability_hint": ["shallow_recall"],
                    "episode_note": None,
                },
            )
            event_emitter(
                "thinking_summary",
                {
                    "conversation_id": conversation_id,
                    "answer_excerpt": f"echo:{message}",
                    "episode_note": "fake summary",
                },
            )
            # bogus event types must be dropped by the runtime allow-list:
            event_emitter("bogus_event_type", {"foo": "bar"})

        # Simulate that the thinking layer wrote a WM entry on this turn.
        if conversation_id is not None:
            self._wm_by_conv.setdefault(conversation_id, []).append(
                {"kind": "recall", "tool": "shallow_recall", "summary": message}
            )

        agent_result = {
            "answer": f"echo:{message}",
            "controller_tool_count": 1,
            "controller_tool_names": ["shallow_recall"],
            "controller_tool_history": [
                {
                    "tool_name": "shallow_recall",
                    "params": {"question": message},
                    "result": {"answer": message},
                }
            ],
            "thinking_decision": {"mode": "execute", "instruction": message},
        }
        return {
            "success": True,
            "thread_id": thread_id,
            "conversation_id": conversation_id,
            "question": message,
            "answer": f"echo:{message}",
            "history_messages": list(history_messages or []),
            "agent_result": agent_result,
            "memory_write": {"success": False, "workflow_id": self.memory_persistence.workflow_id, "error": "persist disabled"},
        }

    def on_flush(self, *, conversation_id: str, thread_id: str) -> List[Dict[str, Any]]:
        self.on_flush_calls.append({"conversation_id": conversation_id, "thread_id": thread_id})
        notes = [{"note": f"flushed:{conversation_id}", "turn_meta": {}}]
        # Drop the WM for the conversation that's been flushed.
        self._wm_by_conv.pop(conversation_id, None)
        return notes

    def snapshot_working_memory(self, conversation_id: str) -> List[Dict[str, Any]]:
        return list(self._wm_by_conv.get(conversation_id, []))


@pytest.fixture()
def fake_runtime(tmp_path: Path) -> ChatServiceRuntime:
    """Boot a ChatServiceRuntime with the fake three-layer agent installed."""
    fake = _FakeThreeLayerAgent()
    with patch(
        "m_agent.api.chat_api_runtime.create_chat_agent",
        return_value=fake,
    ):
        rt = ChatServiceRuntime(
            config_path=tmp_path / "irrelevant.yaml",
            idle_flush_seconds=0,
            history_max_rounds=4,
            idle_scan_interval_seconds=60,
        )
    # Stash the fake on the runtime for the tests to reach into.
    rt._fake_agent = fake  # type: ignore[attr-defined]
    yield rt
    rt.shutdown()


def test_runtime_passes_conversation_id(fake_runtime: ChatServiceRuntime) -> None:
    rt = fake_runtime
    fake: _FakeThreeLayerAgent = rt._fake_agent  # type: ignore[attr-defined]
    assert getattr(rt.agent, "arch_mode", "") == "three_layer"

    rt.run_chat(message="hello", thread_id="alice")

    assert len(fake.chat_calls) == 1
    assert fake.chat_calls[0]["conversation_id"] == "alice::0"
    # Runtime never builds a WM prompt locally (WM is owned by ThinkingAgent state).
    assert fake.chat_calls[0]["working_memory_prompt"] is None


def test_thread_state_working_memory_comes_from_agent(
    fake_runtime: ChatServiceRuntime,
) -> None:
    rt = fake_runtime
    rt.run_chat(message="hello", thread_id="alice")
    state = rt.get_thread_state("alice")
    wm_payload = state["working_memory"]
    assert wm_payload["enabled"] is True
    assert wm_payload["stored_entries"] == 1
    assert wm_payload["entries"][0]["summary"] == "hello"
    assert state["conversation_id"] == "alice::0"


def test_runtime_session_has_no_legacy_wm_field(
    fake_runtime: ChatServiceRuntime,
) -> None:
    rt = fake_runtime
    rt.run_chat(message="hello", thread_id="alice")
    session = rt._threads["alice"]
    # WM ownership is fully in ThinkingAgent state, so the old session-side
    # field should not exist at all.
    assert not hasattr(session, "working_memory_entries")


def test_flush_thread_calls_agent_on_flush_and_bumps_conversation_seq(
    fake_runtime: ChatServiceRuntime,
) -> None:
    rt = fake_runtime
    fake: _FakeThreeLayerAgent = rt._fake_agent  # type: ignore[attr-defined]
    rt.run_chat(message="hello", thread_id="alice")
    assert rt._threads["alice"].conversation_seq == 0

    result = rt.flush_thread("alice", reason="manual_api")

    assert result["success"] is True
    assert rt._threads["alice"].conversation_seq == 1
    assert fake.on_flush_calls == [{"conversation_id": "alice::0", "thread_id": "alice"}]

    # After flush the working memory snapshot for the OLD conversation should
    # be gone; a new turn would start under conversation_id alice::1.
    rt.run_chat(message="world", thread_id="alice")
    assert fake.chat_calls[-1]["conversation_id"] == "alice::1"


def test_runtime_forwards_thinking_events_to_sse_and_drops_unknown_ones(
    fake_runtime: ChatServiceRuntime,
) -> None:
    """When the three-layer agent emits intermediate events through the
    injected ``event_emitter``, the runtime must (a) forward whitelisted
    events to the thread's SSE queue, and (b) silently drop event types
    that aren't part of the protocol allow-list."""
    rt = fake_runtime
    fake: _FakeThreeLayerAgent = rt._fake_agent  # type: ignore[attr-defined]

    captured: List[Dict[str, Any]] = []

    def _sink(thread_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        captured.append({"thread_id": thread_id, "event": event_type, "data": payload})

    rt.set_thread_event_sink(_sink)
    rt.run_chat(message="hi", thread_id="alice")

    # The fake recorded an emitter, proving the runtime injected one.
    assert fake.chat_calls[0]["event_emitter"] is not None

    posted_types = [ev["event"] for ev in captured]
    assert "thinking_plan" in posted_types
    assert "thinking_summary" in posted_types
    # The bogus event type the fake emitted MUST be silently dropped by the
    # runtime's allow-list.
    assert "bogus_event_type" not in posted_types

    plan_event = next(ev for ev in captured if ev["event"] == "thinking_plan")
    assert plan_event["data"]["mode"] == "execute"
    assert plan_event["data"]["conversation_id"] == "alice::0"
    # The runtime closure injects thread_id, even if the agent payload omitted it.
    assert plan_event["thread_id"] == "alice"
    assert plan_event["data"]["thread_id"] == "alice"


def test_idle_flush_noop_when_no_pending_rounds_does_not_call_on_flush(
    fake_runtime: ChatServiceRuntime,
) -> None:
    rt = fake_runtime
    fake: _FakeThreeLayerAgent = rt._fake_agent  # type: ignore[attr-defined]
    # Direct manual flush on a thread with no pending rounds = noop, no on_flush call.
    result = rt.flush_thread("nobody", reason="manual_api")
    assert result["status"] == "noop"
    assert fake.on_flush_calls == []
