from __future__ import annotations

import csv
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx
import hashlib
from dataclasses import asdict, dataclass

from sqlalchemy.orm import Session

from app.models.network import Company, PersonNode
from app.models.opportunity import Opportunity
from app.services.signals import upsert_signal


@dataclass
class ConnectorResult:
    connector: str
from app.models.profile import UserProfile
from app.services.connectors import ConnectorPayload, CSVConnector, NormalizedOpportunityInput, registry
from app.services.events import EventBus
from app.services.scoring import score_opportunity
from app.services.signals import generate_opportunity_signals, upsert_signal


@dataclass
class IngestionResult:
    fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errored: int = 0


class BaseConnector(ABC):
    source = "base"

    @abstractmethod
    def fetch(self) -> list[dict[str, Any]]:
        raise NotImplementedError


class CSVConnector(BaseConnector):
    source = "csv"

    def __init__(self, content: str, source_name: str = "csv"):
        self.content = content
        self.source_name = source_name

    def fetch(self) -> list[dict[str, Any]]:
        if not self.content.strip():
            return []
        reader = csv.DictReader(StringIO(self.content))
        rows: list[dict[str, Any]] = []
        for row in reader:
            norm = {str(k).strip().lower(): (v or "").strip() for k, v in row.items() if k}
            norm["source"] = self.source_name
            rows.append(norm)
        return rows


class RecruiterLeadsConnector(BaseConnector):
    source = "recruiter_leads"

    def __init__(self, content: str):
        self.content = content

    def fetch(self) -> list[dict[str, Any]]:
        return CSVConnector(self.content, source_name=self.source).fetch()


class RSSFeedConnector(BaseConnector):
    source = "rss_feed"

    def __init__(self, feed_url: str):
        self.feed_url = feed_url

    def fetch(self) -> list[dict[str, Any]]:
        if not self.feed_url:
            return []
        text = httpx.get(self.feed_url, timeout=20).text
        root = ElementTree.fromstring(text)
        out: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = (item.findtext("description") or "").strip()
            out.append(
                {
                    "role_title": title or "Unknown Role",
                    "source_url": link,
                    "description": desc,
                    "company": _company_from_url(link) or "Unknown Co",
                    "location": "Unknown",
                    "source": self.source,
                    "external_id": link or title,
                }
            )
        return out


class GreenhouseConnector(BaseConnector):
    source = "company_careers"

    def __init__(self, company_name: str, board_token: str):
        self.company_name = company_name
        self.board_token = board_token

    def fetch(self) -> list[dict[str, Any]]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{self.board_token}/jobs"
        payload = httpx.get(url, timeout=20).json()
        jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
        out: list[dict[str, Any]] = []
        for j in jobs:
            out.append(
                {
                    "company": self.company_name,
                    "role_title": j.get("title", "Unknown Role"),
                    "location": (j.get("location") or {}).get("name", "Unknown"),
                    "estimated_compensation": 0,
                    "source": f"greenhouse:{self.board_token}",
                    "source_url": j.get("absolute_url", ""),
                    "description": "",
                    "status": "new",
                    "external_id": str(j.get("id", "")),
                }
            )
        return out


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
        return [{"company": "Northwind", "role_title": "Head of Corporate Resilience", "location": "New York", "estimated_compensation": 195000, "source": self.source, "source_url": "", "description": "Drive resilience and cross-functional leadership.", "status": "new", "notes": "", "recruiter_name": "Taylor Quinn", "recruiter_title": "Executive Recruiter"}]


CONNECTORS = [MockLinkedInConnector(), MockCompanyJobsConnector(), MockRecruiterConnector()]


def _as_float(value) -> float:
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("$", "").strip()
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _company_from_url(url: str) -> str:
    if not url:
        return ""
    host = urlparse(url).hostname or ""
    parts = [p for p in host.split(".") if p and p not in {"www", "jobs", "careers"}]
    return parts[0].capitalize() if parts else ""


def _normalize_row(row: dict) -> dict:
    company = (row.get("company") or row.get("organization") or row.get("employer") or "Unknown Co").strip()
    role_title = (row.get("role_title") or row.get("title") or row.get("role") or "Unknown Role").strip()
    source = (row.get("source") or "manual").strip()
    source_url = (row.get("source_url") or row.get("url") or "").strip()
    external_id = str(row.get("external_id") or row.get("id") or source_url or "").strip()
    ingestion_key = row.get("ingestion_key")
    if not ingestion_key:
        raw = f"{source}|{external_id or source_url}|{company}|{role_title}|{(row.get('location') or '').strip()}"
        ingestion_key = hashlib.sha1(raw.encode("utf-8")).hexdigest()

    return {
        "company": company,
        "role_title": role_title,
        "location": (row.get("location") or "Unknown").strip(),
        "estimated_compensation": _as_float(row.get("estimated_compensation", row.get("compensation", 0))),
        "source": source,
        "external_id": external_id,
        "ingestion_key": ingestion_key,
        "source_url": source_url,
        "description": row.get("description", "") or "",
        "status": (row.get("status") or "new").strip(),
        "notes": row.get("notes", "") or "",
        "recruiter_name": (row.get("recruiter_name") or row.get("recruiter") or "").strip(),
        "recruiter_title": (row.get("recruiter_title") or "Recruiter").strip(),
    }


