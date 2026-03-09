from pydantic import BaseModel


class ProfileBase(BaseModel):
    full_name: str
    headline: str
    leadership_scale: int
    skills: str
    preferred_geographies: str
    compensation_threshold: float
    industry_preferences: str
    target_time_horizon: str
    networking_style: str
    visibility_preferences: str


class ProfileOut(ProfileBase):
    id: int

    class Config:
        from_attributes = True
