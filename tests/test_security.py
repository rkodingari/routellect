from routellect.security import TokenBucketLimiter


def test_token_bucket_limits_and_refills() -> None:
    now = [100.0]
    limiter = TokenBucketLimiter(2, clock=lambda: now[0])
    assert limiter.allow("client") == (True, 0)
    assert limiter.allow("client") == (True, 0)
    allowed, retry_after = limiter.allow("client")
    assert allowed is False
    assert retry_after == 30
    assert limiter.allow("other") == (True, 0)

    now[0] += 30
    assert limiter.allow("client") == (True, 0)
    limiter.reset()
    assert limiter.allow("client") == (True, 0)


def test_token_bucket_rejects_invalid_capacity() -> None:
    try:
        TokenBucketLimiter(0)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("invalid capacity should fail")
