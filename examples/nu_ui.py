"""nulog viewer: browser log viewer over a live stream of messages + metrics."""

from __future__ import annotations

import asyncio

import nu

import nulog


app = nulog.getLogger("app")
scraper = nulog.getLogger("scraper")
worker = nulog.getLogger("worker")


def _seed() -> nu.Nu:
    """A one-shot burst so the viewer has content on first repaint."""
    return nu.kv.Transaction(
        app.info("server started", extra={"port": 8080, "env": "dev"})
        >> app.debug("config loaded", extra={"source": "env"})
        >> app.warning("cache miss", extra={"key": "user:42"})
        >> app.error("request failed", extra={"path": "/checkout", "code": 500})
        >> scraper.info("scrape started", extra={"target": "example.com"})
        >> scraper.error("blocked", extra={"status": 429})
        >> worker.info("job dequeued", extra={"id": "j-7f2"})
        >> worker.debug("stage begin", extra={"stage": "fetch"})
        >> nulog.observe("cpu_load", 0.31)
        >> nulog.observe("cpu_load", 0.37)
        >> nulog.observe("cpu_load", 0.42)
        >> nulog.observe("http_latency_ms", 12.0)
        >> nulog.observe("http_latency_ms", 18.0)
        >> nulog.observe("mem_mb", 512.0)
        >> nulog.observe("mem_mb", 528.0),
    )


def _tick() -> nu.Nu:
    """Five-step cycle: each step emits one message and one metric point."""
    return nu.ForeverDo(
        nu.kv.Transaction(
            app.info("request ok", extra={"path": "/", "ms": 12})
            >> nulog.observe("cpu_load", 0.45),
        )
        >> nu.Delay(0.4)
        >> nu.kv.Transaction(
            scraper.info("page fetched", extra={"url": "/robots.txt"})
            >> nulog.observe("http_latency_ms", 22.0),
        )
        >> nu.Delay(0.4)
        >> nu.kv.Transaction(
            app.warning("slow request", extra={"ms": 210}) >> nulog.observe("cpu_load", 0.61),
        )
        >> nu.Delay(0.4)
        >> nu.kv.Transaction(
            worker.error("stage failed", extra={"stage": "parse", "code": 3})
            >> nulog.observe("mem_mb", 604.0),
        )
        >> nu.Delay(0.4)
        >> nu.kv.Transaction(
            scraper.info("429 backoff", extra={"retry_in_s": 5})
            >> nulog.observe("http_latency_ms", 34.0),
        )
        >> nu.Delay(0.4),
    )


tree = nu.With(
    nulog.store("fast_updates.db"),
    nulog.ui(port=8080),
    body=_seed() >> _tick(),
)


if __name__ == "__main__":
    asyncio.run(nu.arun(tree))
