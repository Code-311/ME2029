from datetime import datetime, timedelta
from types import SimpleNamespace
from app.services.signals import generate_opportunity_signals


class FakeSignalQuery:
    def __init__(self, existing):
        self.existing = existing

    def filter(self, *_):
        return self

    def first(self):
        return self.existing[0] if self.existing else None


class FakeOppQuery:
    def __init__(self, opps):
        self.opps = opps

    def all(self):
        return self.opps


class FakeDB:
    def __init__(self):
        self.opps = [
            SimpleNamespace(id=1, status='new', company='Acme', role_title='Director', source='mock', estimated_compensation=100, score_total=8.1, discovered_at=datetime.utcnow() - timedelta(days=30), company_id=None)
        ]
        self.existing = []
        self.added = []

    def query(self, model):
        if model.__name__ == 'Opportunity':
            return FakeOppQuery(self.opps)
        return FakeSignalQuery(self.existing)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass


def test_generate_signals_creates_actionable_entries():
    db = FakeDB()
    profile = SimpleNamespace(compensation_threshold=120)
    count = generate_opportunity_signals(db, profile)
    types = {s.signal_type for s in db.added}
    assert count >= 3
    assert 'new_role_posted' in types
    assert 'comp_below_threshold' in types
    assert 'stale_opportunity' in types
