"""
all-MiniLM-L6-v2 sentence embeddings through ONNX Runtime.

The same model sentence-transformers runs, at the same pinned revision, reproduced step by
step: its tokenizer cut at 256 tokens, the transformer, mean pooling over real tokens, and
unit-length normalisation. That keeps the install small (no PyTorch) and the vectors the
benchmarks were measured with.

The two model files are downloaded once from Hugging Face into ~/.cache/ebbtide (or
$XDG_CACHE_HOME/ebbtide) and checked against pinned SHA-256 hashes. After that, nothing
here goes online. The model loads lazily, on the first embed; the tests stub the embedder,
so they never load it.
"""

from __future__ import annotations

import hashlib
import os
import urllib.request
from pathlib import Path

import numpy as np

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"  # pinned: a changed upstream repo is never loaded
FILES = {  # path in the model repo -> SHA-256
    "onnx/model.onnx": "6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452",
    "tokenizer.json": "be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037",
}
MAX_TOKENS = 256  # sentence-transformers' max_seq_length for this model: later tokens are never read

_model = None  # (tokenizer, onnxruntime session), once loaded


def _cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "ebbtide" / "models" / MODEL_NAME.replace("/", "--") / REVISION


def _fetch(name: str, sha256: str) -> Path:
    """The verified local copy of one model file, downloading it only if it is missing."""
    path = _cache_dir() / name
    if path.exists():
        return path  # verified before it was moved into place
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    url = f"https://huggingface.co/{MODEL_NAME}/resolve/{REVISION}/{name}"
    digest = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=60) as response, open(partial, "wb") as out:
        while chunk := response.read(1 << 20):
            digest.update(chunk)
            out.write(chunk)
    if digest.hexdigest() != sha256:
        partial.unlink()
        raise RuntimeError(f"{name} from {url} failed its SHA-256 check; nothing was saved")
    partial.rename(path)
    return path


def warm_model() -> None:
    global _model
    if _model is None:
        import onnxruntime  # heavy imports: defer to the first embed
        from tokenizers import Tokenizer

        tokenizer = Tokenizer.from_file(str(_fetch("tokenizer.json", FILES["tokenizer.json"])))
        tokenizer.enable_truncation(MAX_TOKENS)  # the file's own default is 128
        tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")  # to the longest text in a batch
        session = onnxruntime.InferenceSession(
            str(_fetch("onnx/model.onnx", FILES["onnx/model.onnx"])), providers=["CPUExecutionProvider"])
        _model = (tokenizer, session)


def encode(texts: list[str], batch_size: int = 32) -> np.ndarray:
    """Unit-length float32 embeddings, one 384-dim row per text."""
    warm_model()
    tokenizer, session = _model
    rows = []
    for start in range(0, len(texts), batch_size):
        batch = tokenizer.encode_batch(texts[start:start + batch_size])
        ids = np.array([e.ids for e in batch], dtype=np.int64)
        mask = np.array([e.attention_mask for e in batch], dtype=np.int64)
        tokens = session.run(None, {"input_ids": ids, "attention_mask": mask,
                                    "token_type_ids": np.zeros_like(ids)})[0]
        summed = (tokens * mask[:, :, None]).sum(axis=1)
        mean = summed / np.clip(mask.sum(axis=1, keepdims=True), 1, None)
        rows.append(mean / np.clip(np.linalg.norm(mean, axis=1, keepdims=True), 1e-12, None))
    return np.concatenate(rows).astype(np.float32) if rows else np.zeros((0, 384), np.float32)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch-encode a list of strings. Returns a list of 384-dim float vectors."""
    return encode(texts).tolist()


def embed_query(text: str) -> list[float]:
    """Encode a single query string."""
    return encode([text])[0].tolist()


def fits(text: str) -> bool:
    """Whether the model reads all of `text`, rather than only its first 256 tokens."""
    warm_model()
    return not _model[0].encode(text).overflowing
