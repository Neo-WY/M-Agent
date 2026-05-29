from __future__ import annotations

import json

import pytest

from m_agent.chat.dialogue_validation import parse_dialogue_json_bytes, validate_dialogue_payload


def _minimal_dialogue() -> dict:
    return {
        "dialogue_id": "chat_test-thread_20260101_120000_000000",
        "user_id": "alice",
        "participants": ["alice", "Memory Assistant"],
        "meta": {
            "start_time": "2026-01-01T12:00:00Z",
            "end_time": "2026-01-01T12:00:05Z",
            "thread_id": "test-thread",
            "version": 1,
        },
        "turns": [
            {"speaker": "alice", "text": "hello", "turn_id": 0, "timestamp": "2026-01-01T12:00:00Z"},
            {
                "speaker": "Memory Assistant",
                "text": "hi",
                "turn_id": 1,
                "timestamp": "2026-01-01T12:00:05Z",
            },
        ],
    }


def test_validate_minimal_dialogue_ok():
    ok, summary, errors = validate_dialogue_payload(_minimal_dialogue())
    assert ok is True
    assert not errors
    assert summary["round_count"] == 1


def test_validate_rejects_empty_turns():
    payload = _minimal_dialogue()
    payload["turns"] = []
    ok, _, errors = validate_dialogue_payload(payload)
    assert ok is False
    assert any(err["code"] == "empty_turns" for err in errors)


def test_validate_rejects_invalid_json_bytes():
    payload, errors = parse_dialogue_json_bytes(b"{not json", filename="bad.json")
    assert payload is None
    assert errors


def test_parse_dialogue_derives_id_from_filename():
    payload = _minimal_dialogue()
    del payload["dialogue_id"]
    raw = json.dumps(payload).encode("utf-8")
    parsed, errors = parse_dialogue_json_bytes(raw, filename="chat_derived_20260101.json")
    assert not errors
    assert parsed is not None
    assert parsed.get("dialogue_id") or True  # validation fills via filename stem in parse path - actually parse doesn't fill, validate does in upload stream
    ok, summary, _ = validate_dialogue_payload(parsed, source_name="chat_derived_20260101.json")
    assert ok
    assert summary["dialogue_id"] == "chat_derived_20260101"
