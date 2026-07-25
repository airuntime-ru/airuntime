from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.core.config import settings

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@lru_cache(maxsize=1)
def get_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=lambda template_name: bool(template_name) and template_name.endswith(".html.j2"),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals.update(
        {
            "brand_name": "AIRuntime",
            "frontend_url": settings.resolved_frontend_url.rstrip("/"),
            "support_email": settings.support_email,
            "colors": {
                "page": "#F4F8FD",
                "surface": "#FFFFFF",
                "ink": "#081426",
                "muted": "#60728C",
                "border": "#D9E5F3",
                "accent": "#2F7CFF",
                "accent_soft": "#EAF2FF",
                "cyan": "#43D9FF",
                "success": "#1F8A5B",
                "success_soft": "#E8F7F0",
                "warning": "#B7791F",
                "warning_soft": "#FFF6E5",
                "error": "#C0392B",
                "error_soft": "#FDECEC",
            },
        }
    )
    return env


def logo_url() -> str:
    base = settings.resolved_frontend_url.rstrip("/")
    return f"{base}/brand/email-logo.png"


def logo_src(*, use_cid: bool = True) -> str:
    """Prefer CID when sending (offline-safe); absolute URL for local HTML preview."""
    if use_cid:
        return "cid:airuntime-logo"
    return logo_url()


def render_email(
    name: str, *, subject: str, use_cid: bool = True, **context: object
) -> tuple[str, str]:
    env = get_env()
    payload = {
        "subject": subject,
        "logo_src": logo_src(use_cid=use_cid),
        "logo_url": logo_url(),
        **context,
    }
    html = env.get_template(f"html/{name}.html.j2").render(**payload)
    plain = env.get_template(f"text/{name}.txt.j2").render(**payload)
    return plain.strip() + "\n", html
