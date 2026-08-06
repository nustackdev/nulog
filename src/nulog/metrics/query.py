"""Metric reads -- three primitives: :func:`range`, :func:`sample`, :func:`point`.

Every read touches only the entries it returns; kh57's shifted-key
substrate makes ``range(begin, end)`` an indexed scan and ``sample(n)`` a
reservoir sample -- neither walks the full series.

Rows: ``{"ts_us": int, "ts": float, "value": float}``.
"""

from __future__ import annotations

import nu

from .shape import Metrics


__all__ = [
    "point",
    "range",
    "sample",
]


_PAIR = nu.AnyAttrRef("_nl_mpair")
_KEY = nu.GetItem(_PAIR, 0)
_VIEW = nu.GetItem(_PAIR, 1)


def _row() -> nu.Nu:
    """One ``{ts_us, ts, value}`` row from the current metric pair."""
    return nu.Dict.of(
        ts_us=_KEY,
        ts=nu.GetItem(_VIEW, "ts"),
        value=nu.GetItem(_VIEW, "value"),
    )


def _rows(pairs: nu.Nu) -> nu.Nu:
    """Turn a ``(key, view)`` pair stream into a ``list[dict]`` row list."""
    return nu.Collect(nu.Map(nu.Iter(pairs), _row(), key="_nl_mpair"))


def range(
    name: str,
    begin: int | nu.Nu,
    end: int | nu.Nu,
) -> nu.Nu:
    """Every point in ``name`` with kh57 key in ``[begin, end)``, key-ordered.

    Keys are microsecond epochs, so ``begin`` / ``end`` are microsecond
    bounds. Indexed under the hood -- cost is O(number of points in the
    window), not O(series size).
    """
    return _rows(Metrics.series[name].points.range(begin, end))


def sample(
    name: str,
    n: int | nu.Nu,
    begin: int | nu.Nu | None = None,
    end: int | nu.Nu | None = None,
) -> nu.Nu:
    """Up to ``n`` kh57-sampled points from ``name`` in ``[begin, end)``.

    Kh57 range reservoir sampling: deterministic given the store's salt,
    stable under appends outside the queried range. Cost is ~``2n`` reads,
    not O(series size) -- this is what kh57 buys.
    """
    return _rows(Metrics.series[name].points.sample(n, begin, end))


def point(name: str, key: int | nu.Nu) -> nu.Nu:
    """One metric point in ``name`` at the exact microsecond ``key``."""
    pt = Metrics.series[name].points[key]
    return nu.Dict.of(
        ts_us=nu.Literal(key) if isinstance(key, int) else key,
        ts=pt.ts,
        value=pt.value,
    )
