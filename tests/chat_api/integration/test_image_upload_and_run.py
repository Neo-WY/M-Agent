from __future__ import annotations

import base64
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from m_agent.chat.simple_chat_agent import ChatMemoryPersistence
from tests.fixtures.app_factory import build_test_app
from tests.fixtures.payload_builders import run_payload


pytestmark = pytest.mark.integration


_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF9sAAAAASUVORK5CYII="
)


def _wait_run_completed(client: TestClient, run_id: str, *, timeout_seconds: float = 2.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/v1/chat/runs/{run_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload.get("status") in {"completed", "failed"}:
            return payload
        time.sleep(0.02)
    raise AssertionError(f"run not completed within {timeout_seconds} seconds: {run_id}")


def test_upload_image_endpoint_and_content_route(tmp_path: Path) -> None:
    app = build_test_app(auth_enabled=False)
    app.state.image_store.root_dir = tmp_path / "uploads"
    app.state.image_store.root_dir.mkdir(parents=True, exist_ok=True)
    app.state.image_store.captioner.caption_image = lambda _path: "a tiny test image"

    with TestClient(app) as client:
        upload = client.post(
            "/v1/chat/uploads/images",
            files={"file": ("tiny.png", _PNG_1X1, "image/png")},
            data={"thread_id": "demo-thread"},
        )
        assert upload.status_code == 200
        payload = upload.json()
        assert payload["blip_caption"] == "a tiny test image"
        assert payload["image_url"].startswith("/v1/chat/uploads/images/img_")

        content = client.get(payload["image_url"])
        assert content.status_code == 200
        assert content.headers["content-type"].startswith("image/png")
        assert content.content == _PNG_1X1


def test_create_run_with_attachment_keeps_blip_caption_in_thread_state() -> None:
    app = build_test_app(auth_enabled=False)

    with TestClient(app) as client:
        created = client.post(
            "/v1/chat/runs",
            json=run_payload(
                message="look at this",
                thread_id="image-thread",
                attachments=[
                    {
                        "upload_id": "img_test_1",
                        "image_url": "/v1/chat/uploads/images/img_test_1/content",
                        "image_file": "data/chat_uploads/anonymous/2026-05/img_test_1.png",
                        "blip_caption": "a cat sits on a sofa",
                    }
                ],
            ),
        )
        assert created.status_code == 201
        run_id = created.json()["run_id"]
        _wait_run_completed(client, run_id)

        state = client.get("/v1/chat/threads/image-thread/memory/state")
        assert state.status_code == 200
        payload = state.json()
        round_item = payload["history_rounds_data"][0]
        assert round_item["user_turn"]["text"] == "look at this"
        assert round_item["user_turn"]["blip_caption"] == "a cat sits on a sofa"
        assert round_item["user_turn"]["img_url"] == "/v1/chat/uploads/images/img_test_1/content"
        assert round_item["user_turn"]["img_file"].endswith("img_test_1.png")


def test_build_dialogue_payload_keeps_structured_turn_fields() -> None:
    agent = ChatMemoryPersistence.__new__(ChatMemoryPersistence)
    agent.user_name = "User"
    agent.assistant_name = "Assistant"

    rounds = [
        {
            "user_message": "look at this",
            "assistant_message": "nice photo",
            "user_at": datetime.now(timezone.utc),
            "assistant_at": datetime.now(timezone.utc),
            "agent_result": {"tool_call_count": 0},
            "user_turn": {
                "speaker": "User",
                "text": "look at this",
                "img_url": "/v1/chat/uploads/images/img_test/content",
                "img_file": "data/chat_uploads/user/2026-05/img_test.png",
                "blip_caption": "a cat sits on a sofa",
            },
            "assistant_turn": {
                "speaker": "Assistant",
                "text": "nice photo",
            },
        }
    ]

    payload = agent._build_dialogue_payload(
        dialogue_id="dlg_001",
        thread_id="demo-thread",
        rounds=rounds,
        source="chat_api_thread_flush",
    )

    assert payload["turns"][0]["blip_caption"] == "a cat sits on a sofa"
    assert payload["turns"][0]["img_url"] == "/v1/chat/uploads/images/img_test/content"
    assert payload["turns"][0]["img_file"].endswith("img_test.png")
