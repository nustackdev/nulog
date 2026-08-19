"""Ready-made brackets: store (kv navigator) + ui (nudle viewer)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu

from .ui import build_ui


if TYPE_CHECKING:
    from nu.context import Provide


__all__ = ["store", "ui"]


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


def ui(*, host: str = "127.0.0.1", port: int = 8080) -> Provide:
    """Boot the nudle log viewer over the enclosing bracket's store.

    Stream + series pickers are populated at eval time from
    ``Messages.streams.keys()`` / ``Metrics.series.keys()``, refreshed
    every tick, so new streams / series show up automatically.

    The viewer tree from :func:`~nulog.ui.build_ui` is scope-free; this
    entrypoint runs an untagged ``nu.kv.auto_flow_atomic`` sweep so a
    single-store standalone user does not have to think about atomicity.
    Callers embedding the viewer inside a multi-scope orchestration
    should call :func:`~nulog.ui.build_ui` directly and wrap themselves
    with the scopes that match their fabric layout (typically
    ``scope=Messages`` and ``scope=Metrics``).

    Args:
        host: uvicorn bind address (default ``127.0.0.1``).
        port: uvicorn bind port (default ``8080``).
    """
    tree = build_ui()
    tree = nu.kv.auto_flow_atomic(tree)
    return nu.ui.nudle.server(tree, host=host, port=port)
