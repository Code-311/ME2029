from datetime import datetime
from sqlalchemy import String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(String(120))
    role_title: Mapped[str] = mapped_column(String(160))
    location: Mapped[str] = mapped_column(String(120))
    estimated_compensation: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(80))
    source_url: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(80), default="new")
    notes: Mapped[str] = mapped_column(Text, default="")
    score_total: Mapped[float] = mapped_column(Float, default=0)
    score_breakdown: Mapped[str] = mapped_column(Text, default="{}")
    score_explanation: Mapped[str] = mapped_column(Text, default="")
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)

    company_rel = relationship("Company", back_populates="opportunities")
