"""Viewer smoke: shapes exist, build_ui returns a Nu tree, seed lands, filters work."""

from __future__ import annotations

import pytest


pytest.importorskip("nudle")

import nu

import nulog
from nulog.ui import (
    DEFAULT_COUNT,
    DEFAULT_LEVEL,
    DEFAULT_MODE,
    DEFAULT_WINDOW,
    LEVEL_OPTIONS,
    MAX_COUNT,
    MIN_COUNT,
    MODE_OPTIONS,
    MODE_TAIL,
    MODE_TAKE,
    SAMPLE_LIMIT,
    TABLE_COLUMNS,
    WINDOW_OPTIONS,
    CountField,
    FilterField,
    LevelField,
    MessagesBody,
    MetricsBody,
    MetricsViewState,
    ModeField,
    StreamField,
    ViewerIndex,
    ViewerPage,
    ViewerTabs,
    ViewState,
    build_ui,
)
from nulog.ui.messages import _repaint as _messages_repaint
from nulog.ui.messages import _table_payload
from nulog.ui.metrics import _chart_points
from nulog.ui.metrics import _repaint as _metrics_repaint


def test_page_declares_heading_and_tabs():
    slots = ViewerPage._slots
    for name in ("heading", "tabs"):
        assert name in slots


def test_messages_body_holds_filters_and_table():
    slots = MessagesBody._slots
    assert set(slots) == {"filters", "table"}


def test_metrics_body_holds_pickers_and_chart():
    slots = MetricsBody._slots
    assert set(slots) == {"pickers", "chart"}


def test_viewer_tabs_covers_both_bodies():
    assert {t["id"] for t in ViewerTabs.tabs} == {"messages", "metrics"}


def test_index_registers_one_page():
    assert ViewerIndex.pages.routes["/"] is ViewerPage


def test_labeled_fields_carry_labels():
    """Each :class:`nu.ui.Field` subclass sets a visible label."""
    assert StreamField.label == "stream"
    assert ModeField.label == "mode"
    assert CountField.label == "count"
    assert LevelField.label == "level"
    assert FilterField.label == "filter"


def test_level_options_include_all_severities():
    assert set(LEVEL_OPTIONS) == {DEFAULT_LEVEL, "debug", "info", "warning", "error", "critical"}


def test_mode_options_cover_tail_and_take():
    assert {opt["value"] for opt in MODE_OPTIONS} == {MODE_TAIL, MODE_TAKE}
    assert DEFAULT_MODE in {MODE_TAIL, MODE_TAKE}


def test_count_defaults_within_bounds():
    assert MIN_COUNT <= DEFAULT_COUNT <= MAX_COUNT


def test_window_options_default_is_valid():
    assert DEFAULT_WINDOW in {opt["value"] for opt in WINDOW_OPTIONS}


def test_sample_limit_is_positive():
    assert SAMPLE_LIMIT > 0


def test_table_columns_shape():
    assert TABLE_COLUMNS == ("time", "level", "message", "fields")


def test_build_ui_returns_nu():
    tree = build_ui(("app", "scraper"), ("cpu_load", "http_latency_ms"))
    assert isinstance(tree, nu.Nu)


def _seed_messages_state(
    ctx,
    *,
    stream: str = "app",
    mode: str = DEFAULT_MODE,
    count: int = DEFAULT_COUNT,
    level: str = DEFAULT_LEVEL,
    filter_: str = "",
) -> None:
    """Convenience: seed ViewState for a messages-tab read test."""
    nu.run(
        ViewState.stream.set(stream)
        >> ViewState.mode.set(mode)
        >> ViewState.count.set(count)
        >> ViewState.level.set(level)
        >> ViewState.filter.set(filter_),
        ctx,
    )


def _seed_stream_of_five(ctx) -> None:
    """Seed 5 messages into stream ``app``, distinguishable by their msg."""
    log = nulog.getLogger("app")
    nu.run(
        nu.kv.Transaction(
            log.info("one")
            >> log.info("two")
            >> log.info("three")
            >> log.info("four")
            >> log.info("five"),
        ),
        ctx,
    )


