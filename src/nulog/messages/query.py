"""Log-stream reads -- three primitives, all O(n) in the size of the *result*.

The message store is an append-only :class:`ShapesListRef`; the substrate
gives us O(1) ``len()`` and O(k) slice-descent, so every read here touches
only the entries it returns. Safe at trillion-entry scale.

Rows: ``{"ts_us": int, "level": str, "msg": str, "fields": dict}``.

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
_TS_US = nu.GetItemQuery(_ITEM, "ts_us")
_LEVEL = nu.GetItemQuery(_ITEM, "level")
_MSG = nu.GetItemQuery(_ITEM, "msg")
_FIELDS_STR = nu.GetItemQuery(_ITEM, "fields")


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


def _entries(stream: str | nu.Nu) -> nu.Nu:
    """The entries list for ``stream`` (``stream`` may be a Nu ref)."""
    return Messages.streams[stream].entries


def _row() -> nu.Nu:
    """One decoded row dict from the current entry view bound at ``_nl_item``."""
    return nu.DictForm.of(
        ts_us=_TS_US,
        level=_LEVEL,
        msg=_MSG,
        fields=FieldsFromJson(_FIELDS_STR),
    )


def _rows_of(seq: nu.Nu) -> nu.Nu:
    """Turn an entry-view stream into a ``list[dict]`` row list."""
    return nu.CollectQuery(nu.MapQuery(nu.IterQuery(seq), _row(), key="_nl_item"))


def tail(stream: str | nu.Nu, n: int | nu.Nu) -> nu.Nu:
    """The newest ``n`` entries of ``stream``, newest-first.

    O(n) -- reads the sequence length once, slices ``[len-n : len]``, then
    reverses the slice. Never walks the whole stream.
    """
    entries = _entries(stream)
    length = entries.len()
    # start = max(0, length - n); Python-style negative slicing wraps at the
    # end of the sequence, so an unclamped ``length - n`` would silently
    # return fewer than the available entries when ``n > len``. Clamp here.
    start = nu.IfQuery(nu.GeQuery(length, n), length - n, nu.LiteralQuery(0))
    window = nu.GetItemQuery(entries, nu.SliceQuery(start, length, 1))
    return _rows_of(nu.ReversedQuery(window))


def slice(
    stream: str | nu.Nu,
    start: int | nu.Nu,
    stop: int | nu.Nu,
    step: int | nu.Nu = 1,
) -> nu.Nu:
    """Positional slice of ``stream``: ``entries[start:stop:step]``, decoded.

    Supports negative indices with Python semantics (``start=-100`` is
    ``len-100``). O(``(stop-start)/step``); does not walk beyond the slice.
    """
    entries = _entries(stream)
    return _rows_of(nu.GetItemQuery(entries, nu.SliceQuery(start, stop, step)))


def point(stream: str | nu.Nu, index: int | nu.Nu) -> nu.Nu:
    """One entry at positional ``index`` in ``stream``, decoded to a row dict."""
    entry = Messages.streams[stream].entries[index]
    return nu.DictForm.of(
        ts_us=entry.ts_us,
        level=entry.level,
        msg=entry.msg,
        fields=FieldsFromJson(entry.fields),
    )
