from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, BigInteger, String, Text, DateTime, Integer, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class SystemSetting(Base):
    __tablename__ = "admin_system_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    setting_type: Mapped[str] = mapped_column(String(32))

    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    value_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    cron_expression: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Helpful for ad-hoc admin debugging in production
    __table_args__ = (Index("ix_admin_system_settings_key", "key"),)

