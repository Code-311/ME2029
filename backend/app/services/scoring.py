from dataclasses import dataclass
from typing import Any
import json
from sqlalchemy.orm import Session
from app.models.config import ScoringWeight
from app.models.profile import UserProfile
from app.models.opportunity import Opportunity

DEFAULT_WEIGHTS = {
    "profile_alignment": 0.24,
    "compensation_fit": 0.2,
    "geography_fit": 0.14,
    "leadership_seniority_fit": 0.14,
    "industry_fit": 0.14,
    "strategic_value": 0.08,
    "ease_of_absorption": 0.06,
}

LEGACY_WEIGHT_MAP = {
    "compensation_threshold": "compensation_fit",
    "leadership_level": "leadership_seniority_fit",
}


@dataclass
class ScoreFactor:
    name: str
    score: float
    weight: float
    reason: str

    @property
    def weighted(self) -> float:
        return round(self.score * self.weight, 3)


def _normalize_weights(raw: dict[str, float]) -> dict[str, float]:
    merged = DEFAULT_WEIGHTS.copy()
    for key, value in raw.items():
        normalized_key = LEGACY_WEIGHT_MAP.get(key, key)
        if normalized_key in merged:
            merged[normalized_key] = max(0.0, float(value))
    total = sum(merged.values()) or 1.0
    return {k: v / total for k, v in merged.items()}


def get_weights(db: Session) -> dict[str, float]:
    rows = db.query(ScoringWeight).all()
    raw = {r.key: r.value for r in rows}
    return _normalize_weights(raw)


def _split_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [i.strip().lower() for i in raw.split(",") if i.strip()]


def _contains_any(text: str | None, terms: list[str]) -> bool:
    t = (text or "").lower()
    return any(term in t for term in terms)


def _factor_profile_alignment(profile: UserProfile, opp: Opportunity, weight: float) -> ScoreFactor:
    skills = _split_list(profile.skills)
    score = 8.8 if _contains_any(opp.description, skills) else 5.5
    reason = "Role description overlaps with profile skills." if score > 8 else "Limited direct skill keyword overlap in role description."
    return ScoreFactor("profile_alignment", score, weight, reason)


def _factor_compensation(profile: UserProfile, opp: Opportunity, weight: float) -> ScoreFactor:
    comp = opp.estimated_compensation or 0
    threshold = profile.compensation_threshold or 0
    if threshold <= 0:
        return ScoreFactor("compensation_fit", 6.5, weight, "Compensation threshold missing; applied neutral score.")
    ratio = comp / threshold
    score = max(0.0, min(10.0, 10 * ratio))
    reason = "Meets/exceeds target compensation." if comp >= threshold else "Below preferred compensation threshold."
    return ScoreFactor("compensation_fit", round(score, 2), weight, reason)


def _factor_geography(profile: UserProfile, opp: Opportunity, weight: float) -> ScoreFactor:
    geos = _split_list(profile.preferred_geographies)
    loc = (opp.location or "").lower()
    if not geos:
        return ScoreFactor("geography_fit", 6.0, weight, "No preferred geographies configured.")
    score = 9.2 if any(g in loc for g in geos) else 4.8
    reason = "Location is within preferred geographies." if score > 8 else "Location is outside preferred geographies."
    return ScoreFactor("geography_fit", score, weight, reason)


def _factor_leadership(profile: UserProfile, opp: Opportunity, weight: float) -> ScoreFactor:
    leadership = max(1, min(10, profile.leadership_scale or 5))
    role_text = f"{opp.role_title} {opp.description}".lower()
    senior_terms = ["director", "vp", "head", "chief", "ciso"]
    expected = 9 if any(t in role_text for t in senior_terms) else 6
    gap = abs(expected - leadership)
    score = max(3.5, 10 - gap * 1.3)
    reason = "Seniority appears aligned with leadership target." if gap <= 2 else "Potential mismatch between target seniority and role level."
    return ScoreFactor("leadership_seniority_fit", round(score, 2), weight, reason)


def _factor_industry(profile: UserProfile, opp: Opportunity, weight: float) -> ScoreFactor:
    industries = _split_list(profile.industry_preferences)
    text = f"{opp.company} {opp.description}".lower()
    score = 8.7 if _contains_any(text, industries) else 5.2
    reason = "Industry preference match found." if score > 8 else "No strong industry preference signal in listing."
    return ScoreFactor("industry_fit", score, weight, reason)


def _factor_strategic_value(profile: UserProfile, opp: Opportunity, weight: float) -> ScoreFactor:
    strategic_terms = ["transformation", "enterprise", "board", "governance", "resilience"]
    hits = sum(1 for t in strategic_terms if t in (opp.description or "").lower())
    score = min(10.0, 5.5 + hits * 1.1)
    reason = "Role carries visible strategic scope." if score >= 7 else "Role appears more tactical than strategic."
    return ScoreFactor("strategic_value", round(score, 2), weight, reason)


def _factor_ease(profile: UserProfile, opp: Opportunity, weight: float) -> ScoreFactor:
    skills = _split_list(profile.skills)
    hits = sum(1 for s in skills[:5] if s in (opp.description or "").lower())
    score = min(9.5, 4.5 + hits * 1.0)
    reason = "Profile should absorb this role quickly." if score >= 7 else "Likely onboarding ramp due to partial overlap."
    return ScoreFactor("ease_of_absorption", round(score, 2), weight, reason)


def build_score_breakdown(db: Session, opp: Opportunity, profile: UserProfile) -> dict[str, Any]:
    weights = get_weights(db)
    factors = [
        _factor_profile_alignment(profile, opp, weights["profile_alignment"]),
        _factor_compensation(profile, opp, weights["compensation_fit"]),
        _factor_geography(profile, opp, weights["geography_fit"]),
        _factor_leadership(profile, opp, weights["leadership_seniority_fit"]),
        _factor_industry(profile, opp, weights["industry_fit"]),
        _factor_strategic_value(profile, opp, weights["strategic_value"]),
        _factor_ease(profile, opp, weights["ease_of_absorption"]),
    ]
    total = round(sum(f.weighted for f in factors), 2)
    return {
        "total": total,
        "factors": [
            {
                "name": f.name,
                "raw_score": round(f.score, 2),
                "weight": round(f.weight, 3),
                "weighted_score": f.weighted,
                "reason": f.reason,
            }
            for f in factors
        ],
    }


def summarize_score(breakdown: dict[str, Any]) -> str:
    factors = sorted(breakdown["factors"], key=lambda f: f["weighted_score"], reverse=True)
    top = ", ".join(f"{f['name']} ({f['raw_score']}/10)" for f in factors[:2])
    low = min(factors, key=lambda f: f["raw_score"])
    return f"Top strengths: {top}. Biggest drag: {low['name']} ({low['raw_score']}/10) - {low['reason']}"


def score_opportunity(db: Session, opp: Opportunity, profile: UserProfile) -> Opportunity:
    breakdown = build_score_breakdown(db, opp, profile)
    opp.score_total = breakdown["total"]
    opp.score_breakdown = json.dumps(breakdown)
    opp.score_explanation = summarize_score(breakdown)
    return opp
