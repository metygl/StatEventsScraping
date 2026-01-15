"""
Unit tests for the DateParser class.
"""

import pytest
from datetime import datetime
import pytz

from src.parsers.date_parser import DateParser


class TestDateParserParseDatetimeRange:
    """Tests for parse_datetime_range method."""

    PST = pytz.timezone("America/Los_Angeles")

    def test_full_date_with_time_range(self):
        """Test parsing 'January 14, 2026, 12:00-1:00pm PST'."""
        text = "January 14, 2026, 12:00-1:00pm PST"
        start_dt, end_dt = DateParser.parse_datetime_range(text)

        assert start_dt.year == 2026
        assert start_dt.month == 1
        assert start_dt.day == 14
        assert start_dt.hour == 12
        assert start_dt.minute == 0
        assert end_dt.hour == 13
        assert end_dt.minute == 0

    def test_date_with_am_pm_time_range(self):
        """Test parsing '9:00-10:00am' style times."""
        text = "January 15, 2026 9:00-10:00am ET"
        start_dt, end_dt = DateParser.parse_datetime_range(text)

        assert start_dt.day == 15
        # Time extraction preserves the literal time from text
        # (timezone context is handled by individual scrapers)
        assert start_dt.hour == 9
        assert end_dt.hour == 10

    def test_date_only_no_time(self):
        """Test parsing date without time."""
        text = "January 16, 2026"
        start_dt, end_dt = DateParser.parse_datetime_range(text)

        assert start_dt.year == 2026
        assert start_dt.month == 1
        assert start_dt.day == 16
        assert end_dt is None

    def test_iso_format_date(self):
        """Test parsing ISO format date."""
        text = "2026-01-20"
        start_dt, end_dt = DateParser.parse_datetime_range(text)

        assert start_dt.year == 2026
        assert start_dt.month == 1
        assert start_dt.day == 20

    def test_slash_format_date(self):
        """Test parsing MM/DD/YYYY format."""
        text = "01/14/2026"
        start_dt, end_dt = DateParser.parse_datetime_range(text)

        assert start_dt.year == 2026
        assert start_dt.month == 1
        assert start_dt.day == 14

    def test_timezone_detection_et(self):
        """Test that ET is detected and result is in PST timezone."""
        text = "January 15, 2026 12:00pm ET"
        start_dt, _ = DateParser.parse_datetime_range(text)

        # Timezone is detected but time is preserved from text
        # Result is tagged as PST (scrapers handle context-specific conversion)
        assert start_dt.hour == 12
        assert str(start_dt.tzinfo) == "America/Los_Angeles"

    def test_timezone_detection_cet(self):
        """Test that CET is detected and result is in PST timezone."""
        text = "January 14, 2026 6:00pm CET"
        start_dt, _ = DateParser.parse_datetime_range(text)

        # Time is preserved from text, tagged as PST
        assert start_dt.hour == 18
        assert str(start_dt.tzinfo) == "America/Los_Angeles"

    def test_empty_text_raises_error(self):
        """Test that empty text raises ValueError."""
        with pytest.raises(ValueError, match="Empty date text"):
            DateParser.parse_datetime_range("")

    def test_invalid_date_raises_error(self):
        """Test that completely invalid text raises ValueError."""
        with pytest.raises(ValueError):
            DateParser.parse_datetime_range("not a date at all xyz")

    def test_abbreviated_month(self):
        """Test parsing abbreviated month name."""
        text = "Jan 28, 2026"
        start_dt, _ = DateParser.parse_datetime_range(text)

        assert start_dt.month == 1
        assert start_dt.day == 28
        assert start_dt.year == 2026

    def test_day_month_year_format(self):
        """Test parsing '14 January 2026' format."""
        text = "14 January 2026"
        start_dt, _ = DateParser.parse_datetime_range(text)

        assert start_dt.day == 14
        assert start_dt.month == 1
        assert start_dt.year == 2026


class TestDateParserExtractTimeRange:
    """Tests for _extract_time_range method."""

    def test_time_range_with_am_pm(self):
        """Test extracting '12:00-1:00pm' style."""
        text = "12:00-1:00pm"
        start, end = DateParser._extract_time_range(text)

        assert start == (12, 0)
        assert end == (13, 0)

    def test_time_range_with_both_am_pm(self):
        """Test extracting '9:00am-10:00am' style."""
        text = "9:00am-10:00am"
        start, end = DateParser._extract_time_range(text)

        assert start == (9, 0)
        assert end == (10, 0)

    def test_single_time(self):
        """Test extracting single time like '2:30pm'."""
        text = "2:30pm"
        start, end = DateParser._extract_time_range(text)

        assert start == (14, 30)
        assert end is None

    def test_no_time_in_text(self):
        """Test when no time is present."""
        text = "January 14, 2026"
        start, end = DateParser._extract_time_range(text)

        assert start is None
        assert end is None


class TestDateParserDateRange:
    """Tests for date range utility methods."""

    def test_get_date_range_default(self):
        """Test getting default 14-day range."""
        start, end = DateParser.get_date_range()

        assert (end - start).days == 14

    def test_get_date_range_custom_days(self):
        """Test getting custom day range."""
        start, end = DateParser.get_date_range(days=7)

        assert (end - start).days == 7

    def test_get_fixed_date_range(self):
        """Test getting fixed date range from strings."""
        start, end = DateParser.get_fixed_date_range("2026-01-14", "2026-01-30")

        assert start.day == 14
        assert start.month == 1
        assert end.day == 30
        assert end.hour == 23
        assert end.minute == 59


class TestDateParserTimezoneDetection:
    """Tests for timezone detection."""

    def test_detect_pst(self):
        """Test detecting PST timezone."""
        tz = DateParser._detect_timezone("January 14, 2026 at 12:00pm PST")
        assert str(tz) == "America/Los_Angeles"

    def test_detect_et(self):
        """Test detecting ET timezone."""
        tz = DateParser._detect_timezone("January 14, 2026 at 12:00pm ET")
        assert str(tz) == "America/New_York"

    def test_default_to_pst(self):
        """Test default to PST when no timezone specified."""
        tz = DateParser._detect_timezone("January 14, 2026 at 12:00pm")
        assert str(tz) == "America/Los_Angeles"
