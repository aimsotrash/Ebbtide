"""
Demo data seeder.

Walks ../brain-backup/ for .md files and ingests them with backdated
timestamps and varied access counts so the Time Machine slider shows
realistic decay across multiple categories.

Usage:
  cd backend
  python seed_demo_data.py

Requires the server's virtualenv to be active so all imports resolve.
"""

import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running from backend/ directory, and make the sibling intelligence/ package importable.
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import init_db, insert_chunk
from intelligence.domain import chunk_text as _chunk_text, complexity_score
from intelligence.embeddings import embed_texts, warm_model
from intelligence.retrieval import add_chunks
from database.db import DEFAULT_USER_ID

BRAIN_BACKUP_DIR = Path(__file__).parent.parent.parent / "brain-backup"
MAX_FILES = 60          # cap to keep demo dataset fast (~200 chunks)
SEED = 42

random.seed(SEED)


def _random_past(min_days: int, max_days: int) -> datetime:
    days = random.randint(min_days, max_days)
    return datetime.now(tz=timezone.utc) - timedelta(days=days)


def _access_count_for_age(created_days_ago: int) -> int:
    """Older notes get fewer reviews — simulates realistic forgetting."""
    if created_days_ago < 30:
        return random.randint(1, 4)
    if created_days_ago < 90:
        return random.randint(0, 2)
    return random.randint(0, 1)


def seed():
    print("Initialising database...")
    init_db()

    print("Loading embedding model (first run may take ~30s)...")
    warm_model()

    md_files = sorted(BRAIN_BACKUP_DIR.rglob("*.md"))[:MAX_FILES]
    if not md_files:
        print(f"No .md files found in {BRAIN_BACKUP_DIR}. Ensure brain-backup repo is present.")
        sys.exit(1)

    print(f"Found {len(md_files)} notes. Seeding...")
    total_chunks = 0

    for md_file in md_files:
        text = md_file.read_text(encoding="utf-8", errors="replace").strip()
        if len(text) < 100:
            continue

        chunks = _chunk_text(text)
        if not chunks:
            continue

        created_days_ago = random.randint(14, 180)
        created_at = _random_past(created_days_ago, created_days_ago)
        access_count = _access_count_for_age(created_days_ago)
        last_accessed = created_at + timedelta(days=random.randint(0, min(created_days_ago, 7)))

        scores = [complexity_score(c) for c in chunks]
        embeddings = embed_texts(chunks)

        chunk_ids = []
        for c, s in zip(chunks, scores):
            cid = insert_chunk(
                content=c,
                source_file=str(md_file.relative_to(BRAIN_BACKUP_DIR)),
                complexity_score=s,
                user_id=DEFAULT_USER_ID,
                created_at=created_at,
                last_accessed=last_accessed,
                access_count=access_count,
            )
            chunk_ids.append(cid)

        metadatas = [
            {
                "user_id": DEFAULT_USER_ID,
                "chunk_id": cid,
                "source_file": str(md_file.relative_to(BRAIN_BACKUP_DIR)),
            }
            for cid in chunk_ids
        ]
        add_chunks(chunk_ids, embeddings, metadatas)
        total_chunks += len(chunk_ids)
        print(f"  OK {md_file.name} -> {len(chunk_ids)} chunks  (created {created_days_ago}d ago, {access_count} reviews)")

    print(f"\nDone. {total_chunks} chunks seeded from {len(md_files)} notes.")
    print("Start the server and open the Health Dashboard — drag the Time Machine slider to see decay.")


if __name__ == "__main__":
    seed()
