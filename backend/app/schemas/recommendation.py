from datetime import datetime
from pydantic import BaseModel


class RecommendationOut(BaseModel):
    id: int
    recommendation_type: str
    entity_type: str
    entity_id: int
    decision_score: float
    urgency: str
    confidence: float
    title: str
    reason_summary: str
    suggested_action: str
    created_at: datetime
    expires_at: datetime | None
    status: str

    class Config:
        from_attributes = True
