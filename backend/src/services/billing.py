from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.models.credit_ledger import CreditLedgerEntry
from src.db.models.credit_topup import CreditTopUp
from src.db.models.plan import Plan
from src.db.models.project import Project
from src.db.models.user import User
from src.services.email import send_branded_email
from src.services.email_templates import (
    credits_exhausted_email,
    credits_topup_paid_email,
    invoice_created_email,
    low_credits_email,
    period_ending_email,
    period_renewed_email,
)

BILLING_PERIOD_DAYS = 30
LOW_CREDITS_THRESHOLD_RATIO = 0.1
PERIOD_ENDING_WARNING_DAYS = 3
RUB_PER_1000_CREDITS = 10

LedgerDirection = str  # "all" | "credit" | "debit"


def _billing_url() -> str:
    return f"{settings.resolved_frontend_url.rstrip('/')}/app/settings"


def get_default_plan(db: Session) -> Plan | None:
    return db.query(Plan).filter(Plan.is_default.is_(True), Plan.is_active.is_(True)).first()


def assign_default_plan(db: Session, user: User) -> None:
    plan = get_default_plan(db)
    if not plan:
        return
    now = datetime.now(UTC)
    user.plan_id = plan.id
    user.credits_balance = plan.monthly_credits
    user.billing_period_start = now
    user.billing_period_end = now + timedelta(days=BILLING_PERIOD_DAYS)


def concurrent_project_limit(db: Session, user: User, *, fallback: int) -> int:
    if not user.plan_id:
        return fallback
    plan = db.get(Plan, user.plan_id)
    return plan.max_concurrent_projects if plan else fallback


def record_ledger_entry(
    db: Session,
    user: User,
    *,
    amount: int,
    reason: str,
    project_id: uuid.UUID | None = None,
    project_name: str | None = None,
) -> None:
    db.add(
        CreditLedgerEntry(
            user_id=user.id,
            project_id=project_id,
            project_name=project_name,
            amount=amount,
            reason=reason,
        )
    )


def record_usage(
    db: Session,
    user: User,
    *,
    project_id: uuid.UUID,
    amount: int,
    project_name: str | None = None,
) -> None:
    """Deduct credits for a chat turn and log it. `amount` is the positive cost - the balance
    change and ledger entry are both negative.

    `project_name` is snapshotted onto the ledger row so history stays readable after the
    project is deleted. If omitted, the current project name is loaded from the DB.
    """
    if project_name is None:
        project = db.get(Project, project_id)
        project_name = project.name if project else None
    user.credits_balance = max(0, user.credits_balance - amount)
    db.add(user)
    record_ledger_entry(
        db,
        user,
        amount=-amount,
        reason="chat_message",
        project_id=project_id,
        project_name=project_name,
    )


def switch_plan(db: Session, user: User, plan: Plan) -> User:
    """Self-service plan change. No proration since there's no real payment yet - switching
    immediately grants the new plan's monthly credits and starts a fresh billing period."""
    now = datetime.now(UTC)
    user.plan_id = plan.id
    user.credits_balance = plan.monthly_credits
    user.billing_period_start = now
    user.billing_period_end = now + timedelta(days=BILLING_PERIOD_DAYS)
    user.low_credits_notified_at = None
    user.period_ending_notified_at = None
    db.add(user)
    record_ledger_entry(db, user, amount=plan.monthly_credits, reason="plan_change")
    db.commit()
    db.refresh(user)
    return user


