from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.profile import UserProfile
from app.models.opportunity import Opportunity
from app.services.connectors import CSVConnector, NormalizedOpportunityInput
from app.services.ingestion import _upsert_opportunity


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_csv_normalization_header_aliases():
    content = "organization,title,city,salary,job_url,id\nAcme,Staff Security Lead,Remote,$190000,https://x/jobs/1,abc-1\n"
    payload = CSVConnector.parse_csv(content, source="csv")
    assert payload.fetched_count == 1
    item = payload.opportunities[0]
    assert item.company == "Acme"
    assert item.role_title == "Staff Security Lead"
    assert item.location == "Remote"
    assert item.external_id == "abc-1"
    assert item.estimated_compensation == 190000.0


def test_upsert_is_idempotent_for_same_external_id():
    db = _db()
    profile = UserProfile(full_name="A", headline="h", leadership_scale=5, skills="security", preferred_geographies="Remote", compensation_threshold=100000, industry_preferences="tech", target_time_horizon="12m", networking_style="balanced", visibility_preferences="high")
    db.add(profile)
    db.commit()

    item = NormalizedOpportunityInput(company="Acme", role_title="Role", source="company_careers", external_id="xyz")
    first = _upsert_opportunity(db, item, profile)
    second = _upsert_opportunity(db, item, profile)
    db.commit()

    assert first == "created"
    assert second == "updated"
    assert db.query(Opportunity).count() == 1
