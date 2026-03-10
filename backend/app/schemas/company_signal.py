from datetime import datetime
from pydantic import BaseModel


class CompanySignalOut(BaseModel):
    id: int
    company_id: int
    signal_type: str
    severity: str
    title: str
    description: str
    source_url: str
    detected_at: datetime

    class Config:
        from_attributes = True
