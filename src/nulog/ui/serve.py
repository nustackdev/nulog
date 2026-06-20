"""Serve a log viewer -- the convenience over ``nudle.serve``.

:func:`serve_logs` mirrors nuspace's ``serve(ctx, app, ...)``: it takes an open
:class:`~nulog.presets.Logs` store (or opens one), builds the viewer's reactive
``app`` over it (see :mod:`nulog.ui.app`), and runs the nudle server. The store's
Context is the one nudle binds a session onto, so the same store that holds the
logs feeds the page.

This is the front door for serving a viewer from plain Python (open store, build
app, run server), so a viewer needs no nudle CLI and embeds in a host process.
"""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
from typing import TYPE_CHECKING

import nudle

from ..presets import open_logs
from .app import build_app


if TYPE_CHECKING:
    from collections.abc import Sequence

    from ..presets import Logs


__all__ = ["run_viewer", "serve_logs"]


async def serve_logs(
    logs: Logs,
    streams: Sequence[str],
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
) -> None:
    """Serve the viewer over an already-open store until cancelled.

    Args:
        logs: the open :class:`~nulog.presets.Logs` handle to view.
        streams: the stream names to offer in the switcher (first is the opener).
        host: the bind address.
        port: the bind port.
    """
    app = build_app(logs, streams)
    await nudle.serve(app, logs.ctx, host=host, port=port)


def run_viewer(
    streams: Sequence[str],
    *,
    path: str | None = None,
    logs: Logs | None = None,
    host: str = "127.0.0.1",
    port: int = 8080,
) -> None:
    """Open (or accept) a store and run the viewer, blocking until interrupted.

    The blocking front door: opens a store at ``path`` (on-disk) or in-memory
    when no ``logs`` handle is given, builds the viewer, and runs the server.
    Pass an existing ``logs`` handle to view a store you already hold open.

    Args:
        streams: the stream names to offer in the switcher (first is the opener).
        path: a RocksDB directory to open, or ``None`` for in-memory (ignored
            when ``logs`` is given).
        logs: an already-open store to view instead of opening one.
        host: the bind address.
        port: the bind port.
    """
    opener = nullcontext(logs) if logs is not None else open_logs(path)
    with opener as handle:
        asyncio.run(serve_logs(handle, streams, host=host, port=port))
