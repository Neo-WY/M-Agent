from __future__ import annotations

from m_agent.chat.working_memory import (
    WorkingMemoryConfig,
    append_tool_history_to_working_memory,
    build_working_memory_api_payload,
    format_working_memory_prompt,
    normalize_working_memory_config,
    project_tool_call_to_entry,
)


def test_normalize_disabled() -> None:
    cfg = normalize_working_memory_config(False)
    assert cfg.enable is False


def test_project_recall() -> None:
    cfg = WorkingMemoryConfig()
    entry = project_tool_call_to_entry(
        {
            "tool_name": "deep_recall",
            "params": {"question": "What happened yesterday?"},
            "result": {"answer": "You discussed travel plans.", "tool_call_count": 3},
        },
        cfg,
    )
    assert entry is not None
    assert entry["kind"] == "recall"
    assert entry["mode"] == "deep_recall"
    assert "yesterday" in entry["question"]
    assert "travel" in entry["answer"]


def test_project_email_ask_caps_items() -> None:
    cfg = WorkingMemoryConfig(max_email_ask_items=3)
    idx = [
        {"message_id": f"id{i}", "thread_id": f"t{i}", "subject": f"S{i}"} for i in range(10)
    ]
    entry = project_tool_call_to_entry(
        {
            "tool_name": "email_ask",
            "params": {"keywords": "invoice", "mail_scope": "unread"},
            "result": {"evidence_index": idx},
        },
        cfg,
    )
    assert entry is not None
    assert len(entry["items"]) == 3


def test_append_and_trim_storage() -> None:
    cfg = WorkingMemoryConfig(max_stored_entries=5)
    entries: list = []
    for i in range(8):
        append_tool_history_to_working_memory(
            entries,
            [
                {
                    "tool_name": "shallow_recall",
                    "params": {"question": f"q{i}"},
                    "result": {"answer": f"a{i}"},
                }
            ],
            cfg,
        )
    assert len(entries) == 5
    assert entries[-1]["question"] == "q7"


def test_format_prompt_tail_inject_max() -> None:
    cfg = WorkingMemoryConfig(enable=True, inject_max_entries=2)
    entries = [
        project_tool_call_to_entry(
            {
                "tool_name": "shallow_recall",
                "params": {"question": f"q{i}"},
                "result": {"answer": f"a{i}"},
            },
            cfg,
        )
        for i in range(5)
    ]
    text = format_working_memory_prompt(entries, cfg, prompt_language="zh")
    assert "q4" in text
    assert "q2" not in text


def test_limit_entry() -> None:
    cfg = WorkingMemoryConfig()
    entry = project_tool_call_to_entry(
        {
            "tool_name": "email_read",
            "params": {},
            "result": {"limit_reached": True, "message": "blocked", "limit_scope": "tool"},
        },
        cfg,
    )
    assert entry is not None
    assert entry["kind"] == "limit"


def test_build_working_memory_api_payload_tail_and_cap() -> None:
    cfg = WorkingMemoryConfig(ui_expose_max_entries=3)
    entries = [{"kind": "recall", "n": i} for i in range(10)]
    payload = build_working_memory_api_payload(entries, cfg)
    assert payload["stored_entries"] == 10
    assert len(payload["entries"]) == 3
    assert payload["entries"][-1]["n"] == 9
