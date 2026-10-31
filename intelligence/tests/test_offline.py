import os

from intelligence.embeddings.provider import MODEL_NAME, REVISION, _offline_if_cached


def test_offline_only_once_the_model_is_fully_cached(tmp_path, monkeypatch):
    env = {"HF_HUB_CACHE": str(tmp_path)}
    monkeypatch.setattr(os, "environ", env)  # a private environment, restored after the test
    snapshot = tmp_path / f"models--{MODEL_NAME.replace('/', '--')}" / "snapshots" / REVISION
    snapshot.mkdir(parents=True)
    (snapshot / "modules.json").write_text("[]")

    _offline_if_cached()  # weights still downloading: a first run must stay online
    assert "HF_HUB_OFFLINE" not in env

    (snapshot / "model.safetensors").write_bytes(b"")
    _offline_if_cached()
    assert env["HF_HUB_OFFLINE"] == "1"
