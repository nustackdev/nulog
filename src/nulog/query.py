"""The read face -- pure Nu builders, the same language used to write.

Every function here takes a log ref (``Streams.logs[stream]``) and returns a Nu
Query that yields matching entry ids. Nothing executes: these are trees the
reader (:mod:`nulog.records`) runs under an ``nv.Snapshot``, decoding the hit ids
into :class:`~nulog.records.LogRecord`s.

The shape: iterate the stream's entry keys (``Iter(log.entries.keys())``), bind
each key to an attr ref, and read the entry's typed slots through
``log.entries[key]`` inside the condition. This is the nuspace ``page_rows``
pattern (``Map(Iter(order), transform=pages[item].title)``) turned to filtering.

Ordering is not done here: the reader sorts on the entry ``ts`` field, so these
builders stay order-agnostic (the design note about lexicographic key order is a
nice-to-have, not something correctness leans on).
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

# The attr ref the entry-key binds to inside Filter/Map. One name across the
# module is fine -- these builders are never nested into each other.
_KEY = nu.StrAttrRef("item")


def _ids(log: nu.Nu) -> nu.Nu:
    """The stream of entry ids in the log (a StreamQuery over the keyset)."""
    return nu.Iter(log.entries.keys())


def _entry(log: nu.Nu) -> nu.Nu:
    """The entry the current iteration key points at (read its typed slots off this)."""
    return log.entries[_KEY]


def all_ids(log: nu.Nu) -> nu.Nu:
    """Every entry id in the log, collected into a list (unordered)."""
    return nu.Collect(_ids(log))


def by_level(log: nu.Nu, level: str) -> nu.Nu:
    """Entry ids whose ``level`` slot equals ``level``."""
    return nu.Collect(
        nu.Filter(_ids(log), condition=(nu.StrForm(_entry(log).level) == level)),
    )


def since(log: nu.Nu, ts_ms: int) -> nu.Nu:
    """Entry ids written at or after ``ts_ms`` (epoch millis, inclusive)."""
    return nu.Collect(
        nu.Filter(_ids(log), condition=(nu.IntForm(_entry(log).ts) >= ts_ms)),
    )


def between(log: nu.Nu, start_ms: int, end_ms: int) -> nu.Nu:
    """Entry ids in the window ``[start_ms, end_ms)`` (start inclusive, end exclusive)."""
    ts = nu.IntForm(_entry(log).ts)
    return nu.Collect(
        nu.Filter(_ids(log), condition=nu.And(ts >= start_ms, ts < end_ms)),
    )


def search(log: nu.Nu, text: str) -> nu.Nu:
    """Entry ids whose ``msg`` contains ``text`` (substring match)."""
    return nu.Collect(
        nu.Filter(_ids(log), condition=nu.Contains(nu.StrForm(_entry(log).msg), text)),
    )


def tail(log: nu.Nu, n: int) -> nu.Nu:
    """The newest ``n`` entry ids, newest-first -- order and limit pushed into Nu.

    Entry ids are fixed-width zero-padded, so lexicographic-descending equals
    chronological-descending: ``Sorted(<ids>, reverse=True)`` puts the most recent
    first, and ``Take(..., n)`` keeps only the newest ``n``. So only ``n`` ids come
    back from the store, already ordered -- the reader decodes them as-is, no
    Python-side sort or slice on the tail path.
    """
    return nu.Take(nu.Sorted(all_ids(log), reverse=True), n)


def count_by_level(log: nu.Nu) -> nu.Nu:
    """One Query grouping entry ids by their ``level`` slot: ``{level: [ids]}``.

    A single ``GroupBy`` over the keyset -- one Snapshot, one pass. The caller runs
    it once and turns the per-level lists into counts, backfilling the levels that
    never appear (see :meth:`~nulog.logger.Logger.count_by_level`).
    """
    return nu.GroupBy(_ids(log), key=nu.StrForm(_entry(log).level), item="item")
