from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.network import Company, PersonNode
from app.models.opportunity import Opportunity
from app.models.signal import Signal
from app.models.company_signal import CompanySignal
from app.models.recommendation import Recommendation
from app.services.decision_engine import refresh_recommendations


def _db_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_refresh_recommendations_generates_ranked_actions():
    db = _db_session()
    company = Company(name='Contoso', industry='Tech')
    db.add(company)
    db.flush()
    opp = Opportunity(
        company='Contoso',
        role_title='Director Security',
        location='Remote',
        estimated_compensation=200000,
        source='mock',
        source_url='',
        description='desc',
        status='new',
        notes='',
        score_total=8.8,
        company_id=company.id,
        discovered_at=datetime.utcnow() - timedelta(days=25),
    )
    db.add(opp)
    db.flush()
    db.add(PersonNode(full_name='Jane Doe', role_title='VP Ops', node_role_type='EXEC', influence_score=8.0, accessibility_score=7.5, relationship_strength=7.0, connection_path='', notes_history='', company_id=company.id, opportunity_id=opp.id))
    db.add(Signal(signal_type='stale_opportunity', severity='warning', title='Stale', details='old', company_id=company.id, opportunity_id=opp.id))
    db.add(CompanySignal(company_id=company.id, signal_type='FUNDING', severity='success', title='Contoso raises funding', description='funding', source_url='https://example.com', detected_at=datetime.utcnow()))
    db.commit()

    created = refresh_recommendations(db)

    assert created >= 4
    recs = db.query(Recommendation).filter(Recommendation.status == 'open').all()
    types = {r.recommendation_type for r in recs}
    assert 'OPPORTUNITY_PRIORITY' in types
    assert 'FOLLOW_UP_ACTION' in types
    assert 'NETWORK_ACTION' in types
    assert 'WATCHLIST_ESCALATION' in types


def test_refresh_recommendations_expires_closed_opportunity_items():
    db = _db_session()
    company = Company(name='Northwind', industry='Tech')
    db.add(company)
    db.flush()
    opp = Opportunity(
        company='Northwind',
        role_title='VP Security',
        location='Remote',
        estimated_compensation=220000,
        source='mock',
        source_url='',
        description='desc',
        status='new',
        notes='',
        score_total=9.0,
        company_id=company.id,
        discovered_at=datetime.utcnow() - timedelta(days=10),
    )
    db.add(opp)
    db.commit()

    refresh_recommendations(db)
    assert db.query(Recommendation).filter(Recommendation.status == 'open').count() >= 1

    opp.status = 'closed'
    db.commit()
    refresh_recommendations(db)

    open_for_opp = (
        db.query(Recommendation)
        .filter(Recommendation.entity_type == 'opportunity')
        .filter(Recommendation.entity_id == opp.id)
        .filter(Recommendation.status == 'open')
        .count()
    )
    assert open_for_opp == 0
