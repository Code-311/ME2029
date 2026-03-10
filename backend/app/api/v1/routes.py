from datetime import datetime
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.session import get_db
from app.models.profile import UserProfile
from app.models.opportunity import Opportunity
from app.models.network import Company, PersonNode
from app.models.strategy import ActionPlanItem
from app.models.config import ScoringWeight, FeatureFlag
from app.models.signal import Signal
from app.models.job import JobRun
from app.models.company_signal import CompanySignal
from app.models.recommendation import Recommendation
from app.schemas.profile import ProfileBase, ProfileOut
from app.schemas.opportunity import OpportunityIn, OpportunityOut
from app.schemas.network import CompanyIn, CompanyOut, PersonNodeIn, PersonNodeOut
from app.schemas.strategy import ActionPlanOut
from app.schemas.signal import SignalOut, JobRunOut
from app.schemas.company_signal import CompanySignalOut
from app.schemas.recommendation import RecommendationOut
from app.services.scoring import score_opportunity, get_weights
from app.services.ingestion import parse_csv, persist_items, ingest_connector, run_all_connectors
from app.services.connectors import registry
from app.services.strategy import generate_plan
from app.services.company_intelligence import run_company_intelligence_connector
from app.services.signals import generate_opportunity_signals
from app.services.decision_engine import refresh_recommendations
from app.services.events import EventBus
from app.jobs.scheduler import ingest_job, rescore_job, strategy_job, stale_check_job, company_intelligence_job, decision_engine_job

router = APIRouter()

def _ensure_company_link(db: Session, opp: Opportunity) -> None:
    company = db.query(Company).filter(Company.name == opp.company).first()
    if not company:
        company = Company(name=opp.company, industry="")
        db.add(company)
        db.flush()
    opp.company_id = company.id


def _opp_out(opp: Opportunity) -> dict:
    breakdown = {}
    if opp.score_breakdown:
        try:
            breakdown = json.loads(opp.score_breakdown)
        except json.JSONDecodeError:
            breakdown = {"total": opp.score_total, "factors": []}
    return {
        "id": opp.id,
        "company": opp.company,
        "role_title": opp.role_title,
        "location": opp.location,
        "estimated_compensation": opp.estimated_compensation,
        "source": opp.source,
        "source_url": opp.source_url,
        "description": opp.description,
        "status": opp.status,
        "notes": opp.notes,
        "external_id": opp.external_id,
        "discovered_at": opp.discovered_at,
        "score_total": opp.score_total,
        "score_breakdown": breakdown,
        "score_explanation": opp.score_explanation,
    }


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ready"}


@router.get("/profile", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db)):
    p = db.query(UserProfile).first()
    if not p:
        raise HTTPException(404, "Profile not found")
    return p


@router.put("/profile", response_model=ProfileOut)
def update_profile(payload: ProfileBase, db: Session = Depends(get_db)):
    p = db.query(UserProfile).first()
    if not p:
        p = UserProfile(**payload.model_dump())
        db.add(p)
    else:
        for k, v in payload.model_dump().items():
            setattr(p, k, v)
    db.commit()
    EventBus.bump("profile_update")
    return p


@router.get("/opportunities", response_model=list[OpportunityOut])
def list_opportunities(
    signal_type: str | None = None,
    status: str | None = None,
    sort_by: str = Query(default="score_total"),
    sort_dir: str = Query(default="desc"),
    db: Session = Depends(get_db),
):
    q = db.query(Opportunity)
    if sort_by not in {"score_total", "discovered_at"}:
        sort_by = "score_total"
    if sort_dir not in {"asc", "desc"}:
        sort_dir = "desc"
    if status:
        q = q.filter(Opportunity.status == status)
    if signal_type:
        q = q.join(Signal, Signal.opportunity_id == Opportunity.id).filter(Signal.signal_type == signal_type).distinct()
    order_col = Opportunity.discovered_at if sort_by == "discovered_at" else Opportunity.score_total
    q = q.order_by(order_col.asc() if sort_dir == "asc" else order_col.desc())
    return [_opp_out(o) for o in q.all()]


@router.get("/opportunities/{opp_id}", response_model=OpportunityOut)
def get_opportunity(opp_id: int, db: Session = Depends(get_db)):
    opp = db.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(404, "Not found")
    return _opp_out(opp)


@router.post("/opportunities", response_model=OpportunityOut)
def create_opportunity(payload: OpportunityIn, db: Session = Depends(get_db)):
    opp = Opportunity(**payload.model_dump())
    db.add(opp)
    db.flush()
    _ensure_company_link(db, opp)
    profile = db.query(UserProfile).first()
    if profile:
        score_opportunity(db, opp, profile)
    db.commit()
    generate_opportunity_signals(db, profile)
    refresh_recommendations(db)
    EventBus.bump("opportunity_created")
    return _opp_out(opp)


@router.patch("/opportunities/{opp_id}/status", response_model=OpportunityOut)
def update_opp_status(opp_id: int, status: str, db: Session = Depends(get_db)):
    opp = db.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(404, "Not found")
    opp.status = status
    db.commit()
    refresh_recommendations(db)
    EventBus.bump("opportunity_status")
    return _opp_out(opp)


