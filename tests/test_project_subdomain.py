import pytest
from fastapi import HTTPException

from src.db.models.project import Project
from src.services.project_subdomain import (
    default_deploy_subdomain,
    normalize_deploy_subdomain,
    resolve_deploy_subdomain,
)


def test_normalize_deploy_subdomain_accepts_valid_value():
    assert normalize_deploy_subdomain("My-Landing") == "my-landing"


def test_normalize_deploy_subdomain_rejects_invalid_value():
    with pytest.raises(HTTPException):
        normalize_deploy_subdomain("bad_sub")


def test_normalize_deploy_subdomain_rejects_reserved():
    with pytest.raises(HTTPException):
        normalize_deploy_subdomain("api")


def test_resolve_deploy_subdomain_prefers_custom_value():
    project = Project(
        id="11111111-1111-4111-8111-111111111111",
        user_id="22222222-2222-4222-8222-222222222222",
        type="website",
        name="NTCN",
        description="",
        deploy_subdomain="ntcn",
    )
    assert resolve_deploy_subdomain(project) == "ntcn"
    assert default_deploy_subdomain(project).startswith("ntcn-")
