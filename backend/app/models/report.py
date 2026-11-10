from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.user import User


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    urgency_level: Mapped[str | None] = mapped_column(String, nullable=True)
    flood_type: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    ai_summary: Mapped[str | None] = mapped_column(String, nullable=True)
    image_classification: Mapped[dict[str, str | float] | None] = mapped_column(JSON, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    post: Mapped["Post"] = relationship(back_populates="reports")
    user: Mapped["User"] = relationship(back_populates="reports")
