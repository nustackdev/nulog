"""nulog -- logs + metrics + browser viewer, all as Nu trees.

Two domains share one RocksDB (via ``nu.v``): logs and metrics, both kh57 shape
maps. One bracket to provide the store, one bracket to boot the browser
viewer, one body of writes-and-reads. Full app in one tree::

    import nu, nulog

    tree = nu.With(nulog.store(),
        body=nu.v.Transaction(
            nulog.info("app", "started", port=8080)
            >> nulog.warn("app", "slow", ms=210)
            >> nulog.observe("cpu_load", 0.42),
        )
        >> nu.v.Snapshot(nu.print(nulog.tail("app", 10))),
    )
    nu.run(tree)

Live viewer::

    tree = nu.With(
        nulog.store("logs.db"),
        nulog.ui(["app", "scraper"], port=8080),
        body=nu.ForeverDo(
            nu.v.Transaction(nulog.info("app", "tick")) >> nu.Delay(1.5),
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
from .writes import debug, entry, error, info, log, observe, warn


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nu.context.fabric import Provide


__version__ = "0.5.0"

__all__ = [
    "DEFAULT_LEVEL",
    "LEVELS",
    "LEVEL_OPTIONS",
    "TABLE_COLUMNS",
    "LogEntry",
    "LogStream",
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
    "debug",
    "entry",
    "error",
    "errors",
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
]


def _scratch_dir() -> str:
    """A unique in-memory RocksDB scratch dir under the system temp."""
    return f"{tempfile.gettempdir()}/nulog-{uuid.uuid4().hex}"


def store(path: str | None = None) -> nu.With:
    """A bracket providing Codec + Observer + RocksDB + Navigator.

    On-disk when ``path`` is given (durable); fresh in-memory scratch otherwise.
    Every ``nulog.entry``/``.info``/``.observe``/``.tail``/... inside the body
    reads and writes through it.
    """
    return nu.v.presets.rocksdb_navigator_inmemory(path if path is not None else _scratch_dir())


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
