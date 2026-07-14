"""Smoke test for the nulog package."""

import nulog


def test_version():
    assert nulog.__version__ == "0.6.0"


def test_public_surface():
    for name in nulog.__all__:
        assert hasattr(nulog, name), name


def test_dropped_imperatives():
    """The old imperative surface stayed dropped."""
    for name in ("open_logs", "read_records", "LogRecord", "MetricPointRow", "entry"):
        assert not hasattr(nulog, name), name


def test_new_logger_surface_present():
    """The Python-``logging`` -shape wrapper is the public write surface."""
    for name in (
        "Logger", "getLogger",
        "debug", "info", "warning", "warn", "error", "critical", "log",
        "DEBUG", "INFO", "WARNING", "WARN", "ERROR", "CRITICAL", "FATAL",
        "from_std_logging", "observe",
    ):
        assert hasattr(nulog, name), name
