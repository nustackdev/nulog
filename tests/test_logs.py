"""Log writes + reads: level shortcuts, ordering, filters, ranges, search, counts."""

from __future__ import annotations

import nu

import nulog


def _write(ctx, cmd):
    """Run one write Command inside a Transaction on ``ctx``."""
    nu.run(nu.v.Transaction(cmd), ctx)


def _read(ctx, atom):
    """Run a read atom under a Snapshot on ``ctx``; return the yielded value."""
    return nu.run(nu.v.Snapshot(atom), ctx)[0]


# ---- write shape ----------------------------------------------------------


def test_write_returns_nu_without_executing(ctx):
    """Building an entry doesn't touch the store."""
    cmd = nulog.entry("app", "info", "deferred")
    assert isinstance(cmd, nu.Nu)
    assert _read(ctx, nulog.tail("app", 5)) == []


def test_append_and_tail(ctx):
    _write(ctx, nulog.info("app", "started", port=8080, host="localhost"))
    rows = _read(ctx, nulog.tail("app", 10))
    assert len(rows) == 1
    r = rows[0]
    assert r["level"] == "info"
    assert r["msg"] == "started"
    assert r["fields"] == {"port": 8080, "host": "localhost"}
    assert isinstance(r["ts_us"], int) and r["ts_us"] > 0
    assert isinstance(r["key"], int) and r["key"] > 0


def test_no_fields_decodes_to_empty_dict(ctx):
    _write(ctx, nulog.info("app", "bare"))
    assert _read(ctx, nulog.tail("app", 1))[0]["fields"] == {}


def test_level_shortcuts(ctx):
    _write(ctx, nulog.debug("app", "d"))
    _write(ctx, nulog.info("app", "i"))
    _write(ctx, nulog.warn("app", "w"))
    _write(ctx, nulog.error("app", "e"))
    rows = _read(ctx, nulog.tail("app", 10))
    assert [r["level"] for r in rows] == ["error", "warn", "info", "debug"]


def test_generic_log_function(ctx):
    _write(ctx, nulog.log("app", "warn", "via log", k=1))
    r = _read(ctx, nulog.tail("app", 1))[0]
    assert r["level"] == "warn"
    assert r["fields"] == {"k": 1}


def test_compose_log_with_other_writes_is_atomic(ctx):
    """A log Command composes with any other Command inside one Transaction."""
    class Account(nu.Shape):
        balance = nu.v.IntRef.slot()

    nu.run(
        nu.v.Transaction(
            Account.balance.store(100),
            nulog.info("app", "debit", amount=5),
        ),
        ctx,
    )
    bal = nu.run(nu.v.Snapshot(nu.IntForm(Account.balance)), ctx)[0]
    assert bal == 100
    r = _read(ctx, nulog.tail("app", 1))[0]
    assert r["msg"] == "debit"
    assert r["fields"] == {"amount": 5}


def test_loop_mints_fresh_key_each_iteration(ctx):
    """A write inside a loop mints a fresh kh57 key per eval (not per build)."""
    nu.run(
        nu.ForEachDo(
            nu.IterQuery(nu.LiteralQuery([1, 2, 3, 4, 5])),
            nu.v.Transaction(nulog.info("app", "tick")),
            item="_nl_i",
        ),
        ctx,
    )
    rows = _read(ctx, nulog.tail("app", 10))
    assert len(rows) == 5
    assert len({r["key"] for r in rows}) == 5


# ---- streams -------------------------------------------------------------


def test_streams_are_isolated(ctx):
    _write(ctx, nulog.info("app", "app line"))
    _write(ctx, nulog.info("scraper", "scraper line"))
    assert [r["msg"] for r in _read(ctx, nulog.tail("app", 10))] == ["app line"]
    assert [r["msg"] for r in _read(ctx, nulog.tail("scraper", 10))] == ["scraper line"]


def test_unwritten_stream_is_clean(ctx):
    _write(ctx, nulog.info("app", "x"))
    assert _read(ctx, nulog.tail("ghost", 5)) == []
    assert _read(ctx, nulog.count_by_level("ghost")) == {
        "debug": 0, "info": 0, "warn": 0, "error": 0,
    }


# ---- order ---------------------------------------------------------------


def test_tail_is_newest_first(ctx):
    for msg in ("first", "second", "third"):
        _write(ctx, nulog.info("app", msg))
    assert [r["msg"] for r in _read(ctx, nulog.tail("app", 10))] == ["third", "second", "first"]


