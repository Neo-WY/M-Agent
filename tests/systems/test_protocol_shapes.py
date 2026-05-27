"""Protocol-shape tests for the five systems access points.

Each subsystem exposes one or two ``@runtime_checkable`` Protocols. These
tests guarantee that:

* the built-in default implementations satisfy ``isinstance(...,
  Protocol)`` (so they remain swap-compatible);
* a minimal user-supplied class with the right method signature also
  satisfies the Protocol (so external plug-ins don't need to inherit
  from anything);
* a class with the wrong shape is correctly rejected.

The tests run without touching the network or any LLM.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from m_agent.systems import (
    DefaultEpisodeRecorder,
    DefaultWMDisplay,
    DefaultWMReader,
    DefaultWMWriter,
    EpisodeRecorder,
    EpisodeRecorderNoop,
    EpisodicMemoryBackend,
    WMDisplay,
    WMReader,
    WMWriter,
)


# ---------------------------------------------------------------------------
# WMReader / WMWriter
# ---------------------------------------------------------------------------


def test_default_wm_reader_satisfies_protocol() -> None:
    from m_agent.chat.working_memory import WorkingMemoryConfig

    reader = DefaultWMReader(WorkingMemoryConfig())
    assert isinstance(reader, WMReader)


def test_default_wm_writer_satisfies_protocol() -> None:
    from m_agent.chat.working_memory import WorkingMemoryConfig

    writer = DefaultWMWriter(WorkingMemoryConfig())
    assert isinstance(writer, WMWriter)


def test_default_wm_display_satisfies_protocol() -> None:
    from m_agent.chat.working_memory import WorkingMemoryConfig

    display = DefaultWMDisplay(WorkingMemoryConfig())
    assert isinstance(display, WMDisplay)


def test_minimal_user_class_satisfies_wm_reader() -> None:
    class _Reader:
        def render(self, entries: List[Dict[str, Any]], *, language: str) -> str:  # noqa: ARG002
            return "stub"

    assert isinstance(_Reader(), WMReader)


def test_wm_reader_rejects_class_without_render() -> None:
    class _NotAReader:
        def something_else(self) -> str:
            return ""

    assert not isinstance(_NotAReader(), WMReader)


# ---------------------------------------------------------------------------
# EpisodeRecorder
# ---------------------------------------------------------------------------


def test_default_recorder_satisfies_protocol() -> None:
    assert isinstance(DefaultEpisodeRecorder(), EpisodeRecorder)


def test_noop_recorder_satisfies_protocol() -> None:
    assert isinstance(EpisodeRecorderNoop(), EpisodeRecorder)


def test_minimal_user_class_satisfies_recorder() -> None:
    class _Recorder:
        def append(
            self,
            buffer: List[Dict[str, Any]],
            *,
            note: Optional[str],
            turn_meta: Dict[str, Any],
        ) -> None:
            pass

        def flush(
            self,
            buffer: List[Dict[str, Any]],
            *,
            thread_id: str,
            conversation_id: str,
        ) -> None:
            pass

    assert isinstance(_Recorder(), EpisodeRecorder)


# ---------------------------------------------------------------------------
# EpisodicMemoryBackend — the new protocol introduced by the refactor
# ---------------------------------------------------------------------------


def test_minimal_episodic_backend_satisfies_protocol() -> None:
    """A user-supplied backend with the five required methods qualifies."""

    class _Backend:
        def shallow_recall(self, question: str, *, thread_id: str) -> Dict[str, Any]:  # noqa: ARG002
            return {"answer": question}

        def deep_recall(self, question: str, *, thread_id: str) -> Dict[str, Any]:  # noqa: ARG002
            return {"answer": question}

        def persist_round(
            self,
            *,
            thread_id: str,  # noqa: ARG002
            user_message: str,  # noqa: ARG002
            assistant_message: str,  # noqa: ARG002
            agent_result: Optional[Dict[str, Any]] = None,  # noqa: ARG002
        ) -> Dict[str, Any]:
            return {"success": True}

        def persist_dialogue(
            self,
            *,
            thread_id: str,  # noqa: ARG002
            rounds: List[Dict[str, Any]],  # noqa: ARG002
            reason: str,  # noqa: ARG002
            source: str,  # noqa: ARG002
            progress_callback: Optional[Any] = None,  # noqa: ARG002
        ) -> Dict[str, Any]:
            return {"success": True}

        def on_flush(
            self,
            *,
            thread_id: str,  # noqa: ARG002
            conversation_id: str,  # noqa: ARG002
            episode_notes: List[Dict[str, Any]],  # noqa: ARG002
        ) -> None:
            return None

    assert isinstance(_Backend(), EpisodicMemoryBackend)


def test_partial_episodic_backend_is_rejected() -> None:
    """A backend missing ``persist_dialogue`` (added in the refactor) fails the check."""

    class _PartialBackend:
        def shallow_recall(self, question: str, *, thread_id: str) -> Dict[str, Any]:  # noqa: ARG002
            return {}

        def deep_recall(self, question: str, *, thread_id: str) -> Dict[str, Any]:  # noqa: ARG002
            return {}

        def persist_round(
            self,
            *,
            thread_id: str,  # noqa: ARG002
            user_message: str,  # noqa: ARG002
            assistant_message: str,  # noqa: ARG002
            agent_result: Optional[Dict[str, Any]] = None,  # noqa: ARG002
        ) -> Dict[str, Any]:
            return {}

        # NOTE: deliberately no `persist_dialogue` / `on_flush`.

    assert not isinstance(_PartialBackend(), EpisodicMemoryBackend)
