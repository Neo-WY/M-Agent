"""Perception layer: normalize chat/runtime payloads for the thinking layer."""
from __future__ import annotations

from m_agent.layers.perception.assemble import (
    build_perception_input,
    normalize_history_messages,
)
from m_agent.layers.perception.contracts import PerceptionInput

__all__ = [
    "PerceptionInput",
    "build_perception_input",
    "normalize_history_messages",
]
