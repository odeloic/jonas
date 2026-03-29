from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class ProcessedImage(Base):
    __tablename__ = "processed_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_unique_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    file_id: Mapped[str] = mapped_column(String(255))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
