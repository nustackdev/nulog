"""Browser log viewer -- one nudle Page with two tabs, one Nu tree.

Split across four files:

- :mod:`.shape` -- view states (:class:`ViewState`, :class:`MetricsViewState`)
  and display shapes (:class:`ViewerPage`, :class:`ViewerTabs`,
  :class:`MessagesBody`, :class:`MetricsBody`, :class:`ViewerIndex`) +
  layout constants.
- :mod:`.messages` -- messages tab: tail-window scan + level / search
  predicates + table payload, plus the value-only ``@nu.host`` formatters.
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
    DEFAULT_LEVEL,
    DEFAULT_WINDOW,
    LEVEL_OPTIONS,
    SAMPLE_LIMIT,
    TABLE_COLUMNS,
    TAIL_LIMIT,
    TICK_SECONDS,
    WINDOW_OPTIONS,
    MessagesBody,
    MetricsBody,
    MetricsViewState,
    ViewerIndex,
    ViewerPage,
    ViewerTabs,
    ViewState,
)


__all__ = [
    "DEFAULT_LEVEL",
    "DEFAULT_WINDOW",
    "LEVEL_OPTIONS",
    "SAMPLE_LIMIT",
    "TABLE_COLUMNS",
    "TAIL_LIMIT",
    "TICK_SECONDS",
    "WINDOW_OPTIONS",
    "FmtFields",
    "FmtTs",
    "MessagesBody",
    "MetricsBody",
    "MetricsViewState",
    "RowAsList",
    "ViewState",
    "ViewerIndex",
    "ViewerPage",
    "ViewerTabs",
    "build_ui",
    "messages",
    "metrics",
]
