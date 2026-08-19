"""Browser log viewer -- one nudle Page with two tabs, one Nu tree.

Split across five files:

- :mod:`.consts` -- tuning knobs: defaults, option sets, bounds, tick pace.
- :mod:`.shape` -- view states (:class:`ViewState`, :class:`MetricsViewState`)
  and display shapes (labeled :class:`~nu.ui.Field` wrappers,
  :class:`FiltersRow` / :class:`MetricsPickers`, :class:`MessagesBody` /
  :class:`MetricsBody`, :class:`ViewerTabs`, :class:`ViewerPage`,
  :class:`ViewerIndex`).
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
from .consts import (
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
)
from .interactions import fmt_fields, fmt_ts
from .shape import (
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
    "build_ui",
    "fmt_fields",
    "fmt_ts",
    "messages",
    "metrics",
]
