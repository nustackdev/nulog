"""The read face -- pure Nu builders, the same language used to write.

Every function here takes a log ref (``Streams.logs[stream]``) and returns a Nu
Query. Nothing executes: these are trees the reader (:mod:`nulog.records`) runs
under an ``nv.Snapshot``, decoding the hits into
:class:`~nulog.records.LogRecord`s.

The shape: walk the stream's entries as ``(id, entry)`` pairs
(``IterQuery(log.entries.items())``), bind each pair to the loop-var attr, read
the entry's typed slots off the materialised view, and keep the ids whose slots
match. One name (``"item"``) is bound across the walk -- these builders are never
nested into each other. The current item is a ``(id, view)`` tuple: ``_key_of``
plucks the id, ``_field(name)`` plucks a slot off the view.

Ordering is not done here (except ``tail``, which sorts the id keyset): the
reader sorts on the entry ``ts`` field, so the filter builders stay
order-agnostic.
"""

from __future__ import annotations

import nu


__all__ = [
    "all_ids",
    "between",
    "by_level",
    "count_by_level",
    "search",
    "since",
    "tail",
]

LEVELS = ("debug", "info", "warn", "error")

# The loop-var the current entry pair binds to inside Filter/Map: a
# ``(id, view)`` tuple. ``_key_of`` is the id, ``_field`` reads a slot off view.
_ITEM = nu.AnyAttrRef("item")
_KEY_OF = nu.GetItemQuery(_ITEM, 0)


def _field(name: str) -> nu.Nu:
    """A slot value off the current entry's materialised view (``view[name]``)."""
    return nu.GetItemQuery(nu.GetItemQuery(_ITEM, 1), name)


def _items(log: nu.Nu) -> nu.Nu:
    """The stream of ``(id, entry-view)`` pairs in the log."""
    return nu.IterQuery(log.entries.items())


def _keys(log: nu.Nu) -> nu.Nu:
    """The stream of entry ids in the log."""
    return nu.MapQuery(_items(log), _KEY_OF)


def _keys_where(log: nu.Nu, predicate: nu.Nu) -> nu.Nu:
    """Collect the ids of entries whose ``predicate`` (over the view) holds."""
    return nu.CollectQuery(nu.MapQuery(nu.FilterQuery(_items(log), predicate), _KEY_OF))


def all_ids(log: nu.Nu) -> nu.Nu:
    """Every entry id in the log, collected into a list (unordered)."""
    return nu.CollectQuery(_keys(log))


def by_level(log: nu.Nu, level: str) -> nu.Nu:
    """Entry ids whose ``level`` slot equals ``level``."""
    return _keys_where(log, nu.EqQuery(_field("level"), nu.LiteralQuery(level)))


def since(log: nu.Nu, ts_ms: int) -> nu.Nu:
    """Entry ids written at or after ``ts_ms`` (epoch millis, inclusive)."""
    return _keys_where(log, nu.GeQuery(_field("ts"), nu.LiteralQuery(ts_ms)))


def between(log: nu.Nu, start_ms: int, end_ms: int) -> nu.Nu:
    """Entry ids in the window ``[start_ms, end_ms)`` (start inclusive, end exclusive)."""
    ts = _field("ts")
    return _keys_where(
        log,
        nu.AndQuery(
            nu.GeQuery(ts, nu.LiteralQuery(start_ms)), nu.LtQuery(ts, nu.LiteralQuery(end_ms))
        ),
    )


def search(log: nu.Nu, text: str) -> nu.Nu:
    """Entry ids whose ``msg`` contains ``text`` (substring match)."""
    return _keys_where(log, nu.ContainsQuery(_field("msg"), nu.LiteralQuery(text)))


def tail(log: nu.Nu) -> nu.Nu:
    """Every entry id, sorted newest-first -- the reader slices to the tail size.

    Entry ids are fixed-width zero-padded, so lexicographic-descending equals
    chronological-descending: ``ReversedQuery(SortedQuery(...))`` puts the most
    recent first. The reader takes the leading ``n`` (its ``limit``) and decodes
    only those, so at most ``n`` entries are read, already ordered.
    """
    return nu.CollectQuery(nu.ReversedQuery(nu.SortedQuery(_keys(log))))


def count_by_level(log: nu.Nu) -> nu.Nu:
    """The ``level`` slot of every entry, collected -- the caller tallies.

    One pass over the keyset yields every level in one Snapshot; the caller
    counts them per level, backfilling the levels that never appear (see
    :meth:`~nulog.logger.Logger.count_by_level`).
    """
    return nu.CollectQuery(nu.MapQuery(_items(log), _field("level")))
