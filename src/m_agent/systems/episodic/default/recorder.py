"""Default and no-op episode recorders.

These are the shipped implementations of
:class:`~m_agent.systems.episodic.protocols.EpisodeRecorder`. The default
implementation keeps notes in the conversation-scoped buffer and leaves
``flush`` to the runtime's drain path (which forwards the notes to the
:class:`EpisodicMemoryBackend.on_flush` hook). The no-op recorder is
useful for eval harnesses that want to disable episode capture entirely.
"""
from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


class DefaultEpisodeRecorder:
    """In-memory buffer; runtime drains via :py:meth:`drain` on flush.

    The recorder itself does NOT call into the long-term store directly —
    persistence belongs to the :class:`EpisodicMemoryBackend` so that the
    "what to record" policy stays decoupled from the "how to store it"
    policy. The runtime's flush path drains the buffer via
    :py:meth:`drain` and passes the result to
    :py:meth:`EpisodicMemoryBackend.on_flush`.
    """

    def append(
        self,
        buffer: List[Dict[str, Any]],
        *,
        note: Optional[str],
        turn_meta: Dict[str, Any],
    ) -> None:
        text = str(note or "").strip()
        if not text:
            return
        entry = {
            "note": text,
            "turn_meta": dict(turn_meta or {}),
        }
        buffer.append(entry)

    def flush(
        self,
        buffer: List[Dict[str, Any]],
        *,
        thread_id: str,
        conversation_id: str,
    ) -> None:
        # Drain is performed by the runtime so the contents survive long
        # enough to be handed to the backend's ``on_flush`` hook.
        return

    @staticmethod
    def drain(buffer: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        snapshot = copy.deepcopy(buffer)
        buffer.clear()
        return snapshot


class EpisodeRecorderNoop:
    """Disable episode recording entirely (still accepts the protocol calls)."""

    def append(
        self,
        buffer: List[Dict[str, Any]],
        *,
        note: Optional[str],
        turn_meta: Dict[str, Any],
    ) -> None:
        return

    def flush(
        self,
        buffer: List[Dict[str, Any]],
        *,
        thread_id: str,
        conversation_id: str,
    ) -> None:
        buffer.clear()


__all__ = ["DefaultEpisodeRecorder", "EpisodeRecorderNoop"]
