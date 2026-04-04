from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base

if TYPE_CHECKING:
    from models.source import Source


class GrammarRule(Base):
    __tablename__ = "grammar_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic: Mapped[str] = mapped_column(String(255))
    rule_name: Mapped[str] = mapped_column(String(255))
    explanation: Mapped[str] = mapped_column(Text)
    pattern: Mapped[str | None] = mapped_column(Text)
    examples: Mapped[list[str]] = mapped_column(JSONB, default=list)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    source_type: Mapped[str] = mapped_column(String(20), default="INGESTED")
    verified: Mapped[bool] = mapped_column(default=False)
    cefr_level: Mapped[str | None] = mapped_column(String(3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped[Source] = relationship(back_populates="grammar_rules")
