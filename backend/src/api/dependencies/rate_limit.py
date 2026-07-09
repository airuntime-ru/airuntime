from fastapi import Request

from src.core.config import settings
from src.core.rate_limit import hit_rate_limit


def enforce_rate_limit(request: Request) -> None:
    if settings.debug:
        return
    client_host = request.client.host if request.client else "unknown"
    hit_rate_limit(client_host)
