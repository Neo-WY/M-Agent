"""Simple RAG implementation of :class:`EpisodicMemoryBackend`."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .rag_store import RagStore


def _truncate(text: str, limit: int = 1200) -> str:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


class SimpleRagEpisodicBackend:
    """Episodic backend: chunk dialogue on persist, cosine retrieval on recall."""

    def __init__(
        self,
        *,
        storage_dir: str = "data/rag/chat",
        workflow_id: str = "default",
        top_k: int = 5,
        embed_model: str = "hash",
        user_name: str = "User",
        assistant_name: str = "Memory Assistant",
    ) -> None:
        self.user_name = str(user_name or "User")
        self.assistant_name = str(assistant_name or "Memory Assistant")
        self.top_k = max(1, int(top_k))
        self.embed_model = str(embed_model or "hash")
        self.storage_dir = str(storage_dir or "data/rag/chat")
        self.workflow_id = str(workflow_id or "default").strip() or "default"
        self._store = RagStore(
            storage_dir=self.storage_dir,
            workflow_id=self.workflow_id,
            embed_model=self.embed_model,
        )

    @property
    def store(self) -> RagStore:
        return self._store

    @property
    def persistence_root(self) -> Path:
        """Directory holding ``chunks.jsonl`` and ``embeddings.npy``."""
        return Path(self._store.root)

    def describe_persistence(self) -> Dict[str, Any]:
        """Paths and counts for HTTP clients / debugging."""
        return {
            "kind": "rag",
            "storage_dir": str(self.storage_dir),
            "workflow_id": self.workflow_id,
            "persistence_root": str(self.persistence_root),
            "chunks_path": str(self._store.chunks_path),
            "embeddings_path": str(self._store.embeddings_path),
            "chunk_count": self._store.chunk_count,
            "embed_model": self.embed_model,
        }

    def _recall(self, question: str, *, thread_id: str) -> Dict[str, Any]:
        hits = self._store.search(question, top_k=self.top_k)
        if not hits:
            return {
                "answer": "",
                "evidence": [],
                "mode": "rag",
                "thread_id": thread_id,
                "hit": False,
            }
        parts = [_truncate(h.get("text", ""), limit=400) for h in hits if h.get("text")]
        answer = "\n\n".join(parts).strip()
        evidence = [
            {
                "text": h.get("text", ""),
                "score": h.get("score", 0.0),
                "source": h.get("source", ""),
            }
            for h in hits
        ]
        return {
            "answer": answer,
            "evidence": evidence,
            "mode": "rag",
            "thread_id": thread_id,
            "hit": bool(answer),
        }

    def shallow_recall(self, question: str, *, thread_id: str) -> Dict[str, Any]:
        return self._recall(question, thread_id=thread_id)

    def deep_recall(self, question: str, *, thread_id: str) -> Dict[str, Any]:
        return self._recall(question, thread_id=thread_id)

    def persist_round(
        self,
        *,
        thread_id: str,
        user_message: str,
        assistant_message: str,
        agent_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        meta = {"agent_result": agent_result} if agent_result else {}
        result = self._store.append_round(
            thread_id=thread_id,
            user_message=user_message,
            assistant_message=assistant_message,
            meta=meta,
        )
        result["success"] = True
        return result

    def persist_dialogue(
        self,
        *,
        thread_id: str,
        rounds: List[Dict[str, Any]],
        reason: str,
        source: str,
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        _ = (reason, source, progress_callback)
        result = self._store.append_dialogue(
            thread_id=thread_id,
            rounds=rounds,
            meta={"source": source, "reason": reason},
        )
        result["thread_id"] = thread_id
        return result

    def on_flush(
        self,
        *,
        thread_id: str,
        conversation_id: str,
        episode_notes: List[Dict[str, Any]],
    ) -> None:
        _ = (thread_id, conversation_id)
        self._store.merge_notes_on_last_chunk(episode_notes)


__all__ = ["SimpleRagEpisodicBackend"]
