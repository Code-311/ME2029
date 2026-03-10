from datetime import datetime
from pydantic import BaseModel


class SignalOut(BaseModel):
    id: int
    signal_type: str
    severity: str
    title: str
    details: str
    company_id: int | None
    opportunity_id: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class JobRunOut(BaseModel):
    id: int
    job_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    processed_count: int
    summary: str

    class Config:
        from_attributes = True
