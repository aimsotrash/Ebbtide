"""Engram panel: what it serves, through its real HTTP handler, on a temporary database."""

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from engram_mcp import panel, server
from intelligence import embeddings

DAY = 86400.0


def test_panel_lists_strengths_and_looks_ahead(tmp_path, monkeypatch):
    clock = SimpleNamespace(now=0.0)
    monkeypatch.setenv("ENGRAM_DB", str(tmp_path / "memory.db"))
    monkeypatch.delenv("ENGRAM_POLICY", raising=False)
    monkeypatch.delenv("ENGRAM_BUDGET", raising=False)
    monkeypatch.setattr(embeddings, "embed_query", lambda text: [text.count("tea"), text.count("cat"), 0.1])
    monkeypatch.setattr(server, "time", SimpleNamespace(time=lambda: clock.now))
    monkeypatch.setattr(panel, "time", SimpleNamespace(time=lambda: clock.now))
    server.remember("Green tea after lunch", tags=["habit"])
    server.remember("My cat is called Miso")
    clock.now = 3 * DAY
    server.recall("what tea do I drink", k=1)  # strengthens the tea memory

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), panel._Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        def get(path, host=None):
            request = urllib.request.Request(base + path, headers={"Host": host} if host else {})
            with urllib.request.urlopen(request) as response:
                return response.headers["Content-Type"], response.read()

        kind, page = get("/")
        assert kind.startswith("text/html") and b"Look ahead" in page
        assert get("/geist.woff2")[0] == "font/woff2"
        today = json.loads(get("/memories")[1])
        week = json.loads(get("/memories?ahead=7")[1])
        with pytest.raises(urllib.error.HTTPError, match="400"):
            get("/memories?ahead=nan")
        with pytest.raises(urllib.error.HTTPError, match="403"):  # a rebound domain, not this machine
            get("/memories", host=f"evil.example:{httpd.server_address[1]}")
    finally:
        httpd.shutdown()

    assert (today["policy"], today["budget"], today["goes_first"]) == ("engram-count", 1000, None)
    tea, cat = today["memories"]  # strongest first: the tea memory was just recalled
    assert (tea["text"], tea["tags"], tea["strength"], tea["recalls"]) == ("Green tea after lunch", ["habit"], 1.0, 1)
    assert (cat["strength"], cat["half_life_days"]) == (0.717, 6.2)  # e^(-72 h / 216 h); ln 2 x 9 days
    assert tea["half_life_days"] == 8.4  # one recall: S = 1 + 0.5 ln 2
    assert [m["strength"] for m in week["memories"]] == [0.561, 0.329]  # the recalled one fades slower
    monkeypatch.setenv("ENGRAM_BUDGET", "2")  # now full: the next add would drop the weaker memory
    assert panel.snapshot(clock.now)["goes_first"] == cat["id"]
