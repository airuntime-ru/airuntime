from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.dependencies.auth import get_current_user
from src.db.models.credit_topup import CreditTopUp
from src.db.models.plan import Plan
from src.db.models.user import User
from src.db.session import get_db
from src.services.billing import request_topup

router = APIRouter(prefix="/billing", tags=["billing"])


class TopUpRequest(BaseModel):
    credits: int = Field(gt=0, le=10_000_000)


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
