"""Viewer tuning knobs -- defaults, option sets, bounds, tick pace.

Kept separate from :mod:`.shape` so the display shapes read cleanly and
the numbers you tune (default window, sample cap, tick period) live in
one obvious place.
"""

from __future__ import annotations

from ..messages.types import LEVELS


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
]


# ---- messages tab -------------------------------------------------------

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


# ---- metrics tab --------------------------------------------------------

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
