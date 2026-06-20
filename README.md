# nulog

Logging as a Nu app: append-only logs over any storage, written and queried in Nu.

## Why

A log line is just data you append and never change. In nulog that line is the
canonical Nu WRITE. Reading the logs back is a Nu Query. Same language both
directions, so there is no separate format for emitting versus searching.

Persistence, structure, and querying all come from the nu stack for free.
nu_virtuals gives you rocksdb-backed storage when you want logs on disk, nu_mem
gives you an in-memory log when you do not. nulog is the thin app on top that
decides what a log entry looks like and how you read it back.

## Usage

```python
from nulog import open_logs

with open_logs() as logs:          # in-memory; pass a path for on-disk rocksdb
    app = logs.stream("app")       # one named stream of many in the store

    app.info("server started", port=8080)
    app.warn("cache miss", key="user:42")
    app.error("request failed", code=500)

    app.tail(10)            # most recent lines, newest-first (list of LogRecord)
    app.errors()            # error lines only
    app.count_by_level()    # {"debug": 0, "info": 1, "warn": 1, "error": 1}
    app.search("request")   # lines whose message contains the text
    app.since(ts_ms)        # lines at or after a timestamp
```

A line carries structured `**fields` (any JSON-serializable kwargs), kept as a
JSON string in the store and decoded back to a dict on read. Reads come back as
frozen `LogRecord(id, ts, level, msg, fields)`.

Compose mode is the Nu payoff: `app.entry(level, msg, **fields)` returns the
append Command without running it, so you can weave a log line into a bigger
program and get an atomic log-plus-effect:

```python
import nu_virtuals as nv
nv.Transaction(Account.balance.store(new), app.entry("info", "debit", amount=n))
```

The runnable example is `examples/basic.py`.

## Viewer (`[ui]` extra)

A log line is a Nu read; so is the viewer. `nulog[ui]` adds a browser viewer
(built on [nudle](https://github.com/nustackdev/nudle)) that queries a store in
the same language the writer used: the table is fed by `query.tail` /
`query.by_level` / `query.search`, the counts by `count_by_level`.

```sh
pip install nulog[ui]
python examples/viewer.py    # then open http://127.0.0.1:8080
```

You get one page: a live, newest-first entry table (time / level / message /
fields), a stream switcher, a level filter, a message search box, and per-level
count stats. The table and counts repaint every second, so new lines surface
live. The whole UI is read-only over the logs -- mounting a viewer never mutates
the store. The viewer serves itself through `run_viewer`, no nudle CLI needed;
to embed it in a host process:

```python
from nulog import open_logs
from nulog.ui import run_viewer

with open_logs("/var/log/myapp") as logs:
    run_viewer(["app", "scraper"], logs=logs)   # blocks, serves on :8080
```

The viewer code lives in `src/nulog/ui/`; the runnable demo is
`examples/viewer.py`. The core package never imports nudle, so plain `nulog`
works without the extra.

## Layout

- `shapes.py` - the `LogEntry`, `Log`, and `Streams` shapes (the store layout)
- `logger.py` - the write face: eager `info`/`warn`/`error`/`debug`/`log` and
  compose-mode `entry`, plus the read convenience methods
- `query.py` - the read face: pure Nu Query builders (`by_level`, `since`,
  `between`, `search`, `count_by_level`, ...)
- `records.py` - `LogRecord` and the reader that decodes a query into records
- `presets.py` - `open_logs` and the `Logs` handle (rocksdb wiring)

## Dev quickstart

```sh
make install   # create .venv, install nu[all] + dev/test
make test      # run the suite
make lint      # ruff check
```

Part of the nu stack (nustackdev), alongside nu, nu_virtuals, nudle, nuspace.
