from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.opportunity import Opportunity
from app.models.signal import Signal
from app.models.network import PersonNode
from app.models.company_signal import CompanySignal
from app.models.recommendation import Recommendation

RECOMMENDATION_TYPES = {
    "OPPORTUNITY_PRIORITY",
    "SIGNAL_ALERT",
    "NETWORK_ACTION",
    "FOLLOW_UP_ACTION",
    "WATCHLIST_ESCALATION",
}


def _severity_weight(severity: str) -> float:
    return {"success": 1.0, "warning": 0.8, "info": 0.5}.get((severity or "").lower(), 0.4)


def _urgency_for(score: float) -> str:
    if score >= 8.5:
        return "high"
    if score >= 6.5:
        return "medium"
    return "low"


def _reco_key(payload: dict) -> tuple[str, str, int]:
    return (payload["recommendation_type"], payload["entity_type"], payload["entity_id"])


def _upsert_recommendation(db: Session, payload: dict) -> int:
    existing = (
        db.query(Recommendation)
        .filter(Recommendation.recommendation_type == payload["recommendation_type"])
        .filter(Recommendation.entity_type == payload["entity_type"])
        .filter(Recommendation.entity_id == payload["entity_id"])
        .filter(Recommendation.status == "open")
        .first()
    )
    if existing:
        for key, value in payload.items():
            setattr(existing, key, value)
        existing.created_at = datetime.utcnow()
        return 0
    db.add(Recommendation(**payload))
    return 1


def _make_opportunity_reco(opp: Opportunity, signals: list[Signal], company_signals: list[CompanySignal]) -> dict:
    recent_signal = sum(_severity_weight(s.severity) for s in signals if s.created_at >= datetime.utcnow() - timedelta(days=10))
    company_context = sum(_severity_weight(s.severity) for s in company_signals[:3])
    timing_penalty = 1.2 if opp.discovered_at < datetime.utcnow() - timedelta(days=21) else 0
    decision_score = max(0.0, (opp.score_total * 0.7) + recent_signal + company_context - timing_penalty)
    confidence = min(0.95, 0.55 + (0.04 * len(signals)) + (0.03 * len(company_signals)))
    return {
        "recommendation_type": "OPPORTUNITY_PRIORITY",
        "entity_type": "opportunity",
        "entity_id": opp.id,
        "decision_score": round(decision_score, 2),
        "urgency": _urgency_for(decision_score),
        "confidence": round(confidence, 2),
        "title": f"Prioritize {opp.role_title} at {opp.company}",
        "reason_summary": f"Opportunity score {opp.score_total:.1f}; recent signals {len(signals)}; company intelligence hits {len(company_signals)}.",
        "suggested_action": "Advance to next milestone this week and initiate targeted outreach.",
        "expires_at": datetime.utcnow() + timedelta(days=14),
        "status": "open",
    }


def _make_follow_up_reco(opp: Opportunity) -> dict | None:
    if opp.status not in {"new", "applied"}:
        return None
    if opp.discovered_at >= datetime.utcnow() - timedelta(days=14):
        return None
    age_days = (datetime.utcnow() - opp.discovered_at).days
    score = min(9.0, 6.5 + (age_days / 10))
    return {
        "recommendation_type": "FOLLOW_UP_ACTION",
        "entity_type": "opportunity",
        "entity_id": opp.id,
        "decision_score": round(score, 2),
        "urgency": "high" if age_days > 21 else "medium",
        "confidence": 0.82,
        "title": f"Follow up on {opp.company} ({opp.role_title})",
        "reason_summary": f"No status movement for {age_days} days while still {opp.status}.",
        "suggested_action": "Send follow-up note to recruiter/hiring manager and update status notes.",
        "expires_at": datetime.utcnow() + timedelta(days=7),
        "status": "open",
    }


