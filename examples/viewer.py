"""nulog viewer demo -- live log table in the browser, over an in-memory store.

Opens an in-memory nulog store, seeds a handful of lines across two streams
(``app`` + ``scraper``) and all four levels with structured fields, runs a
background generator that appends a fresh line every ~1.5s (so the live tail
visibly updates, like counter.py's ``bg`` worker), and serves the viewer.

What you get: a newest-first entry table (time / level / message / fields), a
stream switcher, a level filter, a message search box, and per-level count
stats. The table and counts repaint every second.

Run:
    nudle run examples/viewer.py
    # or, with hot reload:
    nudle dev examples/viewer.py

Then open http://127.0.0.1:8080.
"""

from __future__ import annotations

import itertools
import random
import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING

from nulog import open_logs
from nulog.ui import build_app


if TYPE_CHECKING:
    from collections.abc import Iterator

    import nu


STREAMS = ["app", "scraper"]


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


# ---- one store for the whole process ---------------------------------------
# Opened once at import, kept open for the life of the server. nudle reads the
# module-level `app` once (before entering context()), so `app` closes over this
# same store -- the one context() yields the ctx of.

_store_cm = open_logs()
_LOGS = _store_cm.__enter__()
_seed(_LOGS)


# ---- background generator: a new line every ~1.5s --------------------------
# A daemon thread, the way counter.py's `bg` worker bumps the counter -- but a
# plain eager write here (the store is single-process in-memory), so the live
# tail visibly updates while the page is open.

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


def _generate(stop: threading.Event) -> None:
    counter = itertools.count(1)
    while not stop.wait(1.5):
        n = next(counter)
        stream = random.choice(STREAMS)  # noqa: S311 -- demo jitter, not crypto
        level = random.choice(_LEVELS)  # noqa: S311
        msg = random.choice(_MESSAGES)  # noqa: S311
        _LOGS.stream(stream).log(level, msg, seq=n, stream=stream)


# The per-session UI program, over the same open store.
app = build_app(_LOGS, STREAMS)


@contextmanager
def context() -> Iterator[nu.Context]:
    """Yield the open store's bound Context; run the generator while serving."""
    stop = threading.Event()
    worker = threading.Thread(target=_generate, args=(stop,), daemon=True)
    worker.start()
    try:
        yield _LOGS.ctx
    finally:
        stop.set()
        worker.join(timeout=2.0)
        _store_cm.__exit__(None, None, None)
