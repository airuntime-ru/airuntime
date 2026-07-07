from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.dependencies.auth import get_current_user
from src.api.dto.project import ProjectCreateRequest, ProjectResponse, ProjectUpdateRequest
from src.db.models.chat import Chat
from src.db.models.project import Project
from src.db.models.user import User
from src.db.session import get_db
from src.services.project_subdomain import assert_subdomain_available, normalize_deploy_subdomain

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_response(project: Project) -> ProjectResponse:
    return ProjectResponse.from_project(project)


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ProjectResponse]:
    rows = (
        db.query(Project)
        .filter(Project.user_id == current_user.id)
        .order_by(Project.created_at.desc())
        .all()
    )
    return [_to_response(project) for project in rows]


@router.post("", response_model=ProjectResponse)
def create_project(
    payload: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    project = Project(
        user_id=current_user.id,
        type=payload.type,
        name=payload.name,
        description=payload.description,
    )
    db.add(project)
    db.flush()
    db.add(Chat(project_id=project.id, title="Первый запуск"))
    db.commit()
    db.refresh(project)
    return _to_response(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: UUID,
    payload: ProjectUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if payload.name is not None:
        project.name = payload.name
    if payload.description is not None:
        project.description = payload.description
    if payload.status is not None:
        project.status = payload.status
    if "deploy_subdomain" in payload.model_fields_set:
        if project.type != "website":
            raise HTTPException(status_code=400, detail="Поддомен доступен только для сайтов")
        normalized = normalize_deploy_subdomain(payload.deploy_subdomain)
        if normalized:
            assert_subdomain_available(db, normalized, exclude_project_id=str(project.id))
        project.deploy_subdomain = normalized
    db.add(project)
    db.commit()
    db.refresh(project)
    return _to_response(project)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _to_response(project)
