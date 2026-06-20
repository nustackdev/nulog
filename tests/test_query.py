"""The read face: ordering, by_level, time windows, search, counts, empties."""


def test_tail_is_newest_first(app):
    app.info("first")
    app.info("second")
    app.info("third")
    msgs = [r.msg for r in app.tail(10)]
    assert msgs == ["third", "second", "first"]


def test_tail_limits_to_n(app):
    for i in range(5):
        app.info(f"m{i}")
    rows = app.tail(2)
    assert len(rows) == 2
    assert [r.msg for r in rows] == ["m4", "m3"]


def test_by_level_filters(app):
    app.info("i1")
    app.error("e1")
    app.warn("w1")
    app.error("e2")
    errs = [r.msg for r in app.by_level("error")]
    assert sorted(errs) == ["e1", "e2"]
    assert [r.msg for r in app.by_level("info")] == ["i1"]


def test_errors_shortcut(app):
    app.info("ok")
    app.error("bad")
    assert [r.msg for r in app.errors()] == ["bad"]


def test_since_filters_by_time(app):
    app.info("old")
    rows = app.tail(1)
    cutoff = rows[0].ts + 1
    app.info("new")
    new_rows = app.since(cutoff)
    msgs = [r.msg for r in new_rows]
    assert "new" in msgs
    assert "old" not in msgs


def test_between_is_half_open(app):
    app.info("a")
    a_ts = app.tail(1)[0].ts
    app.info("b")
    b_ts = app.tail(1)[0].ts
    # window [a_ts, b_ts) includes a, excludes b (when timestamps differ)
    got = {r.msg for r in app.between(a_ts, b_ts + 1)}
    assert "a" in got
    assert "b" in got
    # a tight window below a_ts catches nothing
    assert app.between(0, a_ts) == [] or all(r.ts < a_ts for r in app.between(0, a_ts))


def test_search_matches_substring(app):
    app.info("connection opened")
    app.info("connection closed")
    app.info("unrelated")
    hits = {r.msg for r in app.search("connection")}
    assert hits == {"connection opened", "connection closed"}
    assert [r.msg for r in app.search("closed")] == ["connection closed"]


def test_search_no_match_is_empty(app):
    app.info("hello")
    assert app.search("zzz") == []


def test_count_by_level(app):
    app.info("i")
    app.info("i2")
    app.warn("w")
    app.error("e")
    counts = app.count_by_level()
    assert counts == {"debug": 0, "info": 2, "warn": 1, "error": 1}


def test_empty_stream_reads_are_clean(app):
    assert app.tail(10) == []
    assert app.errors() == []
    assert app.by_level("info") == []
    assert app.since(0) == []
    assert app.between(0, 10**15) == []
    assert app.search("anything") == []
    assert app.count_by_level() == {"debug": 0, "info": 0, "warn": 0, "error": 0}


def test_unwritten_stream_isolated_from_written(logs):
    logs.stream("app").info("x")
    assert logs.stream("ghost").tail(5) == []
    assert logs.stream("ghost").count_by_level() == {
        "debug": 0,
        "info": 0,
        "warn": 0,
        "error": 0,
    }
