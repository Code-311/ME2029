from __future__ import annotations

import csv
import io
import json
import logging
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx
from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class NormalizedOpportunityInput:
    company: str
    role_title: str
    location: str = "Unknown"
    estimated_compensation: float = 0.0
    source: str = "connector"
    source_url: str = ""
    description: str = ""
    status: str = "new"
    notes: str = ""
    external_id: str | None = None


@dataclass
class RecruiterLeadInput:
    full_name: str
    role_title: str
    company: str
    email: str = ""
    notes: str = ""
    opportunity_external_id: str | None = None


@dataclass
class ConnectorPayload:
    opportunities: list[NormalizedOpportunityInput] = field(default_factory=list)
    recruiter_leads: list[RecruiterLeadInput] = field(default_factory=list)
    fetched_count: int = 0
    errors: list[str] = field(default_factory=list)


class BaseConnector(ABC):
    name: str = "base"

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    @abstractmethod
    def fetch(self) -> ConnectorPayload:
        ...


class CSVConnector(BaseConnector):
    name = "csv"

    HEADER_ALIASES = {
        "company": ["company", "org", "organization"],
        "role_title": ["role_title", "title", "role", "job_title", "position"],
        "location": ["location", "city", "geo"],
        "estimated_compensation": ["estimated_compensation", "comp", "salary", "compensation"],
        "source_url": ["source_url", "url", "link", "job_url"],
        "description": ["description", "desc", "summary"],
        "external_id": ["external_id", "id", "job_id"],
    }

    def fetch(self) -> ConnectorPayload:
        content = self.config.get("content", "")
        path = self.config.get("path")
        if path and not content:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        if not content.strip():
            return ConnectorPayload()
        return self.parse_csv(content, self.config.get("source", "csv_upload"))

    @classmethod
    def parse_csv(cls, content: str, source: str) -> ConnectorPayload:
        reader = csv.DictReader(io.StringIO(content))
        payload = ConnectorPayload()
        for row in reader:
            payload.fetched_count += 1
            try:
                normalized_row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
                payload.opportunities.append(
                    NormalizedOpportunityInput(
                        company=cls._pick(normalized_row, "company") or "Unknown Co",
                        role_title=cls._pick(normalized_row, "role_title") or "Unknown Role",
                        location=cls._pick(normalized_row, "location") or "Unknown",
                        estimated_compensation=cls._as_float(cls._pick(normalized_row, "estimated_compensation")),
                        source=source,
                        source_url=cls._pick(normalized_row, "source_url") or "",
                        description=cls._pick(normalized_row, "description") or "",
                        external_id=cls._pick(normalized_row, "external_id") or None,
                    )
                )
            except Exception as exc:
                payload.errors.append(f"csv_parse_error: {exc}")
        return payload

    @classmethod
    def _pick(cls, row: dict[str, str], field_name: str) -> str:
        for alias in cls.HEADER_ALIASES[field_name]:
            if alias in row and row[alias]:
                return row[alias]
        return ""

    @staticmethod
    def _as_float(raw: str) -> float:
        cleaned = raw.replace(",", "").replace("$", "") if raw else ""
        try:
            return float(cleaned) if cleaned else 0.0
        except ValueError:
            return 0.0


class RecruiterLeadsConnector(BaseConnector):
    name = "recruiter_leads"

    def fetch(self) -> ConnectorPayload:
        path = self.config.get("path")
        if not path:
            return ConnectorPayload()
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        reader = csv.DictReader(io.StringIO(content))
        payload = ConnectorPayload()
        for row in reader:
            payload.fetched_count += 1
            normalized = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            company = normalized.get("company") or "Unknown Co"
            role_title = normalized.get("opportunity_title") or normalized.get("role_title") or "Recruiter-introduced role"
            ext_id = normalized.get("opportunity_external_id") or normalized.get("job_id") or None
            payload.recruiter_leads.append(
                RecruiterLeadInput(
                    full_name=normalized.get("full_name") or normalized.get("name") or "Unknown Recruiter",
                    role_title=normalized.get("recruiter_title") or normalized.get("title") or "Recruiter",
                    company=company,
                    email=normalized.get("email") or "",
                    notes=normalized.get("notes") or "",
                    opportunity_external_id=ext_id,
                )
            )
            payload.opportunities.append(
                NormalizedOpportunityInput(
                    company=company,
                    role_title=role_title,
                    location=normalized.get("location") or "Unknown",
                    estimated_compensation=CSVConnector._as_float(normalized.get("estimated_compensation", "")),
                    source="recruiter_leads",
                    source_url=normalized.get("source_url") or "",
                    description=normalized.get("description") or "Introduced by recruiter lead.",
                    external_id=ext_id,
                    notes=normalized.get("notes") or "",
                )
            )
        return payload


