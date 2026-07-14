"""nulog viewer: browser log viewer, mounted as a bracket over the store.

Two brackets, one body: `nulog.store()` on top, `nulog.ui(...)` below, the body
seeds a handful of lines then loops one fresh entry every ~1.5s. All the
same-shape as `counter.py` / `wish_jar.py` in nu's own examples.

Open http://127.0.0.1:8080 after starting.

Run::

    python examples/viewer.py
"""

from __future__ import annotations

import asyncio

import nu

import nulog


STREAMS = ["app", "scraper"]


app = nulog.getLogger("app")
scraper = nulog.getLogger("scraper")


def _seed() -> nu.Nu:
    return nu.v.Transaction(
        app.info("server started", extra={"port": 8080})
        >> app.debug("config loaded", extra={"source": "env"})
        >> app.warning("cache miss", extra={"key": "user:42"})
        >> app.error("request failed", extra={"path": "/checkout", "code": 500})
        >> scraper.info("scrape started", extra={"target": "example.com"})
        >> scraper.error("blocked", extra={"status": 429}),
    )


def _tick() -> nu.Nu:
    return nu.ForeverDo(
        nu.v.Transaction(app.info("tick"))
        >> nu.Delay(1.5)
        >> nu.v.Transaction(app.warning("slow request", extra={"ms": 210}))
        >> nu.Delay(1.5)
        >> nu.v.Transaction(scraper.info("page fetched", extra={"url": "/robots.txt"}))
        >> nu.Delay(1.5)
        >> nu.v.Transaction(scraper.error("429 blocked"))
        >> nu.Delay(1.5)
        >> nu.v.Transaction(app.debug("gc pause", extra={"ms": 8}))
        >> nu.Delay(1.5),
    )


tree = nu.With(
    nulog.store(),
    nulog.ui(STREAMS, port=8080),
    body=_seed() >> _tick(),
)


if __name__ == "__main__":
    asyncio.run(nu.arun(tree))
