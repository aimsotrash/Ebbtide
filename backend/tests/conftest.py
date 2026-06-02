"""Pytest config. Each test function gets a fresh SQLite DB (no cross-test pollution)
and skips the heavy SentenceTransformer warm-up. Env vars must be set before importing
`main` so the module-level config picks them up."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add backend/ to path so `from main import app` works, and the repo root so the
# sibling `intelligence/` package is importable.
BACKEND_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT.parent))

# Set env vars BEFORE importing the app. The DORY_DB_PATH value here is a
# placeholder; the per-test client fixture rewrites it.
_BOOTSTRAP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_BOOTSTRAP_DB.close()
os.environ["DORY_DB_PATH"] = _BOOTSTRAP_DB.name
os.environ["DORY_ENV"] = "dev"
os.environ["DORY_SKIP_WARMUP"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Per-test TestClient with an isolated SQLite file. Avoids cross-test
    lock contention from the previous test's WAL files."""
    db_file = tmp_path / "dory_test.db"
    monkeypatch.setenv("DORY_DB_PATH", str(db_file))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def register_user(client):
    """Factory that registers a unique user and returns (user_dict, access_token)."""
    counter = {"i": 0}

    def _register(prefix: str = "u"):
        counter["i"] += 1
        suffix = f"{prefix}_{os.urandom(4).hex()}_{counter['i']}"
        body = {
            "name": f"User {suffix}",
            "email": f"{suffix}@dory.test",
            "password": "test-password-123",
        }
        res = client.post("/api/auth/register", json=body)
        assert res.status_code == 200, res.text
        data = res.json()
        return data, data["access_token"]

    return _register
