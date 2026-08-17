from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from us_mediakit.billing.idempotency import is_duplicate_request
from us_mediakit.db.engine import create_db_engine, create_session_factory, init_db
from us_mediakit.db.models import ApiKey, UsageEvent


@pytest.fixture
def session_factory():
    engine = create_db_engine("sqlite:///:memory:")
    init_db(engine)
    return create_session_factory(engine)


def _usage_event(request_id: str) -> UsageEvent:
    return UsageEvent(
        request_id=request_id,
        api_key_id="key-1",
        account_ref="acct-1",
        operation="thumbnail",
        provider=None,
        status="ok",
        occurred_at=datetime.now(timezone.utc),
        bytes_in=1000,
        bytes_out=500,
        credits=3.0,
        credits_table_version=1,
        external_cost_micros=None,
        duration_ms=42,
    )


def test_api_key_roundtrip(session_factory):
    with session_factory() as session:
        session.add(
            ApiKey(
                id="key-1",
                account_ref="acct-1",
                key_prefix="usmk_abc",
                key_hash="hash",
                label="Test-Key",
                status="active",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

    with session_factory() as session:
        key = session.get(ApiKey, "key-1")
        assert key is not None
        assert key.account_ref == "acct-1"
        assert key.status == "active"


def test_usage_event_request_id_is_unique(session_factory):
    with session_factory() as session:
        session.add(_usage_event("req-1"))
        session.commit()

        session.add(_usage_event("req-1"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_is_duplicate_request(session_factory):
    with session_factory() as session:
        assert is_duplicate_request(session, "req-1") is False

        session.add(_usage_event("req-1"))
        session.commit()

        assert is_duplicate_request(session, "req-1") is True
        assert is_duplicate_request(session, "req-2") is False
