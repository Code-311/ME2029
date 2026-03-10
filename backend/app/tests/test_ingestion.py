from app.services.ingestion import _normalize_row


class FakeOpp:
    def __init__(self, ingestion_key, **kwargs):
        self.ingestion_key = ingestion_key
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_normalize_row_generates_ingestion_key():
    row = {
        "company": "Acme",
        "role_title": "Director",
        "source": "csv",
        "source_url": "https://example/jobs/1",
    }
    norm = _normalize_row(row)
    assert norm["ingestion_key"]
    assert norm["company"] == "Acme"


def test_normalize_row_safe_compensation_parse():
    norm = _normalize_row({"company": "Acme", "role_title": "Director", "estimated_compensation": "$210,000"})
    assert norm["estimated_compensation"] == 210000.0