def list_ledger(
    db: Session,
    user: User,
    *,
    limit: int = 20,
    offset: int = 0,
    direction: LedgerDirection = "all",
) -> tuple[list[CreditLedgerEntry], int]:
    """Return a page of ledger entries plus the filtered total count.

    `direction`:
      - ``all`` — no amount filter
      - ``credit`` — начисления (amount > 0)
      - ``debit`` — списания (amount < 0)
    """
    query = db.query(CreditLedgerEntry).filter(CreditLedgerEntry.user_id == user.id)
    if direction == "credit":
        query = query.filter(CreditLedgerEntry.amount > 0)
    elif direction == "debit":
        query = query.filter(CreditLedgerEntry.amount < 0)
    total = query.count()
    rows = (
        query.order_by(CreditLedgerEntry.created_at.desc(), CreditLedgerEntry.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return rows, total


def list_recent_ledger(db: Session, user: User, *, limit: int = 50) -> list[CreditLedgerEntry]:
    """Backward-compatible helper; prefer :func:`list_ledger` for paginated UIs."""
    rows, _total = list_ledger(db, user, limit=limit, offset=0, direction="all")
    return rows


def credits_to_rub(credits: int) -> int:
    return max(1, math.ceil(credits * RUB_PER_1000_CREDITS / 1000))


def request_topup(db: Session, user: User, credits: int) -> CreditTopUp:
    invoice = CreditTopUp(
        user_id=user.id,
        credits=credits,
        amount_rub=credits_to_rub(credits),
        status="pending",
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    content = invoice_created_email(
        invoice_id=str(invoice.id),
        credits=invoice.credits,
        amount_rub=invoice.amount_rub,
        created_at=invoice.created_at,
        billing_url=_billing_url(),
    )
    send_branded_email(
        to=user.email, subject=content.subject, plain=content.plain, html=content.html
    )
    return invoice


def _renew_period_if_due(db: Session, user: User, *, now: datetime) -> None:
    if not user.billing_period_end or user.billing_period_end > now:
        return
    plan = db.get(Plan, user.plan_id) if user.plan_id else None
    if not plan:
        return
    user.credits_balance = plan.monthly_credits
    user.billing_period_start = now
    user.billing_period_end = now + timedelta(days=BILLING_PERIOD_DAYS)
    user.low_credits_notified_at = None
    user.period_ending_notified_at = None
    db.add(user)
    record_ledger_entry(db, user, amount=plan.monthly_credits, reason="period_renewal")
    content = period_renewed_email(
        plan_name=plan.name,
        credits=plan.monthly_credits,
        period_end=user.billing_period_end,
    )
    send_branded_email(
        to=user.email, subject=content.subject, plain=content.plain, html=content.html
    )


def _notify_low_credits_if_due(db: Session, user: User, *, now: datetime) -> None:
    if not user.plan_id:
        return
    plan = db.get(Plan, user.plan_id)
    if not plan or plan.monthly_credits <= 0:
        return
    threshold = plan.monthly_credits * LOW_CREDITS_THRESHOLD_RATIO
    if user.credits_balance > threshold:
        return
    if user.low_credits_notified_at is not None:
        return
    user.low_credits_notified_at = now
    db.add(user)
    if user.credits_balance <= 0:
        content = credits_exhausted_email(billing_url=_billing_url())
    else:
        content = low_credits_email(
            credits_balance=user.credits_balance, billing_url=_billing_url()
        )
    send_branded_email(
        to=user.email, subject=content.subject, plain=content.plain, html=content.html
    )


def _notify_period_ending_if_due(db: Session, user: User, *, now: datetime) -> None:
    if not user.billing_period_end:
        return
    days_left = (user.billing_period_end - now).total_seconds() / 86400
    if days_left > PERIOD_ENDING_WARNING_DAYS or days_left < 0:
        return
    if user.period_ending_notified_at is not None:
        return
    user.period_ending_notified_at = now
    db.add(user)
    plan = db.get(Plan, user.plan_id) if user.plan_id else None
    content = period_ending_email(
        period_end=user.billing_period_end,
        plan_name=plan.name if plan else None,
        credits_balance=user.credits_balance,
        billing_url=_billing_url(),
    )
    send_branded_email(
        to=user.email, subject=content.subject, plain=content.plain, html=content.html
    )


def _credit_paid_topups(db: Session, *, now: datetime) -> None:
    pending = (
        db.query(CreditTopUp)
        .filter(CreditTopUp.status == "paid", CreditTopUp.credited_at.is_(None))
        .all()
    )
    for invoice in pending:
        user = db.get(User, invoice.user_id)
        if not user:
            continue
        user.credits_balance += invoice.credits
        invoice.credited_at = now
        db.add(user)
        db.add(invoice)
        record_ledger_entry(db, user, amount=invoice.credits, reason="topup")
        content = credits_topup_paid_email(
            credits=invoice.credits,
            amount_rub=invoice.amount_rub,
            new_balance=user.credits_balance,
        )
        send_branded_email(
            to=user.email, subject=content.subject, plain=content.plain, html=content.html
        )


def run_billing_maintenance(db: Session) -> None:
    """Periodic sweep: renew expired billing periods, send low-credit/period-ending warnings,
    and credit any top-up invoices an admin has marked paid. Safe to call repeatedly."""
    now = datetime.now(UTC)
    _credit_paid_topups(db, now=now)
    users = db.query(User).filter(User.plan_id.isnot(None)).all()
    for user in users:
        _renew_period_if_due(db, user, now=now)
        _notify_low_credits_if_due(db, user, now=now)
        _notify_period_ending_if_due(db, user, now=now)
    db.commit()
