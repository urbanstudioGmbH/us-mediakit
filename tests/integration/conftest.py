from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from us_mediakit.api.app import create_app
from us_mediakit.api.deps import generate_api_key, get_session
from us_mediakit.db.engine import create_db_engine, create_session_factory, init_db
from us_mediakit.db.models import ApiKey


@pytest.fixture
def session_factory(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    return create_session_factory(engine)


@pytest.fixture
def client(session_factory, monkeypatch):
    monkeypatch.setenv("USMEDIAKIT_ADMIN_TOKEN", "test-admin-token")

    app = create_app()

    def override_get_session():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


@pytest.fixture
def raw_api_key(session_factory) -> str:
    generated = generate_api_key()
    with session_factory() as session:
        session.add(
            ApiKey(
                id=generated.key_prefix,
                account_ref="acct-1",
                key_prefix=generated.key_prefix,
                key_hash=generated.key_hash,
                label="Test-Key",
                status="active",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
    return generated.raw_key
