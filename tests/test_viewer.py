"""Viewer smoke: shapes exist, build_ui returns a Nu tree, seed lands, filters work."""

from __future__ import annotations

import pytest


pytest.importorskip("nudle")

import nu

import nulog
from nulog.viewer import (
    DEFAULT_LEVEL,
    LEVEL_OPTIONS,
    TABLE_COLUMNS,
    ViewerIndex,
    ViewerPage,
    _repaint,
    _table_payload,
    build_ui,
)


def test_page_has_all_viewer_refs():
    slots = ViewerPage._slots
    for name in ("heading", "table", "stream", "level", "search"):
        assert name in slots
    for name in ("debug_stat", "info_stat", "warn_stat", "error_stat"):
        assert name in slots


def test_index_registers_one_page():
    assert ViewerIndex.pages.routes["/"] is ViewerPage


def test_level_options_include_all_severities():
    assert set(LEVEL_OPTIONS) == {DEFAULT_LEVEL, "debug", "info", "warn", "error"}


def test_table_columns_shape():
    assert TABLE_COLUMNS == ("time", "level", "message", "fields")


def test_build_ui_returns_nu():
    tree = build_ui(("app", "scraper"))
    assert isinstance(tree, nu.Nu)


@pytest.mark.parametrize("level_filter", [DEFAULT_LEVEL, "error"])
def test_repaint_reads_current_stream(ctx, level_filter):
    """After seeding ViewState, the repaint's table payload reflects the store."""
    nu.run(
        nu.v.Transaction(
            nulog.info("app", "hi", n=1)
            >> nulog.error("app", "boom", code=500),
        ),
        ctx,
    )
    from nulog.shapes import ViewState

    nu.run(
        nu.v.Transaction(
            ViewState.stream.store("app")
            >> ViewState.level.store(level_filter)
            >> ViewState.search.store(""),
        ),
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


def test_repaint_composes_as_nu(ctx):
    """`_repaint()` returns a Nu tree of table + four stat stores composed with `|`."""
    tree = _repaint()
    assert isinstance(tree, nu.Nu)
