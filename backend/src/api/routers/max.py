"""HTTP surface for the MAX integration: the bot webhook and the mini app's API.

Two different trust models live here, and conflating them would be the security bug of
this feature:

- ``/max/webhook/{secret}`` is called by MAX. Deliveries are not signed, so the secret in
  the path is the whole authentication; it must never appear in a log line or a response.
- ``/max/miniapp/*`` is called by the mini app running inside a customer's MAX client.
  Identity comes exclusively from the ``X-Max-Init-Data`` header, verified against the bot
  token. No endpoint here accepts a user id from the body.
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.models.max_platform import (
    LEAD_CONFIRMED,
    LEAD_DECLINED,
    LEAD_DONE,
    LEAD_NEW,
    SERVICE_LIVE,
    MaxLead,
    MaxOwner,
    MaxService,
)
from src.db.session import get_db
from src.services.max import bot as max_bot
from src.services.max.init_data import InitDataError, MaxLaunchContext, verify_init_data
from src.services.max.schema import ServiceConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/max", tags=["max"])

MAX_LEADS_PAGE = 50


# --------------------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------------------


def require_launch_context(
    x_max_init_data: str = Header(default="", alias="X-Max-Init-Data"),
) -> MaxLaunchContext:
    """The mini app's only identity. Everything downstream trusts this and nothing else."""
    try:
        return verify_init_data(
            x_max_init_data,
            settings.max_bot_token or "",
            max_age_seconds=settings.max_init_data_max_age_seconds,
        )
    except InitDataError as exc:
        # The message is safe to surface: it says the data is bad, never why the secret
        # did not match.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


# --------------------------------------------------------------------------------------
# Webhook
# --------------------------------------------------------------------------------------


@router.post("/webhook/{secret}", status_code=status.HTTP_200_OK)
async def max_webhook(secret: str, request: Request, db: Session = Depends(get_db)) -> dict:
    configured = (settings.max_webhook_secret or "").strip()
    if not configured or secret != configured:
        # 404 rather than 403: an unconfigured or mistyped endpoint should look like it
        # does not exist, not like a guarded door.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    try:
        update = await request.json()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed update"
        ) from None
    if not isinstance(update, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed update")

    try:
        await max_bot.handle_update(db, update)
    except Exception:
        # Always ack. MAX redelivers on non-2xx, and a handler bug would turn one broken
        # message into a retry storm against our own API.
        db.rollback()
        logger.exception("max_webhook_failed type=%s", update.get("update_type"))
    return {"ok": True}


# --------------------------------------------------------------------------------------
# Mini app: customer side
# --------------------------------------------------------------------------------------


class LeadRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=64)
    item_title: str = Field(default="", max_length=255)
    slot_label: str = Field(default="", max_length=64)
    customer_name: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=32)
    comment: str = Field(default="", max_length=1000)


def _service_payload(service: MaxService) -> dict:
    config = ServiceConfig.model_validate(json.loads(service.config_json))
    return {
        "slug": service.slug,
        "status": service.status,
        "config": config.model_dump(),
    }


@router.get("/miniapp/service/{slug}")
def get_service(
    slug: str,
    db: Session = Depends(get_db),
    _: MaxLaunchContext = Depends(require_launch_context),
) -> dict:
    """The storefront a customer sees. Verified launch data is required even though the
    content is public — it is what proves the request came from inside MAX."""
    service = db.query(MaxService).filter(MaxService.slug == slug).first()
    if service is None or service.status != SERVICE_LIVE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return _service_payload(service)


