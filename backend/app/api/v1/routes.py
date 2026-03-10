import asyncio
import hashlib
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
from app.schemas.profile import ProfileBase, ProfileOut
from app.schemas.opportunity import OpportunityIn, OpportunityOut
from app.schemas.network import CompanyIn, CompanyOut, PersonNodeIn, PersonNodeOut
from app.schemas.strategy import ActionPlanOut
from app.schemas.signal import SignalOut, JobRunOut
from app.services.scoring import score_opportunity, get_weights
from app.services.ingestion import CONNECTORS, parse_csv, persist_items, connector_registry, CSVConnector, RecruiterLeadsConnector, RSSFeedConnector, GreenhouseConnector
from app.services.strategy import generate_plan
from app.services.signals import generate_opportunity_signals
from app.services.events import EventBus
from app.jobs.scheduler import ingest_job, rescore_job, strategy_job, stale_check_job

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
    data = payload.model_dump()
    raw = f"{data.get('source','manual')}|{data.get('source_url','')}|{data.get('company','')}|{data.get('role_title','')}|{data.get('location','')}"
    data["ingestion_key"] = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    data["external_id"] = data.get("source_url", "")
    opp = Opportunity(**data)
    db.add(opp)
    db.flush()
    _ensure_company_link(db, opp)
    profile = db.query(UserProfile).first()
    if profile:
        score_opportunity(db, opp, profile)
    db.commit()
    generate_opportunity_signals(db, profile)
    EventBus.bump("opportunity_created")
    return _opp_out(opp)


@router.patch("/opportunities/{opp_id}/status", response_model=OpportunityOut)
def update_opp_status(opp_id: int, status: str, db: Session = Depends(get_db)):
    opp = db.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(404, "Not found")
    opp.status = status
    db.commit()
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
    created, stats = persist_items(db, rows)
    profile = db.query(UserProfile).first()
    if profile:
        for opp in created:
            score_opportunity(db, opp, profile)
        db.commit()
    signal_count = generate_opportunity_signals(db, profile)
    EventBus.bump("ingest_connectors")
    return {"created": stats["created"], "updated": stats["updated"], "skipped": stats["skipped"], "signals": signal_count}


@router.post("/ingest/csv")
async def ingest_csv(file: UploadFile, db: Session = Depends(get_db)):
    content = (await file.read()).decode()
    rows = parse_csv(content)
    created, stats = persist_items(db, rows)
    profile = db.query(UserProfile).first()
    if profile:
        for opp in created:
            score_opportunity(db, opp, profile)
        db.commit()
    signal_count = generate_opportunity_signals(db, profile)
    EventBus.bump("ingest_csv")
    return {"created": stats["created"], "updated": stats["updated"], "skipped": stats["skipped"], "signals": signal_count}


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
    EventBus.bump("rescore")
    return {"status": "done", "rescored": count, "signals": signal_count}


@router.get("/signals", response_model=list[SignalOut])
def list_signals(signal_type: str | None = None, severity: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Signal)
    if signal_type:
        q = q.filter(Signal.signal_type == signal_type)
    if severity:
        q = q.filter(Signal.severity == severity)
    return q.order_by(Signal.created_at.desc()).all()


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




@router.get("/admin/connectors")
def list_connectors():
    return {"connectors": sorted(connector_registry().keys())}


@router.post("/admin/connectors/{name}/run")
def run_connector(name: str, payload: dict | None = None, db: Session = Depends(get_db)):
    payload = payload or {}
    if name == "csv":
        connector = CSVConnector(payload.get("content", ""), source_name=payload.get("source", "csv"))
    elif name == "recruiter_leads":
        connector = RecruiterLeadsConnector(payload.get("content", ""))
    elif name == "rss_feed":
        connector = RSSFeedConnector(payload.get("feed_url", ""))
    elif name == "company_careers":
        connector = GreenhouseConnector(payload.get("company", "Unknown Co"), payload.get("board_token", ""))
    else:
        preset = connector_registry().get(name)
        if not preset:
            raise HTTPException(404, "unknown connector")
        connector = preset

    rows = connector.fetch()
    created, stats = persist_items(db, rows)
    profile = db.query(UserProfile).first()
    if profile:
        for opp in created:
            score_opportunity(db, opp, profile)
        db.commit()
    signal_count = generate_opportunity_signals(db, profile)
    EventBus.bump(f"connector:{name}")
    return {"connector": name, "fetched": len(rows), **stats, "signals": signal_count}
@router.get("/admin/jobs/runs", response_model=list[JobRunOut])
def job_runs(db: Session = Depends(get_db)):
    return db.query(JobRun).order_by(JobRun.started_at.desc()).limit(50).all()


@router.post("/admin/jobs/{job_name}")
def run_job(job_name: str):
    jobs = {"ingest": ingest_job, "rescore": rescore_job, "strategy": strategy_job, "stale": stale_check_job}
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
