import pytest

from us_mediakit.billing.rate_limit import (
    ConcurrencyLimiter,
    ConcurrencyLimitExceeded,
    CreditsRateLimiter,
)


def test_credits_rate_limiter_allows_within_limit():
    limiter = CreditsRateLimiter(window_seconds=60)
    assert limiter.check_and_record("acct-1", 10, limit_per_window=100) is True
    assert limiter.check_and_record("acct-1", 50, limit_per_window=100) is True


def test_credits_rate_limiter_rejects_over_limit():
    limiter = CreditsRateLimiter(window_seconds=60)
    assert limiter.check_and_record("acct-1", 60, limit_per_window=100) is True
    assert limiter.check_and_record("acct-1", 60, limit_per_window=100) is False


def test_credits_rate_limiter_expires_old_entries():
    limiter = CreditsRateLimiter(window_seconds=-1)  # sofort abgelaufenes Fenster
    assert limiter.check_and_record("acct-1", 90, limit_per_window=100) is True
    assert limiter.check_and_record("acct-1", 90, limit_per_window=100) is True  # altes Fenster verfallen


def test_credits_rate_limiter_tracks_accounts_independently():
    limiter = CreditsRateLimiter(window_seconds=60)
    assert limiter.check_and_record("acct-1", 100, limit_per_window=100) is True
    assert limiter.check_and_record("acct-2", 100, limit_per_window=100) is True


def test_concurrency_limiter_blocks_when_full():
    limiter = ConcurrencyLimiter(max_concurrent=1)
    with limiter, pytest.raises(ConcurrencyLimitExceeded), limiter:
        pass


def test_concurrency_limiter_releases_after_context():
    limiter = ConcurrencyLimiter(max_concurrent=1)
    with limiter:
        pass
    with limiter:
        pass  # zweiter Durchlauf darf nicht blockieren, da der erste freigegeben wurde
