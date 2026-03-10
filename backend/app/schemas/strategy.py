from pydantic import BaseModel


class ActionPlanOut(BaseModel):
    id: int
    period_type: str
    title: str
    details: str
    due_label: str
    completed: bool
    opportunity_id: int | None

    class Config:
        from_attributes = True
