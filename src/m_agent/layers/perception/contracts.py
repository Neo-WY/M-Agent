"""Perception-layer data contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class PerceptionInput:
    """Structured input handed to the thinking layer by the perception layer.

    Built from the raw HTTP request (or heartbeat-triggered schedule item) so
    the thinking layer never has to parse the original message format.
    """

    thread_id: str
    conversation_id: str
    user_message: str
    history_messages: List[Dict[str, str]] = field(default_factory=list)
    source: str = "user"
    system_context: Dict[str, Any] = field(default_factory=dict)
    attachments: Optional[List[Dict[str, Any]]] = None
