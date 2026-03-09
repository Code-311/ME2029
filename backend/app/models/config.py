from sqlalchemy import String, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class ScoringWeight(Base):
    __tablename__ = "scoring_weights"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    value: Mapped[float] = mapped_column(Float)


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
