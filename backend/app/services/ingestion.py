from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass

from sqlalchemy.orm import Session

from app.models.network import Company, PersonNode
from app.models.opportunity import Opportunity
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
