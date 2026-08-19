"""Read + write primitives over the message store.

Write:
- :func:`append` -- the write-tree primitive. Every logger method, every
  ``std_compat`` rewrite, every direct write funnels through here.

Read:
- :func:`tail`  -- newest N, newest-first. O(n) via a bounded reverse-cursor
  scan (``reversed_values``), safe against arbitrarily large streams.
- :func:`slice` -- forward ``islice`` over ``.values()``. O(``stop``), no
  full-stream materialization. Non-negative bounds only; for "last N",
  use :func:`tail`.

Rows: ``{"ts_us": int, "level": str, "msg": str, "fields": dict}``.

Callers who want level or substring filtering do it *outside* the read
(``[r for r in rows if r["level"] == "error"]``). No index-less full-scan
predicates live in this module -- this is not Elasticsearch.
"""

from __future__ import annotations

import nu

from .interactions import level_name, percent_format
from .shapes import Messages


__all__ = [
    "append",
    "slice",
    "tail",
]


# --- write -----------------------------------------------------------------


def append(
    stream: nu.StrArg,
    level: nu.IntArg | nu.StrArg,
    msg: nu.StrArg,
    args: tuple[object, ...],
    extra: nu.DictArg[str, object] | None,
) -> nu.Nu:
    """Build the Command tree that appends one entry to ``stream``."""
    return Messages.streams[stream].entries.set_item(
        nu.std.uuid.uuid4().hex(),
        nu.Dict.of(
            ts_us=nu.std.time.time_ns() // 1000,
            level=level_name(level),
            msg=percent_format(msg, *args),
            fields=extra or {},
        ),
    )


# --- read ------------------------------------------------------------------


def _row_from(item_key: nu.StrArg) -> nu.Nu:
    """The ``{ts_us, level, msg, fields}`` row projected off ``item_key``."""
    return nu.Dict.of(
        ts_us=nu.AnyAttrRef(item_key)["ts_us"],
        level=nu.AnyAttrRef(item_key)["level"],
        msg=nu.AnyAttrRef(item_key)["msg"],
        fields=nu.AnyAttrRef(item_key)["fields"],
    )


def tail(stream: nu.StrArg, n: nu.IntArg) -> nu.Nu:
    """The newest ``n`` entries of ``stream``, newest-first.

    O(n) via a bounded reverse-cursor scan over ``__keys__/`` -- reads
    exactly n entries regardless of stream size.
    """
    return nu.Collect(
        nu.Map(
            nu.std.itertools.islice(Messages.streams[stream].entries.reversed_values(), n),
            _row_from("_nl_item"),
            key="_nl_item",
        )
    )


def slice(
    stream: nu.StrArg,
    start: nu.IntArg,
    stop: nu.IntArg,
    step: nu.IntArg = 1,
) -> nu.Nu:
    """Positional forward slice of ``stream``: ``islice(entries, start, stop, step)``.

    O(``stop``): walks the value stream via ``itertools.islice`` and stops
    early -- no full-stream materialization. Non-negative bounds only;
    for "last N" use :func:`tail`.
    """
    return nu.Collect(
        nu.Map(
            nu.std.itertools.islice(
                Messages.streams[stream].entries.values(),
                start,
                stop,
                step,
            ),
            _row_from("_nl_item"),
            key="_nl_item",
        )
    )
