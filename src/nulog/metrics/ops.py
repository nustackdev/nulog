"""Write + read primitives over the metric store.

Write:
- :func:`observe` -- append one point to ``Metrics.series[name].points``
  keyed by microsecond epoch. Same-us writes collide (last-write-wins);
  pass an explicit ``ts`` for replay or batches.

Read:
- :func:`range`  -- every point with kh57 key in ``[begin, end)``,
  key-ordered. Indexed; cost is O(number of points in the window).
- :func:`sample` -- kh57 range reservoir sample: up to ``n`` points from
  ``[begin, end)``. Deterministic given the store's salt, stable under
  appends outside the window. ~``2n`` reads, not O(series size).

Rows: ``{"ts_us": int, "ts": float, "value": float}``.
"""

from __future__ import annotations

import nu

from .shapes import Metrics


__all__ = [
    "observe",
    "range",
    "sample",
]


# --- write -----------------------------------------------------------------


def observe(name: nu.StrArg, value: nu.FloatArg, *, ts: nu.FloatArg | None = None) -> nu.Nu:
    """Append one point to metric ``name``.

    Args:
        name: series name (``"cpu_load"``, ``"http_latency_ms"``, ...).
        value: the sample. Python numbers get wrapped in ``Float``; a
            Nu expression (Ref / Query yielding a float) is cast through
            ``ToFloat`` so live-computed values (rates from a loop,
            deltas over scratch counters, etc.) can be observed directly.
        ts: optional wall-clock time (seconds since epoch). When ``None``,
            key + ``ts`` are minted at eval time. Same-microsecond writes
            collide (last-write-wins).
    """
    return nu.Let(
        "_nl_key_us",
        nu.If(ts, nu.int(ts) * 1_000_000, nu.std.time.time_ns() // 1000),
        body=Metrics.series[name].points.set_item(
            nu.IntAttrRef("_nl_key_us"),
            nu.Dict.of(
                ts=nu.IntAttrRef("_nl_key_us") / 1_000_000.0,
                value=nu.float(value),
            ),
        ),
    )


# --- read ------------------------------------------------------------------


def range(
    name: nu.StrArg,
    begin: nu.IntArg,
    end: nu.IntArg,
) -> nu.Nu:
    """Every point in ``name`` with kh57 key in ``[begin, end)``, key-ordered.

    Keys are microsecond epochs, so ``begin`` / ``end`` are microsecond
    bounds. Indexed under the hood -- cost is O(number of points in the
    window), not O(series size).
    """
    pair = nu.AnyAttrRef("_nl_mpair")
    return nu.Collect(
        nu.Map(
            nu.Iter(Metrics.series[name].points.range(begin, end)),
            nu.Dict.of(
                ts_us=nu.GetItem(pair, 0),
                ts=nu.GetItem(nu.GetItem(pair, 1), "ts"),
                value=nu.GetItem(nu.GetItem(pair, 1), "value"),
            ),
            key="_nl_mpair",
        )
    )


def sample(
    name: nu.StrArg,
    n: nu.IntArg,
    begin: nu.IntArg | None = None,
    end: nu.IntArg | None = None,
) -> nu.Nu:
    """Up to ``n`` kh57-sampled points from ``name`` in ``[begin, end)``.

    Kh57 range reservoir sampling: deterministic given the store's salt,
    stable under appends outside the queried range. Cost is ~``2n`` reads,
    not O(series size) -- this is what kh57 buys.
    """
    pair = nu.AnyAttrRef("_nl_mpair")
    return nu.Collect(
        nu.Map(
            nu.Iter(Metrics.series[name].points.sample(n, begin, end)),
            nu.Dict.of(
                ts_us=nu.GetItem(pair, 0),
                ts=nu.GetItem(nu.GetItem(pair, 1), "ts"),
                value=nu.GetItem(nu.GetItem(pair, 1), "value"),
            ),
            key="_nl_mpair",
        )
    )
