"""The store layout -- one picture of the two Nu trees behind nulog.

Two disjoint Shape trees share one virtuals Navigator:

- :class:`Logs` -- append-only log streams. Each stream is a kh57 shapes map of
  :class:`LogEntry`, keyed by an integer minted at eval time via
  :data:`nulog.writes.NextLogKey` (see the key encoding there).
- :class:`Metrics` -- kh57 time series. Each series is a kh57 shapes map of
  :class:`MetricPoint`, keyed by microsecond epoch time.

Kh57 gives us chronological order for free, cheap ``entries.range(begin, end)``
scans for time windows, and ``entries.sample(n, ...)`` reservoir sampling for
chart thinning -- one substrate for both domains.

:class:`ViewState` is the viewer's tiny server-side mirror of the browser's
filter picks; the tick reads it, so the table always reflects the current
selection without round-tripping to the tab every second.
"""

from __future__ import annotations

import nu


__all__ = [
    "LEVELS",
    "LogEntry",
    "LogStream",
    "Logs",
    "MetricPoint",
    "MetricSeries",
    "Metrics",
    "ViewState",
]

# Canonical severity levels the viewer tallies. Any string level is valid on
# write; these four just get first-class count Refs on the page.
LEVELS: tuple[str, ...] = ("debug", "info", "warn", "error")


# ---- logs -----------------------------------------------------------------


class LogEntry(nu.Shape):
    """One log line -- immutable.

    ``ts_us`` is absolute epoch microseconds (redundant with ``key >> 8`` on the
    parent kh57 map, kept as a leaf so reads don't decode the key). ``fields``
    is a JSON string blob of structured kwargs.
    """

    ts_us: nu.v.IntRef
    level: nu.v.StrRef
    msg: nu.v.StrRef
    fields: nu.v.StrRef


class LogStream(nu.Shape):
    """One named stream -- a kh57 map of entries, chronological by key."""

    entries: nu.v.Kh57ShapesRef[LogEntry]


class Logs(nu.Shape):
    """The log store root -- every stream, keyed by name."""

    streams: nu.v.ShapesDictRef[str, LogStream]


# ---- metrics --------------------------------------------------------------


class MetricPoint(nu.Shape):
    """One metric sample -- precise float wall-clock ts + numeric value.

    ``ts`` is the float epoch-seconds at write time; the kh57 key on the
    parent :class:`MetricSeries` is ``int(ts * 1_000_000)`` (microseconds).
    """

    ts: nu.v.FloatRef
    value: nu.v.FloatRef


class MetricSeries(nu.Shape):
    """One named time series -- kh57 int->MetricPoint map."""

    points: nu.v.Kh57ShapesRef[MetricPoint]


class Metrics(nu.Shape):
    """The metrics store root -- every named series, keyed by name."""

    series: nu.v.ShapesDictRef[str, MetricSeries]


# ---- viewer state ---------------------------------------------------------


class ViewState(nu.Shape):
    """Server-side mirror of the viewer's current filter, read by the tick."""

    stream: nu.v.StrRef
    level: nu.v.StrRef      # "all" | "debug" | "info" | "warn" | "error"
    search: nu.v.StrRef
