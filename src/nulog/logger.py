"""The write face -- a handle on one stream, in two modes.

A :class:`Logger` is bound to one stream name and one Context. It writes lines and
reads them back, both in Nu:

- **Eager** (the 90% case): ``log.info(msg, **fields)`` (and ``.warn`` / ``.error``
  / ``.debug`` / the generic ``.log``) build the append Command and run it now,
  inside an ``nv.Transaction``, returning the new entry id.
- **Compose** (the Nu payoff): ``log.entry(level, msg, **fields)`` returns the
  append Command WITHOUT running it, so a host can weave it into a bigger program
  and get an atomic log-plus-effect, e.g.::

      nv.Transaction(Account.balance.store(...), log.entry("info", "debit", amount=n))

The eager methods are thin wrappers: they call :meth:`Logger.entry`, wrap it in a
Transaction, and execute.

Entry ids are minted in Python (like nuspace mints block ids): zero-padded epoch
millis plus a process-local monotonic counter, so ids are unique within a process
and sort chronologically. The counter breaks ties inside the same millisecond.
"""

from __future__ import annotations

import itertools
import json
import time
from typing import TYPE_CHECKING

import nu
import nu_virtuals as nv
from nu import runtime

from . import query
from .records import read_records
from .shapes import Streams


if TYPE_CHECKING:
    from .records import LogRecord


__all__ = ["Logger", "new_entry_id", "now_ms"]

# Process-local monotonic counter, zero-padded into the entry id so two lines in
# the same millisecond still get distinct, ordered ids.
_counter = itertools.count()


def now_ms() -> int:
    """The current time as epoch millis."""
    return int(time.time() * 1000)


def new_entry_id(ts_ms: int) -> str:
    """Mint a sortable entry id from a timestamp.

    Args:
        ts_ms: epoch millis for the entry.

    Returns:
        ``f"{ts_ms:013d}{counter:06d}"`` -- zero-padded so lexicographic and
        chronological order agree, with the process-local counter for collisions
        inside one millisecond.
    """
    return f"{ts_ms:013d}{next(_counter):06d}"


class Logger:
    """A write-plus-read handle on one named stream, bound to one Context.

    Build these through :meth:`nulog.presets.Logs.stream`, not directly. The same
    handle writes lines (eager or compose) and reads them back as
    :class:`~nulog.records.LogRecord`s.

    Attributes:
        stream: the stream name this handle writes to and reads from.
    """

    def __init__(self, ctx: nu.Context, stream: str) -> None:
        """Bind a logger to a stream and a Context.

        Args:
            ctx: the bound Context (its Navigator carries the store).
            stream: the stream name (``"app"``, ``"scraper"``, ...).
        """
        self._ctx = ctx
        self.stream = stream

    # ---- the log ref this handle reads/writes through ----------------------

    @property
    def _log(self) -> nu.Nu:
        """The ref for this handle's stream: ``Streams.logs[stream]``."""
        return Streams.logs[self.stream]

    # ---- compose mode (returns Nu, does not run) ---------------------------

    def entry(
        self, level: str, msg: str, *, entry_id: str | None = None, **fields: object
    ) -> nu.Nu:
        """Build the append Command for one line WITHOUT running it.

        The returned Command writes the four slots (``ts``, ``level``, ``msg``,
        ``fields``) at a fresh entry id. Hand it to ``nv.Transaction`` yourself to
        weave it into a bigger atomic program.

        Args:
            level: the severity (``"debug"`` / ``"info"`` / ``"warn"`` /
                ``"error"``).
            msg: the human-readable message.
            entry_id: override the minted id (rarely needed; for testing/replay).
            **fields: arbitrary JSON-serializable structured kwargs.

        Returns:
            A Nu Command (append the entry). Not executed.
        """
        eid = entry_id or new_entry_id(now_ms())
        ts_ms = int(eid[:13])
        rec = self._log.entries[eid]
        return (
            rec.ts.store(ts_ms)
            >> rec.level.store(level)
            >> rec.msg.store(msg)
            >> rec.fields.store(json.dumps(fields))
        )

    # ---- eager mode (builds, wraps, runs now) ------------------------------

    def log(self, level: str, msg: str, **fields: object) -> str:
        """Append one line now, inside a Transaction. Returns the new entry id.

        Args:
            level: the severity.
            msg: the human-readable message.
            **fields: arbitrary JSON-serializable structured kwargs.

        Returns:
            The minted entry id of the line just written.
        """
        eid = new_entry_id(now_ms())
        runtime.execute(nv.Transaction(self.entry(level, msg, entry_id=eid, **fields)), self._ctx)
        return eid

    def debug(self, msg: str, **fields: object) -> str:
        """Append a ``debug`` line now. Returns the entry id."""
        return self.log("debug", msg, **fields)

    def info(self, msg: str, **fields: object) -> str:
        """Append an ``info`` line now. Returns the entry id."""
        return self.log("info", msg, **fields)

    def warn(self, msg: str, **fields: object) -> str:
        """Append a ``warn`` line now. Returns the entry id."""
        return self.log("warn", msg, **fields)

    def error(self, msg: str, **fields: object) -> str:
        """Append an ``error`` line now. Returns the entry id."""
        return self.log("error", msg, **fields)

    # ---- read face (runs query.py builders, decodes to records) ------------

    def tail(self, n: int = 20) -> list[LogRecord]:
        """The most recent ``n`` lines, newest-first."""
        return read_records(self._ctx, self.stream, query.tail(self._log, n), presorted=True)

    def by_level(self, level: str) -> list[LogRecord]:
        """Every line at ``level``, newest-first."""
        return read_records(self._ctx, self.stream, query.by_level(self._log, level))

    def errors(self) -> list[LogRecord]:
        """Every ``error`` line, newest-first."""
        return self.by_level("error")

    def since(self, ts_ms: int) -> list[LogRecord]:
        """Lines written at or after ``ts_ms``, newest-first."""
        return read_records(self._ctx, self.stream, query.since(self._log, ts_ms))

    def between(self, start_ms: int, end_ms: int) -> list[LogRecord]:
        """Lines in ``[start_ms, end_ms)``, newest-first."""
        return read_records(self._ctx, self.stream, query.between(self._log, start_ms, end_ms))

    def search(self, text: str) -> list[LogRecord]:
        """Lines whose message contains ``text``, newest-first."""
        return read_records(self._ctx, self.stream, query.search(self._log, text))

    def count_by_level(self) -> dict[str, int]:
        """A ``{level: count}`` tally over the whole stream."""
        groups = runtime.collect(nv.Snapshot(query.count_by_level(self._log)), self._ctx)[0]
        groups = groups if isinstance(groups, dict) else {}
        return {level: len(groups.get(level, ())) for level in query.LEVELS}
