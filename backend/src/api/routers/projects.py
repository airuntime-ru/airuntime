import shutil
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.dependencies.auth import get_current_user
from src.api.dto.project import (
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)
from src.api.dto.project_logs import ProjectLogsResponse
from src.api.dto.project_runtime import ProjectRuntimeLimitsResponse
from src.db.models.chat import Chat
from src.db.models.project import Project
from src.db.models.user import User
from src.db.session import get_db
from src.services.docker_control_queue import submit_control_job
from src.services.project_intent import infer_project_type
from src.services.project_logs import read_project_logs
from src.services.project_runtime import (
    RunningProjectLimitError,
    count_running_projects,
    get_running_limit,
    start_project_runtime,
    stop_project_runtime,
)
from src.services.project_subdomain import assert_subdomain_available, normalize_deploy_subdomain
from src.services.system_settings import get_system_setting_number
from src.services.workspace import project_dir
from src.core.config import settings

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_response(project: Project) -> ProjectResponse:
    return ProjectResponse.from_project(project)


@router.get("", response_model=ProjectListResponse)
def list_projects(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectListResponse:
    base_query = db.query(Project).filter(Project.user_id == current_user.id)
    total = base_query.count()
    deployed_total = base_query.filter(Project.deployment_url.isnot(None)).count()
    rows = base_query.order_by(Project.created_at.desc()).offset(offset).limit(limit).all()
    return ProjectListResponse(
        items=[_to_response(project) for project in rows], total=total, deployed_total=deployed_total
    )


@router.post("", response_model=ProjectResponse)
def create_project(
    payload: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    max_projects = get_system_setting_number("max_projects_per_user")
    if max_projects is not None:
        existing_count = db.query(Project).filter(Project.user_id == current_user.id).count()
        if existing_count >= max_projects:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Достигнут лимит проектов на аккаунт ({max_projects}). "
                "Удалите неиспользуемый проект, чтобы создать новый.",
            )

    project_type = payload.type or infer_project_type(f"{payload.name}\n{payload.description}")
    project = Project(
        user_id=current_user.id,
        type=project_type,
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


@router.get("/runtime-limits", response_model=ProjectRuntimeLimitsResponse)
def get_runtime_limits(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ProjectRuntimeLimitsResponse:
    return ProjectRuntimeLimitsResponse(
        running=count_running_projects(db, current_user.id),
        max_running=get_running_limit(db, current_user.id),
    )


@router.post("/{project_id}/stop", response_model=ProjectResponse)
def stop_project(
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
    try:
        project = stop_project_runtime(db, project)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_response(project)


@router.post("/{project_id}/start", response_model=ProjectResponse)
def start_project(
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
    try:
        project = start_project_runtime(db, project)
    except RunningProjectLimitError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_response(project)


@router.get("/{project_id}/logs", response_model=ProjectLogsResponse)
def get_project_logs(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectLogsResponse:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return read_project_logs(db, project)


@router.delete("/{project_id}")
def delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    submit_control_job(action="cleanup", project_id=str(project.id))
    shutil.rmtree(project_dir(project.id), ignore_errors=True)
    db.delete(project)
    db.commit()
    return {"status": "deleted"}


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
