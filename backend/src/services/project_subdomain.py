"""Project public subdomain helpers."""

from __future__ import annotations

import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.models.project import Project

SUBDOMAIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,46}[a-z0-9])?$")
RESERVED_SUBDOMAINS = frozenset(
    {
        "www",
        "api",
        "admin",
        "mail",
        "s3",
        "s3-console",
        "traefik",
        "frontend",
        "backend",
        "worker",
        "postgres",
        "redis",
        "minio",
    }
)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    return slug or "project"


def normalize_deploy_subdomain(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    if not SUBDOMAIN_RE.fullmatch(cleaned):
        raise HTTPException(
            status_code=400,
            detail="Поддомен: только латиница, цифры и дефис, от 3 до 48 символов",
        )
    if cleaned in RESERVED_SUBDOMAINS:
        raise HTTPException(status_code=400, detail="Этот поддомен зарезервирован")
    return cleaned


def default_deploy_subdomain(project: Project) -> str:
    return f"{slugify(project.name)}-{str(project.id)[:8]}"


def resolve_deploy_subdomain(project: Project) -> str:
    return project.deploy_subdomain or default_deploy_subdomain(project)


def planned_public_url(project: Project) -> str | None:
    if project.type != "website":
        return None
    return settings.build_project_url(resolve_deploy_subdomain(project))


def assert_subdomain_available(
    db: Session, subdomain: str, *, exclude_project_id: str | None = None
) -> None:
    query = db.query(Project).filter(Project.deploy_subdomain == subdomain)
    if exclude_project_id:
        query = query.filter(Project.id != exclude_project_id)
    if query.first():
        raise HTTPException(status_code=409, detail="Этот поддомен уже занят")