class CompanyCareersConnector(BaseConnector):
    name = "company_careers"

    def fetch(self) -> ConnectorPayload:
        companies = self.config.get("companies", [])
        payload = ConnectorPayload()
        with httpx.Client(timeout=20) as client:
            for c in companies:
                adapter = c.get("adapter", "lever")
                if adapter != "lever":
                    payload.errors.append(f"unsupported_adapter:{adapter}")
                    continue
                try:
                    endpoint = c["careers_url"]
                    resp = client.get(endpoint)
                    resp.raise_for_status()
                    jobs = resp.json() if isinstance(resp.json(), list) else []
                    payload.fetched_count += len(jobs)
                    for j in jobs:
                        payload.opportunities.append(
                            NormalizedOpportunityInput(
                                company=c["company_name"],
                                role_title=j.get("text") or "Unknown Role",
                                location=(j.get("categories") or {}).get("location") or "Unknown",
                                source="company_careers",
                                source_url=j.get("hostedUrl") or "",
                                description=(j.get("descriptionPlain") or "")[:3000],
                                external_id=str(j.get("id") or "") or None,
                            )
                        )
                except Exception as exc:
                    payload.errors.append(f"{c.get('company_name','unknown')}:{exc}")
        return payload


class RSSConnector(BaseConnector):
    name = "rss"

    def fetch(self) -> ConnectorPayload:
        payload = ConnectorPayload()
        feeds = self.config.get("feeds", [])
        with httpx.Client(timeout=20) as client:
            for feed in feeds:
                try:
                    resp = client.get(feed["url"])
                    resp.raise_for_status()
                    root = ET.fromstring(resp.text)
                    for item in root.findall("./channel/item"):
                        payload.fetched_count += 1
                        title = (item.findtext("title") or "").strip() or "Unknown Role"
                        link = (item.findtext("link") or "").strip()
                        desc = (item.findtext("description") or "").strip()
                        payload.opportunities.append(
                            NormalizedOpportunityInput(
                                company=feed.get("company", "Unknown Co"),
                                role_title=title,
                                source="rss_feed",
                                source_url=link,
                                description=desc[:3000],
                                external_id=link or None,
                            )
                        )
                except Exception as exc:
                    payload.errors.append(f"rss:{feed.get('url','')}:{exc}")
        return payload


class ConnectorRegistry:
    def __init__(self):
        settings = get_settings()
        self.connector_configs = {
            "csv": {},
            "recruiter_leads": self._json(settings.recruiter_leads_config),
            "company_careers": self._json(settings.company_careers_config),
            "rss": self._json(settings.rss_feeds_config),
        }
        self.connector_classes = {
            "csv": CSVConnector,
            "recruiter_leads": RecruiterLeadsConnector,
            "company_careers": CompanyCareersConnector,
            "rss": RSSConnector,
        }

    @staticmethod
    def _json(raw: str | None) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("invalid_connector_config", extra={"raw": raw})
            return {}

    def list(self) -> list[dict[str, Any]]:
        return [{"name": name, "configured": bool(self.connector_configs.get(name))} for name in self.connector_classes]

    def build(self, name: str, override_config: dict[str, Any] | None = None) -> BaseConnector:
        if name not in self.connector_classes:
            raise KeyError(name)
        merged = {**self.connector_configs.get(name, {}), **(override_config or {})}
        return self.connector_classes[name](merged)


registry = ConnectorRegistry()
