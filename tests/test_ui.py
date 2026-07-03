"""UI smoke tests: the viewer shapes + app flow build (no live server)."""

import pytest


pytest.importorskip("nudle")

import nu

from nulog import open_logs
from nulog.ui import build_app, default_stream
from nulog.ui.app import _build_table, _read_view, _seed_view
from nulog.ui.pages import LEVEL_OPTIONS, TABLE_COLUMNS, LogIndex, LogViewer


def test_page_has_viewer_refs():
    slots = LogViewer._slots
    for name in ("heading", "table", "stream", "level", "search"):
        assert name in slots
    for name in ("debug_count", "info_count", "warn_count", "error_count"):
        assert name in slots
    # the index registers exactly the one viewer page at /
    assert LogIndex.pages.routes["/"] is LogViewer


def test_build_app_returns_nu():
    with open_logs() as logs:
        logs.stream("app").info("hi", x=1)
        app = build_app(logs, ["app", "scraper"])
        assert isinstance(app, nu.Nu)


def test_default_stream():
    assert default_stream(["scraper", "app"]) == "scraper"
    assert default_stream([]) == "app"


def test_repaint_reads_through_core_queries():
    # The table payload is shaped from the core query builders: tail by default,
    # by_level when a level is set, search when text is present.
    with open_logs() as logs:
        nu.run(_seed_view(["app"]), logs.ctx)
        app = logs.stream("app")
        app.info("connection opened", a=1)
        app.error("boom")

        payload = _build_table(logs)
        assert payload["columns"] == TABLE_COLUMNS
        # newest-first: the error landed last
        assert [r[2] for r in payload["rows"]] == ["boom", "connection opened"]
        # the fields cell renders structured kwargs compactly
        assert payload["rows"][1][3] == "a=1"


def test_view_state_seeded_defaults():
    with open_logs() as logs:
        nu.run(_seed_view(["scraper", "app"]), logs.ctx)
        stream, level, search = _read_view(logs)
        assert stream == "scraper"
        assert level == LEVEL_OPTIONS[0]  # "all"
        assert search == ""
