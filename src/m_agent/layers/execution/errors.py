"""Execution-layer exceptions."""
from __future__ import annotations


class ExecutionCancelledError(Exception):
    """Raised when cooperative preemption cancels an in-flight execute loop."""

    def __init__(self, message: str = "execution cancelled") -> None:
        super().__init__(message)


__all__ = ["ExecutionCancelledError"]
