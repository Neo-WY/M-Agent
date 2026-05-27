"""Per-thread runtime busy/queue status for schedule lease and health endpoints."""

from __future__ import annotations



import threading

from dataclasses import dataclass

from typing import Any, Dict, Optional



from m_agent.api.chat_api_shared import _get_thread_lock, _now_iso





@dataclass

class ThreadRuntimeSnapshot:

    thread_id: str

    busy: bool = False

    busy_reason: str = "idle"

    busy_since_at: Optional[str] = None

    active_run_id: Optional[str] = None

    active_transaction_id: Optional[str] = None

    pending_stimuli: int = 0

    drainer_active: bool = False

    runtime_profile: str = "legacy"

    lock_holder: str = "none"

    runtime_phase: str = "ready"

    effective_depth: int = 0

    in_flight_stimulus_id: Optional[str] = None

    preempt_enabled: bool = False



    def to_dict(self) -> Dict[str, Any]:

        return {

            "thread_id": self.thread_id,

            "busy": self.busy,

            "busy_reason": self.busy_reason,

            "busy_since_at": self.busy_since_at,

            "active_run_id": self.active_run_id,

            "active_transaction_id": self.active_transaction_id,

            "pending_stimuli": self.pending_stimuli,

            "drainer_active": self.drainer_active,

            "runtime_profile": self.runtime_profile,

            "lock_holder": self.lock_holder,

            "runtime_phase": self.runtime_phase,

            "effective_depth": self.effective_depth,

            "in_flight_stimulus_id": self.in_flight_stimulus_id,

            "preempt_enabled": self.preempt_enabled,

        }





@dataclass

class _ThreadRuntimeState:

    explicit_busy: bool = False

    busy_reason: str = "idle"

    busy_since_at: Optional[str] = None

    active_run_id: Optional[str] = None

    active_transaction_id: Optional[str] = None

    pending_stimuli: int = 0

    drainer_active: bool = False

    cpu_holder_transaction_id: Optional[str] = None

    runtime_profile: Optional[str] = None

    preempt_enabled: bool = False





