"""Metrics store layout.

One shape tree: :class:`Metrics` at the root, keyed by series name, each
series a :class:`Kh57ShapesRef` of :class:`MetricPoint`. Kh57 is the whole
point here -- ``points.sample(n, begin, end)`` gives reservoir-sampled
downsampling for charts, ``points.range(begin, end)`` gives an indexed
time-window scan, and the key IS the timestamp so ordering comes free.
"""

from __future__ import annotations

import nu


__all__ = [
    "MetricPoint",
    "MetricSeries",
    "Metrics",
]


class MetricPoint(nu.Shape):
    """One metric sample -- precise float wall-clock ``ts`` + numeric ``value``.

    ``ts`` is float epoch-seconds at write time; the kh57 key on the parent
    :class:`MetricSeries` is ``int(ts * 1_000_000)`` (microseconds).
    """

    ts: nu.v.FloatRef
    value: nu.v.FloatRef


class MetricSeries(nu.Shape):
    """One named time series -- kh57 int->MetricPoint map."""

    points: nu.v.Kh57ShapesRef[MetricPoint]


class Metrics(nu.Shape):
    """The metrics store root -- every named series, keyed by name."""

    series: nu.v.ShapesDictRef[str, MetricSeries]
