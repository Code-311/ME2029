from sqlalchemy.orm import Session
from app.models.profile import UserProfile
from app.models.config import ScoringWeight, FeatureFlag
from app.models.network import Company, PersonNode
from app.models.opportunity import Opportunity
from app.services.scoring import score_opportunity
from app.services.signals import generate_opportunity_signals
from app.services.scoring import DEFAULT_WEIGHTS


def seed_data(db: Session):
    if db.query(UserProfile).first():
        return
    profile = UserProfile(
        full_name="Alex Morgan",
        headline="Senior Operations, Governance & Security Leader",
        leadership_scale=9,
        skills="operations,governance,security,risk,transformation",
        preferred_geographies="London,Remote,New York",
        compensation_threshold=175000,
        industry_preferences="financial services,technology,critical infrastructure",
        target_time_horizon="6-12 months",
        networking_style="Warm intros + targeted direct outreach",
        visibility_preferences="Moderate cadence thought leadership"
    )
    db.add(profile)
    db.add_all([ScoringWeight(key=k, value=v) for k, v in DEFAULT_WEIGHTS.items()])
    db.add_all([FeatureFlag(key="use_llm_strategy", enabled=False)])
    c = Company(name="Contoso", industry="Technology")
    db.add(c)
    db.flush()
    db.add(PersonNode(full_name="Jamie Lee", role_title="VP Security", node_role_type="hiring_manager", influence_score=9, accessibility_score=6, relationship_strength=5, connection_path="ex-colleague", company_id=c.id))
    db.flush()
    opp = Opportunity(
        company="Contoso",
        role_title="Director, Security Operations",
        location="London",
        estimated_compensation=185000,
        source="seed",
        source_url="",
        description="Lead enterprise governance, security operations and resilience transformation.",
        status="new",
        company_id=c.id,
    )
    db.add(opp)
    db.flush()
    score_opportunity(db, opp, profile)
    db.commit()
    generate_opportunity_signals(db, profile)
