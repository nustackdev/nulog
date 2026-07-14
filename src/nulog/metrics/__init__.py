"""nulog.metrics -- metric time-series store: shape + write API + read API.

Writes are one op (``nulog.observe(name, value)``); reads are three
primitives (``range``, ``sample``, ``point``) that ride kh57's shifted-key
substrate. See :mod:`nulog.metrics.shape`, :mod:`nulog.metrics.log`,
:mod:`nulog.metrics.query`.
"""

from __future__ import annotations

from .log import observe
from .query import point, range, sample
from .shape import MetricPoint, Metrics, MetricSeries


__all__ = [
    "MetricPoint",
    "MetricSeries",
    "Metrics",
    "observe",
    "point",
    "range",
    "sample",
]
