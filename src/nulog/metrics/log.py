"""Metric writes -- one op, :func:`observe`.

``observe(name, value)`` builds the Command tree that appends one point to
``Metrics.series[name].points`` keyed by microsecond epoch. Same-us writes
collide (last-write-wins); pass an explicit ``ts`` for replay or batches.
"""

from __future__ import annotations

import itertools

import nu
import nu.std.time as _nu_time

from .shape import Metrics


__all__ = [
    "observe",
]


_call_counter = itertools.count()


def _now_us() -> nu.Nu:
    """Absolute epoch microseconds at eval time."""
    return _nu_time.time_ns() // 1000


def _now_seconds() -> nu.Nu:
    """Absolute epoch seconds at eval time."""
    return _nu_time.time()


def observe(name: str, value: float | nu.Nu, *, ts: float | None = None) -> nu.Nu:
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
    seq = next(_call_counter)
    key = nu.IntAttrRef(f"_nl_metric_key_{seq}")
    pt = Metrics.series[name].points[key]

    if ts is None:
        key_query: nu.Nu = _now_us()
        ts_query: nu.Nu = _now_seconds()
    else:
        key_query = nu.Literal(int(ts * 1_000_000))
        ts_query = nu.Float(float(ts))

    value_expr = nu.ToFloat(value) if isinstance(value, nu.Nu) else nu.Float(float(value))

    return (
        nu.SetCmd(key, key_query)
        >> pt.set(nu.Dict.of(
            ts=ts_query,
            value=value_expr,
        ))
    )
