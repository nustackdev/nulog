"""nulog viewer demo -- live log table in the browser, over an in-memory store.

A plain Python script: opens an in-memory nulog store, seeds a handful of lines
across two streams (``app`` + ``scraper``) and all four levels with structured
fields, starts a background thread that appends a fresh line every ~1.5s (so the
live tail visibly updates), and serves the viewer with ``run_viewer``.

``run_viewer`` builds the reactive page over the store and runs the server, so
this needs no ``nudle`` CLI -- just run the file.

What you get: a newest-first entry table (time / level / message / fields), a
stream switcher, a level filter, a message search box, and per-level count
stats. The table and counts repaint every second.

Run:
    python examples/viewer.py

Then open http://127.0.0.1:8080. Ctrl-C to stop.
"""

from __future__ import annotations

import itertools
import random
import threading

from nulog import open_logs
from nulog.ui import run_viewer


STREAMS = ["app", "scraper"]

_LEVELS = ["debug", "info", "warn", "error"]
_MESSAGES = [
    "tick processed",
    "user signed in",
    "payment captured",
    "queue drained",
    "retry scheduled",
    "connection reset",
    "snapshot written",
]


def _seed(logs) -> None:
    """Write a handful of lines across both streams and all four levels."""
    a = logs.stream("app")
    scraper = logs.stream("scraper")

    a.info("server started", port=8080, env="dev")
    a.debug("config loaded", source="env")
    a.warn("cache miss", key="user:42")
    a.error("request failed", path="/checkout", code=500)
    a.info("request ok", path="/", ms=12)

    scraper.info("scrape started", target="example.com")
    scraper.debug("fetched page", url="/list", bytes=20413)
    scraper.warn("rate limited", retry_after=2)
    scraper.error("blocked", status=429)


def _generate(logs, stop: threading.Event) -> None:
    """Append a new line to a random stream every ~1.5s until stopped."""
    counter = itertools.count(1)
    while not stop.wait(1.5):
        n = next(counter)
        stream = random.choice(STREAMS)  # noqa: S311 -- demo jitter, not crypto
        level = random.choice(_LEVELS)  # noqa: S311
        msg = random.choice(_MESSAGES)  # noqa: S311
        logs.stream(stream).log(level, msg, seq=n, stream=stream)


def main() -> None:
    """Open a store, seed it, run the background generator, and serve the viewer."""
    with open_logs() as logs:
        _seed(logs)
        stop = threading.Event()
        worker = threading.Thread(target=_generate, args=(logs, stop), daemon=True)
        worker.start()
        try:
            run_viewer(STREAMS, logs=logs)
        finally:
            stop.set()
            worker.join(timeout=2.0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
