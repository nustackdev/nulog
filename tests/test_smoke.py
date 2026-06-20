"""Smoke test for the nulog package."""

import nulog


def test_version():
    assert nulog.__version__ == "0.1.0"


def test_public_surface():
    for name in nulog.__all__:
        assert hasattr(nulog, name), name
