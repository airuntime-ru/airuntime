"""Credit ledger: project name snapshot, pagination, and direction filter."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session
from tests.conftest import auth_tokens

from src.db.models.credit_ledger import CreditLedgerEntry
from src.db.models.project import Project
from src.db.models.user import User
from src.services.billing import list_ledger, record_usage


def _user(db: Session, email: str = "ledger@airuntime.dev") -> User:
    user = User(email=email, is_verified=True, credits_balance=10_000)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _project(db: Session, user: User, name: str = "Landing Studio") -> Project:
    project = Project(
        user_id=user.id,
        type="website",
        name=name,
        description="",
        status="created",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def test_record_usage_snapshots_project_name(db: Session):
    user = _user(db)
    project = _project(db, user, name="My Shop")

    record_usage(
        db,
        user,
        project_id=project.id,
        amount=250,
        project_name=project.name,
        provider="openai",
        model="gpt-5.6-terra",
        input_tokens=1_000,
        cached_input_tokens=100,
        cache_write_input_tokens=200,
        output_tokens=50,
        provider_cost_usd_micros=2_500,
    )
    db.commit()

    entry = db.query(CreditLedgerEntry).one()
    assert entry.amount == -250
    assert entry.reason == "chat_message"
    assert entry.project_id == project.id
    assert entry.project_name == "My Shop"
    assert entry.provider == "openai"
    assert entry.model == "gpt-5.6-terra"
    assert entry.input_tokens == 1_000
    assert entry.provider_cost_usd_micros == 2_500
    assert user.credits_balance == 9_750


def test_record_usage_loads_name_when_omitted(db: Session):
    user = _user(db, email="ledger-lookup@airuntime.dev")
    project = _project(db, user, name="Looked Up")

    record_usage(db, user, project_id=project.id, amount=100)
    db.commit()

    entry = db.query(CreditLedgerEntry).one()
    assert entry.project_name == "Looked Up"


def test_list_ledger_filters_and_paginates(db: Session):
    user = _user(db, email="ledger-page@airuntime.dev")
    project = _project(db, user)

    record_usage(db, user, project_id=project.id, amount=10, project_name=project.name)
    record_usage(db, user, project_id=project.id, amount=20, project_name=project.name)
    db.add(
        CreditLedgerEntry(
            user_id=user.id,
            amount=500,
            reason="topup",
            project_id=None,
            project_name=None,
        )
    )
    db.commit()

    all_rows, all_total = list_ledger(db, user, limit=10, offset=0, direction="all")
    assert all_total == 3
    assert len(all_rows) == 3

    debits, debit_total = list_ledger(db, user, limit=10, offset=0, direction="debit")
    assert debit_total == 2
    assert all(row.amount < 0 for row in debits)

    credits, credit_total = list_ledger(db, user, limit=10, offset=0, direction="credit")
    assert credit_total == 1
    assert credits[0].amount == 500

    page, page_total = list_ledger(db, user, limit=1, offset=1, direction="all")
    assert page_total == 3
    assert len(page) == 1


def test_billing_usage_api_pagination_and_project_name(client, db: Session):
    headers = auth_tokens(client, "ledger-api@airuntime.dev")
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    user_id = uuid.UUID(me.json()["id"])
    user = db.get(User, user_id)
    assert user is not None

    project = _project(db, user, name="API Project")
    for amount in (11, 22, 33):
        record_usage(db, user, project_id=project.id, amount=amount, project_name=project.name)
    db.add(
        CreditLedgerEntry(
            user_id=user.id,
            amount=1000,
            reason="topup",
        )
    )
    db.commit()

    listed = client.get("/api/v1/billing/usage?limit=2&offset=0&direction=debit", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["items"][0]["project_name"] == "API Project"
    assert body["items"][0]["amount"] < 0
    assert "project_id" in body["items"][0]
    assert body["items"][0]["cost_rub"] == abs(body["items"][0]["amount"]) / 100

    credits = client.get("/api/v1/billing/usage?direction=credit", headers=headers)
    assert credits.status_code == 200
    credit_body = credits.json()
    assert credit_body["total"] == 2, "top-up plus the signup grant"
    # Both rows are written inside one transaction, so Postgres stamps them with the same
    # now() and the id tiebreak is a random UUID - assert on content, not position.
    by_reason = {row["reason"]: row for row in credit_body["items"]}
    assert by_reason["topup"]["amount"] == 1000
    assert by_reason["topup"]["project_name"] is None
    assert by_reason["signup_grant"]["amount"] > 0

    bad = client.get("/api/v1/billing/usage?direction=sideways", headers=headers)
    assert bad.status_code == 422
