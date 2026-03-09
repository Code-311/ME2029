from datetime import datetime
from pydantic import BaseModel, Field


class OpportunityIn(BaseModel):
    company: str = Field(min_length=1)
    role_title: str = Field(min_length=1)
    location: str = Field(default="Unknown")
    estimated_compensation: float = Field(default=0, ge=0)
    source: str = Field(default="manual")
    source_url: str = ""
    description: str = ""
    status: str = "new"
    notes: str = ""


class OpportunityOut(OpportunityIn):
    id: int
    discovered_at: datetime
    score_total: float
    score_breakdown: dict
    score_explanation: str

    class Config:
        from_attributes = True
