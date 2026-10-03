"""Durable RunEvent log + live in-process fan-out (spec section 19's event catalog). Every
event is persisted (RunEventRepository) BEFORE being handed to live subscribers, so a
reconnecting client can always replay everything after its last-seen `seq` from the database -
closing the exact gap the pre-existing chat SSE stream has (chat-stream-runtime.ts's
sessionStorage snapshot is a lossy, client-only substitute; there was no server-side record of
what a turn had sent at all - see that module's own audit note).

One process-wide `EventBus` instance (module-level singleton, same pattern as skills/base.py's
`registry`). Live fan-out is deliberately in-process only, not a distributed pub/sub - a single
backend process owns whichever SSE connections it's currently serving, and a reconnect after a
process restart or a request landing on a *different* backend replica falls back to DB replay
from `run_events`, which is what makes that an acceptable simplification rather than a gap: the
durable log is the source of truth, live fan-out is purely a latency optimization on top of it.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

from src.services.orchestration.repository import RunEventRepository

logger = logging.getLogger(__name__)

# The exact catalog from spec section 19 - chat.py's translation layer (chat.py wiring, section
# 26) maps these onto the existing {chunk}/{status:{phase,label,state}} SSE frame shape for
# backward compatibility; a native orchestration API (section 25) can send them as-is.
EVENT_TYPES = frozenset(
    {
        "run_created",
        "planning_started",
        "plan_created",
        "plan_revised",
        "task_ready",
        "task_started",
        "task_progress",
        "skill_started",
        "skill_completed",
        "capability_started",
        "task_validating",
        "task_completed",
        "task_repairing",
        "task_failed",
        # Per-task running total of what this run has cost, plus an APPROACHING warning as it
        # nears its ceiling - so spend is visible while the run is still going, not only after
        # it parks on an exhausted budget.
        "budget_updated",
        "waiting_for_secret",
        "waiting_for_user",
        "integration_started",
        "build_started",
        "build_completed",
        "build_failed",
        "deploy_started",
        "deploy_completed",
        "deploy_failed",
        "runtime_verification_started",
        "runtime_verification_completed",
        "runtime_verification_failed",
        "run_completed",
        "run_failed",
        "run_cancelled",
        "trace",
        "llm_call",
    }
)

TERMINAL_EVENT_TYPES = frozenset({"run_completed", "run_failed", "run_cancelled"})


class _RunSubscription:
    __slots__ = ("queue", "loop")

    def __init__(self) -> None:
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = None


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[_RunSubscription]] = {}

    def subscribe(self, run_id: str) -> _RunSubscription:
        sub = _RunSubscription()
        self._subscribers.setdefault(run_id, set()).add(sub)
        return sub

    def unsubscribe(self, run_id: str, sub: _RunSubscription) -> None:
        subs = self._subscribers.get(run_id)
        if not subs:
            return
        subs.discard(sub)
        if not subs:
            self._subscribers.pop(run_id, None)

    def publish(self, run_id: str, envelope: dict[str, Any]) -> None:
        for sub in tuple(self._subscribers.get(run_id, ())):
            if sub.loop is not None:
                sub.loop.call_soon_threadsafe(sub.queue.put_nowait, envelope)
            else:
                sub.queue.put_nowait(envelope)


_bus = EventBus()


@event.listens_for(Session, "after_commit")
def _publish_committed(db: Session) -> None:
    if db.in_nested_transaction():
        return
    for _, run_id, envelope in db.info.pop("orchestration_events", []):
        _bus.publish(run_id, envelope)


@event.listens_for(Session, "after_soft_rollback")
def _discard_rolled_back(db: Session, previous_transaction) -> None:
    def rolled_back(tx) -> bool:
        while tx is not None:
            if tx is previous_transaction:
                return True
            tx = tx.parent
        return False

    pending = db.info.get("orchestration_events", [])
    db.info["orchestration_events"] = [item for item in pending if not rolled_back(item[0])]


def get_event_bus() -> EventBus:
    return _bus


def emit(
    db: Session, *, run_id: object, event_type: str, payload: dict, task_id: object | None = None
) -> dict[str, Any]:
    """Persist THEN fan out - a subscriber only ever sees an event that's already durably
    stored, so replay-after-reconnect and live-tail can never disagree about what happened."""
    if event_type not in EVENT_TYPES:
        logger.warning("orchestration events_bus: emitting unrecognized event_type %r", event_type)
    repo = RunEventRepository(db)
    row = repo.append(
        run_id=run_id,
        task_id=task_id,
        event_type=event_type,
        payload_json=json.dumps(payload, default=str),
    )
    envelope = {
        "seq": row.seq,
        "event_type": event_type,
        "payload": payload,
        "task_id": str(task_id) if task_id else None,
    }
    transaction = db.get_nested_transaction() or db.get_transaction()
    db.info.setdefault("orchestration_events", []).append((transaction, str(run_id), envelope))
    return envelope


async def stream_events(
    db_factory: Callable[[], Session], run_id: str, *, after_seq: int = 0
) -> AsyncIterator[dict[str, Any]]:
    """Replay everything after `after_seq` from the durable log, then tail live events as
    they're published, until a terminal event type is seen or the caller stops iterating
    (client disconnect - same abandonment semantics chat.py's own SSE generator already has).

    Subscribes to the live bus BEFORE running the replay query (not after) - otherwise an event
    published in the window between "replay snapshot taken" and "live tail begins" would never
    be observed by either half (missed by the snapshot, missed by a subscription that did not
    exist yet) and would silently vanish. Subscribing first means that window's events land in
    `sub.queue` instead, and the `seq <= last_seq` check below simply skips whichever of them the
    replay already yielded - trading a small amount of harmless dedup work for never losing one.

    `db_factory` is a zero-arg callable returning a fresh Session for the one-off replay query -
    deliberately not a Session held for this generator's entire (potentially long) lifetime.
    """
    sub = _bus.subscribe(run_id)
    try:
        last_seq = after_seq
        db = db_factory()
        try:
            repo = RunEventRepository(db)
            for row in repo.list_since(run_id, after_seq=after_seq):
                last_seq = row.seq
                envelope = {
                    "seq": row.seq,
                    "event_type": row.event_type,
                    "payload": json.loads(row.payload_json),
                    "task_id": str(row.task_id) if row.task_id else None,
                }
                yield envelope
                if row.event_type in TERMINAL_EVENT_TYPES:
                    return
        finally:
            db.close()

        while True:
            try:
                await asyncio.wait_for(sub.queue.get(), timeout=1.0)
            except TimeoutError:
                pass
            # Replay in sequence from committed rows; also works across backend replicas.
            db = db_factory()
            try:
                rows = RunEventRepository(db).list_since(run_id, after_seq=last_seq)
                for row in rows:
                    last_seq = row.seq
                    yield {
                        "seq": row.seq,
                        "event_type": row.event_type,
                        "payload": json.loads(row.payload_json),
                        "task_id": str(row.task_id) if row.task_id else None,
                    }
                    if row.event_type in TERMINAL_EVENT_TYPES:
                        return
            finally:
                db.close()
    finally:
        _bus.unsubscribe(run_id, sub)
