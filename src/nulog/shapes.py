"""The store layout -- the single source of truth for a nulog store.

nulog is append-only logs kept in nv (the RocksDB-backed Shape fabric). One store
holds many named streams ("app", "scraper", ...). A stream is a Log, a Log is a
dict of entries keyed by a sortable entry id, and an entry is four slots:

- ``ts``     -- epoch millis, when the line was written.
- ``level``  -- one of ``"debug"`` / ``"info"`` / ``"warn"`` / ``"error"``.
- ``msg``    -- the human message.
- ``fields`` -- a JSON object string of structured kwargs, decoded to a dict on
  read (the same trick nuspace uses for block meta).

Nothing here is ever updated in place. A log line is one new entry under a fresh
id, so the whole store is append-only and history is just the keyset.

Navigation mirrors nuspace: ``Streams.logs[stream].entries[entry_id].ts``, and so
on. Entry ids are minted in Python (see :mod:`nulog.logger`), no seq counter in
the store.
"""

from __future__ import annotations

import nu
import nu_virtuals as nv


__all__ = ["Log", "LogEntry", "Streams"]


class LogEntry(nu.Shape):
    """One log entry -- a single immutable line.

    Attributes:
        ts: epoch millis at write time (the clock the read layer sorts on).
        level: the severity, one of ``"debug"`` / ``"info"`` / ``"warn"`` /
            ``"error"``.
        msg: the human-readable message.
        fields: structured kwargs as a JSON object string (``"{}"`` when none),
            decoded back to a dict on read.
    """

    ts = nv.IntRef.slot()
    level = nv.StrRef.slot()
    msg = nv.StrRef.slot()
    fields = nv.StrRef.slot()  # JSON object string of structured kwargs


class Log(nu.Shape):
    """One named stream -- an append-only dict of entries keyed by entry id.

    Attributes:
        entries: maps a sortable entry id to its :class:`LogEntry`. Append-only:
            a new line is a new key, existing keys are never rewritten.
    """

    entries = nv.ShapesDictRef.slot(LogEntry, key_type=str)


class Streams(nu.Shape):
    """The store root -- every stream, keyed by name.

    Attributes:
        logs: maps a stream name (``"app"``, ``"scraper"``, ...) to its
            :class:`Log`. One store holds them all; a Navigator bound to this
            shape is what the logger and queries run against.
    """

    logs = nv.ShapesDictRef.slot(Log, key_type=str)
