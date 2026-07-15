"""Browser log viewer -- one nudle Page with two tabs, one Nu tree.

Split across four files:

- :mod:`.shape` -- view states (:class:`ViewState`, :class:`MetricsViewState`)
  and display shapes (labeled :class:`~nu.ui.FieldRef` wrappers,
  :class:`FiltersRow` / :class:`MetricsPickers`, :class:`MessagesBody` /
  :class:`MetricsBody`, :class:`ViewerTabs`, :class:`ViewerPage`,
  :class:`ViewerIndex`) + layout constants.
- :mod:`.messages` -- messages tab: bounded slice (tail / take) +
  in-window level / substring predicates + table payload, plus the
  value-only ``@nu.host`` formatters.
- :mod:`.metrics` -- metrics tab: kh57-sampled ``[ts_us, value]`` points
  for the line chart.
- :mod:`.app` -- :func:`build_ui`, the reactive composer that seeds
  state, hydrates chrome, and races the tick against filter reactives.
"""

from __future__ import annotations

from . import messages, metrics
from .app import build_ui
from .messages import FmtFields, FmtTs, RowAsList
from .shape import (
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
    TICK_SECONDS,
    WINDOW_OPTIONS,
    CountField,
    FilterField,
    FiltersRow,
    LevelField,
    MessagesBody,
    MetricsBody,
    MetricsViewState,
    ModeField,
    SeriesField,
    StreamField,
    ViewerIndex,
    ViewerPage,
    ViewerTabs,
    ViewState,
    WindowField,
)


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
    "FmtFields",
    "FmtTs",
    "LevelField",
    "MessagesBody",
    "MetricsBody",
    "MetricsViewState",
    "ModeField",
    "RowAsList",
    "SeriesField",
    "StreamField",
    "ViewState",
    "ViewerIndex",
    "ViewerPage",
    "ViewerTabs",
    "WindowField",
    "build_ui",
    "messages",
    "metrics",
]
