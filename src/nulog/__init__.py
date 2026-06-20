"""nulog -- logging as a Nu app.

Append-only logs kept in nv, written and queried in Nu. A log line is a Nu WRITE
(append an entry); reading the logs is a Nu Query (iterate, filter, collect). Same
language both directions.

Quickstart::

    from nulog import open_logs

    with open_logs() as logs:  # in-memory; pass a path for on-disk
        app = logs.stream("app")
        app.info("started", port=8080)
        app.error("boom", code=500)

        app.tail(10)  # most recent lines, newest-first
        app.errors()  # error lines only
        app.count_by_level()  # {"info": 1, "error": 1, ...}

Compose mode weaves a log line into a bigger atomic program::

    import nu_virtuals as nv

    nv.Transaction(Account.balance.store(...), app.entry("info", "debit", amount=n))
"""

from __future__ import annotations

from . import query
from .logger import Logger
from .presets import Logs, open_logs
from .records import LogRecord
from .shapes import Log, LogEntry, Streams


__version__ = "0.1.0"

__all__ = [
    "Log",
    "LogEntry",
    "LogRecord",
    "Logger",
    "Logs",
    "Streams",
    "open_logs",
    "query",
]
