"""Log-stream reads -- two primitives.

Rows: ``{"ts_us": int, "level": str, "msg": str, "fields": dict}``.

The message store is a :class:`LogIndexedDictView` (multi-writer-safe append
log). Its ``__keys__/`` sibling holds chronological order, so:

- :func:`tail` uses a bounded reverse-cursor scan (``reversed_values``) --
  O(n) in the *result*, safe against arbitrarily large streams.
- :func:`slice` is a forward ``islice`` over ``.values()`` -- O(stop) walks,
  no full-stream materialization. Non-negative bounds only; for "last N"
  use :func:`tail`.

Callers who want level or substring filtering do it *outside* the read
(``[r for r in rows if r["level"] == "error"]``). No index-less full-scan
predicates live in this module -- this is not Elasticsearch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu

from .shapes import Messages


if TYPE_CHECKING:
    from nu.lang import IntArg, StrArg


__all__ = [
    "slice",
    "tail",
]


def _row_from(item_key: str) -> nu.Nu:
    """The ``{ts_us, level, msg, fields}`` row projected off ``item_key``."""
    return nu.Dict.of(
        ts_us=nu.AnyAttrRef(item_key)["ts_us"],
        level=nu.AnyAttrRef(item_key)["level"],
        msg=nu.AnyAttrRef(item_key)["msg"],
        fields=nu.AnyAttrRef(item_key)["fields"],
    )


def tail(stream: StrArg, n: IntArg) -> nu.Nu:
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
    stream: StrArg,
    start: IntArg,
    stop: IntArg,
    step: IntArg = 1,
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
