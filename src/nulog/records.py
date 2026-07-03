"""Read results as plain Python -- the decode side of a nulog read.

A :class:`LogRecord` is one entry pulled out of the store as a frozen dataclass
(mirrors nuspace's ``BlockData``). :func:`read_records` runs a query that yields
entry ids under an ``nv.Snapshot``, reads each entry's slots, decodes the
``fields`` JSON back to a dict, and hands back ``LogRecord``s sorted newest-first
on ``ts``.

The entry-id stream comes from :mod:`nulog.query` builders (``tail``,
``by_level``, ...). This module owns the id -> record decode and the final sort,
so nothing else parses the store layout by hand.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field

import nu
import nu.virtuals as nv

from .shapes import Streams


__all__ = ["LogRecord", "read_records"]


@dataclass(frozen=True, slots=True)
class LogRecord:
    """One log entry read out of the store.

    Attributes:
        id: the entry id (its key in the stream's ``entries``). Sortable: zero
            padded epoch millis plus a process-local counter.
        ts: epoch millis at write time.
        level: the severity (``"debug"`` / ``"info"`` / ``"warn"`` / ``"error"``).
        msg: the human-readable message.
        fields: the decoded structured kwargs (``{}`` when none).
    """

    id: str
    ts: int
    level: str
    msg: str
    fields: dict[str, object] = field(default_factory=dict)


def _decode_fields(raw: str) -> dict[str, object]:
    """Decode an entry's ``fields`` JSON slot into a dict (``{}`` when blank/bad)."""
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def read_entry(ctx: nu.Context, stream: str, entry_id: str) -> LogRecord:
    """Read one entry record into a :class:`LogRecord`.

    All four slots (``ts``, ``level``, ``msg``, ``fields``) are read in ONE
    ``nv.Snapshot`` generation: a ``DictForm.of`` gathers them into one dict, so
    it's ~1 round-trip per entry, not 4. A missing slot reads as ``EMPTY`` and is
    coerced to its typed default below.
    """
    entry = Streams.logs[stream].entries[entry_id]
    read = nu.DictForm.of(
        ts=nu.IntForm(entry.ts),
        level=nu.StrForm(entry.level),
        msg=nu.StrForm(entry.msg),
        fields=nu.StrForm(entry.fields),
    )
    data = nu.run(nv.Snapshot(read), ctx)[0]
    ts, level, msg, fields = data["ts"], data["level"], data["msg"], data["fields"]
    return LogRecord(
        id=entry_id,
        ts=ts if isinstance(ts, int) else 0,
        level=level if isinstance(level, str) else "",
        msg=msg if isinstance(msg, str) else "",
        fields=_decode_fields(fields if isinstance(fields, str) else ""),
    )


def read_records(
    ctx: nu.Context,
    stream: str,
    id_query: nu.Nu,
    *,
    presorted: bool = False,
    limit: int | None = None,
) -> list[LogRecord]:
    """Run an entry-id query and decode the hits into records, newest-first.

    Args:
        ctx: the bound Context (its Navigator carries the store).
        stream: the stream name the ids belong to.
        id_query: a Nu Query yielding entry ids (from :mod:`nulog.query`).
        presorted: when True the query already yields ids newest-first (the
            ``tail`` path sorts in Nu), so skip the Python-side sort.
        limit: keep at most this many records. On the presorted (``tail``) path
            the ids are sliced before decoding, so only ``limit`` entries are
            read; otherwise the slice is applied after the sort.

    Returns:
        The matching entries as :class:`LogRecord`s, sorted by ``ts`` descending
        (ties broken by id, also descending) so the most recent line is first.
    """
    ids = _as_ids(nu.run(nv.Snapshot(id_query), ctx)[0])
    if presorted:
        if limit is not None:
            ids = ids[:limit]
        return [read_entry(ctx, stream, eid) for eid in ids]
    records = [read_entry(ctx, stream, eid) for eid in ids]
    records.sort(key=lambda r: (r.ts, r.id), reverse=True)
    if limit is not None:
        records = records[:limit]
    return records


def _as_ids(value: object) -> list[str]:
    """Coerce a collected query result into a plain list of id strings."""
    if not isinstance(value, Iterable) or isinstance(value, str | bytes):
        return []
    return [str(v) for v in value]