def test_tail_limits_to_n(ctx):
    for i in range(5):
        _write(ctx, nulog.info("app", f"m{i}"))
    rows = _read(ctx, nulog.tail("app", 2))
    assert [r["msg"] for r in rows] == ["m4", "m3"]


def test_head_is_oldest_first(ctx):
    for msg in ("first", "second", "third"):
        _write(ctx, nulog.info("app", msg))
    assert [r["msg"] for r in _read(ctx, nulog.head("app", 10))] == ["first", "second", "third"]


# ---- filters -------------------------------------------------------------


def test_by_level_keeps_only_that_level(ctx):
    _write(ctx, nulog.info("app", "i1"))
    _write(ctx, nulog.error("app", "e1"))
    _write(ctx, nulog.warn("app", "w1"))
    _write(ctx, nulog.error("app", "e2"))
    errs = {r["msg"] for r in _read(ctx, nulog.by_level("app", "error"))}
    assert errs == {"e1", "e2"}
    assert [r["msg"] for r in _read(ctx, nulog.by_level("app", "info"))] == ["i1"]


def test_errors_shortcut(ctx):
    _write(ctx, nulog.info("app", "ok"))
    _write(ctx, nulog.error("app", "bad"))
    assert [r["msg"] for r in _read(ctx, nulog.errors("app"))] == ["bad"]


def test_search_substring(ctx):
    _write(ctx, nulog.info("app", "connection opened"))
    _write(ctx, nulog.info("app", "connection closed"))
    _write(ctx, nulog.info("app", "unrelated"))
    hits = {r["msg"] for r in _read(ctx, nulog.search("app", "connection"))}
    assert hits == {"connection opened", "connection closed"}
    assert [r["msg"] for r in _read(ctx, nulog.search("app", "closed"))] == ["connection closed"]


def test_search_no_match_is_empty(ctx):
    _write(ctx, nulog.info("app", "hello"))
    assert _read(ctx, nulog.search("app", "zzz")) == []


# ---- time windows --------------------------------------------------------


def test_since_filters_by_ts(ctx):
    _write(ctx, nulog.info("app", "old"))
    old_us = _read(ctx, nulog.tail("app", 1))[0]["ts_us"]
    _write(ctx, nulog.info("app", "new"))
    new_rows = _read(ctx, nulog.since("app", old_us + 1))
    assert "new" in {r["msg"] for r in new_rows}
    assert "old" not in {r["msg"] for r in new_rows}


def test_between_is_half_open(ctx):
    _write(ctx, nulog.info("app", "a"))
    a_us = _read(ctx, nulog.tail("app", 1))[0]["ts_us"]
    _write(ctx, nulog.info("app", "b"))
    b_us = _read(ctx, nulog.tail("app", 1))[0]["ts_us"]
    got = {r["msg"] for r in _read(ctx, nulog.between("app", a_us, b_us + 1))}
    assert got == {"a", "b"}
    below = _read(ctx, nulog.between("app", 0, a_us))
    assert below == [] or all(r["ts_us"] < a_us for r in below)


# ---- tally ---------------------------------------------------------------


def test_count_by_level(ctx):
    _write(ctx, nulog.info("app", "i"))
    _write(ctx, nulog.info("app", "i2"))
    _write(ctx, nulog.warn("app", "w"))
    _write(ctx, nulog.error("app", "e"))
    assert _read(ctx, nulog.count_by_level("app")) == {
        "debug": 0, "info": 2, "warn": 1, "error": 1,
    }


def test_empty_stream_all_reads_are_clean(ctx):
    assert _read(ctx, nulog.tail("app", 10)) == []
    assert _read(ctx, nulog.head("app", 10)) == []
    assert _read(ctx, nulog.errors("app")) == []
    assert _read(ctx, nulog.by_level("app", "info")) == []
    assert _read(ctx, nulog.since("app", 0)) == []
    assert _read(ctx, nulog.between("app", 0, 10**15)) == []
    assert _read(ctx, nulog.search("app", "anything")) == []
    assert _read(ctx, nulog.count_by_level("app")) == {
        "debug": 0, "info": 0, "warn": 0, "error": 0,
    }


# ---- one-tree end-to-end -------------------------------------------------


def test_bracket_form_all_in_one_tree():
    """Full Nu-app shape: bracket + writes + reads composed under one nu.With."""
    tree = nu.With(
        nulog.store(),
        body=nu.v.Transaction(
            nulog.info("app", "bracketed", n=1) >> nulog.error("app", "boom"),
        )
        >> nu.v.Snapshot(nu.print(nulog.tail("app", 10))),
    )
    nu.run(tree)
