from datetime import datetime
from xml.etree import ElementTree
from sqlalchemy.orm import Session
from app.models.network import Company
from app.models.opportunity import Opportunity
from app.models.signal import Signal
from app.models.company_signal import CompanySignal

SIGNAL_TYPES = {
    "EXPANSION",
    "LEADERSHIP_CHANGE",
    "CONTRACT",
    "FUNDING",
    "DIVISION_LAUNCH",
}


class CompanyIntelligenceConnector:
    source = "company_intelligence_rss"

    def __init__(self, feeds: list[str] | None = None):
        self.feeds = feeds or []

    def ingest(self, payloads: list[str]) -> list[dict]:
        events: list[dict] = []
        for payload in payloads:
            events.extend(parse_rss_events(payload))
        return [normalize_company_event(e) for e in events if e.get("title")]


def parse_rss_events(payload: str) -> list[dict]:
    root = ElementTree.fromstring(payload)
    out = []
    for item in root.findall("./channel/item"):
        out.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "description": (item.findtext("description") or "").strip(),
                "source_url": (item.findtext("link") or "").strip(),
                "detected_at": _parse_datetime(item.findtext("pubDate")),
            }
        )
    return out


def _parse_datetime(raw: str | None) -> datetime:
    if not raw:
        return datetime.utcnow()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.replace(tzinfo=None)
        except ValueError:
            continue
    return datetime.utcnow()


def _extract_company_name(title: str, description: str) -> str:
    merged = f"{title} {description}".strip()
    if ":" in merged:
        merged = merged.split(":", 1)[0]
    words = merged.split()
    return " ".join(words[:3]) if words else "Unknown Co"


def classify_signal_type(title: str, description: str) -> str:
    haystack = f"{title} {description}".lower()
    if any(token in haystack for token in ["raises", "series", "funding", "investment"]):
        return "FUNDING"
    if any(token in haystack for token in ["appoints", "appointed", "ceo", "cfo", "chief"]):
        return "LEADERSHIP_CHANGE"
    if any(token in haystack for token in ["contract", "agreement", "deal", "awarded"]):
        return "CONTRACT"
    if any(token in haystack for token in ["launches", "launch", "division", "business unit"]):
        return "DIVISION_LAUNCH"
    if any(token in haystack for token in ["expand", "expands", "opens", "new office", "growth"]):
        return "EXPANSION"
    return "EXPANSION"


def normalize_company_event(event: dict) -> dict:
    title = event.get("title", "")
    description = event.get("description", "")
    signal_type = classify_signal_type(title, description)
    severity = "success" if signal_type in {"FUNDING", "CONTRACT"} else "info"
    return {
        "company": event.get("company") or _extract_company_name(title, description),
        "signal_type": signal_type,
        "severity": severity,
        "title": title[:180],
        "description": description,
        "source_url": event.get("source_url", ""),
        "detected_at": event.get("detected_at") or datetime.utcnow(),
    }


def ingest_company_signals(db: Session, events: list[dict]) -> int:
    created = 0
    for event in events:
        normalized = normalize_company_event(event)
        company = db.query(Company).filter(Company.name == normalized["company"]).first()
        if not company:
            company = Company(name=normalized["company"], industry="")
            db.add(company)
            db.flush()
        exists = (
            db.query(CompanySignal)
            .filter(CompanySignal.company_id == company.id)
            .filter(CompanySignal.title == normalized["title"])
            .first()
        )
        if exists:
            continue
        db.add(
            CompanySignal(
                company_id=company.id,
                signal_type=normalized["signal_type"],
                severity=normalized["severity"],
                title=normalized["title"],
                description=normalized["description"],
                source_url=normalized["source_url"],
                detected_at=normalized["detected_at"],
            )
        )
        created += 1
        _create_opportunity_signal_for_company_event(db, company.id, normalized)
    db.commit()
    return created


def _create_opportunity_signal_for_company_event(db: Session, company_id: int, signal: dict) -> None:
    related = (
        db.query(Opportunity)
        .filter(Opportunity.company_id == company_id)
        .filter(Opportunity.status.in_(["new", "applied"]))
        .all()
    )
    for opp in related:
        db.add(
            Signal(
                signal_type=f"company_{signal['signal_type'].lower()}",
                severity=signal["severity"],
                title=f"Company event: {signal['title']}",
                details=signal["description"] or "Company intelligence event detected.",
                company_id=company_id,
                opportunity_id=opp.id,
            )
        )

SAMPLE_RSS_FEED = """<?xml version='1.0' encoding='UTF-8'?>
<rss><channel>
<item><title>Contoso raises Series C funding</title><description>Contoso announces new funding round to expand operations.</description><link>https://news.example/contoso-funding</link><pubDate>Mon, 01 Jan 2024 10:00:00 +0000</pubDate></item>
<item><title>Fabrikam appoints new Chief Risk Officer</title><description>Leadership update as Fabrikam hires CRO.</description><link>https://news.example/fabrikam-leadership</link><pubDate>Tue, 02 Jan 2024 11:00:00 +0000</pubDate></item>
</channel></rss>
"""


def run_company_intelligence_connector(db: Session, payloads: list[str] | None = None) -> int:
    connector = CompanyIntelligenceConnector()
    events = connector.ingest(payloads or [SAMPLE_RSS_FEED])
    return ingest_company_signals(db, events)
