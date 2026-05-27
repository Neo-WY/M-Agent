"""Map stimuli to transaction lines."""
from __future__ import annotations

from typing import Optional, Tuple

from m_agent.runtime.think_life.config import ThinkLifeConfig
from m_agent.runtime.think_life.contracts import (
    Stimulus,
    StimulusKind,
    TransactionKind,
    TransactionRecord,
    TransactionStatus,
)
from m_agent.runtime.think_life.transaction_registry import TransactionRegistry


class TransactionAttributor:
    def __init__(
        self,
        *,
        registry: TransactionRegistry,
        config: ThinkLifeConfig,
    ) -> None:
        self.registry = registry
        self.config = config

    def resolve(self, stimulus: Stimulus) -> Tuple[TransactionRecord, bool]:
        """Return (transaction, created_new)."""
        if stimulus.kind == StimulusKind.EXECUTION_FEEDBACK:
            return self._resolve_feedback(stimulus)
        if stimulus.kind == StimulusKind.HEARTBEAT:
            return self._resolve_heartbeat(stimulus)
        return self._resolve_user(stimulus)

    def _resolve_feedback(self, stimulus: Stimulus) -> Tuple[TransactionRecord, bool]:
        delegate_id = str(stimulus.delegate_id or stimulus.payload.get("delegate_id", "") or "").strip()
        if not delegate_id:
            raise ValueError("execution_feedback requires delegate_id")
        record = self.registry.find_by_delegate(delegate_id)
        if record is None:
            suggested = str(stimulus.suggested_transaction_id or "").strip()
            if suggested:
                record = self.registry.get(suggested)
            if record is None:
                raise ValueError(f"no transaction for delegate_id={delegate_id}")
        return record, False

    def _resolve_heartbeat(self, stimulus: Stimulus) -> Tuple[TransactionRecord, bool]:
        schedule_id = str(stimulus.schedule_id or stimulus.payload.get("schedule_id", "") or "").strip()
        priority = stimulus.priority_override or self.config.scheduler.default_heartbeat_priority
        from m_agent.runtime.think_life.contracts import TransactionCorrelation

        payload = stimulus.payload if isinstance(stimulus.payload, dict) else {}
        correlation = TransactionCorrelation(
            schedule_id=schedule_id or None,
            schedule_owner_id=str(payload.get("owner_id", "") or "").strip() or None,
            schedule_run_id=str(payload.get("run_id", "") or "").strip() or None,
        )
        record = self.registry.create(
            thread_id=stimulus.thread_id,
            kind=TransactionKind.SCHEDULE,
            priority=int(priority),
            correlation=correlation,
        )
        return record, True

    def _resolve_user(self, stimulus: Stimulus) -> Tuple[TransactionRecord, bool]:
        priority = stimulus.priority_override or self.config.scheduler.default_user_priority
        active = self.registry.get_active_user_transaction(stimulus.thread_id)
        if active is not None and active.status in {
            TransactionStatus.RUNNING,
            TransactionStatus.WAITING_EXECUTION,
            TransactionStatus.PENDING,
        }:
            return active, False
        record = self.registry.create(
            thread_id=stimulus.thread_id,
            kind=TransactionKind.USER_TASK,
            priority=int(priority),
        )
        self.registry.set_active_user_transaction(stimulus.thread_id, record.transaction_id)
        return record, True

    def priority_for(self, stimulus: Stimulus) -> int:
        if stimulus.priority_override is not None:
            return int(stimulus.priority_override)
        if stimulus.kind == StimulusKind.USER_MESSAGE:
            return self.config.scheduler.default_user_priority
        if stimulus.kind == StimulusKind.EXECUTION_FEEDBACK:
            return self.config.scheduler.default_feedback_priority
        return self.config.scheduler.default_heartbeat_priority
