"""Renew workspace ownership independently of a long-running task's DB transaction."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.db.models.workspace_lease import WorkspaceLease
from src.services.orchestration.cancellation import CancellationToken
from src.services.orchestration.workspace_isolation import AcquiredWorkspace

logger = logging.getLogger(__name__)


class WorkspaceLeaseLost(RuntimeError):
    pass


class LeaseHeartbeat:
    def __init__(
        self, db_factory: Callable[[], Session], cancellation: CancellationToken, ttl_seconds: int
    ) -> None:
        self.db_factory = db_factory
        self.cancellation = cancellation
        self.ttl_seconds = max(3, ttl_seconds)
        self.interval = min(30.0, self.ttl_seconds / 3)
        self._watched: dict[object, str] = {}
        self._stop = asyncio.Event()
        self._runner: asyncio.Task | None = None

    async def __aenter__(self):
        self._runner = asyncio.create_task(self._run())
        return self

    async def __aexit__(self, *_):
        self._stop.set()
        if self._runner is not None:
            await self._runner

    def watch(self, acquired: AcquiredWorkspace) -> None:
        if acquired.lease is not None:
            self._watched[acquired.lease.id] = acquired.lease.holder

    def unwatch(self, acquired: AcquiredWorkspace) -> None:
        if acquired.lease is not None:
            self._watched.pop(acquired.lease.id, None)

    def _renew(self, lease_id: object, holder: str) -> bool:
        db = self.db_factory()
        try:
            if db.get_bind().dialect.name == "postgresql":
                db.execute(text("SET LOCAL statement_timeout = '5s'"))
            now = datetime.now(UTC)
            changed = (
                db.query(WorkspaceLease)
                .filter(
                    WorkspaceLease.id == lease_id,
                    WorkspaceLease.holder == holder,
                    WorkspaceLease.released_at.is_(None),
                    WorkspaceLease.expires_at > now,
                )
                .update(
                    {WorkspaceLease.expires_at: now + timedelta(seconds=self.ttl_seconds)},
                    synchronize_session=False,
                )
            )
            db.commit()
            return changed == 1
        finally:
            db.close()

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
                break
            except TimeoutError:
                pass
            for lease_id, holder in list(self._watched.items()):
                try:
                    owned = await asyncio.to_thread(self._renew, lease_id, holder)
                except Exception:
                    logger.exception("Workspace heartbeat failed lease=%s", lease_id)
                    owned = False
                if not owned and lease_id in self._watched and not self._stop.is_set():
                    logger.error("Workspace ownership lost lease=%s", lease_id)
                    self.cancellation.cancel("Workspace lease lost; execution stopped")
                    return
