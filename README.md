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

## Status

Early scaffold. The package layout is in place, real logger features land next.

## Layout

Intended modules (all in progress):

- `shapes.py` - the LogEntry and Log shapes
- `logger.py` - the write handle you append entries through
- `query.py` - read helpers that hand back Nu Queries
- `presets.py` - rocksdb setup and other ready storage presets

## Dev quickstart

```sh
make install   # create .venv, install nu[all] + dev/test
make test      # run the suite
make lint      # ruff check
```

Part of the nu stack (nustackdev), alongside nu, nu_virtuals, nudle, nuspace.
