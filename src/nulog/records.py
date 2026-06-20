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
import nu_virtuals as nv
from nu import runtime

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


def _read_str(ctx: nu.Context, ref: nu.Nu, default: str = "") -> str:
    """Read a StrRef into a Python string, defaulting when the slot is missing."""
    expr = nu.If(ref.missing(), nu.Literal(default), nu.StrForm(ref))
    val = runtime.collect(nv.Snapshot(expr), ctx)[0]
    return val if isinstance(val, str) else default


def _read_int(ctx: nu.Context, ref: nu.Nu, default: int = 0) -> int:
    """Read an IntRef into a Python int, defaulting when the slot is missing."""
    expr = nu.If(ref.missing(), nu.Literal(default), nu.IntForm(ref))
    val = runtime.collect(nv.Snapshot(expr), ctx)[0]
    return val if isinstance(val, int) else default


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
    """Read one entry record into a :class:`LogRecord`."""
    entry = Streams.logs[stream].entries[entry_id]
    return LogRecord(
        id=entry_id,
        ts=_read_int(ctx, entry.ts),
        level=_read_str(ctx, entry.level),
        msg=_read_str(ctx, entry.msg),
        fields=_decode_fields(_read_str(ctx, entry.fields)),
    )


def read_records(ctx: nu.Context, stream: str, id_query: nu.Nu) -> list[LogRecord]:
    """Run an entry-id query and decode the hits into records, newest-first.

    Args:
        ctx: the bound Context (its Navigator carries the store).
        stream: the stream name the ids belong to.
        id_query: a Nu Query yielding entry ids (from :mod:`nulog.query`).

    Returns:
        The matching entries as :class:`LogRecord`s, sorted by ``ts`` descending
        (ties broken by id, also descending) so the most recent line is first.
    """
    ids = runtime.collect(nv.Snapshot(id_query), ctx)[0]
    records = [read_entry(ctx, stream, eid) for eid in _as_ids(ids)]
    records.sort(key=lambda r: (r.ts, r.id), reverse=True)
    return records


def _as_ids(value: object) -> list[str]:
    """Coerce a collected query result into a plain list of id strings."""
    if not isinstance(value, Iterable) or isinstance(value, str | bytes):
        return []
    return [str(v) for v in value]
