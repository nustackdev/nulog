# nulog

Logging + metrics as a Nu app. Append-only logs and kh57-backed metric series
kept in `nu.v`, written and read in Nu. Every write is a Nu Command; every
read is a Nu Query. Nothing imperative.

## Why

A log line is data you append and never change. In nulog that line is a Nu
WRITE (a Command that folds into any bigger Transaction). Reading the logs is
a Nu Query (a tree of `IterQuery`/`FilterQuery`/`MapQuery`/`CollectQuery`
walking the same shape refs the writer stored to). Same language both
directions, same tree.

Persistence comes from `nu.v` (RocksDB via virtuals). Metric series ride on
top of kh57 — sparse int-keyed time series with cheap range reservoir
sampling for chart thinning. Both logs and metrics are `Kh57ShapesRef` maps,
so they share the same substrate.

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

Compose mode is the Nu payoff: every write is a Command, so a log line rides
inside any bigger atomic program in the tree.

```python
nu.v.Transaction(Account.balance.store(new), nulog.info("app", "debit", amount=n))
```

## Viewer (`[ui]` extra)

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

## Layout

- `shapes.py` — the two Nu Shape trees: `Logs / LogStream / LogEntry`,
  `Metrics / MetricSeries / MetricPoint`, plus `ViewState` for the viewer.
  Both stream shapes use `Kh57ShapesRef` so range/sample are cheap on both.
- `writes.py` — the write Commands (`entry / info / warn / error / debug /
  log / observe`) plus the `@nu.host` seams that mint eval-time values
  (`NowUs`, `NowSeconds`, `EncodeLogKey`, `FieldsAsJson`).
- `reads.py` — the read Queries. Everything composes from
  `IterQuery / FilterQuery / MapQuery / CollectQuery / ReversedQuery /
  CountQuery / GetItemQuery / SliceQuery / DictForm.of` over the kh57 shape
  maps. One `@nu.host` (`FieldsFromJson`) decodes the opaque JSON blob.
- `viewer.py` — the browser page + reactive tree, same shape as `wish_jar.py`
  / `counter.py` in `nu/examples/nudle/`. Two `@nu.host` formatters (`FmtTs`,
  `FmtFields`) plus `RowAsList` for the table wire payload.
- `__init__.py` — the two brackets (`store(path=None)` and `ui(streams,
  port=)`) plus the re-exports.

## Dev quickstart

```sh
make install   # create .venv, install nu[all] + dev/test
make test      # run the suite
make lint      # ruff check
```

Part of the nu stack (nustackdev), alongside nu, virtuals, nudle, kh57.
