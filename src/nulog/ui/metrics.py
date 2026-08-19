"""Metrics tab reads -- kh57-sampled ``[ts_us, value]`` points for the chart.

The tick calls :func:`repaint`; that returns a Nu store command whose
payload is a sample of the selected series over the selected window
(``now_us - window_us .. now_us``). Kh57's range reservoir gives us at
most :data:`~.consts.SAMPLE_LIMIT` points at ~2N read cost regardless of
how many points sit in the window -- billion-entry safe.

Cost analysis: reservoir sampling walks the shifted-key index for the
window and picks ``SAMPLE_LIMIT`` reads; ``Sorted`` sorts the tiny
result by ts. Neither step touches series-size-many keys, so the chart
stays flat-cost as a series grows.
"""

from __future__ import annotations

import nu

from nulog.metrics import Metrics

from . import consts, shape


def repaint() -> nu.Nu:
    """One repaint pass: refresh the metrics chart with fresh sampled points."""
    now = nu.std.time.time_ns() // 1000
    begin = nu.std.time.time_ns() // 1000 - nu.int(shape.MetricsViewState.window) * 1_000_000

    return shape.MetricsBody.chart.set_points(
        nu.Collect(
            nu.Sorted(
                nu.Map(
                    nu.Iter(
                        Metrics.series[shape.MetricsViewState.series].points.sample(
                            consts.SAMPLE_LIMIT,
                            begin,
                            now,
                        )
                    ),
                    nu.List.of(
                        nu.TupleAttrRef("_nl_mpair")[0],
                        nu.dict(nu.TupleAttrRef("_nl_mpair")[1])["value"],
                    ),
                    key="_nl_mpair",
                ),
            ),
        )
    )
