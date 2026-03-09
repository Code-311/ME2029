from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.opportunity import Opportunity
from app.models.profile import UserProfile
from app.models.signal import Signal


def upsert_signal(
    db: Session,
    signal_type: str,
    title: str,
    details: str,
    severity: str = "info",
    company_id: int | None = None,
    opportunity_id: int | None = None,
) -> bool:
    existing = (
        db.query(Signal)
        .filter(Signal.signal_type == signal_type)
        .filter(Signal.opportunity_id == opportunity_id)
        .filter(Signal.company_id == company_id)
        .first()
    )
    if existing:
        existing.title = title
        existing.details = details
        existing.severity = severity
        existing.created_at = datetime.utcnow()
        return False
    db.add(
        Signal(
            signal_type=signal_type,
            title=title,
            details=details,
            severity=severity,
            company_id=company_id,
            opportunity_id=opportunity_id,
        )
    )
    return True


def generate_opportunity_signals(db: Session, profile: UserProfile | None = None) -> int:
    profile = profile or db.query(UserProfile).first()
    created = 0
    for opp in db.query(Opportunity).all():
        if opp.status == "new":
            created += int(
                upsert_signal(
                    db,
                    "new_role_posted",
                    f"New role posted at {opp.company}",
                    f"{opp.role_title} was added from {opp.source}.",
                    "info",
                    opportunity_id=opp.id,
                    company_id=opp.company_id,
                )
            )
        if profile and opp.estimated_compensation < profile.compensation_threshold:
            created += int(
                upsert_signal(
                    db,
                    "comp_below_threshold",
                    f"Comp below threshold: {opp.company}",
                    f"Estimated comp {opp.estimated_compensation:.0f} < target {profile.compensation_threshold:.0f}.",
                    "warning",
                    opportunity_id=opp.id,
                    company_id=opp.company_id,
                )
            )
        if opp.score_total >= 8:
            created += int(
                upsert_signal(
                    db,
                    "high_strategic_visibility",
                    f"High strategic visibility opportunity at {opp.company}",
                    "High-scoring role worth priority networking and outreach.",
                    "success",
                    opportunity_id=opp.id,
                    company_id=opp.company_id,
                )
            )
        if opp.discovered_at < datetime.utcnow() - timedelta(days=21) and opp.status in {"new", "applied"}:
            created += int(
                upsert_signal(
                    db,
                    "stale_opportunity",
                    f"Stale opportunity at {opp.company}",
                    "No progress in >21 days; either follow up or archive.",
                    "warning",
                    opportunity_id=opp.id,
                    company_id=opp.company_id,
                )
            )
    db.commit()
    return created
