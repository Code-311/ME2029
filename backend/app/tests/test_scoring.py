from types import SimpleNamespace
from app.services.scoring import _normalize_weights, build_score_breakdown, summarize_score


class FakeQuery:
    def all(self):
        return []


class FakeDB:
    def query(self, _):
        return FakeQuery()


def test_weights_normalize_and_legacy_keys():
    out = _normalize_weights({"compensation_threshold": 2, "profile_alignment": 2})
    assert "compensation_fit" in out
    assert abs(sum(out.values()) - 1) < 1e-6


def test_scoring_handles_missing_profile_fields():
    profile = SimpleNamespace(
        skills="",
        compensation_threshold=0,
        preferred_geographies="",
        leadership_scale=0,
        industry_preferences="",
    )
    opp = SimpleNamespace(
        role_title="Manager",
        description="",
        estimated_compensation=0,
        location="",
        company="Acme",
    )
    breakdown = build_score_breakdown(FakeDB(), opp, profile)
    assert breakdown["total"] >= 0
    assert len(breakdown["factors"]) == 7


def test_score_summary_mentions_strength_and_drag():
    breakdown = {
        "factors": [
            {"name": "profile_alignment", "raw_score": 8.5, "weighted_score": 2.0, "reason": "x"},
            {"name": "industry_fit", "raw_score": 7.5, "weighted_score": 1.8, "reason": "y"},
            {"name": "geography_fit", "raw_score": 4.0, "weighted_score": 0.8, "reason": "no fit"},
        ]
    }
    text = summarize_score(breakdown)
    assert "Top strengths" in text
    assert "Biggest drag" in text
