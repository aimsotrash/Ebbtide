"""
A quiet local page that lists the agent's memories and how strong each one is.

  python -m engram_mcp.panel [--port 8765]   # then open http://127.0.0.1:8765

It reads the server's database (ENGRAM_DB) read-only on every request, so each remember,
recall and eviction shows up within a couple of seconds. The look-ahead slider shows how
strong each memory would be after that many more days without a recall.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import time
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from engram_mcp.server import _config, _iso, _load
from intelligence.memory import POLICIES, MemoryStore

PAGE = Path(__file__).with_name("panel.html")
FONT = Path(__file__).with_name("fonts") / "geist.woff2"  # the landing page's typeface, served locally


def snapshot(now: float, ahead_days: float = 0.0) -> dict:
    """Every memory with its strength `ahead_days` after `now`, strongest first."""
    db, policy, budget = _config()
    store = MemoryStore(POLICIES[policy], budget)
    if db.exists():
        with closing(sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)) as conn:
            store = _load(conn, policy, budget)
    hours, when = store.policy.scale_hours, now + ahead_days * 86400
    ranked = sorted(zip(store.retrievability(when), store.memories), key=lambda pair: -pair[0])  # exact strength
    rows = [
        {"id": m.id, "text": m.text, "tags": (m.source or {}).get("tags", []), "strength": round(float(r), 3),
         "half_life_days": round(math.log(2) * m.stability * hours / 24, 1), "recalls": m.recall_count,
         "added": _iso(m.created_at)}
        for r, m in ranked
    ]
    # Only a full store evicts, and the policy decides which memory: the next add removes this one.
    full = store.budget is not None and len(store.memories) >= store.budget
    victim = store.next_eviction(when) if full else None
    return {"policy": policy, "budget": store.budget, "ahead_days": ahead_days, "memories": rows,
            "goes_first": victim.id if victim else None}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Only this machine's own names: a web page that rebinds its domain to 127.0.0.1
        # (DNS rebinding) sends its own Host, and must not read the memories.
        port = self.server.server_address[1]
        if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            self.send_error(403)
            return
        url = urlsplit(self.path)
        if url.path == "/":
            body, kind = PAGE.read_bytes(), "text/html; charset=utf-8"
        elif url.path == "/geist.woff2":
            body, kind = FONT.read_bytes(), "font/woff2"
        elif url.path == "/memories":
            try:
                ahead = float(parse_qs(url.query).get("ahead", ["0"])[0])
            except ValueError:
                ahead = math.nan
            if not 0 <= ahead <= 3650:  # also rejects NaN
                self.send_error(400, "ahead must be a number of days from 0 to 3650")
                return
            body, kind = json.dumps(snapshot(time.time(), ahead)).encode(), "application/json"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # the page polls every 2 s; don't log each request
        pass


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m engram_mcp.panel", description=__doc__.split("\n\n")[0])
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    db, policy, budget = _config()
    MemoryStore(POLICIES[policy], budget)  # a bad ENGRAM_* value fails here
    server = ThreadingHTTPServer(("127.0.0.1", args.port), _Handler)  # this machine only
    print(f"Engram panel for {db}: http://127.0.0.1:{args.port} (Ctrl+C stops it)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
