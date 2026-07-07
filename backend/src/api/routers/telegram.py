from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.dependencies.auth import get_current_user
from src.db.models.project import Project
from src.db.models.secret import Secret
from src.db.models.user import User
from src.db.session import get_db
from src.services.secrets import encrypt_secret

router = APIRouter(prefix="/projects/{project_id}/telegram", tags=["telegram"])


class TelegramTokenRequest(BaseModel):
    bot_token: str = Field(min_length=20, max_length=256)
    mode: str = Field(default="polling", pattern="^(polling|webhook)$")


@router.post("/token")
def save_bot_token(
    project_id: str,
    payload: TelegramTokenRequest,
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
    existing = (
        db.query(Secret)
        .filter(Secret.project_id == project.id, Secret.key == "TELEGRAM_BOT_TOKEN")
        .first()
    )
    if existing:
        existing.encrypted_value = encrypt_secret(payload.bot_token)
    else:
        db.add(
            Secret(
                project_id=project.id,
                key="TELEGRAM_BOT_TOKEN",
                encrypted_value=encrypt_secret(payload.bot_token),
            )
        )
    db.commit()
    return {"status": "saved", "mode": payload.mode}


@router.post("/start")
def start_bot(
    project_id: str,
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
    if project.type != "telegram_bot":
        raise HTTPException(status_code=400, detail="Project is not a Telegram bot")
    token = (
        db.query(Secret)
        .filter(Secret.project_id == project.id, Secret.key == "TELEGRAM_BOT_TOKEN")
        .first()
    )
    if not token:
        raise HTTPException(status_code=400, detail="Telegram bot token is not configured")
    project.status = "telegram_ready"
    db.commit()
    return {"status": "ready", "project_id": project_id, "runtime": "telegram-worker"}
