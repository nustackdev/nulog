"""Smoke test for the nulog package."""

import nulog


def test_version():
    assert nulog.__version__ == "0.5.0"


def test_public_surface():
    for name in nulog.__all__:
        assert hasattr(nulog, name), name


def test_dropped_imperatives():
    """The old imperative surface stayed dropped."""
    for name in ("open_logs", "Logger", "read_records", "LogRecord", "MetricPointRow"):
        assert not hasattr(nulog, name), name
