"""nulog basics: write lines across levels and streams, read them back.

The whole app is one Nu tree. Writes compose under a `Transaction`, reads
compose under `Snapshot` and get piped through `nu.print`. No held ctx, no
imperative Python.

Run::

    python examples/basic.py
"""

from __future__ import annotations

import nu

import nulog


writes = (
    nulog.info("app", "server started", port=8080, env="dev")
    >> nulog.debug("app", "config loaded", source="env")
    >> nulog.warn("app", "cache miss", key="user:42")
    >> nulog.error("app", "request failed", path="/checkout", code=500)
    >> nulog.info("app", "request ok", path="/", ms=12)
    >> nulog.info("scraper", "scrape started", target="example.com")
    >> nulog.error("scraper", "blocked", status=429)
)

reads = (
    nu.v.Snapshot(nu.print("== app: tail(3) ==", nulog.tail("app", 3)))
    >> nu.v.Snapshot(nu.print("== app: errors ==", nulog.errors("app")))
    >> nu.v.Snapshot(nu.print("== app: count_by_level ==", nulog.count_by_level("app")))
    >> nu.v.Snapshot(nu.print("== app: search 'request' ==", nulog.search("app", "request")))
    >> nu.v.Snapshot(nu.print("== scraper: tail(5) ==", nulog.tail("scraper", 5)))
)

tree = nu.With(nulog.store(), body=nu.v.Transaction(writes) >> reads)


if __name__ == "__main__":
    nu.run(tree)
