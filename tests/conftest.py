"""
Pytest configuration and fixtures.
"""

import pytest
from datetime import datetime
import pytz


@pytest.fixture
def pst_timezone():
    """PST timezone fixture."""
    return pytz.timezone("America/Los_Angeles")


@pytest.fixture
def et_timezone():
    """ET timezone fixture."""
    return pytz.timezone("America/New_York")


@pytest.fixture
def sample_datetime(pst_timezone):
    """Sample PST datetime for testing."""
    return pst_timezone.localize(datetime(2026, 1, 14, 12, 0))


@pytest.fixture
def date_range(pst_timezone):
    """Sample date range for testing."""
    start = pst_timezone.localize(datetime(2026, 1, 14, 0, 0))
    end = pst_timezone.localize(datetime(2026, 1, 28, 23, 59, 59))
    return start, end
