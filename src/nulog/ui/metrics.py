"""Metrics tab reads -- kh57-sampled ``[ts_us, value]`` points for the chart.

The tick calls :func:`_repaint`; that returns a Nu store command whose
payload is a sample of the selected series over the selected window
(``now_us - window_us .. now_us``). Kh57's range reservoir gives us at
most :data:`~.shape.SAMPLE_LIMIT` points at ~2N read cost regardless of
how many points sit in the window -- billion-entry safe.

Cost analysis: reservoir sampling walks the shifted-key index for the
window and picks ``SAMPLE_LIMIT`` reads; ``SortedQuery`` sorts the tiny
result by ts. Neither step touches series-size-many keys, so the chart
stays flat-cost as a series grows.
"""

from __future__ import annotations

import nu
import nu.std.time as _nu_time

from ..metrics.shape import Metrics
from .shape import SAMPLE_LIMIT, MetricsBody, MetricsViewState


__all__ = ["XYPair"]


_PAIR = nu.AnyAttrRef("_nl_mpair")
_KEY = nu.GetItemQuery(_PAIR, 0)
_VALUE = nu.GetItemQuery(nu.GetItemQuery(_PAIR, 1), "value")


@nu.host
def XYPair(x: int, y: float) -> list:  # noqa: N802
    """Two-element positional row for :class:`nu.ui.LineChart`."""
    return [x, y]


def _now_us() -> nu.Nu:
    """Absolute epoch microseconds at eval time."""
    return _nu_time.time_ns() // 1000


def _window_us() -> nu.Nu:
    """The currently-selected window in microseconds (parsed from ``MetricsViewState.window``)."""
    return nu.MulQuery(nu.IntQuery(MetricsViewState.window), nu.LiteralQuery(1_000_000))


def _chart_points() -> nu.Nu:
    """``[[ts_us, value], ...]`` sorted by ts, sampled from the selected series."""
    now = _now_us()
    begin = nu.SubQuery(now, _window_us())
    pairs = Metrics.series[MetricsViewState.series].points.sample(SAMPLE_LIMIT, begin, now)
    return nu.CollectQuery(
        nu.SortedQuery(nu.MapQuery(nu.IterQuery(pairs), XYPair(_KEY, _VALUE), key="_nl_mpair")),
    )


def _repaint() -> nu.Nu:
    """One repaint pass: refresh the metrics chart with fresh sampled points."""
    return MetricsBody.chart.set_points(_chart_points())