@router.post("/miniapp/lead", status_code=status.HTTP_201_CREATED)
def create_lead(
    payload: LeadRequest,
    db: Session = Depends(get_db),
    launch: MaxLaunchContext = Depends(require_launch_context),
) -> dict:
    service = db.query(MaxService).filter(MaxService.slug == payload.slug).first()
    if service is None or service.status != SERVICE_LIVE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    config = ServiceConfig.model_validate(json.loads(service.config_json))
    # The item and slot must be ones this storefront actually offers: otherwise the owner's
    # chat becomes a place anyone can write arbitrary text into.
    titles = {item.title for item in config.items}
    if payload.item_title and payload.item_title not in titles:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown item")
    if payload.slot_label and payload.slot_label not in set(config.slots):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown slot")

    lead = MaxLead(
        service_id=service.id,
        max_user_id=launch.user_id,
        customer_name=(payload.customer_name or launch.display_name)[:255],
        phone=payload.phone.strip() or None,
        item_title=payload.item_title[:255],
        slot_label=payload.slot_label[:64],
        comment=payload.comment.strip(),
        status=LEAD_NEW,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    # Delivery is best-effort on purpose: the lead is already durable, and a MAX API hiccup
    # must not turn into a 500 that makes the customer submit twice.
    try:
        max_bot.notify_owner_of_lead(db, lead)
    except Exception:
        logger.warning("max_lead_notify_failed lead_id=%s", lead.id, exc_info=True)

    return {
        "id": str(lead.id),
        "status": lead.status,
        "success_message": config.success_message,
    }


# --------------------------------------------------------------------------------------
# Mini app: owner side
# --------------------------------------------------------------------------------------


def _owner_or_404(db: Session, launch: MaxLaunchContext) -> MaxOwner:
    owner = db.query(MaxOwner).filter(MaxOwner.max_user_id == launch.user_id).first()
    if owner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner not found")
    return owner


@router.get("/miniapp/owner/overview")
def owner_overview(
    db: Session = Depends(get_db),
    launch: MaxLaunchContext = Depends(require_launch_context),
) -> dict:
    """Services plus their pending-lead counts — the owner's home screen in one request."""
    owner = db.query(MaxOwner).filter(MaxOwner.max_user_id == launch.user_id).first()
    if owner is None:
        # Not an error: someone who opened the mini app before ever writing to the bot.
        return {"owner": None, "services": []}

    services = (
        db.query(MaxService)
        .filter(MaxService.owner_id == owner.id)
        .order_by(MaxService.created_at.desc())
        .all()
    )
    service_ids = [service.id for service in services]
    new_counts: dict[uuid.UUID, int] = {}
    if service_ids:
        rows = (
            db.query(MaxLead.service_id, MaxLead.status)
            .filter(MaxLead.service_id.in_(service_ids), MaxLead.status == LEAD_NEW)
            .all()
        )
        for service_id, _status in rows:
            new_counts[service_id] = new_counts.get(service_id, 0) + 1

    return {
        "owner": {"name": owner.name, "username": owner.username},
        "services": [
            {
                **_service_payload(service),
                "link": settings.build_max_service_link(service.slug),
                "new_leads": new_counts.get(service.id, 0),
            }
            for service in services
        ],
    }


@router.get("/miniapp/owner/leads")
def owner_leads(
    slug: str | None = None,
    db: Session = Depends(get_db),
    launch: MaxLaunchContext = Depends(require_launch_context),
) -> dict:
    owner = _owner_or_404(db, launch)
    query = (
        db.query(MaxLead, MaxService.title, MaxService.slug)
        .join(MaxService, MaxService.id == MaxLead.service_id)
        .filter(MaxService.owner_id == owner.id)
    )
    if slug:
        query = query.filter(MaxService.slug == slug)
    rows = query.order_by(MaxLead.created_at.desc()).limit(MAX_LEADS_PAGE).all()

    return {
        "leads": [
            {
                "id": str(lead.id),
                "service_title": title,
                "service_slug": service_slug,
                "customer_name": lead.customer_name,
                "phone": lead.phone,
                "item_title": lead.item_title,
                "slot_label": lead.slot_label,
                "comment": lead.comment,
                "status": lead.status,
                "created_at": lead.created_at.isoformat() if lead.created_at else None,
            }
            for lead, title, service_slug in rows
        ]
    }


class LeadStatusRequest(BaseModel):
    status: str = Field(pattern=f"^({LEAD_CONFIRMED}|{LEAD_DECLINED}|{LEAD_DONE}|{LEAD_NEW})$")


@router.post("/miniapp/owner/leads/{lead_id}/status")
def set_lead_status(
    lead_id: uuid.UUID,
    payload: LeadStatusRequest,
    db: Session = Depends(get_db),
    launch: MaxLaunchContext = Depends(require_launch_context),
) -> dict:
    owner = _owner_or_404(db, launch)
    lead = (
        db.query(MaxLead)
        .join(MaxService, MaxService.id == MaxLead.service_id)
        .filter(MaxLead.id == lead_id, MaxService.owner_id == owner.id)
        .first()
    )
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    lead.status = payload.status
    db.commit()
    return {"id": str(lead.id), "status": lead.status}
