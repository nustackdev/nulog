"""Log + metric reads as pure Nu Query trees.

Every function here returns a Nu ``Query`` that yields a ``list[dict]`` (rows)
or a ``dict`` (tally). Drop it into a tree, wrap the outer body in
``nu.v.Snapshot(...)`` so the whole read runs in one consistent generation,
and evaluate. No custom :class:`nu.ScalarQuery` subclass anywhere -- the reads
are compositions of ``IterQuery`` / ``FilterQuery`` / ``MapQuery`` /
``CollectQuery`` / ``ReversedQuery`` / ``CountQuery`` / ``GetItemQuery`` /
``SliceQuery`` / ``DictForm.of`` over the kh57 shape maps.

Log rows: ``{"key": int, "ts_us": int, "level": str, "msg": str, "fields": dict}``.
Metric rows: ``{"ts_us": int, "ts": float, "value": float}``.

The one ``@nu.host`` seam is :data:`FieldsFromJson` -- the JSON decode of the
opaque ``fields`` string on read. Everything else is Nu-composed.

Range windows (``since`` / ``between``) map straight to
``entries.range(begin_key, end_key)`` on shifted keys -- cheap indexed scans
over the kh57 substrate.
"""

from __future__ import annotations

import json

import nu

from .shapes import LEVELS, Logs, Metrics
from .writes import _EPOCH_US  # kh57 log-key epoch offset (2020)


__all__ = [
    "FieldsFromJson",
    "between",
    "by_level",
    "count_by_level",
    "errors",
    "head",
    "range_metric",
    "sample_metric",
    "search",
    "since",
    "tail",
]


# ---- key bounds for log range windows -------------------------------------


_KH57_MAX = (1 << 57) - 1  # widest legal kh57 key


def _log_key_lo(ts_us: int) -> int:
    """Lower kh57 log key bound for a ts_us cutoff (inclusive)."""
    return max(0, ts_us - _EPOCH_US) << 8


def _log_key_hi(ts_us: int) -> int:
    """Upper kh57 log key bound for a ts_us cutoff (exclusive).

    The +1 lifts us past every counter LSB inside the same microsecond so
    ``between(a_us, b_us)`` includes every write that happened at exactly
    ``b_us - 1`` (any counter slot).
    """
    return max(0, ts_us - _EPOCH_US + 1) << 8


# ---- @nu.host: the one Python seam on the read side ----------------------


@nu.host
def FieldsFromJson(raw: str) -> dict:  # noqa: N802 -- atom class name is CamelCase
    """Decode the opaque ``fields`` JSON string back to a dict (empty on bad/None)."""
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return obj if isinstance(obj, dict) else {}


# ---- shared item-binding helpers -----------------------------------------
#
# `FilterQuery` / `MapQuery` bind each `(key, view)` pair to a loop-var slot.
# The scalar helpers below project the pair (key/view) so predicates and row
# builders read as `_level` / `_msg` / `_ts_us` regardless of the wrapping.


_ITEM = nu.AnyAttrRef("_nl_item")
_KEY = nu.GetItemQuery(_ITEM, 0)
_VIEW = nu.GetItemQuery(_ITEM, 1)
_TS_US = nu.GetItemQuery(_VIEW, "ts_us")
_LEVEL = nu.GetItemQuery(_VIEW, "level")
_MSG = nu.GetItemQuery(_VIEW, "msg")
_FIELDS_STR = nu.GetItemQuery(_VIEW, "fields")


def _stream_ref(stream: str | nu.Nu) -> nu.Nu:
    """The kh57 entries map for ``stream`` (``stream`` may be a Nu ref)."""
    return Logs.streams[stream].entries


def _pairs(stream: str | nu.Nu, *, begin: int | nu.Nu = 0, end: int | nu.Nu = _KH57_MAX) -> nu.Nu:
    """Ordered ``(key, view)`` pair stream for ``stream`` in ``[begin, end)``.

    ``entries.range(...)`` yields a scalar list of pairs; ``IterQuery`` opens
    it into a stream the lens Queries (Map, Filter, Collect, Count) consume.
    """
    return nu.IterQuery(_stream_ref(stream).range(begin, end))


def _row_from_item() -> nu.Nu:
    """One decoded row dict from the current ``(key, view)`` pair bound at ``_nl_item``."""
    return nu.DictForm.of(
        key=_KEY,
        ts_us=_TS_US,
        level=_LEVEL,
        msg=_MSG,
        fields=FieldsFromJson(_FIELDS_STR),
    )


def _rows_of(pairs: nu.Nu) -> nu.Nu:
    """Turn a `(key, view)` pair stream into a `list[dict]` row list."""
    return nu.CollectQuery(nu.MapQuery(pairs, _row_from_item(), key="_nl_item"))


def _filter_pairs(pairs: nu.Nu, predicate: nu.Nu) -> nu.Nu:
    """Keep pairs where the given ``predicate`` (over ``_nl_item``) holds."""
    return nu.FilterQuery(pairs, predicate, key="_nl_item")


