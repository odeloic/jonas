from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base

if TYPE_CHECKING:
    from models.grammar_rule import GrammarRule
    from models.vocabulary_item import VocabularyItem


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(20), default="IMAGE")
    filename: Mapped[str | None] = mapped_column(String(255))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")

    grammar_rules: Mapped[list[GrammarRule]] = relationship(back_populates="source")
    vocabulary_items: Mapped[list[VocabularyItem]] = relationship(back_populates="source")
