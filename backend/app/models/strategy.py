from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class ActionPlanItem(Base):
    __tablename__ = "action_plan_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    period_type: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    details: Mapped[str] = mapped_column(Text)
    due_label: Mapped[str] = mapped_column(String(60))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    opportunity_id: Mapped[int | None] = mapped_column(nullable=True)
