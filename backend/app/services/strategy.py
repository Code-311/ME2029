from sqlalchemy.orm import Session
from app.models.strategy import ActionPlanItem
from app.models.opportunity import Opportunity
from app.models.config import FeatureFlag


class DeterministicStrategyService:
    def generate(self, db: Session) -> list[ActionPlanItem]:
        db.query(ActionPlanItem).delete()
        top = db.query(Opportunity).order_by(Opportunity.score_total.desc()).limit(3).all()
        items = []
        for opp in top:
            items.append(ActionPlanItem(period_type="weekly", title=f"Reach out at {opp.company}", details=f"Send tailored outreach for {opp.role_title}", due_label="This week", opportunity_id=opp.id))
            items.append(ActionPlanItem(period_type="monthly", title=f"Strategic review: {opp.company}", details="Assess traction, referrals, and interview velocity.", due_label="Month end", opportunity_id=opp.id))
        items.append(ActionPlanItem(period_type="weekly", title="Publish visibility post", details="Share governance/security operations case study on LinkedIn.", due_label="Friday", opportunity_id=None))
        db.add_all(items)
        db.commit()
        return db.query(ActionPlanItem).all()


class LLMStrategyService:
    def generate(self, db: Session) -> list[ActionPlanItem]:
        return DeterministicStrategyService().generate(db)


def generate_plan(db: Session) -> list[ActionPlanItem]:
    ff = db.query(FeatureFlag).filter(FeatureFlag.key == "use_llm_strategy").first()
    service = LLMStrategyService() if ff and ff.enabled else DeterministicStrategyService()
    return service.generate(db)
