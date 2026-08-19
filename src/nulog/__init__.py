"""nulog -- messages + metrics + browser viewer, all as Nu trees.

Two submodules share one RocksDB (via ``nu.kv``): :mod:`nulog.messages`
(append-only log streams on :class:`ShapesListRef`) and :mod:`nulog.metrics`
(kh57 time series). One bracket to provide the store, one bracket to boot
the browser viewer, one body of writes-and-reads. The write API mirrors
``nu.std.logging`` / Python's ``logging`` 1-1::

    import nu, nulog

    log = nulog.getLogger("app")

    tree = nu.With(nulog.store(),
        body=nu.kv.Transaction(
            log.info("started", extra={"port": 8080})
            >> log.warning("slow: %s ms", 210)
            >> nulog.observe("cpu_load", 0.42),
        )
        >> nu.kv.Snapshot(nu.print(nulog.messages.tail("app", 10))),
    )
    nu.run(tree)

Or write app code in ``nu.std.logging`` style and swap to persistence with
the :func:`from_std_logging` rewriter (Python's ``logging`` stays the
default sink; the rewriter walks the tree and swaps every log statement
for the equivalent persistent write)::

    from nu.std import logging
    log = logging.getLogger("app")

    body = log.info("started") >> log.warning("slow: %s ms", 210)
    tree = nu.With(nulog.store(), body=nulog.from_std_logging(body))

Live viewer::

    tree = nu.With(
        nulog.store("logs.db"),
        nulog.ui(port=8080),
        body=nu.ForeverDo(
            nu.kv.Transaction(nulog.getLogger("app").info("tick")) >> nu.Delay(1.5),
        ),
    )
    asyncio.run(nu.arun(tree))
"""

from __future__ import annotations

from . import messages, metrics
from .messages import (
    CRITICAL,
    DEBUG,
    ERROR,
    FATAL,
    INFO,
    LEVELS,
    NOTSET,
    WARN,
    WARNING,
    Logger,
    critical,
    debug,
    error,
    from_std_logging,
    getLogger,
    info,
    log,
    warn,
    warning,
)
from .client import Client, init
from .metrics import observe
from .ui import (
    DEFAULT_LEVEL,
    LEVEL_OPTIONS,
    TABLE_COLUMNS,
    MessagesPage,
    MetricsPage,
    ViewerIndex,
    build_ui,
)
from .presets import store, store_ro, ui, viewer  # noqa: E402  -- rebinds ``ui`` over the submodule


__version__ = "0.1.6"

__all__ = [
    "CRITICAL",
    "DEBUG",
    "DEFAULT_LEVEL",
    "ERROR",
    "FATAL",
    "INFO",
    "LEVELS",
    "LEVEL_OPTIONS",
    "NOTSET",
    "TABLE_COLUMNS",
    "WARN",
    "WARNING",
    "Client",
    "Logger",
    "MessagesPage",
    "MetricsPage",
    "ViewerIndex",
    "build_ui",
    "critical",
    "debug",
    "error",
    "from_std_logging",
    "getLogger",
    "info",
    "init",
    "log",
    "messages",
    "metrics",
    "observe",
    "store",
    "store_ro",
    "ui",
    "viewer",
    "warn",
    "warning",
]