def _make_network_reco(opp: Opportunity, nodes: list[PersonNode]) -> dict | None:
    if not nodes:
        return None
    top = max(nodes, key=lambda n: n.influence_score + n.accessibility_score + n.relationship_strength)
    network_score = top.influence_score + top.accessibility_score + top.relationship_strength
    decision_score = min(9.5, (opp.score_total * 0.45) + (network_score * 0.55))
    return {
        "recommendation_type": "NETWORK_ACTION",
        "entity_type": "opportunity",
        "entity_id": opp.id,
        "decision_score": round(decision_score, 2),
        "urgency": _urgency_for(decision_score),
        "confidence": 0.76,
        "title": f"Use network path for {opp.company}",
        "reason_summary": f"Best connector is {top.full_name} ({top.node_role_type}) with combined network strength {network_score:.1f}.",
        "suggested_action": f"Request intro through {top.full_name} and tailor outreach to {opp.role_title}.",
        "expires_at": datetime.utcnow() + timedelta(days=10),
        "status": "open",
    }


def _make_company_watchlist_reco(cs: CompanySignal) -> dict:
    score = 7.5 + _severity_weight(cs.severity)
    return {
        "recommendation_type": "WATCHLIST_ESCALATION",
        "entity_type": "company",
        "entity_id": cs.company_id,
        "decision_score": round(score, 2),
        "urgency": "high" if cs.signal_type in {"FUNDING", "CONTRACT"} else "medium",
        "confidence": 0.72,
        "title": f"Escalate watchlist: {cs.signal_type}",
        "reason_summary": f"{cs.title} ({cs.signal_type}) detected from company intelligence feed.",
        "suggested_action": "Review active roles and refresh target-company strategy.",
        "expires_at": datetime.utcnow() + timedelta(days=21),
        "status": "open",
    }


def _make_signal_alert(signal: Signal) -> dict:
    age_days = max(0, (datetime.utcnow() - signal.created_at).days)
    score = max(4.5, 8.5 - (age_days * 0.2) + _severity_weight(signal.severity))
    return {
        "recommendation_type": "SIGNAL_ALERT",
        "entity_type": "opportunity" if signal.opportunity_id else "company",
        "entity_id": signal.opportunity_id or signal.company_id or 0,
        "decision_score": round(score, 2),
        "urgency": _urgency_for(score),
        "confidence": 0.67,
        "title": f"Signal alert: {signal.title}",
        "reason_summary": signal.details[:220],
        "suggested_action": "Validate signal relevance and convert into a concrete next step.",
        "expires_at": datetime.utcnow() + timedelta(days=10),
        "status": "open",
    }


def refresh_recommendations(db: Session) -> int:
    generated: list[dict] = []

    opportunities = db.query(Opportunity).all()
    for opp in opportunities:
        if opp.status in {"closed", "archived", "rejected"}:
            continue
        opp_signals = db.query(Signal).filter(Signal.opportunity_id == opp.id).order_by(Signal.created_at.desc()).limit(5).all()
        intel = []
        if opp.company_id:
            intel = db.query(CompanySignal).filter(CompanySignal.company_id == opp.company_id).order_by(CompanySignal.detected_at.desc()).limit(3).all()
        nodes = db.query(PersonNode).filter(PersonNode.company_id == opp.company_id).all() if opp.company_id else []

        generated.append(_make_opportunity_reco(opp, opp_signals, intel))
        follow_up = _make_follow_up_reco(opp)
        if follow_up:
            generated.append(follow_up)
        network = _make_network_reco(opp, nodes)
        if network:
            generated.append(network)

    for cs in db.query(CompanySignal).order_by(CompanySignal.detected_at.desc()).limit(20).all():
        generated.append(_make_company_watchlist_reco(cs))
    for signal in db.query(Signal).order_by(Signal.created_at.desc()).limit(20).all():
        generated.append(_make_signal_alert(signal))

    keys = {_reco_key(r) for r in generated}
    stale = db.query(Recommendation).filter(Recommendation.status == "open").all()
    for rec in stale:
        rec_key = (rec.recommendation_type, rec.entity_type, rec.entity_id)
        if rec_key not in keys:
            rec.status = "expired"

    created = 0
    for payload in generated:
        created += _upsert_recommendation(db, payload)

    db.commit()
    return created
