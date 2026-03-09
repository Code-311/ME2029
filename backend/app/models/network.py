from sqlalchemy import String, Float, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(140), unique=True)
    industry: Mapped[str] = mapped_column(String(120), default="")

    people = relationship("PersonNode", back_populates="company", cascade="all, delete-orphan")
    opportunities = relationship("Opportunity", back_populates="company_rel")


class PersonNode(Base):
    __tablename__ = "person_nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(140))
    role_title: Mapped[str] = mapped_column(String(120))
    node_role_type: Mapped[str] = mapped_column(String(80))
    influence_score: Mapped[float] = mapped_column(Float)
    accessibility_score: Mapped[float] = mapped_column(Float)
    relationship_strength: Mapped[float] = mapped_column(Float)
    connection_path: Mapped[str] = mapped_column(String(255), default="")
    notes_history: Mapped[str] = mapped_column(Text, default="")
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    opportunity_id: Mapped[int | None] = mapped_column(ForeignKey("opportunities.id"), nullable=True)

    company = relationship("Company", back_populates="people")
