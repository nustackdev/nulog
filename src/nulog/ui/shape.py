"""Viewer state + display shapes -- what the browser sees.

Two pages sit behind the sidebar:

- :class:`MessagesPage` -- labeled filters row over the entries table.
  The filter set is: stream / mode (tail vs take) / count / level /
  in-window substring filter. Every read boils down to a bounded slice
  (``entries[len-count:len]`` for tail, ``entries[0:count]`` for take)
  then in-slice predicates, so no read walks the full stream.

- :class:`MetricsPage` -- series + window pickers over one kh57-sampled
  :class:`~nu.ui.LineChart`.

Server-side filter state lives in :mod:`nu.mem` (dict-backed, process-local):

- :class:`ViewState` -- messages page (stream / mode / count / level / filter).
- :class:`MetricsViewState` -- metrics page (series / window).

Neither survives a restart. Log data itself sits under the enclosing
:mod:`nu.kv` store bracket. Tuning knobs (defaults, option sets, bounds,
tick pace) live in :mod:`.consts`.
"""

from __future__ import annotations

import nu

from . import consts


__all__ = [
    "CountField",
    "FilterField",
    "FiltersRow",
    "LevelField",
    "MessagesPage",
    "MetricsPage",
    "MetricsPickers",
    "MetricsViewState",
    "ModeField",
    "SeriesField",
    "StreamField",
    "ViewState",
    "ViewerIndex",
    "WindowField",
]


# ---- viewer state (nu.mem -- transient, not persisted) --------------------


class ViewState(nu.Shape):
    """Server-side mirror of the messages page filter set."""

    stream: nu.mem.StrRef
    mode: nu.mem.StrRef  # "tail" | "take"
    count: nu.mem.IntRef  # slice size for tail / take
    level: nu.mem.StrRef  # "all" | "debug" | ... | "critical"
    filter: nu.mem.StrRef  # in-window substring match (never a full scan)


class MetricsViewState(nu.Shape):
    """Server-side mirror of the metrics page filter (series / window)."""

    series: nu.mem.StrRef
    window: nu.mem.StrRef  # seconds as string, matches WINDOW_OPTIONS values


# ---- labeled input wrappers --------------------------------------------


class StreamField(nu.ui.Field):
    """Stream picker. Options hydrate every tick from ``Messages.streams.keys()``."""

    control = nu.ui.SelectRef.slot()


class ModeField(nu.ui.Field):
    """Tail vs take switch (which end of the stream to read)."""

    control = nu.ui.RadioGroupRef.slot(
        options=list(consts.MODE_OPTIONS),
        selected=consts.DEFAULT_MODE,
    )


class CountField(nu.ui.Field):
    """How many entries the mode reads."""

    control = nu.ui.NumberInputRef.slot(
        min=float(consts.MIN_COUNT),
        max=float(consts.MAX_COUNT),
        step=10.0,
        default=float(consts.DEFAULT_COUNT),
    )


class LevelField(nu.ui.Field):
    """Level filter, applied inside the tail / take slice."""

    control = nu.ui.SelectRef.slot(
        options=list(consts.LEVEL_OPTIONS),
        selected=consts.DEFAULT_LEVEL,
    )


class FilterField(nu.ui.Field):
    """Substring match against ``msg``. In-window only -- never a full scan."""

    control = nu.ui.InputRef.slot()


class SeriesField(nu.ui.Field):
    """Metric series picker. Options hydrate every tick from ``Metrics.series.keys()``."""

    control = nu.ui.SelectRef.slot()


class WindowField(nu.ui.Field):
    """Time-window picker for the metrics chart."""

    control = nu.ui.SelectRef.slot(
        options=list(consts.WINDOW_OPTIONS),
        selected=consts.DEFAULT_WINDOW,
    )


# ---- picker rows -------------------------------------------------------


class FiltersRow(nu.ui.Row):
    """Horizontal strip of labeled fields above the entries table."""

    stream = StreamField.slot(label="stream")
    mode = ModeField.slot(label="mode")
    count = CountField.slot(
        label="count",
        help=f"{consts.MIN_COUNT}..{consts.MAX_COUNT} entries; slice cost is O(count).",
    )
    level = LevelField.slot(label="level")
    filter = FilterField.slot(
        label="filter",
        help="substring in message; applied within the current slice.",
    )


class MetricsPickers(nu.ui.Row):
    """Horizontal strip of labeled pickers above the chart."""

    series = SeriesField.slot(label="series")
    window = WindowField.slot(label="window")


# ---- pages + index -----------------------------------------------------


class MessagesPage(nu.ui.Page):
    """Messages page: filters row + entries table."""

    nav_label = "messages"

    filters = FiltersRow.slot()
    table = nu.ui.TableRef.slot()


class MetricsPage(nu.ui.Page):
    """Metrics page: picker row + one sampled line chart."""

    nav_label = "metrics"

    pickers = MetricsPickers.slot()
    chart = nu.ui.LineChart.slot(x_format="datetime_us")


class ViewerIndex(nu.ui.Index):
    """Browser entrypoint: title, nav, and the two pages."""

    title = nu.ui.TitleRef.slot()
    nav = nu.ui.NavRef.slot()
    pages = nu.ui.Pages({"/": MessagesPage, "/metrics": MetricsPage})
