"""Browser log viewer -- one nudle Page, one Nu tree.

Split into three files:

- :mod:`.shape` -- view state (:class:`ViewState`) and display shapes
  (:class:`ViewerPage`, :class:`ViewerIndex`) + layout constants.
- :mod:`.query` -- table read pipeline (tail window + level / search
  predicates) and value-only ``@nu.host`` formatting seams.
- :mod:`.app` -- :func:`build_ui`, the reactive composer that seeds
  state, hydrates chrome, and races the tick against filter reactives.
"""

from __future__ import annotations

from .app import build_ui
from .query import FmtFields, FmtTs, RowAsList
from .shape import (
    DEFAULT_LEVEL,
    LEVEL_OPTIONS,
    TABLE_COLUMNS,
    TAIL_LIMIT,
    TICK_SECONDS,
    ViewerIndex,
    ViewerPage,
    ViewState,
)


__all__ = [
    "DEFAULT_LEVEL",
    "LEVEL_OPTIONS",
    "TABLE_COLUMNS",
    "TAIL_LIMIT",
    "TICK_SECONDS",
    "FmtFields",
    "FmtTs",
    "RowAsList",
    "ViewState",
    "ViewerIndex",
    "ViewerPage",
    "build_ui",
]