@router.get("/opportunities/{opp_id}/signals", response_model=list[SignalOut])
def opportunity_signals(opp_id: int, db: Session = Depends(get_db)):
    return db.query(Signal).filter(Signal.opportunity_id == opp_id).order_by(Signal.created_at.desc()).all()


@router.post("/ingest/connectors")
def ingest_connectors(db: Session = Depends(get_db)):
    rows = []
    for c in CONNECTORS:
        rows.extend(c.fetch())
    created = persist_items(db, rows)
    for opp in created:
        _ensure_company_link(db, opp)
    profile = db.query(UserProfile).first()
    if profile:
        for opp in created:
            score_opportunity(db, opp, profile)
        db.commit()
    signal_count = generate_opportunity_signals(db, profile)
    recommendation_count = refresh_recommendations(db)
    EventBus.bump("ingest_connectors")
    return {"created": len(created), "signals": signal_count, "recommendations": recommendation_count}


@router.post("/ingest/csv")
async def ingest_csv(file: UploadFile, db: Session = Depends(get_db)):
    content = (await file.read()).decode()
    rows = parse_csv(content)
    created = persist_items(db, rows)
    for opp in created:
        _ensure_company_link(db, opp)
    profile = db.query(UserProfile).first()
    if profile:
        for opp in created:
            score_opportunity(db, opp, profile)
        db.commit()
    signal_count = generate_opportunity_signals(db, profile)
    recommendation_count = refresh_recommendations(db)
    EventBus.bump("ingest_csv")
    return {"created": len(created), "signals": signal_count, "recommendations": recommendation_count}


@router.get("/admin/connectors")
def list_connectors():
    return registry.list()


@router.post("/admin/connectors/{connector_name}/run")
def run_connector(connector_name: str, payload: dict | None = None, db: Session = Depends(get_db)):
    run = JobRun(job_name=f"connector:{connector_name}", status="running", started_at=datetime.utcnow(), summary="")
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        result, errors = ingest_connector(db, connector_name, payload or {})
        run.status = "success"
        run.processed_count = result.created + result.updated
        run.summary = (
            f"fetched={result.fetched} created={result.created} "
            f"updated={result.updated} skipped={result.skipped} errored={result.errored}"
        )
        if errors:
            run.summary += f" errors={';'.join(errors[:2])}"
        run.finished_at = datetime.utcnow()
        db.commit()
        return {"connector": connector_name, "result": result.__dict__, "errors": errors}
    except Exception as exc:
        run.status = "failed"
        run.summary = str(exc)
        run.finished_at = datetime.utcnow()
        db.commit()
        raise


@router.get("/admin/connectors/outcomes")
def connector_outcomes(db: Session = Depends(get_db)):
    return (
        db.query(JobRun)
        .filter(JobRun.job_name.like("connector:%"))
        .order_by(JobRun.started_at.desc())
        .limit(50)
        .all()
    )


@router.post("/rescore")
def rescore(db: Session = Depends(get_db)):
    profile = db.query(UserProfile).first()
    if not profile:
        raise HTTPException(400, "profile required")
    count = 0
    for opp in db.query(Opportunity).all():
        score_opportunity(db, opp, profile)
        count += 1
    db.commit()
    signal_count = generate_opportunity_signals(db, profile)
    recommendation_count = refresh_recommendations(db)
    EventBus.bump("rescore")
    return {"status": "done", "rescored": count, "signals": signal_count, "recommendations": recommendation_count}


@router.get("/signals", response_model=list[SignalOut])
def list_signals(signal_type: str | None = None, severity: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Signal)
    if signal_type:
        q = q.filter(Signal.signal_type == signal_type)
    if severity:
        q = q.filter(Signal.severity == severity)
    return q.order_by(Signal.created_at.desc()).all()


@router.get("/company-signals", response_model=list[CompanySignalOut])
def list_company_signals(company_id: int | None = None, signal_type: str | None = None, db: Session = Depends(get_db)):
    q = db.query(CompanySignal)
    if company_id is not None:
        q = q.filter(CompanySignal.company_id == company_id)
    if signal_type:
        q = q.filter(CompanySignal.signal_type == signal_type)
    return q.order_by(CompanySignal.detected_at.desc()).all()


@router.post("/ingest/company-intelligence")
def ingest_company_intelligence(db: Session = Depends(get_db)):
    created = run_company_intelligence_connector(db)
    recommendation_count = refresh_recommendations(db)
    EventBus.bump("company_intelligence_ingest")
    return {"created": created, "recommendations": recommendation_count}




@router.get("/recommendations", response_model=list[RecommendationOut])
def list_recommendations(
    recommendation_type: str | None = None,
    status: str | None = None,
    urgency: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Recommendation)
    if recommendation_type:
        q = q.filter(Recommendation.recommendation_type == recommendation_type)
    if status:
        q = q.filter(Recommendation.status == status)
    if urgency:
        q = q.filter(Recommendation.urgency == urgency)
    return q.order_by(Recommendation.decision_score.desc(), Recommendation.created_at.desc()).all()


