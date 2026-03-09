from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.network import Company
from app.models.opportunity import Opportunity
from app.models.signal import Signal
from app.models.company_signal import CompanySignal
from app.services.company_intelligence import classify_signal_type, ingest_company_signals


def _db_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_classify_signal_type_funding():
    assert classify_signal_type('Contoso raises Series C funding', 'Round led by investors') == 'FUNDING'


def test_ingest_company_signal_creates_company_and_opportunity_signal():
    db = _db_session()
    company = Company(name='Contoso', industry='Tech')
    db.add(company)
    db.flush()
    db.add(Opportunity(company='Contoso', role_title='Director', location='Remote', estimated_compensation=1, source='x', source_url='', description='', status='new', notes='', company_id=company.id))
    db.commit()

    created = ingest_company_signals(db, [{
        'company': 'Contoso',
        'title': 'Contoso raises Series C funding',
        'description': 'Growth financing to scale internationally.',
        'source_url': 'https://news.example/funding',
    }])

    assert created == 1
    assert db.query(CompanySignal).count() == 1
    linked = db.query(Signal).all()
    assert len(linked) == 1
    assert linked[0].signal_type == 'company_funding'
