import logging
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
from src.db.models.secret import Secret
from src.db.models.user import User
from src.db.session import get_db
from src.services.cloudflare_dns import delete_dns_for_website_deploy
from src.services.deployment_check import check_and_repair_deployment
from src.services.docker_control_queue import submit_control_job
from src.services.project_intent import infer_project_type, reconcile_type_with_workspace
from src.services.project_logs import read_project_logs
from src.services.project_runtime import (
    RunningProjectLimitError,
    count_running_projects,
    get_running_limit,
    start_project_runtime,
    stop_project_runtime,
)
from src.services.project_subdomain import (
    assert_subdomain_available,
    normalize_deploy_subdomain,
    resolve_deploy_subdomain,
)
from src.services.secrets import TELEGRAM_BOT_TOKEN_KEY
from src.services.system_settings import get_system_setting_number
from src.services.workspace import project_dir

logger = logging.getLogger(__name__)

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
        items=[_to_response(project) for project in rows],
        total=total,
        deployed_total=deployed_total,
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
        # Not gated on project.type - harmless to set for a bot-only project (simply unused at
        # deploy time), and gating it here was a recurring source of confusing 400s whenever
        # classification lagged behind what the project actually contains.
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


@router.post("/{project_id}/check-deployment")
def check_project_deployment(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Inspect the latest completed or failed deployment, repair code if an error is found,
    and queue a redeploy. Works for crashed/failed launches as well as live containers."""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return check_and_repair_deployment(db, project)


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
    # Best-effort, not best-effort-and-silent: deletion must not get stuck on a Docker/worker
    # hiccup (the user asked their data gone, a transient failure shouldn't trap them with an
    # undeletable project) - but a failure here means containers/volumes/images for this project
    # are about to become unrecoverable orphans the moment the row below is gone, so it has to be
    # logged loudly enough to find and clean up by hand.
    cleanup_result = submit_control_job(action="cleanup", project_id=str(project.id))
    if not cleanup_result or not cleanup_result.get("ok"):
        logger.warning(
            "Docker cleanup did not confirm success for deleted project %s (result=%r) - "
            "containers/volumes/images for this project may be orphaned; check `docker ps -a` / "
            "`docker images` for name/label airuntime.project_id=%s",
            project.id,
            cleanup_result,
            project.id,
        )
    workspace_path = project_dir(project.id)
    shutil.rmtree(workspace_path, ignore_errors=True)
    if workspace_path.exists():
        logger.warning("Workspace directory still present after rmtree: %s", workspace_path)
    # DNS cleanup must run while deploy_subdomain / resolved host are still available.
    # Best-effort: a Cloudflare outage must not leave the project undeletable.
    if project.type in ("website", "mixed"):
        subdomain = resolve_deploy_subdomain(project)
        try:
            delete_dns_for_website_deploy(subdomain)
        except Exception as dns_exc:  # noqa: BLE001 - never block project deletion on DNS
            logger.warning(
                "Cloudflare DNS cleanup failed for deleted project %s (subdomain=%s): %s",
                project.id,
                subdomain,
                dns_exc,
            )
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
    has_bot_secret = (
        db.query(Secret.id)
        .filter(Secret.project_id == project.id, Secret.key == TELEGRAM_BOT_TOKEN_KEY)
        .first()
        is not None
    )
    if reconcile_type_with_workspace(project, has_bot_secret=has_bot_secret):
        db.add(project)
        db.commit()
        db.refresh(project)
    return _to_response(project)
