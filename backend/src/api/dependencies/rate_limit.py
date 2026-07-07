from fastapi import Request

from src.core.rate_limit import hit_rate_limit


def enforce_rate_limit(request: Request) -> None:
    client_host = request.client.host if request.client else "unknown"
    hit_rate_limit(client_host)
