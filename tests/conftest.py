"""Shared fixtures and test helpers for wg-heimdallr."""

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def clean_env():
    """Isolate environment variables between tests."""
    old = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(old)


@pytest.fixture
def tmp_secrets(tmp_path):
    """Create a temporary secrets file with empty JSON."""
    p = tmp_path / "secrets.json"
    p.write_text("{}")
    return str(p)


@pytest.fixture
def mock_run():
    """Mock subprocess.run for wg / nft calls."""
    with mock.patch("subprocess.run") as m:
        yield m


@pytest.fixture
def mock_popen():
    """Mock subprocess.Popen for Telegram curl calls."""
    with mock.patch("subprocess.Popen") as m:
        yield m


@pytest.fixture
def mock_os_path_exists():
    """Mock os.path.exists."""
    with mock.patch("os.path.exists") as m:
        yield m
