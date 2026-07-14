"""nulog -- logs + metrics + browser viewer, all as Nu trees.

Two domains share one RocksDB (via ``nu.v``): logs and metrics, both kh57 shape
maps. One bracket to provide the store, one bracket to boot the browser
viewer, one body of writes-and-reads. The write API mirrors
``nu.std.logging`` (and Python's ``logging``) 1-1::

    import nu, nulog

    log = nulog.getLogger("app")

    tree = nu.With(nulog.store(),
        body=nu.v.Transaction(
            log.info("started", extra={"port": 8080})
            >> log.warning("slow: %s ms", 210)
            >> nulog.observe("cpu_load", 0.42),
        )
        >> nu.v.Snapshot(nu.print(nulog.tail("app", 10))),
    )
    nu.run(tree)

Or write app code in ``nu.std.logging`` style and swap to persistence with
the :func:`from_std_logging` rewriter (Python's ``logging`` stays the
default sink; the rewriter walks the tree and swaps every log statement
for the equivalent persistent write into kh57 storage)::

    from nu.std import logging
    log = logging.getLogger("app")

    body = log.info("started") >> log.warning("slow: %s ms", 210)
    tree = nu.With(nulog.store(), body=nulog.from_std_logging(body))

Live viewer::

    tree = nu.With(
        nulog.store("logs.db"),
        nulog.ui(["app", "scraper"], port=8080),
        body=nu.ForeverDo(
            nu.v.Transaction(nulog.getLogger("app").info("tick")) >> nu.Delay(1.5),
        ),
    )
    asyncio.run(nu.arun(tree))
"""

from __future__ import annotations

import tempfile
import uuid
from typing import TYPE_CHECKING

import nu

from .reads import (
    between,
    by_level,
    count_by_level,
    errors,
    head,
    range_metric,
    sample_metric,
    search,
    since,
    tail,
)
from .rewrite import from_std_logging
from .shapes import (
    LEVELS,
    LogEntry,
    Logs,
    LogStream,
    MetricPoint,
    Metrics,
    MetricSeries,
    ViewState,
)
from .viewer import (
    DEFAULT_LEVEL,
    LEVEL_OPTIONS,
    TABLE_COLUMNS,
    ViewerIndex,
    ViewerPage,
    build_ui,
)
from .writes import (
    CRITICAL,
    DEBUG,
    ERROR,
    FATAL,
    INFO,
    NOTSET,
    WARN,
    WARNING,
    Logger,
    critical,
    debug,
    error,
    getLogger,
    info,
    log,
    observe,
    warn,
    warning,
)


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nu.context.fabric import Provide


__version__ = "0.6.0"

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
    "LogEntry",
    "LogStream",
    "Logger",
    "Logs",
    "MetricPoint",
    "MetricSeries",
    "Metrics",
    "ViewState",
    "ViewerIndex",
    "ViewerPage",
    "between",
    "build_ui",
    "by_level",
    "count_by_level",
    "critical",
    "debug",
    "error",
    "errors",
    "from_std_logging",
    "getLogger",
    "head",
    "info",
    "log",
    "observe",
    "range_metric",
    "sample_metric",
    "search",
    "since",
    "store",
    "tail",
    "ui",
    "warn",
    "warning",
]


def _scratch_dir() -> str:
    """A unique in-memory RocksDB scratch dir under the system temp."""
    return f"{tempfile.gettempdir()}/nulog-{uuid.uuid4().hex}"


def store(path: str | None = None) -> nu.With:
    """A bracket providing Codec + Observer + storage + Navigator.

    On-disk RocksDB when ``path`` is given (durable); pure in-memory when
    ``None`` (default -- fresh per call, gone on process exit). Every
    ``nulog.getLogger(...)`` / ``.info()`` / ``.observe()`` / ``.tail()``
    / ... inside the body reads and writes through it.
    """
    if path is None:
        return nu.v.presets.memory_navigator()
    return nu.v.presets.rocksdb_navigator(path)


def ui(
    streams: Sequence[str],
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
) -> Provide:
    """Boot the nudle log viewer over the enclosing bracket's store.

    Drop under :func:`store` in a ``nu.With(...)`` tree; the viewer reads from
    whatever Navigator that bracket provides.
    """
    return nu.nd.presets.server(build_ui(tuple(streams)), host=host, port=port)
