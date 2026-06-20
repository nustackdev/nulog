"""nulog.ui -- a nudle log viewer mounted over a nulog store.

The optional ``[ui]`` extra: a browser viewer that queries a log store in the
same Nu language the writer used. Importing this package needs ``nudle``
(``pip install nulog[ui]``); the core ``nulog`` package never imports it, so
plain ``nulog`` works without nudle.

What you get is one page: a live, newest-first entry table; a stream switcher; a
level filter; a message search box; and per-level count Stats. The table and the
counts repaint every second off the core query builders (:mod:`nulog.query`), so
new lines surface live.

Quickstart::

    from nulog import open_logs
    from nulog.ui import run_viewer

    with open_logs("/var/log/myapp") as logs:
        run_viewer(["app", "scraper"], logs=logs)

``run_viewer`` runs the server itself, so a viewer is a plain Python script, no
nudle CLI needed (see ``examples/viewer.py``). For finer control over the
lifecycle, ``serve_logs`` is the async coroutine underneath.
"""

from __future__ import annotations

from .app import build_app, default_stream
from .pages import LEVEL_OPTIONS, TABLE_COLUMNS, LogIndex, LogViewer
from .serve import run_viewer, serve_logs


__all__ = [
    "LEVEL_OPTIONS",
    "TABLE_COLUMNS",
    "LogIndex",
    "LogViewer",
    "build_app",
    "default_stream",
    "run_viewer",
    "serve_logs",
]
