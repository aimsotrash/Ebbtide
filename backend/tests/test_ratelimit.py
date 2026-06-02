"""Verify the in-memory rate limiter actually returns 429 past the threshold.

The limiter is inert in dev (so the rest of the suite isn't throttled); here we
force it on with a low limit and prove the gate fires."""

import ratelimit


def test_rate_limit_blocks_after_threshold(client, monkeypatch):
    monkeypatch.setattr(ratelimit, "_enabled", lambda: True)
    monkeypatch.setattr(ratelimit, "_limit", lambda: 3)
    ratelimit._hits.clear()

    # 3 allowed, 4th throttled. Wrong creds (401) still consume the budget,
    # because the limiter runs as a dependency before the handler.
    codes = [
        client.post("/api/auth/login", json={"email": "x@y.z", "password": "nope"}).status_code
        for _ in range(4)
    ]
    assert codes[:3] == [401, 401, 401]
    assert codes[3] == 429


def test_rate_limit_inert_in_dev(client):
    """With the default dev config the limiter must not throttle (regression guard
    so the rest of the suite, which logs in repeatedly, never trips it)."""
    ratelimit._hits.clear()
    codes = [
        client.post("/api/auth/login", json={"email": "x@y.z", "password": "nope"}).status_code
        for _ in range(10)
    ]
    assert all(c == 401 for c in codes)
