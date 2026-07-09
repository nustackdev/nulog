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


def _seed() -> nu.Nu:
    return nu.v.Transaction(
        nulog.info("app", "server started", port=8080)
        >> nulog.debug("app", "config loaded", source="env")
        >> nulog.warn("app", "cache miss", key="user:42")
        >> nulog.error("app", "request failed", path="/checkout", code=500)
        >> nulog.info("scraper", "scrape started", target="example.com")
        >> nulog.error("scraper", "blocked", status=429),
    )


def _tick() -> nu.Nu:
    return nu.ForeverDo(
        nu.v.Transaction(nulog.info("app", "tick"))
        >> nu.Delay(1.5)
        >> nu.v.Transaction(nulog.warn("app", "slow request", ms=210))
        >> nu.Delay(1.5)
        >> nu.v.Transaction(nulog.info("scraper", "page fetched", url="/robots.txt"))
        >> nu.Delay(1.5)
        >> nu.v.Transaction(nulog.error("scraper", "429 blocked"))
        >> nu.Delay(1.5)
        >> nu.v.Transaction(nulog.debug("app", "gc pause", ms=8))
        >> nu.Delay(1.5),
    )


tree = nu.With(
    nulog.store(),
    nulog.ui(STREAMS, port=8080),
    body=_seed() >> _tick(),
)


if __name__ == "__main__":
    asyncio.run(nu.arun(tree))
