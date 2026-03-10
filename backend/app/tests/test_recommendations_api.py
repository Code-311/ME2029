from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.api.v1.routes import router
from app.db.session import get_db
from app.models.base import Base


def test_recommendations_endpoints_exist():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(router, prefix='/api/v1')
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    resp = client.get('/api/v1/recommendations')
    assert resp.status_code == 200

    refresh = client.post('/api/v1/recommendations/refresh')
    assert refresh.status_code == 200
