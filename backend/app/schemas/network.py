from pydantic import BaseModel


class CompanyIn(BaseModel):
    name: str
    industry: str = ""


class CompanyOut(CompanyIn):
    id: int

    class Config:
        from_attributes = True


class PersonNodeIn(BaseModel):
    full_name: str
    role_title: str
    node_role_type: str
    influence_score: float
    accessibility_score: float
    relationship_strength: float
    connection_path: str = ""
    notes_history: str = ""
    company_id: int
    opportunity_id: int | None = None


class PersonNodeOut(PersonNodeIn):
    id: int

    class Config:
        from_attributes = True
