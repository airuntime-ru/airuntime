from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.dependencies.auth import get_current_user
from src.db.models.credit_ledger import CreditLedgerEntry
from src.db.models.credit_topup import CreditTopUp
from src.db.models.plan import Plan
from src.db.models.user import User
from src.db.session import get_db
from src.services.billing import list_ledger, request_topup, switch_plan, usage_credits_to_rub

router = APIRouter(prefix="/billing", tags=["billing"])

LedgerDirectionParam = Literal["all", "credit", "debit"]


class TopUpRequest(BaseModel):
    credits: int = Field(gt=0, le=10_000_000)


class SwitchPlanRequest(BaseModel):
    plan_id: str


def _plan_response(plan: Plan) -> dict:
    return {
        "id": str(plan.id),
        "key": plan.key,
        "name": plan.name,
        "description": plan.description,
        "monthly_credits": plan.monthly_credits,
        "max_concurrent_projects": plan.max_concurrent_projects,
        "price_rub": plan.price_rub,
    }


def _topup_response(invoice: CreditTopUp) -> dict:
    return {
        "id": str(invoice.id),
        "credits": invoice.credits,
        "amount_rub": invoice.amount_rub,
        "status": invoice.status,
        "created_at": invoice.created_at,
        "paid_at": invoice.paid_at,
    }


def _ledger_response(entry: CreditLedgerEntry) -> dict:
    cost_rub = float(usage_credits_to_rub(entry.amount)) if entry.reason == "chat_message" else None
    return {
        "id": str(entry.id),
        "amount": entry.amount,
        "reason": entry.reason,
        "project_id": str(entry.project_id) if entry.project_id else None,
        "project_name": entry.project_name,
        "provider": entry.provider,
        "model": entry.model,
        "input_tokens": entry.input_tokens,
        "cached_input_tokens": entry.cached_input_tokens,
        "cache_write_input_tokens": entry.cache_write_input_tokens,
        "output_tokens": entry.output_tokens,
        "provider_cost_usd": (
            entry.provider_cost_usd_micros / 1_000_000
            if entry.provider_cost_usd_micros is not None
            else None
        ),
        "cost_rub": cost_rub,
        "created_at": entry.created_at,
    }


@router.get("/plans")
def list_plans(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(Plan).filter(Plan.is_active.is_(True)).order_by(Plan.sort_order).all()
    return [_plan_response(row) for row in rows]


@router.get("/me")
def get_my_billing(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    plan = db.get(Plan, current_user.plan_id) if current_user.plan_id else None
    return {
        "credits_balance": current_user.credits_balance,
        "billing_period_start": current_user.billing_period_start,
        "billing_period_end": current_user.billing_period_end,
        "plan": _plan_response(plan) if plan else None,
    }


@router.post("/topups")
def create_topup(
    payload: TopUpRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    invoice = request_topup(db, current_user, payload.credits)
    return _topup_response(invoice)


@router.get("/topups")
def list_topups(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    rows = (
        db.query(CreditTopUp)
        .filter(CreditTopUp.user_id == current_user.id)
        .order_by(CreditTopUp.created_at.desc())
        .all()
    )
    return [_topup_response(row) for row in rows]


@router.post("/plan")
def change_plan(
    payload: SwitchPlanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    plan = db.query(Plan).filter(Plan.id == payload.plan_id, Plan.is_active.is_(True)).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Тариф не найден")
    if current_user.plan_id and str(current_user.plan_id) == payload.plan_id:
        raise HTTPException(status_code=400, detail="Этот тариф уже активен")
    switch_plan(db, current_user, plan)
    return {
        "credits_balance": current_user.credits_balance,
        "billing_period_start": current_user.billing_period_start,
        "billing_period_end": current_user.billing_period_end,
        "plan": _plan_response(plan),
    }


@router.get("/usage")
def get_usage_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    direction: LedgerDirectionParam = Query(default="all"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    rows, total = list_ledger(db, current_user, limit=limit, offset=offset, direction=direction)
    return {
        "items": [_ledger_response(row) for row in rows],
        "total": total,
    }
