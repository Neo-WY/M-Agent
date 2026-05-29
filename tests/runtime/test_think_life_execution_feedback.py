"""Tests for Think-life execution feedback + completion gate."""
from __future__ import annotations

from m_agent.runtime.think_life.contracts import (
    SceneActor,
    SceneEntry,
    SceneEntryType,
    Stimulus,
    StimulusKind,
    TransactionKind,
    TransactionRecord,
    TransactionStatus,
)
from m_agent.runtime.think_life.scheduler.execution_feedback import (
    build_feedback_user_message,
    feedback_summary_from_tool_history,
    looks_like_multi_step_request,
    premature_reply_block_reason,
)
from m_agent.runtime.think_life.scheduler.think_context import build_perception_for_stimulus
from m_agent.systems.scene.default.jsonl_store import SceneLogStore


def test_looks_like_multi_step_request() -> None:
    assert looks_like_multi_step_request("帮我安排一周，每天6点起床")
    assert not looks_like_multi_step_request("下午好")


def test_feedback_summary_uses_tool_count() -> None:
    history = [
        {
            "tool_name": "schedule_manage",
            "result": {
                "success": True,
                "action": "create",
                "count": 1,
                "answer": "已创建日程：2026-05-30 06:00 起床。",
            },
        }
    ]
    summary = feedback_summary_from_tool_history(history)
    assert "count=1" in summary
    assert "schedule_manage" in summary


def test_premature_reply_block_after_single_schedule_create() -> None:
    stimulus = Stimulus(
        stimulus_id="s1",
        thread_id="t1",
        kind=StimulusKind.EXECUTION_FEEDBACK,
        payload={
            "tool_history": [
                {
                    "tool_name": "schedule_manage",
                    "result": {"success": True, "action": "create", "count": 1, "answer": "已创建日程"},
                }
            ],
            "summary": "created whole week",
        },
        occurred_at="2026-01-01T00:00:01Z",
    )
    reason = premature_reply_block_reason(
        pending_user_request="安排一周，每天6点起床20点睡觉",
        stimulus=stimulus,
    )
    assert reason == "schedule_manage_created_only_one"


def test_feedback_user_message_does_not_claim_request_finished() -> None:
    text = build_feedback_user_message(
        pending_user_request="安排一周作息",
        tool_history=[
            {
                "tool_name": "schedule_manage",
                "result": {"count": 1, "answer": "已创建日程"},
            }
        ],
        llm_summary="整周已安排好",
    )
    assert "may still be incomplete" in text
    assert "Structured tool result" in text
    assert "count=1" in text
    assert "Tools finished for the current request" not in text


def test_build_perception_includes_structured_feedback() -> None:
    store = SceneLogStore(persist_enabled=False)
    store.append(
        "t1",
        SceneEntry(
            seq=0,
            occurred_at="2026-01-01T00:00:00Z",
            entry_type=SceneEntryType.UTTERANCE,
            actor=SceneActor.USER,
            text="安排一周每天6点起床",
        ),
    )
    txn = TransactionRecord(
        transaction_id="txn1",
        thread_id="t1",
        status=TransactionStatus.RUNNING,
        kind=TransactionKind.USER_TASK,
    )
    stimulus = Stimulus(
        stimulus_id="s1",
        thread_id="t1",
        kind=StimulusKind.EXECUTION_FEEDBACK,
        payload={
            "tool_history": [
                {"tool_name": "schedule_manage", "result": {"count": 1, "answer": "ok"}}
            ],
            "summary": "llm says done",
        },
        occurred_at="2026-01-01T00:00:01Z",
    )
    perception = build_perception_for_stimulus(
        transaction=txn,
        stimulus=stimulus,
        scene_reader=store,
        scene_context_max_entries=10,
    )
    fb = perception.system_context.get("execution_feedback") or {}
    assert fb.get("structured_summary")
    assert "count=1" in str(fb.get("structured_summary"))
    assert fb.get("multi_step_request") is True