def parse_csv(content: str) -> list[dict]:
    return CSVConnector(content).fetch()


def ensure_company(db: Session, company_name: str) -> Company:
    company = db.query(Company).filter(Company.name == company_name).first()
    if not company:
        company = Company(name=company_name, industry="")
        db.add(company)
        db.flush()
    return company


def persist_items(db: Session, rows: list[dict]) -> tuple[list[Opportunity], dict[str, int]]:
    created_or_updated: list[Opportunity] = []
    stats = {"created": 0, "updated": 0, "skipped": 0}
    for row in rows:
        norm = _normalize_row(row)
        if not norm["company"] or not norm["role_title"]:
            stats["skipped"] += 1
            continue

        existing = db.query(Opportunity).filter(Opportunity.ingestion_key == norm["ingestion_key"]).first()
        company = ensure_company(db, norm["company"])
        if existing:
            existing.location = norm["location"]
            existing.estimated_compensation = norm["estimated_compensation"]
            existing.source_url = norm["source_url"]
            existing.description = norm["description"]
            existing.status = norm["status"] or existing.status
            existing.notes = norm["notes"]
            existing.external_id = norm["external_id"]
            existing.company_id = company.id
            created_or_updated.append(existing)
            stats["updated"] += 1
            opp = existing
        else:
            opp = Opportunity(
                company=norm["company"],
                role_title=norm["role_title"],
                location=norm["location"],
                estimated_compensation=norm["estimated_compensation"],
                source=norm["source"],
                external_id=norm["external_id"],
                ingestion_key=norm["ingestion_key"],
                source_url=norm["source_url"],
                description=norm["description"],
                status=norm["status"],
                notes=norm["notes"],
                discovered_at=datetime.now(timezone.utc),
                company_id=company.id,
            )
            db.add(opp)
            db.flush()
            created_or_updated.append(opp)
            stats["created"] += 1

        if norm["recruiter_name"]:
            _upsert_recruiter_node(db, company.id, opp.id, norm["recruiter_name"], norm["recruiter_title"])
            upsert_signal(
                db,
                signal_type="new_recruiter_contact",
                title=f"Recruiter contact for {norm['company']}",
                details=f"{norm['recruiter_name']} linked to {norm['role_title']}",
                severity="info",
                company_id=company.id,
                opportunity_id=opp.id,
            )

    db.commit()
    return created_or_updated, stats


def _upsert_recruiter_node(db: Session, company_id: int, opportunity_id: int, name: str, title: str) -> None:
    existing = db.query(PersonNode).filter(PersonNode.company_id == company_id, PersonNode.full_name == name).first()
    if existing:
        existing.node_role_type = "recruiter"
        existing.opportunity_id = opportunity_id
        existing.role_title = title or existing.role_title
        return
    db.add(
        PersonNode(
            full_name=name,
            role_title=title or "Recruiter",
            node_role_type="recruiter",
            influence_score=6,
            accessibility_score=8,
            relationship_strength=4,
            connection_path="connector_import",
            notes_history="Imported from recruiter lead connector",
            company_id=company_id,
            opportunity_id=opportunity_id,
        )
    )


def connector_registry() -> dict[str, BaseConnector]:
    reg = {c.source: c for c in CONNECTORS}
    reg["rss_feed"] = RSSFeedConnector("")
    reg["company_careers"] = GreenhouseConnector("Demo", "demo")
    return reg
def parse_csv(content: str) -> list[dict]:
    payload = CSVConnector.parse_csv(content, source="csv_upload")
    return [asdict(o) for o in payload.opportunities]


def _ensure_company(db: Session, name: str) -> Company:
    company = db.query(Company).filter(Company.name == name).first()
    if company:
        return company
    company = Company(name=name, industry="")
    db.add(company)
    db.flush()
    return company


def _dedupe_key(item: NormalizedOpportunityInput) -> str:
    text = "|".join(
        [
            item.source,
            item.external_id or "",
            item.source_url,
            item.company.strip().lower(),
            item.role_title.strip().lower(),
            item.location.strip().lower(),
        ]
    )
    return hashlib.sha256(text.encode()).hexdigest()