@router.post("/recommendations/refresh")
def refresh_decisions(db: Session = Depends(get_db)):
    created = refresh_recommendations(db)
    EventBus.bump("recommendations_refresh")
    return {"created": created}


@router.get("/recommendations/{recommendation_id}", response_model=RecommendationOut)
def recommendation_detail(recommendation_id: int, db: Session = Depends(get_db)):
    rec = db.get(Recommendation, recommendation_id)
    if not rec:
        raise HTTPException(404, "Not found")
    return rec


@router.get("/companies", response_model=list[CompanyOut])
def companies(db: Session = Depends(get_db)):
    return db.query(Company).all()


@router.post("/companies", response_model=CompanyOut)
def create_company(payload: CompanyIn, db: Session = Depends(get_db)):
    c = Company(**payload.model_dump())
    db.add(c)
    db.commit()
    EventBus.bump("company_create")
    return c


@router.get("/companies/{company_id}/signals", response_model=list[CompanySignalOut])
def company_signals(company_id: int, db: Session = Depends(get_db)):
    return db.query(CompanySignal).filter(CompanySignal.company_id == company_id).order_by(CompanySignal.detected_at.desc()).all()


@router.get("/nodes", response_model=list[PersonNodeOut])
def nodes(db: Session = Depends(get_db)):
    return db.query(PersonNode).all()


@router.post("/nodes", response_model=PersonNodeOut)
def create_node(payload: PersonNodeIn, db: Session = Depends(get_db)):
    n = PersonNode(**payload.model_dump())
    db.add(n)
    db.commit()
    EventBus.bump("node_create")
    return n


@router.get("/opportunities/{opp_id}/network-recommendations", response_model=list[PersonNodeOut])
def network_recos(opp_id: int, db: Session = Depends(get_db)):
    opp = db.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(404, "Not found")
    q = db.query(PersonNode)
    if opp.company_id:
        q = q.filter(PersonNode.company_id == opp.company_id)
    return (
        q.order_by(
            (PersonNode.influence_score + PersonNode.accessibility_score + PersonNode.relationship_strength).desc()
        )
        .limit(3)
        .all()
    )


@router.get("/plans", response_model=list[ActionPlanOut])
def plans(db: Session = Depends(get_db)):
    return db.query(ActionPlanItem).all()


@router.post("/plans/regenerate", response_model=list[ActionPlanOut])
def regenerate_plans(db: Session = Depends(get_db)):
    out = generate_plan(db)
    EventBus.bump("plan_regen")
    return out


@router.patch("/plans/{plan_id}/toggle", response_model=ActionPlanOut)
def toggle_plan(plan_id: int, db: Session = Depends(get_db)):
    p = db.get(ActionPlanItem, plan_id)
    if not p:
        raise HTTPException(404, "Not found")
    p.completed = not p.completed
    db.commit()
    EventBus.bump("plan_toggle")
    return p


@router.get("/settings/weights")
def get_scoring_weights(db: Session = Depends(get_db)):
    return get_weights(db)


@router.put("/settings/weights")
def set_weights(payload: dict[str, float], db: Session = Depends(get_db)):
    db.query(ScoringWeight).delete()
    for k, v in payload.items():
        db.add(ScoringWeight(key=k, value=v))
    db.commit()
    EventBus.bump("weights_update")
    return get_weights(db)


@router.get("/settings/flags")
def get_flags(db: Session = Depends(get_db)):
    return {f.key: f.enabled for f in db.query(FeatureFlag).all()}


@router.put("/settings/flags")
def set_flags(payload: dict[str, bool], db: Session = Depends(get_db)):
    db.query(FeatureFlag).delete()
    for k, v in payload.items():
        db.add(FeatureFlag(key=k, enabled=v))
    db.commit()
    EventBus.bump("flags_update")
    return payload


@router.get("/admin/jobs/runs", response_model=list[JobRunOut])
def job_runs(db: Session = Depends(get_db)):
    return db.query(JobRun).order_by(JobRun.started_at.desc()).limit(50).all()


@router.post("/admin/jobs/{job_name}")
def run_job(job_name: str):
    jobs = {"ingest": ingest_job, "rescore": rescore_job, "strategy": strategy_job, "stale": stale_check_job, "company_intelligence": company_intelligence_job, "decision_engine": decision_engine_job}
    if job_name not in jobs:
        raise HTTPException(404, "unknown job")
    jobs[job_name]()
    return {"ran": job_name}


@router.get("/events/stream")
async def event_stream():
    async def gen():
        last = -1
        yield "retry: 3000\n\n"
        while True:
            if EventBus.version != last:
                last = EventBus.version
                data = {"version": EventBus.version, "event": EventBus.last_event, "updated_at": EventBus.updated_at}
                yield f"id: {EventBus.version}\ndata: {json.dumps(data)}\n\n"
            else:
                yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})
