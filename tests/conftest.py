import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/airuntime_test"
)
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
os.environ.setdefault("DEBUG", "true")
os.environ["S3_ENDPOINT_URL"] = ""
os.environ["S3_PUBLIC_ENDPOINT_URL"] = ""
os.environ.setdefault("S3_ACCESS_KEY", "testing")
os.environ.setdefault("S3_SECRET_KEY", "testing")
os.environ.setdefault("S3_BUCKET", "airuntime-files-test")

import src.db.models  # noqa: F401
from src.db.session import Base, get_db
from src.main import app
from src.services import storage as storage_module
from src.services.storage import storage_service

TEST_DATABASE_URL = os.environ["DATABASE_URL"]
engine_kwargs = {"pool_pre_ping": True}
if TEST_DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update(
        {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }
    )
engine = create_engine(TEST_DATABASE_URL, **engine_kwargs)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


def auth_tokens(client: TestClient, email: str) -> dict[str, str]:
    issued = client.post("/api/v1/auth/request-code", json={"email": email})
    assert issued.status_code == 200
    code = issued.json().get("dev_code")
    assert code
    verified = client.post("/api/v1/auth/verify-code", json={"email": email, "code": code})
    assert verified.status_code == 200
    tokens = verified.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture(scope="session")
def ensure_tables() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _no_startup_run_recovery(monkeypatch: pytest.MonkeyPatch) -> None:
    """main.py's lifespan sweeps for crash-stranded orchestration runs and relaunches them.
    That is correct in production and wrong in tests: every TestClient(app) would fire it
    against the shared test database on its own connection - outside this test's rolled-back
    transaction - and start background work for rows other tests created. Tests that want to
    exercise the sweep call engine.recover_stranded_runs() directly (see
    TestRestartRecoverySweep)."""
    from src.services.orchestration import engine as orchestration_engine

    monkeypatch.setattr(orchestration_engine, "recover_stranded_runs", lambda *a, **k: 0)


@pytest.fixture(autouse=True)
def mock_s3() -> Generator[None, None, None]:
    storage_module._internal_client.cache_clear()
    storage_module._public_client.cache_clear()
    with mock_aws():
        storage_service.ensure_bucket()
        yield
    storage_module._internal_client.cache_clear()
    storage_module._public_client.cache_clear()


@pytest.fixture()
def db(ensure_tables: None) -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
