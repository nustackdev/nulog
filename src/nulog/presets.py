"""Setup -- open a store and hand back a logs handle.

:func:`open_logs` is the front door. It opens a RocksDB storage (on disk at
``path``, or an in-process in-memory one when ``path is None``), binds a Nu
Context onto a Navigator (the exact wiring from ``basic_virtuals.py`` and
nuspace), and yields a :class:`Logs` handle. ``Logs.stream(name)`` gives you a
:class:`~nulog.logger.Logger` for one named stream, the same handle for writing
and reading.

The store layout (:mod:`nulog.shapes`) carries many streams in one store, so one
``open_logs`` covers a whole app's logging.
"""

from __future__ import annotations

import tempfile
import uuid
from contextlib import contextmanager
from typing import TYPE_CHECKING

import nu
from nu.virtuals.presets import rocksdb_storage_inmemory
from virtuals import Navigator

from .logger import Logger


if TYPE_CHECKING:
    from collections.abc import Generator


__all__ = ["Logs", "open_logs"]


class Logs:
    """A bound store of named log streams.

    Wraps one Context (its Navigator carries the store) and mints a
    :class:`~nulog.logger.Logger` per stream name on demand. All streams share the
    one store and the one Context.

    Attributes:
        ctx: the bound Nu Context. Reach for it to weave compose-mode log Commands
            (``logs.stream("app").entry(...)``) into your own Transactions.
    """

    def __init__(self, ctx: nu.Context) -> None:
        """Bind a logs handle to a Context.

        Args:
            ctx: a Context whose Navigator is bound to the store.
        """
        self.ctx = ctx

    def stream(self, name: str) -> Logger:
        """A write-plus-read handle on the named stream.

        Args:
            name: the stream name (``"app"``, ``"scraper"``, ...).

        Returns:
            A :class:`~nulog.logger.Logger` bound to this store and that stream.
        """
        return Logger(self.ctx, name)


@contextmanager
def open_logs(path: str | None = None) -> Generator[Logs, None, None]:
    """Open a log store and yield a :class:`Logs` handle.

    On-disk when ``path`` is given (durable, RocksDB), in-memory otherwise
    (in-process, dropped on close -- good for tests and one-off scripts). The
    in-memory store still takes an exclusive directory lock, so each call gets a
    unique scratch dir under the system temp.

    Args:
        path: a RocksDB directory for durable logs, or ``None`` for in-memory.

    Yields:
        A :class:`Logs` handle bound to the freshly opened store.
    """
    store_dir = path if path is not None else f"{tempfile.gettempdir()}/nulog-{uuid.uuid4().hex}"
    with rocksdb_storage_inmemory(store_dir) as storage:
        yield Logs(nu.Context().bind(Navigator, Navigator(storage)))
