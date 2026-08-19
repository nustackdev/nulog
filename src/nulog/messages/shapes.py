"""Log-message store layout.

One shape tree: :class:`Messages` at the root, keyed by stream name, each
stream an append-only :class:`ShapesListRef` of :class:`LogEntry`.

No kh57 key encoding on the message path -- ordering is positional (append time),
which is chronological by construction.
Kh57 stays on the metric side because that's where reservoir sampling earns its keep.
"""

from __future__ import annotations

import nu
from virtuals.views import LazyLogIndexedDictView


__all__ = [
    "LogEntry",
    "MessageStream",
    "Messages",
]


class LogEntry(nu.Shape):
    """One log line -- immutable.

    ``ts_us`` is absolute epoch microseconds captured at eval time. ``fields``
    is a whole-blob dict of structured kwargs, stored opaquely via
    :class:`~nu.kv.PrimitiveDictRef` (no per-key decomposition).
    """

    ts_us: nu.kv.IntRef
    level: nu.kv.StrRef
    msg: nu.kv.StrRef
    fields: nu.kv.PrimitiveDictRef[str, object]


class MessageStream(nu.Shape):
    """One named stream -- append-only sequence of :class:`LogEntry`.

    Backed by :class:`LogIndexedDictView` (via ``ShapesDictRef``) rather
    than a positional list, so parallel writers never contend on the same
    rocksdb row -- each ``.append()`` picks its own unique log key.
    """

    entries = nu.kv.ShapesDictRef.slot(
        LogEntry,
        view_type=LazyLogIndexedDictView,
        key_type=str,
    )


class Messages(nu.Shape):
    """The message store root -- every stream, keyed by name."""

    streams: nu.kv.ShapesDictRef[str, MessageStream]
