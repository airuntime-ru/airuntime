from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class OrchestrationRunCreateRequest(BaseModel):
    chat_id: UUID
    content: str = Field(min_length=1, max_length=500_000)
    provider: str | None = None
    model: str | None = None


class OrchestrationRunResponse(BaseModel):
    id: UUID
    project_id: UUID
    chat_id: UUID
    status: str
    goal: str | None
    original_request: str | None
    complexity: str | None
    plan_version: int
    credits_used: int
    cancel_requested: bool
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class OrchestrationRunListResponse(BaseModel):
    items: list[OrchestrationRunResponse]
    total: int


class OrchestrationTaskResponse(BaseModel):
    id: UUID
    local_id: str
    title: str
    role: str
    execution_kind: str
    status: str
    attempt: int
    max_attempts: int
    error_code: str | None
    error_message: str | None

    model_config = {"from_attributes": True}


class OrchestrationRunDetailResponse(OrchestrationRunResponse):
    tasks: list[OrchestrationTaskResponse]
