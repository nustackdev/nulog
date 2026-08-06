"""Metric writes + reads: observe, range, sample, point."""

from __future__ import annotations

import nu

import nulog


def _write(ctx, cmd):
    nu.run(nu.v.Transaction(cmd), ctx)


def _read(ctx, atom):
    return nu.run(nu.v.Snapshot(atom), ctx)[0]


def test_observe_returns_nu_without_executing(ctx):
    cmd = nulog.observe("cpu", 0.42)
    assert isinstance(cmd, nu.Nu)
    assert _read(ctx, nulog.metrics.range("cpu", 0, 10**17)) == []


def test_observe_with_explicit_ts_and_range(ctx):
    _write(ctx, nulog.observe("cpu", 0.1, ts=1000.0))
    _write(ctx, nulog.observe("cpu", 0.2, ts=1001.0))
    _write(ctx, nulog.observe("cpu", 0.3, ts=1002.0))
    begin = int(999.0 * 1_000_000)
    end = int(1003.0 * 1_000_000)
    rows = _read(ctx, nulog.metrics.range("cpu", begin, end))
    assert [r["value"] for r in rows] == [0.1, 0.2, 0.3]
    assert rows[0]["ts"] == 1000.0


def test_observe_defaults_to_eval_time(ctx):
    _write(ctx, nulog.observe("gauge", 42.0))
    rows = _read(ctx, nulog.metrics.range("gauge", 0, 10**17))
    assert len(rows) == 1
    assert rows[0]["value"] == 42.0
    assert rows[0]["ts"] > 0
    assert isinstance(rows[0]["ts_us"], int) and rows[0]["ts_us"] > 0


def test_series_are_isolated(ctx):
    _write(ctx, nulog.observe("a", 1.0, ts=1.0))
    _write(ctx, nulog.observe("b", 2.0, ts=1.0))
    a_rows = _read(ctx, nulog.metrics.range("a", 0, 10**12))
    b_rows = _read(ctx, nulog.metrics.range("b", 0, 10**12))
    assert [r["value"] for r in a_rows] == [1.0]
    assert [r["value"] for r in b_rows] == [2.0]


def test_sample_returns_at_most_n(ctx):
    for i in range(20):
        _write(ctx, nulog.observe("burst", float(i), ts=1000.0 + i * 0.01))
    begin = int(1000.0 * 1_000_000)
    end = int(1001.0 * 1_000_000)
    rows = _read(ctx, nulog.metrics.sample("burst", 5, begin, end))
    assert len(rows) <= 5
    assert {r["value"] for r in rows}.issubset({float(i) for i in range(20)})


def test_range_out_of_bounds_is_empty(ctx):
    _write(ctx, nulog.observe("m", 1.0, ts=5000.0))
    assert _read(ctx, nulog.metrics.range("m", 0, 1000)) == []
    assert _read(ctx, nulog.metrics.sample("m", 3, 0, 1000)) == []


def test_point_exact_key(ctx):
    """`point(name, us)` reads one metric point at the exact microsecond key."""
    ts = 1234.567
    us = int(ts * 1_000_000)
    _write(ctx, nulog.observe("m", 9.5, ts=ts))
    r = _read(ctx, nulog.metrics.point("m", us))
    assert r["value"] == 9.5
    assert r["ts"] == ts
    assert r["ts_us"] == us


def test_compose_metric_and_log_is_atomic(ctx):
    """A metric and a log write ride the same Transaction."""
    nu.run(
        nu.v.Transaction(
            nulog.getLogger("app").info("sample recorded", extra={"n": 1}),
            nulog.observe("throughput", 100.0, ts=1000.0),
        ),
        ctx,
    )
    r = _read(ctx, nulog.messages.tail("app", 1))[0]
    m = _read(ctx, nulog.metrics.range("throughput", 0, 10**17))
    assert r["msg"] == "sample recorded"
    assert m[0]["value"] == 100.0


def test_loop_mints_fresh_metric_key(ctx):
    """A metric write inside a loop mints a fresh kh57 key per iteration."""
    nu.run(
        nu.ForEachDo(
            nu.Iter(nu.Literal([1, 2, 3, 4])),
            nu.v.Transaction(nulog.observe("hb", 1.0)),
            item="_nl_i",
        ),
        ctx,
    )
    rows = _read(ctx, nulog.metrics.range("hb", 0, 10**17))
    assert len(rows) == 4
    assert len({r["ts_us"] for r in rows}) == 4
