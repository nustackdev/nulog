"""Log-message store layout.

One shape tree: :class:`Messages` at the root, keyed by stream name, each
stream an append-only :class:`ShapesListRef` of :class:`LogEntry`. No kh57
key encoding on the message path -- ordering is positional (append time),
which is chronological by construction. Kh57 stays on the metric side
because that's where reservoir sampling earns its keep.

The :func:`len` op on a ShapesListRef is O(1) via the underlying
substrate, so ``tail(stream, n)`` compiles down to ``len -> slice[len-n:len]
-> reverse`` and touches only the last ``n`` entries -- safe at
trillion-entry scale.
"""

from __future__ import annotations

import nu
from virtuals._views.log_indexed_dict_view import LazyLogIndexedDictView


__all__ = [
    "LEVELS",
    "LogEntry",
    "MessageStream",
    "Messages",
]


LEVELS: tuple[str, ...] = ("debug", "info", "warning", "error", "critical")


class LogEntry(nu.Shape):
    """One log line -- immutable.

    ``ts_us`` is absolute epoch microseconds captured at eval time. ``fields``
    is a JSON string blob of structured kwargs (decoded on read via
    :func:`nulog.messages.query.FieldsFromJson`).
    """

    ts_us: nu.kv.IntRef
    level: nu.kv.StrRef
    msg: nu.kv.StrRef
    fields: nu.kv.StrRef


class MessageStream(nu.Shape):
    """One named stream -- append-only sequence of :class:`LogEntry`.

    Backed by :class:`LogIndexedDictView` (via ``ShapesDictRef``) rather
    than a positional list, so parallel writers never contend on the same
    rocksdb row -- each ``.append()`` picks its own unique log key.
    """

    entries = nu.kv.ShapesDictRef.slot(
        LogEntry, view_type=LazyLogIndexedDictView, key_type=str,
    )


class Messages(nu.Shape):
    """The message store root -- every stream, keyed by name."""

    streams: nu.kv.ShapesDictRef[str, MessageStream]
