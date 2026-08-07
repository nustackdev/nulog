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
        nulog.ui(["app", "scraper"], port=8080),
        body=nu.ForeverDo(
            nu.kv.Transaction(nulog.getLogger("app").info("tick")) >> nu.Delay(1.5),
        ),
    )
    asyncio.run(nu.arun(tree))
"""

from __future__ import annotations

import tempfile
import uuid
from typing import TYPE_CHECKING

import nu

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
from .metrics import observe
from .ui import (
    DEFAULT_LEVEL,
    LEVEL_OPTIONS,
    TABLE_COLUMNS,
    ViewerIndex,
    ViewerPage,
    build_ui,
)


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nu.context import Provide


__version__ = "0.7.0"

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
    "Logger",
    "ViewerIndex",
    "ViewerPage",
    "build_ui",
    "critical",
    "debug",
    "error",
    "from_std_logging",
    "getLogger",
    "info",
    "log",
    "messages",
    "metrics",
    "observe",
    "store",
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
    ``nulog.getLogger(...)`` / ``.info()`` / ``nulog.observe()`` /
    ``nulog.messages.tail()`` / ... inside the body reads and writes
    through it.
    """
    if path is None:
        return nu.kv.presets.memory_navigator()
    return nu.kv.presets.rocksdb_navigator(path)


def ui(
    streams: Sequence[str],
    series: Sequence[str],
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
) -> Provide:
    """Boot the nudle log viewer over the enclosing bracket's store.

    The viewer tree from :func:`~nulog.ui.build_ui` is scope-free; this
    entrypoint runs an untagged ``nu.kv.auto_flow_atomic`` sweep so a
    single-store standalone user does not have to think about atomicity.
    Callers embedding the viewer inside a multi-scope orchestration
    should call :func:`~nulog.ui.build_ui` directly and wrap themselves
    with the scopes that match their fabric layout (typically
    ``scope=Messages`` and ``scope=Metrics``).

    Args:
        streams: message stream names to offer in the messages tab picker.
        series: metric series names to offer in the metrics tab picker.
        host: uvicorn bind address (default ``127.0.0.1``).
        port: uvicorn bind port (default ``8080``).
    """
    tree = build_ui(tuple(streams), tuple(series))
    tree = nu.kv.auto_flow_atomic(tree)
    return nu.ui.nudle.server(tree, host=host, port=port)
