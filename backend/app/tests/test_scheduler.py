from types import SimpleNamespace
from app.jobs.scheduler import _record_job_end


class FakeDB:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def test_record_job_end_sets_fields():
    db = FakeDB()
    run = SimpleNamespace(status='running', processed_count=0, summary='', finished_at=None)
    _record_job_end(db, run, 'success', 5, 'done')
    assert run.status == 'success'
    assert run.processed_count == 5
    assert run.summary == 'done'
    assert run.finished_at is not None
    assert db.commits == 1
