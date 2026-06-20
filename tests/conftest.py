"""Shared fixtures: a fresh in-memory log store per test."""

from __future__ import annotations

import pytest

from nulog import open_logs


@pytest.fixture
def logs():
    """A fresh in-memory Logs handle, unique store dir, torn down after the test."""
    with open_logs() as handle:
        yield handle


@pytest.fixture
def app(logs):
    """A logger on the 'app' stream of the per-test store."""
    return logs.stream("app")
