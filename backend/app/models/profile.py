from sqlalchemy import String, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    headline: Mapped[str] = mapped_column(String(200))
    leadership_scale: Mapped[int] = mapped_column(Integer)
    skills: Mapped[str] = mapped_column(Text)
    preferred_geographies: Mapped[str] = mapped_column(Text)
    compensation_threshold: Mapped[float] = mapped_column(Float)
    industry_preferences: Mapped[str] = mapped_column(Text)
    target_time_horizon: Mapped[str] = mapped_column(String(80))
    networking_style: Mapped[str] = mapped_column(String(120))
    visibility_preferences: Mapped[str] = mapped_column(String(120))
