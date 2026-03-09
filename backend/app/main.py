from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.api.v1.routes import router as v1_router
from app.jobs.scheduler import start_scheduler, stop_scheduler
from app.db.session import SessionLocal
from app.db.seed import seed_data

settings = get_settings()
setup_logging()
app = FastAPI(title=settings.app_name)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(v1_router, prefix=settings.api_prefix)


@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()
    start_scheduler()


@app.on_event("shutdown")
def shutdown_event():
    stop_scheduler()