class ThreadRuntimeStatusRegistry:

    """Process-wide per-thread runtime flags."""



    def __init__(self) -> None:

        self._lock = threading.RLock()

        self._states: Dict[str, _ThreadRuntimeState] = {}



    def _state(self, thread_id: str) -> _ThreadRuntimeState:

        tid = str(thread_id or "").strip()

        if not tid:

            tid = "__default__"

        with self._lock:

            state = self._states.get(tid)

            if state is None:

                state = _ThreadRuntimeState()

                self._states[tid] = state

            return state



    def mark_busy(

        self,

        thread_id: str,

        *,

        reason: str,

        active_run_id: Optional[str] = None,

        active_transaction_id: Optional[str] = None,

    ) -> None:

        state = self._state(thread_id)

        with self._lock:

            state.explicit_busy = True

            state.busy_reason = str(reason or "busy").strip() or "busy"

            state.busy_since_at = _now_iso()

            if active_run_id is not None:

                state.active_run_id = active_run_id

            if active_transaction_id is not None:

                state.active_transaction_id = active_transaction_id



    def clear_busy(self, thread_id: str, *, reason: Optional[str] = None) -> None:

        state = self._state(thread_id)

        with self._lock:

            if reason is not None and state.busy_reason != reason:

                return

            state.explicit_busy = False

            state.busy_reason = "idle"

            state.busy_since_at = None

            state.active_run_id = None

            state.active_transaction_id = None



    def set_pending_stimuli(self, thread_id: str, count: int) -> None:

        state = self._state(thread_id)

        with self._lock:

            state.pending_stimuli = max(0, int(count))



    def set_drainer_active(self, thread_id: str, active: bool) -> None:

        state = self._state(thread_id)

        with self._lock:

            state.drainer_active = bool(active)



    def set_cpu_holder(self, thread_id: str, transaction_id: Optional[str]) -> None:

        state = self._state(thread_id)

        with self._lock:

            state.cpu_holder_transaction_id = str(transaction_id or "").strip() or None



    def set_runtime_profile(self, thread_id: str, profile: str) -> None:

        state = self._state(thread_id)

        with self._lock:

            state.runtime_profile = str(profile or "legacy").strip().lower() or "legacy"



    def set_preempt_enabled(self, thread_id: str, enabled: bool) -> None:

        state = self._state(thread_id)

        with self._lock:

            state.preempt_enabled = bool(enabled)



    def snapshot(

        self,

        thread_id: str,

        *,

        default_profile: str = "legacy",

    ) -> ThreadRuntimeSnapshot:

        tid = str(thread_id or "").strip()

        state = self._state(tid)

        thread_lock = _get_thread_lock(tid)

        lock_held = thread_lock.locked()



        with self._lock:

            profile = str(state.runtime_profile or default_profile or "legacy").strip().lower() or "legacy"

            pending = int(state.pending_stimuli)

            drainer_active = bool(state.drainer_active)

            cpu_txn = state.cpu_holder_transaction_id

            explicit = bool(state.explicit_busy)

            reason = state.busy_reason

            since_at = state.busy_since_at

            run_id = state.active_run_id

            active_txn = state.active_transaction_id or cpu_txn

            preempt_enabled = bool(state.preempt_enabled)



        if profile == "think_life":
            from m_agent.runtime.think_life.scheduler.cpu_state import (
                THREAD_CPU_STATE,
                compute_runtime_phase,
            )

            in_flight = THREAD_CPU_STATE.get_in_flight(tid)

            effective_depth, runtime_phase = compute_runtime_phase(

                inbox_pending=pending,

                in_flight=in_flight is not None,

            )

            in_flight_stimulus_id = in_flight.stimulus_id if in_flight else None

            if in_flight is not None:

                active_txn = in_flight.transaction_id or active_txn

            busy = effective_depth >= 2

            busy_reason = runtime_phase if runtime_phase != "ready" else "idle"

            lock_holder = "none"

            if lock_held:

                lock_holder = "thread_lock"

            return ThreadRuntimeSnapshot(

                thread_id=tid,

                busy=busy,

                busy_reason=busy_reason,

                busy_since_at=since_at if runtime_phase != "ready" else None,

                active_run_id=run_id,

                active_transaction_id=active_txn,

                pending_stimuli=pending,

                drainer_active=drainer_active,

                runtime_profile=profile,

                lock_holder=lock_holder,

                runtime_phase=runtime_phase,

                effective_depth=effective_depth,

                in_flight_stimulus_id=in_flight_stimulus_id,

                preempt_enabled=preempt_enabled,

            )



        busy = False

        busy_reason = "idle"

        lock_holder = "none"



        if lock_held:

            busy = True

            busy_reason = reason if explicit else "thread_lock"

            lock_holder = "thread_lock"

        elif cpu_txn:

            busy = True

            busy_reason = "think_life_cpu"

        elif explicit:

            busy = True

            busy_reason = reason or "busy"

        elif drainer_active and pending > 0:

            busy = True

            busy_reason = "drainer"



        if busy and not since_at and explicit:

            since_at = _now_iso()



        legacy_phase = "ready"

        if busy:

            legacy_phase = "busy"

        elif pending > 0 or cpu_txn:

            legacy_phase = "processing"



        return ThreadRuntimeSnapshot(

            thread_id=tid,

            busy=busy,

            busy_reason=busy_reason if busy else "idle",

            busy_since_at=since_at if busy else None,

            active_run_id=run_id,

            active_transaction_id=active_txn,

            pending_stimuli=pending,

            drainer_active=drainer_active,

            runtime_profile=profile,

            lock_holder=lock_holder,

            runtime_phase=legacy_phase,

            effective_depth=pending + (1 if cpu_txn else 0),

            in_flight_stimulus_id=None,

            preempt_enabled=preempt_enabled,

        )



    def is_busy(self, thread_id: str, *, default_profile: str = "legacy") -> bool:

        return self.snapshot(thread_id, default_profile=default_profile).busy



    def is_processing(self, thread_id: str, *, default_profile: str = "legacy") -> bool:

        snap = self.snapshot(thread_id, default_profile=default_profile)

        return snap.runtime_phase in {"processing", "busy"}





THREAD_RUNTIME_STATUS = ThreadRuntimeStatusRegistry()



__all__ = [

    "THREAD_RUNTIME_STATUS",

    "ThreadRuntimeSnapshot",

    "ThreadRuntimeStatusRegistry",

]

