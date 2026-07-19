# nulog

Logging + metrics as a Nu app. Append-only logs and kh57-backed metric series
kept in `nu.v`, written and read in Nu. Every write is a Nu Command; every
read is a Nu Query.

## Usage

Everything happens inside a `nulog.store(...)` bracket. Writes are Nu
Commands, reads are Nu Queries that yield `list[dict]` or `dict[str, int]`.

```python
import nu, nulog

tree = nu.With(nulog.store(),
    body=nu.v.Transaction(
        nulog.info("app", "server started", port=8080)
        >> nulog.warn("app", "cache miss", key="user:42")
        >> nulog.error("app", "request failed", path="/checkout", code=500)
        >> nulog.observe("cpu_load", 0.42)
    )
    >> nu.v.Snapshot(nu.print("tail:", nulog.tail("app", 3)))
    >> nu.v.Snapshot(nu.print("errors:", nulog.errors("app")))
    >> nu.v.Snapshot(nu.print("count:", nulog.count_by_level("app"))),
)

nu.run(tree)
```

Read atoms cover the search space:

- Logs: `tail(stream, n)`, `head(stream, n)`, `by_level(stream, level)`,
  `errors(stream)`, `since(stream, ts_us)`,
  `between(stream, start_us, end_us)`, `search(stream, text)`,
  `count_by_level(stream)`.
- Metrics: `range_metric(name, begin, end)`,
  `sample_metric(name, n, begin, end)`.

Rows come out as plain dicts. Log rows:
`{"key": int, "ts_us": int, "level": str, "msg": str, "fields": dict}`.
Metric rows: `{"ts_us": int, "ts": float, "value": float}`.

## UI

The viewer is a bracket too: `nulog.ui(streams, port=)` boots a nudle server
under `nulog.store(...)`. Same shape as any Nu-nudle app.

```python
import asyncio, nu, nulog

tree = nu.With(
    nulog.store("logs.db"),
    nulog.ui(["app", "scraper"], port=8080),
    body=nulog.info("app", "server started")
         >> nu.ForeverDo(
             nu.v.Transaction(nulog.info("app", "tick")) >> nu.Delay(1.5)
         ),
)

asyncio.run(nu.arun(tree))
```

Open <http://127.0.0.1:8080>: live newest-first entry table, stream switcher,
level filter, message search, per-level count stats. The table + counts
repaint every second off the same read atoms above.
