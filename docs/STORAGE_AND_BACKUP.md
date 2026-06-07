# Dory.md — Storage Risks & Backup Readiness

## What the app persists

| Store | Path (default) | Override | Holds |
|---|---|---|---|
| SQLite | `backend/data/dory.db` (+ `-wal`/`-shm`) | `DORY_DB_PATH` | users, chunks, FSRS state, quiz sessions, refresh tokens, access log |
| ChromaDB | `backend/data/chroma/` | `DORY_CHROMA_PATH` | per-chunk embedding vectors + metadata |

Both live on **local disk** under `backend/data/`. There is no managed database.

## Storage risks (current)

1. **Ephemeral filesystem = total data loss on redeploy.** On platforms with
   ephemeral disks (Heroku dynos, Render without a disk, Fly without a volume,
   most container PaaS), `backend/data/` is wiped on every restart/redeploy.
   Users, notes, and embeddings vanish. **This is the single biggest deployment
   risk.**
2. **Single-node only.** SQLite + a local Chroma dir cannot be shared across
   horizontally-scaled instances. Run exactly one backend instance, or migrate
   to a networked DB first.
3. **Non-atomic dual writes.** Ingest/delete write SQLite and Chroma separately;
   a crash between them can leave the two stores out of sync (edit is kept in
   sync — AUDIT P0-1). No reconciliation job exists.
4. **No backups by default.** Nothing snapshots the data unless you run the
   utility below or schedule it.

## Does data survive a restart?

- **Yes, IF `backend/data/` is on a persistent volume.** The Dockerfile declares
  `VOLUME ["/app/backend/data"]`; mount a real disk there and both stores
  survive restarts/redeploys.
- **No, on an ephemeral filesystem.** You MUST attach persistent storage.

### Per-platform requirement

| Platform | Action required |
|---|---|
| Docker / Compose | Bind-mount or named volume → `/app/backend/data` |
| Render | Add a **Persistent Disk**, mount at `/app/backend/data` |
| Fly.io | Create a **volume**, mount at `/app/backend/data` |
| Railway | Attach a **volume** at `/app/backend/data` |
| Heroku | Filesystem is ephemeral — not viable without migrating to Postgres + a hosted vector store |

Point `DORY_DB_PATH` / `DORY_CHROMA_PATH` at the mounted path if it differs.

## Minimum viable backup strategy (implemented)

[`backend/scripts/backup.py`](../backend/scripts/backup.py) snapshots both stores
into a timestamped directory:

- **SQLite** via the online backup API (`Connection.backup`) — safe while the
  server runs, WAL-aware, yields one consistent `dory.db`.
- **Chroma** as a `chroma.tar.gz` of the persistence directory.

Run a one-off backup:

```bash
cd backend
python -m scripts.backup --out /mnt/backups
# -> /mnt/backups/<UTC-timestamp>/{dory.db, chroma.tar.gz}
```

Schedule daily backups with cron on the host:

```cron
# 03:17 UTC daily; keep the volume mounted at /app/backend/data
17 3 * * *  cd /app/backend && DORY_BACKUP_DIR=/mnt/backups python -m scripts.backup >> /var/log/dory-backup.log 2>&1
```

> Store backups **off the app volume** (object storage / a separate disk).
> Add a retention sweep (e.g. `find /mnt/backups -mtime +30 -delete`) and,
> ideally, sync the timestamped dir to S3/GCS after each run.

### Restore

```bash
# 1. Stop the backend.
# 2. Restore SQLite:
cp /mnt/backups/<stamp>/dory.db   "$DORY_DB_PATH"          # default: backend/data/dory.db
#    (remove any stale -wal/-shm next to the target first)
# 3. Restore Chroma:
rm -rf "$DORY_CHROMA_PATH" && \
  tar -xzf /mnt/backups/<stamp>/chroma.tar.gz -C "$(dirname "$DORY_CHROMA_PATH")"
# 4. Start the backend; /readyz should return 200.
```

## Recommended next steps (beyond P0)

1. **Managed Postgres** for the relational data (durable, multi-node, point-in-time
   recovery) — see the migration path in the original `DATABASE_REVIEW.md`.
2. **Hosted vector store** (or `pgvector`) so ingest/edit/delete become atomic
   with the relational write.
3. Automated off-host backup shipping + restore drills.
