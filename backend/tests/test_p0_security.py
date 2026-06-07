"""P0 security/deployment hardening tests.

Covers the public-deployment-safety objectives:
  1. JWT secret safety  — prod fails fast, dev uses an ephemeral (non-hardcoded) secret.
  3. Demo account       — disabled outside dev; usable in dev; no shared prod creds.
  4. CORS               — explicit allow-list, dev-only LAN regex, no wildcard in prod.
  7. Storage backup     — backup utility produces a restorable snapshot.
  8. Dangerous defaults — the old hardcoded dev secret is gone.

These run at the function level with monkeypatched env where they need a non-dev
profile, so they never destabilise the shared dev TestClient fixture.
"""

import re
import sqlite3
import tarfile

import pytest
from fastapi.testclient import TestClient

import routers.deps as deps
import database.db as db
import routers.auth as auth
from main import app, resolve_cors_kwargs

OLD_HARDCODED_SECRET = "dory-dev-only-secret-do-not-deploy"


# ── 1 & 8: JWT secret safety ──────────────────────────────────────────────────

def test_production_startup_fails_without_jwt_secret(monkeypatch):
    """The startup guard must raise (fail fast at boot) in a non-dev env with no secret."""
    monkeypatch.setenv("DORY_ENV", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError) as exc:
        deps.require_secret_configured()
    assert "JWT_SECRET is required" in str(exc.value)
    assert "token_urlsafe" in str(exc.value)  # message is actionable


