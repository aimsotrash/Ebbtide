import hashlib
import io

import pytest

from intelligence.embeddings import provider


def test_model_files_are_verified_and_never_refetched(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    body = b"model bytes"
    calls = []

    def urlopen(url, timeout):
        calls.append(url)
        return io.BytesIO(body)

    monkeypatch.setattr(provider.urllib.request, "urlopen", urlopen)

    with pytest.raises(RuntimeError):  # a tampered or truncated download is refused
        provider._fetch("tokenizer.json", "0" * 64)
    assert not (provider._cache_dir() / "tokenizer.json").exists()
    assert not list(provider._cache_dir().rglob("*.partial"))

    path = provider._fetch("tokenizer.json", hashlib.sha256(body).hexdigest())
    assert path.read_bytes() == body
    assert provider.REVISION in calls[-1]  # always the pinned revision

    provider._fetch("tokenizer.json", hashlib.sha256(body).hexdigest())
    assert len(calls) == 2  # the verified copy is reused: no third download
