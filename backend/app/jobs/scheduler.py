from datetime import datetime
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.services.ingestion import CONNECTORS, persist_items
from app.services.ingestion import ingest_connector
from app.services.scoring import score_opportunity
from app.services.strategy import generate_plan
from app.services.signals import generate_opportunity_signals
from app.services.company_intelligence import run_company_intelligence_connector
from app.models.opportunity import Opportunity
from app.models.profile import UserProfile
from app.models.job import JobRun
from app.services.events import EventBus
from app.services.decision_engine import refresh_recommendations

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def _record_job_start(db: Session, job_name: str) -> JobRun:
    jr = JobRun(job_name=job_name, status="running", started_at=datetime.utcnow(), summary="")
    db.add(jr)
    db.commit()
    db.refresh(jr)
    return jr


def _record_job_end(db: Session, run: JobRun, status: str, processed: int, summary: str) -> None:
    run.status = status
    run.processed_count = processed
    run.summary = summary
    run.finished_at = datetime.utcnow()
    db.commit()


def run_connector_job(connector_name: str | None = None):
    db: Session = SessionLocal()
    target = connector_name or "company_careers"
    run = _record_job_start(db, f"connector:{target}")
    try:
        result, errors = ingest_connector(db, target)
        summary = f"fetched={result.fetched} created={result.created} updated={result.updated} skipped={result.skipped} errored={result.errored}"
        if errors:
            summary += f" errors={';'.join(errors[:2])}"
        _record_job_end(db, run, "success", result.created + result.updated, summary)
    except Exception as exc:
        logger.exception("connector_job_failed", extra={"connector": target})
        _record_job_end(db, run, "failed", 0, str(exc))
        raise
    finally:
        db.close()


def ingest_job():
    db: Session = SessionLocal()
    run = _record_job_start(db, "ingest")
    try:
        rows = []
        for c in CONNECTORS:
            connector_rows = c.fetch()
            rows.extend(connector_rows)
            logger.info("connector_fetch", extra={"connector": c.source, "count": len(connector_rows)})
        created, stats = persist_items(db, rows)
        profile = db.query(UserProfile).first()
        for opp in created:
            if profile:
                score_opportunity(db, opp, profile)
        db.commit()
        generated_signals = generate_opportunity_signals(db, profile)
        _record_job_end(db, run, "success", len(created), f"fetched={len(rows)} created={stats['created']} updated={stats['updated']} skipped={stats['skipped']} signals={generated_signals}")
        totals = {"fetched": 0, "created": 0, "updated": 0, "errored": 0}
        for c in registry.list():
            if c["name"] == "csv":
                continue
            result, _ = ingest_connector(db, c["name"])
            totals["fetched"] += result.fetched
            totals["created"] += result.created
            totals["updated"] += result.updated
            totals["errored"] += result.errored
        _record_job_end(
            db,
            run,
            "success",
            totals["created"] + totals["updated"],
            f"fetched={totals['fetched']} created={totals['created']} updated={totals['updated']} errored={totals['errored']}",
        )
        EventBus.bump("ingest")
    except Exception as exc:
        logger.exception("ingest_job_failed")
        _record_job_end(db, run, "failed", 0, str(exc))
        raise
    finally:
        db.close()


def rescore_job():
    db: Session = SessionLocal()
    run = _record_job_start(db, "rescore")
    try:
        profile = db.query(UserProfile).first()
        if not profile:
            _record_job_end(db, run, "success", 0, "no profile present")
            return
        count = 0
        for opp in db.query(Opportunity).all():
            score_opportunity(db, opp, profile)
            count += 1
        db.commit()
        generated_signals = generate_opportunity_signals(db, profile)
        _record_job_end(db, run, "success", count, f"rescored={count} signals={generated_signals}")
        EventBus.bump("rescore")
    except Exception as exc:
        logger.exception("rescore_job_failed")
        _record_job_end(db, run, "failed", 0, str(exc))
        raise
    finally:
        db.close()


def strategy_job():
    db: Session = SessionLocal()
    run = _record_job_start(db, "strategy")
    try:
        plans = generate_plan(db)
        _record_job_end(db, run, "success", len(plans), f"generated_plans={len(plans)}")
        EventBus.bump("strategy")
    except Exception as exc:
        logger.exception("strategy_job_failed")
        _record_job_end(db, run, "failed", 0, str(exc))
        raise
    finally:
        db.close()


def stale_check_job():
    db: Session = SessionLocal()
    run = _record_job_start(db, "stale")
    try:
        profile = db.query(UserProfile).first()
        generated_signals = generate_opportunity_signals(db, profile)
        _record_job_end(db, run, "success", generated_signals, f"generated_signals={generated_signals}")
        EventBus.bump("stale_check")
    except Exception as exc:
        _record_job_end(db, run, "failed", 0, str(exc))
        raise
    finally:
        db.close()




def company_intelligence_job():
    db: Session = SessionLocal()
    run = _record_job_start(db, "company_intelligence")
    try:
        created = run_company_intelligence_connector(db)
        _record_job_end(db, run, "success", created, f"company_signals={created}")
        EventBus.bump("company_intelligence")
    except Exception as exc:
        logger.exception("company_intelligence_job_failed")
        _record_job_end(db, run, "failed", 0, str(exc))
        raise
    finally:
        db.close()



def decision_engine_job():
    db: Session = SessionLocal()
    run = _record_job_start(db, "decision_engine")
    try:
        created = refresh_recommendations(db)
        _record_job_end(db, run, "success", created, f"recommendations={created}")
        EventBus.bump("decision_engine")
    except Exception as exc:
        logger.exception("decision_engine_job_failed")
        _record_job_end(db, run, "failed", 0, str(exc))
        raise
    finally:
        db.close()


def start_scheduler():
    if scheduler.running:
        return
    scheduler.add_job(ingest_job, "interval", minutes=30, id="ingest", replace_existing=True)
    scheduler.add_job(rescore_job, "interval", minutes=20, id="rescore", replace_existing=True)
    scheduler.add_job(strategy_job, "interval", minutes=60, id="strategy", replace_existing=True)
    scheduler.add_job(stale_check_job, "interval", hours=6, id="stale", replace_existing=True)
    scheduler.add_job(company_intelligence_job, "interval", minutes=45, id="company_intelligence", replace_existing=True)
    scheduler.add_job(decision_engine_job, "interval", minutes=30, id="decision_engine", replace_existing=True)
    scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
