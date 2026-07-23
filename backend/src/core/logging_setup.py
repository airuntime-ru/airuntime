"""Console logging for the API and worker processes.

Both processes run under Docker with the default json-file log driver, so anything sent to
stdout/stderr is already captured by `docker compose logs` - there was just nothing calling
`logging` anywhere in the app to put a line there (confirmed by grep before this was added: the
only two callers of `logging.getLogger` in the whole backend were an Alembic migration script and
cloudflare_dns.py). Call configure_logging() once, as early as possible, from each process
entrypoint (src/main.py for the API, src/workers/deployment_worker.py for the worker).
"""

from __future__ import annotations

import logging

from src.core.config import settings

_CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    # uvicorn installs its own handlers on these loggers before app code runs; only bump the
    # level so LOG_LEVEL=DEBUG actually shows uvicorn's own request-cycle detail too.
    logging.getLogger("uvicorn").setLevel(level)
    logging.getLogger("uvicorn.error").setLevel(level)
    _CONFIGURED = True
