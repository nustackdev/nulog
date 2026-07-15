"""Viewer smoke: shapes exist, build_ui returns a Nu tree, seed lands, filters work."""

from __future__ import annotations

import pytest


pytest.importorskip("nudle")

import nu

import nulog
from nulog.ui import (
    DEFAULT_LEVEL,
    DEFAULT_WINDOW,
    LEVEL_OPTIONS,
    SAMPLE_LIMIT,
    TABLE_COLUMNS,
    WINDOW_OPTIONS,
    MessagesBody,
    MetricsBody,
    MetricsViewState,
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


def test_messages_body_has_expected_refs():
    slots = MessagesBody._slots
    for name in ("stream", "level", "search", "table"):
        assert name in slots


def test_metrics_body_has_expected_refs():
    slots = MetricsBody._slots
    for name in ("series", "window", "chart"):
        assert name in slots


def test_viewer_tabs_covers_both_bodies():
    assert {t["id"] for t in ViewerTabs.tabs} == {"messages", "metrics"}


def test_index_registers_one_page():
    assert ViewerIndex.pages.routes["/"] is ViewerPage


def test_level_options_include_all_severities():
    assert set(LEVEL_OPTIONS) == {DEFAULT_LEVEL, "debug", "info", "warning", "error", "critical"}


def test_window_options_default_is_valid():
    assert DEFAULT_WINDOW in {opt["value"] for opt in WINDOW_OPTIONS}


def test_sample_limit_is_positive():
    assert SAMPLE_LIMIT > 0


def test_table_columns_shape():
    assert TABLE_COLUMNS == ("time", "level", "message", "fields")


def test_build_ui_returns_nu():
    tree = build_ui(("app", "scraper"), ("cpu_load", "http_latency_ms"))
    assert isinstance(tree, nu.Nu)


@pytest.mark.parametrize("level_filter", [DEFAULT_LEVEL, "error"])
def test_messages_repaint_reads_current_stream(ctx, level_filter):
    """After seeding ViewState, the messages repaint's payload reflects the store."""
    app = nulog.getLogger("app")
    nu.run(
        nu.v.Transaction(
            app.info("hi", extra={"n": 1})
            >> app.error("boom", extra={"code": 500}),
        ),
        ctx,
    )
    nu.run(
        ViewState.stream.store("app")
        >> ViewState.level.store(level_filter)
        >> ViewState.search.store(""),
        ctx,
    )
    payload = nu.run(nu.v.Snapshot(_table_payload()), ctx)[0]
    assert payload["columns"] == list(TABLE_COLUMNS)
    if level_filter == "error":
        assert len(payload["rows"]) == 1
        assert payload["rows"][0][1] == "error"
        assert payload["rows"][0][2] == "boom"
    else:
        assert len(payload["rows"]) == 2


def test_metrics_chart_points_are_ordered_xy_pairs(ctx):
    """Sampled points come back as ``[[ts_us, value], ...]`` sorted by ts."""
    nu.run(
        nu.v.Transaction(
            nulog.observe("cpu_load", 0.30)
            >> nulog.observe("cpu_load", 0.55)
            >> nulog.observe("cpu_load", 0.71),
        ),
        ctx,
    )
    nu.run(
        MetricsViewState.series.store("cpu_load")
        >> MetricsViewState.window.store(DEFAULT_WINDOW),
        ctx,
    )
    points = nu.run(nu.v.Snapshot(_chart_points()), ctx)[0]
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
