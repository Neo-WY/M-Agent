"""EpisodicMemorySystem dataclass + YAML loader."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from ..loader import (
    SystemsConfigError,
    load_system_yaml,
    materialize_plugin,
)
from .protocols import EpisodeRecorder, EpisodicMemoryBackend
from .query_module import EpisodeQueryModule
from .default import DefaultEpisodeRecorder, SimpleRagEpisodicBackend


@dataclass
class EpisodicMemorySystem:
    """Bundle of episodic-memory plug-in points + the query switch."""

    recorder: EpisodeRecorder
    backend: EpisodicMemoryBackend
    query_module: EpisodeQueryModule


def build_default_episodic_system(
    *,
    query_enabled: bool = True,
    user_name: str = "User",
    assistant_name: str = "Memory Assistant",
    storage_dir: str = "data/rag/chat",
    workflow_id: str = "default",
    top_k: int = 5,
    embed_model: str = "hash",
) -> EpisodicMemorySystem:
    """Built-in episodic system using :class:`SimpleRagEpisodicBackend`."""
    backend = SimpleRagEpisodicBackend(
        storage_dir=storage_dir,
        workflow_id=workflow_id,
        top_k=top_k,
        embed_model=embed_model,
        user_name=user_name,
        assistant_name=assistant_name,
    )
    return EpisodicMemorySystem(
        recorder=DefaultEpisodeRecorder(),
        backend=backend,
        query_module=EpisodeQueryModule(enabled=bool(query_enabled)),
    )


def load_episodic_system(
    source: Path | str | Mapping[str, Any],
) -> EpisodicMemorySystem:
    """Build a :class:`EpisodicMemorySystem` from YAML."""
    if isinstance(source, Mapping):
        payload: dict[str, Any] = dict(source)
    else:
        payload = load_system_yaml(Path(source), expected_kind="episodic")

    recorder_spec = payload.get("recorder")
    if recorder_spec is None:
        recorder: EpisodeRecorder = DefaultEpisodeRecorder()
    else:
        recorder = materialize_plugin("episodic.recorder", recorder_spec)

    backend_spec = payload.get("backend")
    if backend_spec is None:
        backend: EpisodicMemoryBackend = SimpleRagEpisodicBackend()
    else:
        backend = materialize_plugin("episodic.backend", backend_spec)

    query_section = payload.get("query") or {}
    if not isinstance(query_section, Mapping):
        raise SystemsConfigError(
            f"episodic.query must be a mapping (got {type(query_section).__name__})"
        )
    enabled = bool(query_section.get("enabled", True))
    capability_names_raw = query_section.get("capability_names")
    if capability_names_raw is None:
        query_module = EpisodeQueryModule(enabled=enabled)
    else:
        if not isinstance(capability_names_raw, (list, tuple)):
            raise SystemsConfigError(
                "episodic.query.capability_names must be a list of strings"
            )
        query_module = EpisodeQueryModule(
            enabled=enabled,
            capability_names=tuple(str(name) for name in capability_names_raw if str(name).strip()),
        )

    if not isinstance(recorder, EpisodeRecorder):
        raise SystemsConfigError(
            f"episodic.recorder must satisfy EpisodeRecorder protocol; got {type(recorder).__name__}"
        )
    if not isinstance(backend, EpisodicMemoryBackend):
        raise SystemsConfigError(
            f"episodic.backend must satisfy EpisodicMemoryBackend protocol; got {type(backend).__name__}"
        )

    return EpisodicMemorySystem(
        recorder=recorder,
        backend=backend,
        query_module=query_module,
    )


__all__ = [
    "EpisodicMemorySystem",
    "build_default_episodic_system",
    "load_episodic_system",
]
