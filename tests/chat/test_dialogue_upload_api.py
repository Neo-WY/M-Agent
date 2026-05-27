from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from tests.fixtures.app_factory import build_test_app
from tests.fixtures.sse_helpers import parse_sse_events


pytestmark = pytest.mark.integration


def _dialogue_bytes() -> bytes:
    payload = {
        "dialogue_id": "chat_upload-test_20260102_120000_000001",
        "user_id": "testuser",
        "participants": ["testuser", "Memory Assistant"],
        "meta": {
            "start_time": "2026-01-02T12:00:00Z",
            "end_time": "2026-01-02T12:00:05Z",
            "thread_id": "upload-thread",
            "version": 1,
        },
        "turns": [
            {"speaker": "testuser", "text": "ping", "turn_id": 0},
            {"speaker": "Memory Assistant", "text": "pong", "turn_id": 1},
        ],
    }
    return json.dumps(payload).encode("utf-8")


def _sse_types(response_text: str) -> list[str]:
    events = parse_sse_events(response_text.splitlines())
    return [str((item.get("data") or {}).get("type", "")) for item in events if isinstance(item.get("data"), dict)]


def test_upload_dialogues_sse() -> None:
    app = build_test_app(auth_enabled=False)
    with TestClient(app) as client:
        files = [("files", ("one.json", _dialogue_bytes(), "application/json"))]
        response = client.post(
            "/v1/chat/dialogues/upload",
            files=files,
            data={"rebuild_rag": "true", "index_rag": "true"},
        )
        assert response.status_code == 200
        types = _sse_types(response.text)
        assert "upload_started" in types
        assert "upload_completed" in types


def test_upload_rejects_invalid_json() -> None:
    app = build_test_app(auth_enabled=False)
    with TestClient(app) as client:
        files = [("files", ("bad.json", b"not-json", "application/json"))]
        response = client.post("/v1/chat/dialogues/upload", files=files)
        assert response.status_code == 200
        events = parse_sse_events(response.text.splitlines())
        started = next(
            item["data"]
            for item in events
            if isinstance(item.get("data"), dict) and item["data"].get("type") == "upload_started"
        )
        assert started["payload"]["rejected_count"] >= 1
