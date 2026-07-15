"""Viewer state + display shapes -- what the browser sees.

Two tabs share one :class:`ViewerPage`: :class:`MessagesBody` (stream +
level + search picker over a table of log entries) and
:class:`MetricsBody` (series + window picker over one line chart).

Server-side filter state lives in :mod:`nu.m` (dict-backed, process-local):

- :class:`ViewState` -- messages tab filters (stream / level / search).
- :class:`MetricsViewState` -- metrics tab filters (series / window).

Neither survives a restart. Log data itself is under the enclosing
:mod:`nu.v` store bracket.
"""

from __future__ import annotations

from typing import ClassVar

import nu

from ..messages.shape import LEVELS


__all__ = [
    "DEFAULT_LEVEL",
    "DEFAULT_WINDOW",
    "LEVEL_OPTIONS",
    "SAMPLE_LIMIT",
    "TABLE_COLUMNS",
    "TAIL_LIMIT",
    "TICK_SECONDS",
    "WINDOW_OPTIONS",
    "MessagesBody",
    "MetricsBody",
    "MetricsViewState",
    "ViewState",
    "ViewerIndex",
    "ViewerPage",
    "ViewerTabs",
]


# ---- messages tab constants ---------------------------------------------

TABLE_COLUMNS: tuple[str, ...] = ("time", "level", "message", "fields")
DEFAULT_LEVEL = "all"
LEVEL_OPTIONS: tuple[str, ...] = (DEFAULT_LEVEL, *LEVELS)
TAIL_LIMIT = 200


# ---- metrics tab constants ----------------------------------------------

# Values are seconds-as-strings so ``SelectRef`` (which speaks strings)
# can round-trip them; labels are the human form.
WINDOW_OPTIONS: tuple[dict[str, str], ...] = (
    {"value": "60", "label": "1m"},
    {"value": "300", "label": "5m"},
    {"value": "900", "label": "15m"},
    {"value": "3600", "label": "1h"},
)
DEFAULT_WINDOW = "300"
# Cap on the number of sampled points fed into a chart per repaint. Chosen
# to match nudle's default ``LineChart.max_points`` and to keep the wire
# payload small at billion-entry scale (2 * SAMPLE_LIMIT kh57 reads).
SAMPLE_LIMIT = 500


# ---- global tick pace ---------------------------------------------------

TICK_SECONDS = 1.0


# ---- viewer state (nu.m -- transient, not persisted) --------------------


class ViewState(nu.Shape):
    """Server-side mirror of the messages tab filter (stream / level / search)."""

    stream: nu.m.StrRef
    level: nu.m.StrRef       # "all" | "debug" | "info" | "warning" | "error" | "critical"
    search: nu.m.StrRef


class MetricsViewState(nu.Shape):
    """Server-side mirror of the metrics tab filter (series / window)."""

    series: nu.m.StrRef
    window: nu.m.StrRef      # seconds as string, matches WINDOW_OPTIONS values


# ---- tab bodies + tabs ref ---------------------------------------------


class MessagesBody(nu.ui.Column):
    """Messages tab: filters row (stream + level + search) above the entries table."""

    stream = nu.ui.SelectRef.slot()
    level = nu.ui.SelectRef.slot()
    search = nu.ui.InputRef.slot()
    table = nu.ui.TableRef.slot()


class MetricsBody(nu.ui.Column):
    """Metrics tab: series + window pickers above one sampled line chart."""

    series = nu.ui.SelectRef.slot()
    window = nu.ui.SelectRef.slot()
    chart = nu.ui.LineChart.slot()


class ViewerTabs(nu.ui.TabsRef):
    """Two-tab strip; body slot per tab id."""

    tabs: ClassVar[list[dict[str, str]]] = [
        {"id": "messages", "label": "messages"},
        {"id": "metrics", "label": "metrics"},
    ]
    active: ClassVar[str] = "messages"

    messages = MessagesBody.slot()
    metrics = MetricsBody.slot()


# ---- page + index -------------------------------------------------------


class ViewerPage(nu.ui.Page):
    """The viewer page: heading, then the two-tab strip."""

    heading = nu.ui.HeadingRef.slot()
    tabs = ViewerTabs.slot()


class ViewerIndex(nu.ui.Index):
    """Browser entrypoint: title, nav, the one page."""

    title = nu.ui.TitleRef.slot()
    nav = nu.ui.NavRef.slot()
    pages = nu.ui.Pages({"/": ViewerPage})
