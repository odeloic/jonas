from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class LearnerProfile(Base):
    __tablename__ = "learner_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_chat_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    streak_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_active_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    xp: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cefr_estimate: Mapped[str] = mapped_column(String(3), default="B1", server_default="B1")
    weak_topics: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