def _find_existing(db: Session, item: NormalizedOpportunityInput) -> Opportunity | None:
    if item.external_id:
        found = (
            db.query(Opportunity)
            .filter(Opportunity.source == item.source)
            .filter(Opportunity.external_id == item.external_id)
            .first()
        )
        if found:
            return found
    if item.source_url:
        found = db.query(Opportunity).filter(Opportunity.source_url == item.source_url).first()
        if found:
            return found
    key = _dedupe_key(item)
    return db.query(Opportunity).filter(Opportunity.ingest_key == key).first()


def _upsert_opportunity(db: Session, item: NormalizedOpportunityInput, profile: UserProfile | None) -> str:
    existing = _find_existing(db, item)
    company = _ensure_company(db, item.company)
    if existing:
        existing.company = item.company
        existing.role_title = item.role_title
        existing.location = item.location
        existing.estimated_compensation = item.estimated_compensation
        existing.source_url = item.source_url
        existing.description = item.description
        existing.notes = item.notes
        existing.external_id = item.external_id
        existing.ingest_key = _dedupe_key(item)
        existing.company_id = company.id
        if profile:
            score_opportunity(db, existing, profile)
        return "updated"

    opp = Opportunity(
        company=item.company,
        role_title=item.role_title,
        location=item.location,
        estimated_compensation=item.estimated_compensation,
        source=item.source,
        source_url=item.source_url,
        description=item.description,
        status=item.status,
        notes=item.notes,
        external_id=item.external_id,
        ingest_key=_dedupe_key(item),
        company_id=company.id,
    )
    db.add(opp)
    db.flush()
    if profile:
        score_opportunity(db, opp, profile)
    return "created"


def _ingest_recruiter_leads(db: Session, payload: ConnectorPayload) -> None:
    for lead in payload.recruiter_leads:
        company = _ensure_company(db, lead.company)
        node = (
            db.query(PersonNode)
            .filter(PersonNode.company_id == company.id)
            .filter(PersonNode.full_name == lead.full_name)
            .first()
        )
        if not node:
            node = PersonNode(
                full_name=lead.full_name,
                role_title=lead.role_title,
                node_role_type="recruiter",
                influence_score=6.0,
                accessibility_score=6.5,
                relationship_strength=4.5,
                connection_path=lead.email,
                notes_history=lead.notes,
                company_id=company.id,
            )
            db.add(node)
            db.flush()
            upsert_signal(
                db,
                "new_recruiter_contact",
                f"New recruiter contact at {lead.company}",
                f"{lead.full_name} ({lead.role_title}) was added.",
                "info",
                company_id=company.id,
            )

        linked_opp = None
        if lead.opportunity_external_id:
            linked_opp = (
                db.query(Opportunity)
                .filter(Opportunity.external_id == lead.opportunity_external_id)
                .filter(Opportunity.company_id == company.id)
                .first()
            )

        upsert_signal(
            db,
            "recruiter_lead_added",
            f"Recruiter lead added for {lead.company}",
            f"Lead {lead.full_name} submitted a potential role.",
            "info",
            company_id=company.id,
            opportunity_id=linked_opp.id if linked_opp else None,
        )

        if linked_opp:
            upsert_signal(
                db,
                "recruiter_linked_opportunity",
                f"Recruiter-linked opportunity at {lead.company}",
                f"{lead.full_name} is linked to {linked_opp.role_title}.",
                "success",
                company_id=company.id,
                opportunity_id=linked_opp.id,
            )


def ingest_connector(db: Session, connector_name: str, override_config: dict | None = None) -> tuple[IngestionResult, list[str]]:
    connector = registry.build(connector_name, override_config)
    payload = connector.fetch()
    result = IngestionResult(fetched=payload.fetched_count, errored=len(payload.errors))
    profile = db.query(UserProfile).first()

    for item in payload.opportunities:
        try:
            status = _upsert_opportunity(db, item, profile)
            if status == "created":
                result.created += 1
            else:
                result.updated += 1
        except Exception:
            result.errored += 1

    _ingest_recruiter_leads(db, payload)
    generate_opportunity_signals(db, profile)
    db.commit()
    EventBus.bump(f"connector_{connector_name}")
    return result, payload.errors


def run_all_connectors(db: Session) -> dict[str, IngestionResult]:
    output: dict[str, IngestionResult] = {}
    for c in registry.list():
        if c["name"] == "csv":
            continue
        result, _ = ingest_connector(db, c["name"])
        output[c["name"]] = result
    return output


def persist_items(db: Session, rows: list[dict]):
    profile = db.query(UserProfile).first()
    created: list[Opportunity] = []
    for row in rows:
        item = NormalizedOpportunityInput(**row)
        status = _upsert_opportunity(db, item, profile)
        if status == "created":
            opp = db.query(Opportunity).filter(Opportunity.ingest_key == _dedupe_key(item)).first()
            if opp:
                created.append(opp)
    db.commit()
    return created
