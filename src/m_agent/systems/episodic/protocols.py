"""Plug-in protocols for the episodic-memory system.

The episodic-memory system has two access points:

* :class:`EpisodeRecorder` — buffers per-turn ``episode_note`` strings the
  thinking layer wants to keep. Drained on flush.
* :class:`EpisodicMemoryBackend` — actually answers recall questions and
  persists chat rounds. The default implementation
  (:class:`~m_agent.systems.episodic.default.rag_backend.SimpleRagEpisodicBackend`)
  uses a lightweight local RAG store; custom implementations swap backends
  without touching the chat stack.

A third "access point" — the on/off switch for the recall capabilities —
is a configuration knob rather than a Protocol; see
:class:`~m_agent.systems.episodic.query_module.EpisodeQueryModule`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class EpisodeRecorder(Protocol):
    """Pluggable interface for the per-conversation episode buffer."""

    def append(
        self,
        buffer: List[Dict[str, Any]],
        *,
        note: Optional[str],
        turn_meta: Dict[str, Any],
    ) -> None:
        ...

    def flush(
        self,
        buffer: List[Dict[str, Any]],
        *,
        thread_id: str,
        conversation_id: str,
    ) -> None:
        ...


@runtime_checkable
class EpisodicMemoryBackend(Protocol):
    """Answer recall queries + persist chat rounds for the chat stack.

    Implementations may be backed by a RAG store (default), an external
    service, or a stub. The contract is
    deliberately narrow so the chat stack does not depend on any single
    storage system.
    """

    def shallow_recall(self, question: str, *, thread_id: str) -> Dict[str, Any]:
        """Single-round episodic recall; return the raw recall payload."""
        ...

    def deep_recall(self, question: str, *, thread_id: str) -> Dict[str, Any]:
        """Multi-round episodic recall; return the raw recall payload."""
        ...

    def persist_round(
        self,
        *,
        thread_id: str,
        user_message: str,
        assistant_message: str,
        agent_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Persist one chat round (called per-turn)."""
        ...

    def persist_dialogue(
        self,
        *,
        thread_id: str,
        rounds: List[Dict[str, Any]],
        reason: str,
        source: str,
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Persist a multi-round dialogue (called on conversation flush)."""
        ...

    def on_flush(
        self,
        *,
        thread_id: str,
        conversation_id: str,
        episode_notes: List[Dict[str, Any]],
    ) -> None:
        """Hook called once per conversation flush with drained episode notes.

        The default implementation merges ``episode_notes`` into the
        already-persisted dialogue's ``meta.trace_summary.episode_notes``
        field. Stateless backends may treat this as a no-op.
        """
        ...


__all__ = ["EpisodeRecorder", "EpisodicMemoryBackend"]
