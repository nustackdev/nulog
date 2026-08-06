"""Log-stream reads -- three primitives.

Rows: ``{"ts_us": int, "level": str, "msg": str, "fields": dict}``.

The message store is a :class:`LogIndexedDictView` (multi-writer-safe append
log). Its ``__keys__/`` sibling holds chronological order, so:

- :func:`tail` uses a bounded reverse-cursor scan (``keys_reverse``) -- O(n)
  in the *result*, safe against arbitrarily large streams.
- :func:`slice` and :func:`point` are inherently positional; the view has no
  positional index, so they materialize the value stream and slice it
  client-side. O(*stream*) -- use ``tail`` when you can.

Callers who want level or substring filtering do it *outside* the read
(``[r for r in rows if r["level"] == "error"]``). No index-less full-scan
predicates live in this module -- this is not Elasticsearch.
"""

from __future__ import annotations

import json

import nu

from .shape import Messages


__all__ = [
    "FieldsFromJson",
    "point",
    "slice",
    "tail",
]


_ITEM = nu.AnyAttrRef("_nl_item")
_TS_US = nu.GetItem(_ITEM, "ts_us")
_LEVEL = nu.GetItem(_ITEM, "level")
_MSG = nu.GetItem(_ITEM, "msg")
_FIELDS_STR = nu.GetItem(_ITEM, "fields")


@nu.host
def FieldsFromJson(raw: str) -> dict:  # noqa: N802
    """Decode the opaque ``fields`` JSON string back to a dict (empty on bad/None)."""
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return obj if isinstance(obj, dict) else {}


_KEY = nu.AnyAttrRef("_nl_key")


def _entries(stream: str | nu.Nu) -> nu.Nu:
    """The entries mapping for ``stream`` (``stream`` may be a Nu ref)."""
    return Messages.streams[stream].entries


def _values_list(stream: str | nu.Nu) -> nu.Nu:
    """Materialize entry values in insertion order.

    Used only by :func:`slice` and :func:`point`, which are inherently
    positional. Cost is O(*stream size*); prefer :func:`tail` when you can.
    """
    return nu.Collect(nu.Iter(_entries(stream).values()))


def _row() -> nu.Nu:
    """One decoded row dict from the current entry view bound at ``_nl_item``."""
    return nu.Dict.of(
        ts_us=_TS_US,
        level=_LEVEL,
        msg=_MSG,
        fields=FieldsFromJson(_FIELDS_STR),
    )


def _rows_of(seq: nu.Nu) -> nu.Nu:
    """Turn an entry-view stream into a ``list[dict]`` row list."""
    return nu.Collect(nu.Map(nu.Iter(seq), _row(), key="_nl_item"))


def tail(stream: str | nu.Nu, n: int | nu.Nu) -> nu.Nu:
    """The newest ``n`` entries of ``stream``, newest-first.

    O(n) via a bounded reverse-cursor scan over ``__keys__/`` -- reads
    exactly n keys and n entries regardless of stream size.
    """
    entries = _entries(stream)
    keys = nu.Collect(nu.std.itertools.islice(entries.reversed_keys(), n))
    return _rows_of(
        nu.Map(
            nu.Iter(keys),
            nu.GetItem(entries, _KEY),
            key="_nl_key",
        ),
    )


def slice(
    stream: str | nu.Nu,
    start: int | nu.Nu,
    stop: int | nu.Nu,
    step: int | nu.Nu = 1,
) -> nu.Nu:
    """Positional slice of ``stream``: ``entries[start:stop:step]``, decoded.

    O(*stream size*): the view has no positional index, so the whole value
    stream materializes client-side before slicing. Prefer :func:`tail` for
    "last N" reads.
    """
    values = _values_list(stream)
    return _rows_of(nu.GetItem(values, nu.Slice(start, stop, step)))


def point(stream: str | nu.Nu, index: int | nu.Nu) -> nu.Nu:
    """One entry at positional ``index`` in ``stream``, decoded to a row dict.

    O(*stream size*) for the same reason as :func:`slice`.
    """
    entry = nu.GetItem(_values_list(stream), index)
    return nu.Dict.of(
        ts_us=nu.GetItem(entry, "ts_us"),
        level=nu.GetItem(entry, "level"),
        msg=nu.GetItem(entry, "msg"),
        fields=FieldsFromJson(nu.GetItem(entry, "fields")),
    )