def test_messages_tail_returns_newest_first(ctx):
    """``tail`` mode reads ``entries[len-count:len]`` reversed."""
    _seed_stream_of_five(ctx)
    _seed_messages_state(ctx, mode=MODE_TAIL, count=3)
    payload = nu.run(nu.kv.Snapshot(_table_payload()), ctx)[0]
    msgs = [row[2] for row in payload["rows"]]
    assert msgs == ["five", "four", "three"]


def test_messages_take_returns_oldest_first(ctx):
    """``take`` mode reads ``entries[0:count]`` in order."""
    _seed_stream_of_five(ctx)
    _seed_messages_state(ctx, mode=MODE_TAKE, count=3)
    payload = nu.run(nu.kv.Snapshot(_table_payload()), ctx)[0]
    msgs = [row[2] for row in payload["rows"]]
    assert msgs == ["one", "two", "three"]


def test_messages_count_beyond_length_returns_all(ctx):
    """Count > len(stream) is clamped by the slice math to whatever exists."""
    _seed_stream_of_five(ctx)
    _seed_messages_state(ctx, mode=MODE_TAIL, count=100)
    payload = nu.run(nu.kv.Snapshot(_table_payload()), ctx)[0]
    assert len(payload["rows"]) == 5


def test_messages_count_zero_is_clamped_to_min(ctx):
    """``SafeCount`` bumps a zero (or negative) count to ``MIN_COUNT``."""
    _seed_stream_of_five(ctx)
    _seed_messages_state(ctx, mode=MODE_TAIL, count=0)
    payload = nu.run(nu.kv.Snapshot(_table_payload()), ctx)[0]
    assert len(payload["rows"]) == MIN_COUNT


def test_messages_filter_narrows_within_window(ctx):
    """The substring filter applies inside the current slice, not across the stream."""
    _seed_stream_of_five(ctx)
    _seed_messages_state(ctx, mode=MODE_TAIL, count=3, filter_="four")
    payload = nu.run(nu.kv.Snapshot(_table_payload()), ctx)[0]
    msgs = [row[2] for row in payload["rows"]]
    assert msgs == ["four"]


def test_messages_filter_outside_window_yields_nothing(ctx):
    """A match that lives outside the count window does not surface."""
    _seed_stream_of_five(ctx)
    # tail(2) window is ["five", "four"] -- "one" is out of scope.
    _seed_messages_state(ctx, mode=MODE_TAIL, count=2, filter_="one")
    payload = nu.run(nu.kv.Snapshot(_table_payload()), ctx)[0]
    assert payload["rows"] == []


@pytest.mark.parametrize("level_filter", [DEFAULT_LEVEL, "error"])
def test_messages_level_filter(ctx, level_filter):
    """Level filter reduces the window to matching entries; ``all`` passes through."""
    log = nulog.getLogger("app")
    nu.run(
        nu.kv.Transaction(
            log.info("hi", extra={"n": 1})
            >> log.error("boom", extra={"code": 500}),
        ),
        ctx,
    )
    _seed_messages_state(ctx, level=level_filter)
    payload = nu.run(nu.kv.Snapshot(_table_payload()), ctx)[0]
    assert payload["columns"] == list(TABLE_COLUMNS)
    if level_filter == "error":
        assert [row[1] for row in payload["rows"]] == ["error"]
    else:
        assert len(payload["rows"]) == 2


def test_metrics_chart_points_are_ordered_xy_pairs(ctx):
    """Sampled points come back as ``[[ts_us, value], ...]`` sorted by ts."""
    nu.run(
        nu.kv.Transaction(
            nulog.observe("cpu_load", 0.30)
            >> nulog.observe("cpu_load", 0.55)
            >> nulog.observe("cpu_load", 0.71),
        ),
        ctx,
    )
    nu.run(
        MetricsViewState.series.set("cpu_load")
        >> MetricsViewState.window.set(DEFAULT_WINDOW),
        ctx,
    )
    points = nu.run(nu.kv.Snapshot(_chart_points()), ctx)[0]
    assert points  # not empty
    for pair in points:
        assert len(pair) == 2
        assert isinstance(pair[0], int)      # ts_us
        assert isinstance(pair[1], float)    # value
    ts = [p[0] for p in points]
    assert ts == sorted(ts)


def test_repaints_compose_as_nu():
    """Both repaints return Nu trees."""
    assert isinstance(_messages_repaint(), nu.Nu)
    assert isinstance(_metrics_repaint(), nu.Nu)
