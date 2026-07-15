"""Viewer state + display shapes -- what the browser sees.

Two tabs share one :class:`ViewerPage`:

- :class:`MessagesBody` -- a labeled filters row over the entries table.
  The filter set is: stream / mode (tail vs take) / count / level /
  in-window substring filter. Every read boils down to a bounded slice
  (``entries[len-count:len]`` for tail, ``entries[0:count]`` for take)
  then in-slice predicates, so no read walks the full stream.

- :class:`MetricsBody` -- series + window pickers over one kh57-sampled
  :class:`~nu.ui.LineChart`.

Server-side filter state lives in :mod:`nu.m` (dict-backed, process-local):

- :class:`ViewState` -- messages tab (stream / mode / count / level / filter).
- :class:`MetricsViewState` -- metrics tab (series / window).

Neither survives a restart. Log data itself sits under the enclosing
:mod:`nu.v` store bracket.
"""

from __future__ import annotations

from typing import ClassVar

import nu

from ..messages.shape import LEVELS


__all__ = [
    "DEFAULT_COUNT",
    "DEFAULT_LEVEL",
    "DEFAULT_MODE",
    "DEFAULT_WINDOW",
    "LEVEL_OPTIONS",
    "MAX_COUNT",
    "MIN_COUNT",
    "MODE_OPTIONS",
    "MODE_TAIL",
    "MODE_TAKE",
    "SAMPLE_LIMIT",
    "TABLE_COLUMNS",
    "TICK_SECONDS",
    "WINDOW_OPTIONS",
    "CountField",
    "FilterField",
    "FiltersRow",
    "LevelField",
    "MessagesBody",
    "MetricsBody",
    "MetricsViewState",
    "ModeField",
    "SeriesField",
    "StreamField",
    "ViewState",
    "ViewerIndex",
    "ViewerPage",
    "ViewerTabs",
    "WindowField",
]


# ---- messages tab constants ---------------------------------------------

TABLE_COLUMNS: tuple[str, ...] = ("time", "level", "message", "fields")
DEFAULT_LEVEL = "all"
LEVEL_OPTIONS: tuple[str, ...] = (DEFAULT_LEVEL, *LEVELS)

MODE_TAIL = "tail"
MODE_TAKE = "take"
MODE_OPTIONS: tuple[dict[str, str], ...] = (
    {"value": MODE_TAIL, "label": "tail (newest)"},
    {"value": MODE_TAKE, "label": "take (oldest)"},
)
DEFAULT_MODE = MODE_TAIL

# Hard bounds on the requested slice size. The min stops zero / negative
# reads; the max is a safety cap so a big number in the count field can't
# balloon a single repaint. Both are enforced browser-side by
# ``NumberInputRef`` and server-side by clamp expressions in the read.
MIN_COUNT = 1
MAX_COUNT = 10_000
DEFAULT_COUNT = 200


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
# Cap on the number of sampled points fed into a chart per repaint. Matches
# nudle's default ``LineChart.max_points`` and keeps the wire payload small
# at billion-entry scale (~2 * SAMPLE_LIMIT kh57 reads per repaint).
SAMPLE_LIMIT = 500


# ---- global tick pace ---------------------------------------------------

TICK_SECONDS = 1.0


# ---- viewer state (nu.m -- transient, not persisted) --------------------


class ViewState(nu.Shape):
    """Server-side mirror of the messages tab filter set."""

    stream: nu.m.StrRef
    mode: nu.m.StrRef        # "tail" | "take"
    count: nu.m.IntRef       # slice size for tail / take
    level: nu.m.StrRef       # "all" | "debug" | ... | "critical"
    filter: nu.m.StrRef      # in-window substring match (never a full scan)


class MetricsViewState(nu.Shape):
    """Server-side mirror of the metrics tab filter (series / window)."""

    series: nu.m.StrRef
    window: nu.m.StrRef      # seconds as string, matches WINDOW_OPTIONS values


# ---- labeled input wrappers --------------------------------------------
#
# One :class:`nu.ui.FieldRef` per control gives each input a visible
# ``label`` above it -- the whole point of this pass. Access the wrapped
# control via ``<Field>.control`` (e.g. ``StreamField.control.set(...)``).


class StreamField(nu.ui.FieldRef):
    """Stream picker."""

    label: ClassVar[str] = "stream"
    control = nu.ui.SelectRef.slot()


class ModeField(nu.ui.FieldRef):
    """Tail vs take switch (which end of the stream to read)."""

    label: ClassVar[str] = "mode"
    control = nu.ui.RadioGroupRef.slot()


class CountField(nu.ui.FieldRef):
    """How many entries the mode reads."""

    label: ClassVar[str] = "count"
    help: ClassVar[str] = f"{MIN_COUNT}..{MAX_COUNT} entries; slice cost is O(count)."
    control = nu.ui.NumberInputRef.slot()


class LevelField(nu.ui.FieldRef):
    """Level filter, applied inside the tail / take slice."""

    label: ClassVar[str] = "level"
    control = nu.ui.SelectRef.slot()


class FilterField(nu.ui.FieldRef):
    """Substring match against ``msg``. In-window only -- never a full scan."""

    label: ClassVar[str] = "filter"
    help: ClassVar[str] = "substring in message; applied within the current slice."
    control = nu.ui.InputRef.slot()


class SeriesField(nu.ui.FieldRef):
    """Metric series picker."""

    label: ClassVar[str] = "series"
    control = nu.ui.SelectRef.slot()


class WindowField(nu.ui.FieldRef):
    """Time-window picker for the metrics chart."""

    label: ClassVar[str] = "window"
    control = nu.ui.SelectRef.slot()


# ---- tab bodies + tabs ref ---------------------------------------------


class FiltersRow(nu.ui.Row):
    """Horizontal strip of labeled fields above the entries table."""

    gap: ClassVar[str] = "md"

    stream = StreamField.slot()
    mode = ModeField.slot()
    count = CountField.slot()
    level = LevelField.slot()
    filter = FilterField.slot()


class MetricsPickers(nu.ui.Row):
    """Horizontal strip of labeled pickers above the chart."""

    gap: ClassVar[str] = "md"

    series = SeriesField.slot()
    window = WindowField.slot()


class MessagesBody(nu.ui.Column):
    """Messages tab: filters row + entries table."""

    filters = FiltersRow.slot()
    table = nu.ui.TableRef.slot()


class MetricsBody(nu.ui.Column):
    """Metrics tab: picker row + one sampled line chart."""

    pickers = MetricsPickers.slot()
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