def test_production_startup_ok_with_jwt_secret(monkeypatch):
    monkeypatch.setenv("DORY_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "a-real-production-secret-value-1234567890")
    deps.require_secret_configured()  # must not raise


def test_dev_startup_ok_without_secret(monkeypatch):
    monkeypatch.setenv("DORY_ENV", "dev")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    deps.require_secret_configured()  # dev is allowed to run secret-less


def test_dev_generates_safe_ephemeral_secret(monkeypatch):
    """Dev with no JWT_SECRET must mint a random per-process secret — never the
    old hardcoded string — and reuse it within the process."""
    monkeypatch.setenv("DORY_ENV", "dev")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setattr(deps, "_DEV_EPHEMERAL_SECRET", None)

    s1 = deps._get_secret()
    assert s1 != OLD_HARDCODED_SECRET
    assert len(s1) >= 32  # token_urlsafe(48) -> ~64 chars
    s2 = deps._get_secret()
    assert s1 == s2, "ephemeral secret must be stable within a process"


def test_get_secret_prefers_explicit_env_secret(monkeypatch):
    monkeypatch.setenv("DORY_ENV", "dev")
    monkeypatch.setenv("JWT_SECRET", "explicit-secret")
    assert deps._get_secret() == "explicit-secret"


def test_get_secret_raises_in_prod_without_secret(monkeypatch):
    monkeypatch.setenv("DORY_ENV", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setattr(deps, "_DEV_EPHEMERAL_SECRET", None)
    with pytest.raises(RuntimeError):
        deps._get_secret()


def test_no_hardcoded_secret_in_source():
    """Defence in depth: the old hardcoded secret must not reappear in deps.py."""
    import inspect
    source = inspect.getsource(deps)
    assert OLD_HARDCODED_SECRET not in source


# ── 3: Demo account security ───────────────────────────────────────────────────

def test_demo_user_not_seeded_in_production(monkeypatch, tmp_path):
    monkeypatch.setenv("DORY_ENV", "production")
    monkeypatch.setenv("DORY_DB_PATH", str(tmp_path / "prod.db"))
    db.init_db()
    auth.setup_demo_user()
    assert db.get_user_by_email("demo@dory.md") is None, "no demo/default user in prod"


def test_demo_user_seeded_in_dev(monkeypatch, tmp_path):
    monkeypatch.setenv("DORY_ENV", "dev")
    monkeypatch.setenv("DORY_DB_PATH", str(tmp_path / "dev.db"))
    db.init_db()
    auth.setup_demo_user()
    user = db.get_user_by_email("demo@dory.md")
    assert user is not None
    assert user["password_hash"], "dev demo user has a usable password hash"


def test_demo_login_fails_in_production(monkeypatch, tmp_path):
    """End-to-end: with a prod profile, the shared demo credentials must not log in."""
    monkeypatch.setenv("DORY_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "prod-secret-value-for-this-test-00000000")
    monkeypatch.setenv("DORY_DB_PATH", str(tmp_path / "prod_e2e.db"))
    with TestClient(app) as c:
        res = c.post("/api/auth/login", json={"email": "demo@dory.md", "password": "demo123"})
    assert res.status_code == 401


def test_demo_login_succeeds_in_dev(monkeypatch, tmp_path):
    monkeypatch.setenv("DORY_ENV", "dev")
    monkeypatch.setenv("DORY_DB_PATH", str(tmp_path / "dev_e2e.db"))
    with TestClient(app) as c:
        res = c.post("/api/auth/login", json={"email": "demo@dory.md", "password": "demo123"})
    assert res.status_code == 200


# ── 4: CORS hardening ───────────────────────────────────────────────────────--

def test_cors_explicit_allowlist_wins(monkeypatch):
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://app.dory.md, https://dory.vercel.app")
    monkeypatch.delenv("CORS_ORIGIN_REGEX", raising=False)
    assert resolve_cors_kwargs(env="production") == {
        "allow_origins": ["https://app.dory.md", "https://dory.vercel.app"]
    }


def test_cors_regex_used_when_set(monkeypatch):
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    monkeypatch.setenv("CORS_ORIGIN_REGEX", r"https://app\.dory\.md")
    assert resolve_cors_kwargs(env="production") == {"allow_origin_regex": r"https://app\.dory\.md"}


def test_cors_production_blocks_all_when_unconfigured(monkeypatch):
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    monkeypatch.delenv("CORS_ORIGIN_REGEX", raising=False)
    assert resolve_cors_kwargs(env="production") == {"allow_origins": []}


def test_cors_dev_allows_lan_only_no_wildcard(monkeypatch):
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    monkeypatch.delenv("CORS_ORIGIN_REGEX", raising=False)
    kw = resolve_cors_kwargs(env="dev")
    rx = re.compile(kw["allow_origin_regex"])
    # Allowed: localhost + RFC-1918 LAN.
    assert rx.fullmatch("http://localhost:5173")
    assert rx.fullmatch("http://127.0.0.1:8001")
    assert rx.fullmatch("http://192.168.1.50:5173")
    # Rejected: arbitrary public hosts, vercel wildcard, public IPs.
    assert not rx.fullmatch("https://anything.vercel.app")
    assert not rx.fullmatch("https://evil.example.com")
    assert not rx.fullmatch("http://8.8.8.8")


# ── 7: Storage backup ───────────────────────────────────────────────────────--

def test_backup_creates_restorable_snapshot(tmp_path):
    from scripts.backup import run_backup

    src_db = tmp_path / "src.db"
    conn = sqlite3.connect(str(src_db))
    conn.execute("CREATE TABLE t (id INTEGER, v TEXT)")
    conn.execute("INSERT INTO t VALUES (1, 'hello')")
    conn.commit()
    conn.close()

    chroma = tmp_path / "chroma"
    chroma.mkdir()
    (chroma / "data.bin").write_bytes(b"vectors")

    manifest = run_backup(out_dir=tmp_path / "backups", db_path=src_db, chroma_path=chroma)

    # SQLite snapshot is a valid DB and still holds the row.
    assert manifest["sqlite"]
    restored = sqlite3.connect(manifest["sqlite"])
    assert restored.execute("SELECT v FROM t WHERE id = 1").fetchone()[0] == "hello"
    restored.close()

    # Chroma archive contains the directory contents.
    assert manifest["chroma"]
    with tarfile.open(manifest["chroma"]) as tar:
        assert any(n.endswith("data.bin") for n in tar.getnames())


def test_backup_handles_missing_chroma(tmp_path):
    from scripts.backup import run_backup

    src_db = tmp_path / "src.db"
    conn = sqlite3.connect(str(src_db))
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.commit()
    conn.close()

    manifest = run_backup(out_dir=tmp_path / "b", db_path=src_db, chroma_path=tmp_path / "absent")
    assert manifest["sqlite"]
    assert manifest["chroma"] is None