# ---- log reads -----------------------------------------------------------


def head(stream: str | nu.Nu, n: int = 20) -> nu.Nu:
    """The oldest ``n`` entries of ``stream``, chronological order."""
    ordered = nu.CollectQuery(_pairs(stream))
    take = nu.IterQuery(nu.GetItemQuery(ordered, nu.SliceQuery(0, n, 1)))
    return _rows_of(take)


def tail(stream: str | nu.Nu, n: int = 20) -> nu.Nu:
    """The newest ``n`` entries of ``stream``, newest-first."""
    reversed_pairs = nu.CollectQuery(nu.ReversedQuery(_pairs(stream)))
    take = nu.IterQuery(nu.GetItemQuery(reversed_pairs, nu.SliceQuery(0, n, 1)))
    return _rows_of(take)


def by_level(stream: str | nu.Nu, level: str | nu.Nu) -> nu.Nu:
    """Every entry at ``level`` in ``stream``, newest-first."""
    kept = _filter_pairs(_pairs(stream), nu.EqQuery(_LEVEL, level))
    return _rows_of(nu.ReversedQuery(kept))


def errors(stream: str | nu.Nu) -> nu.Nu:
    """Every ``error`` entry in ``stream``, newest-first."""
    return by_level(stream, "error")


def since(stream: str | nu.Nu, ts_us: int | nu.Nu) -> nu.Nu:
    """Entries with ``ts_us >= ts_us`` in ``stream``, chronological.

    Concrete ``ts_us`` maps to a kh57 begin-key (cheap indexed scan); a Nu
    ``ts_us`` degrades to a stream-level ``GeQuery`` filter.
    """
    if isinstance(ts_us, int):
        return _rows_of(_pairs(stream, begin=_log_key_lo(ts_us)))
    kept = _filter_pairs(_pairs(stream), nu.GeQuery(_TS_US, ts_us))
    return _rows_of(kept)


def between(
    stream: str | nu.Nu,
    start_us: int | nu.Nu,
    end_us: int | nu.Nu,
) -> nu.Nu:
    """Entries with ``start_us <= ts_us < end_us`` in ``stream``, chronological."""
    if isinstance(start_us, int) and isinstance(end_us, int):
        return _rows_of(_pairs(stream, begin=_log_key_lo(start_us), end=_log_key_hi(end_us - 1)))
    kept = _filter_pairs(
        _pairs(stream),
        nu.AndQuery(nu.GeQuery(_TS_US, start_us), nu.LtQuery(_TS_US, end_us)),
    )
    return _rows_of(kept)


def search(stream: str | nu.Nu, text: str | nu.Nu) -> nu.Nu:
    """Entries whose ``msg`` contains ``text`` in ``stream``, newest-first."""
    kept = _filter_pairs(_pairs(stream), nu.ContainsQuery(_MSG, text))
    return _rows_of(nu.ReversedQuery(kept))


def count_by_level(stream: str | nu.Nu) -> nu.Nu:
    """A ``{level: count}`` tally over ``stream`` -- one Nu tree, four CountQuery walks.

    Each level is one ``CountQuery(FilterQuery(pairs, level == lvl))`` reading
    only the level slot off each entry; the tally shape is a ``DictForm.of``.
    """
    def _count(lvl: str) -> nu.Nu:
        return nu.CountQuery(
            _filter_pairs(_pairs(stream), nu.EqQuery(_LEVEL, lvl)),
        )

    return nu.DictForm.of(**{lvl: _count(lvl) for lvl in LEVELS})


# ---- metric reads --------------------------------------------------------


_MPAIR = nu.AnyAttrRef("_nl_mpair")
_MKEY = nu.GetItemQuery(_MPAIR, 0)
_MVIEW = nu.GetItemQuery(_MPAIR, 1)


def _metric_row() -> nu.Nu:
    """One `{ts_us, ts, value}` row from the current metric pair bound at ``_nl_mpair``."""
    return nu.DictForm.of(
        ts_us=_MKEY,
        ts=nu.GetItemQuery(_MVIEW, "ts"),
        value=nu.GetItemQuery(_MVIEW, "value"),
    )


def _metric_rows(pairs: nu.Nu) -> nu.Nu:
    """Turn a metric ``(key, view)`` pair stream into a `list[dict]` row list."""
    return nu.CollectQuery(nu.MapQuery(nu.IterQuery(pairs), _metric_row(), key="_nl_mpair"))


def range_metric(name: str, begin: int, end: int) -> nu.Nu:
    """Every point in ``name`` with kh57 key in ``[begin, end)``, key-ordered."""
    return _metric_rows(Metrics.series[name].points.range(begin, end))


def sample_metric(
    name: str,
    n: int,
    begin: int | None = None,
    end: int | None = None,
) -> nu.Nu:
    """Up to ``n`` kh57-sampled points from ``name`` in ``[begin, end)``.

    Kh57 range reservoir sampling: deterministic given the store's salt,
    stable under appends outside the queried range.
    """
    return _metric_rows(Metrics.series[name].points.sample(n, begin, end))
