"""Chat flush episode payload aligns with LoCoMo segmentation pipeline when available."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from m_agent.chat.simple_chat_agent import ChatMemoryPersistence


class _FakeMemoryCore:
    workflow_id = "test_wf"
    memory_owner_name = "TestOwner"

    def __init__(self, root: Path) -> None:
        self.memory_root = root
        self.dialogues_dir = root / "dialogues"
        self.episodes_dir = root / "episodes"

    def load_from_episode_path(self, path: Path, progress_callback=None, **kwargs):  # noqa: ANN001
        _ = progress_callback
        return {"success": True}


def _fake_segmentation(dialogue_json: dict, prompts: dict, llm_model=None):  # noqa: ANN001
    did = dialogue_json["dialogue_id"]
    return {
        "episodes": [
            {
                "episode_id": "ep_001",
                "topic": "first",
                "dialogue_id": did,
                "turn_span": [0, 1],
                "segments": [
                    {
                        "segment_id": "seg_001",
                        "turn_span": [0, 1],
                        "topic": "seg topic",
                        "segment_memory_title": "Title",
                        "segment_memory_content": "Body",
                    }
                ],
            },
            {
                "episode_id": "ep_002",
                "topic": "second",
                "dialogue_id": did,
                "turn_span": [2, 3],
                "segments": [
                    {
                        "segment_id": "seg_001",
                        "turn_span": [2, 3],
                        "topic": "other",
                        "segment_memory_title": "T2",
                        "segment_memory_content": "C2",
                    }
                ],
            },
        ]
    }


@pytest.fixture
def persistence(tmp_path: Path) -> ChatMemoryPersistence:
    return ChatMemoryPersistence(_FakeMemoryCore(tmp_path))


def test_persist_writes_segmented_episodes_and_eligibility_per_episode(persistence: ChatMemoryPersistence) -> None:
    assert isinstance(persistence.memory_core, _FakeMemoryCore)

    with (
        patch(
            "m_agent.chat.simple_chat_agent.segment_dialogue_with_buffer",
            side_effect=_fake_segmentation,
        ),
        patch(
            "m_agent.chat.simple_chat_agent.load_prompts",
            return_value={"system_prompt": "x"},
        ),
    ):
        result = persistence.persist_dialogue(
            thread_id="t1",
            rounds=[
                {"user_message": "hi", "assistant_message": "hello"},
                {"user_message": "bye", "assistant_message": "see you"},
            ],
            reason="test",
            source="test",
        )

    assert result["success"] is True
    assert result["episode_build_source"] == "locomo_segmentation"
    assert result["episode_ids"] == ["ep_001", "ep_002"]

    episode_file = Path(result["episode_file"])
    assert episode_file.exists()
    ep_payload = json.loads(episode_file.read_text(encoding="utf-8"))
    assert len(ep_payload["episodes"]) == 2
    assert all("segments" in ep for ep in ep_payload["episodes"])

    elig_path = Path(result["eligibility_file"])
    elig = json.loads(elig_path.read_text(encoding="utf-8"))
    eids = {r["episode_id"] for r in elig["results"]}
    assert eids == {"ep_001", "ep_002"}


def test_persist_falls_back_when_prompts_missing(persistence: ChatMemoryPersistence) -> None:
    with patch("m_agent.chat.simple_chat_agent.load_prompts", return_value={}):
        result = persistence.persist_dialogue(
            thread_id="t2",
            rounds=[{"user_message": "a", "assistant_message": "b"}],
            reason="test",
            source="test",
        )

    assert result["success"] is True
    assert result["episode_build_source"] == "minimal_no_prompts"
    assert result["episode_ids"] == ["ep_001"]
    ep_payload = json.loads(Path(result["episode_file"]).read_text(encoding="utf-8"))
    assert len(ep_payload["episodes"]) == 1
    assert "segments" not in ep_payload["episodes"][0]
