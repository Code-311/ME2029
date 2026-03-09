import csv
from io import StringIO
from app.models.opportunity import Opportunity


class BaseConnector:
    source = "base"

    def fetch(self) -> list[dict]:
        return []


class MockLinkedInConnector(BaseConnector):
    source = "mock_linkedin"

    def fetch(self):
        return [{"company": "Contoso", "role_title": "Director, Security Operations", "location": "London", "estimated_compensation": 180000, "source": self.source, "source_url": "https://linkedin.example/jobs/1", "description": "Lead corporate security governance and operations.", "status": "new", "notes": ""}]


class MockCompanyJobsConnector(BaseConnector):
    source = "mock_company_jobs"

    def fetch(self):
        return [{"company": "Fabrikam", "role_title": "VP Governance & Risk", "location": "Remote", "estimated_compensation": 210000, "source": self.source, "source_url": "https://jobs.example/2", "description": "Scale governance across enterprise operations.", "status": "new", "notes": ""}]


class MockRecruiterConnector(BaseConnector):
    source = "mock_recruiter_leads"

    def fetch(self):
        return [{"company": "Northwind", "role_title": "Head of Corporate Resilience", "location": "New York", "estimated_compensation": 195000, "source": self.source, "source_url": "", "description": "Drive resilience and cross-functional leadership.", "status": "new", "notes": ""}]


CONNECTORS = [MockLinkedInConnector(), MockCompanyJobsConnector(), MockRecruiterConnector()]


def _as_float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _normalize_row(row: dict) -> dict:
    return {
        "company": row.get("company", "Unknown Co"),
        "role_title": row.get("role_title", row.get("title", "Unknown Role")),
        "location": row.get("location", "Unknown"),
        "estimated_compensation": _as_float(row.get("estimated_compensation", 0)),
        "source": row.get("source", "manual"),
        "source_url": row.get("source_url", ""),
        "description": row.get("description", ""),
        "status": row.get("status", "new"),
        "notes": row.get("notes", ""),
    }


def parse_csv(content: str) -> list[dict]:
    reader = csv.DictReader(StringIO(content))
    return [_normalize_row(row) for row in reader]


def persist_items(db, rows: list[dict]):
    created = []
    for row in rows:
        opp = Opportunity(**_normalize_row(row))
        db.add(opp)
        created.append(opp)
    db.commit()
    return created
