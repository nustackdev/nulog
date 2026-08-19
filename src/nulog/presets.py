"""Ready-made brackets: store (kv navigator), ui (nudle viewer), viewer (both)."""

from __future__ import annotations

import tempfile
from typing import TYPE_CHECKING

import nu

from .ui import build_ui


if TYPE_CHECKING:
    from nu.context import Provide, With


__all__ = ["store", "store_ro", "ui", "viewer"]


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


def store_ro(path: str, *, secondary_path: str | None = None) -> nu.With:
    """Read-only Navigator over the RocksDB nulog at ``path``, secondary mode.

    Always opens as a RocksDB secondary instance that catches up with the
    primary in the background, so a live DB another process is writing is
    safe to read. ``secondary_path`` defaults to a fresh directory under
    the system temp dir (not cleaned up on process exit -- the tail files
    are tiny; pass an explicit path if you want to control lifetime).
    """
    if secondary_path is None:
        secondary_path = tempfile.mkdtemp(prefix="nulog-sec-")
    return nu.kv.presets.rocksdb_navigator(
        path,
        read_only=True,
        secondary_path=secondary_path,
    )


def viewer(
    path: str,
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
    secondary_path: str | None = None,
) -> nu.With:
    """One-shot read-only viewer over a RocksDB nulog at ``path``.

    Composes :func:`store_ro` + :func:`ui` + an idle body so the tree runs
    forever until interrupted. The 99% Python-side entrypoint for "open a
    live nulog and just look at it"; also what the ``nulog`` CLI drives.

    Args:
        path: RocksDB directory to open.
        host: uvicorn bind address.
        port: uvicorn bind port.
        secondary_path: RocksDB secondary directory. Defaults to a fresh
            temp dir; pass a stable path when you want to reuse the tail
            state across restarts.
    """
    return nu.With(
        store_ro(path, secondary_path=secondary_path),
        ui(host=host, port=port),
        body=nu.ForeverDo(nu.Delay(nu.Literal(3600))),
    )


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
