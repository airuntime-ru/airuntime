from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.dependencies.auth import get_current_user
from src.db.models.project import Project
from src.db.models.secret import Secret
from src.db.models.user import User
from src.db.session import get_db
from src.services.secrets import encrypt_secret

router = APIRouter(prefix="/projects/{project_id}/secrets", tags=["secrets"])


class SecretCreateRequest(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=4000)


@router.post("")
def create_secret(
    project_id: str,
    payload: SecretCreateRequest,
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
    secret = Secret(project_id=project.id, key=payload.key, encrypted_value=encrypt_secret(payload.value))
    db.add(secret)
    db.commit()
    return {"id": str(secret.id), "key": secret.key}


@router.get("")
def list_secrets(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    rows = db.query(Secret).filter(Secret.project_id == project_id).all()
    return [{"id": str(row.id), "key": row.key, "created_at": row.created_at} for row in rows]


@router.delete("/{secret_id}")
def delete_secret(
    project_id: str,
    secret_id: UUID,
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
    secret = db.get(Secret, secret_id)
    if not secret or str(secret.project_id) != project_id:
        raise HTTPException(status_code=404, detail="Secret not found")
    db.delete(secret)
    db.commit()
    return {"status": "deleted"}
