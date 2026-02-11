"""
Date parsing and timezone normalization utilities.
Handles various date formats from different event sources.
"""

from datetime import datetime, timedelta
from typing import Tuple, Optional
import re
import pytz
from dateutil import parser as dateutil_parser


class DateParser:
    """Utility class for parsing and normalizing dates to PST."""

    PST = pytz.timezone("America/Los_Angeles")
    UTC = pytz.UTC

    # Common timezone abbreviations and their pytz names
    TIMEZONE_MAP = {
        "PST": "America/Los_Angeles",
        "PDT": "America/Los_Angeles",
        "PT": "America/Los_Angeles",
        "EST": "America/New_York",
        "EDT": "America/New_York",
        "ET": "America/New_York",
        "CST": "America/Chicago",
        "CDT": "America/Chicago",
        "CT": "America/Chicago",
        "MST": "America/Denver",
        "MDT": "America/Denver",
        "MT": "America/Denver",
        "GMT": "UTC",
        "UTC": "UTC",
        "BST": "Europe/London",
        "CET": "Europe/Paris",
        "CEST": "Europe/Paris",
        "AKST": "US/Alaska",
        "AKDT": "US/Alaska",
        "AKT": "US/Alaska",
    }

    # Month name mappings
    MONTHS = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }

    # Timezone info for dateutil parser
    TZINFOS = {
        "ET": pytz.timezone("America/New_York"),
        "EST": pytz.timezone("America/New_York"),
        "EDT": pytz.timezone("America/New_York"),
        "PT": pytz.timezone("America/Los_Angeles"),
        "PST": pytz.timezone("America/Los_Angeles"),
        "PDT": pytz.timezone("America/Los_Angeles"),
        "CT": pytz.timezone("America/Chicago"),
        "CST": pytz.timezone("America/Chicago"),
        "CDT": pytz.timezone("America/Chicago"),
        "MT": pytz.timezone("America/Denver"),
        "MST": pytz.timezone("America/Denver"),
        "MDT": pytz.timezone("America/Denver"),
        "GMT": pytz.UTC,
        "UTC": pytz.UTC,
        "CET": pytz.timezone("Europe/Paris"),
        "CEST": pytz.timezone("Europe/Paris"),
        "BST": pytz.timezone("Europe/London"),
        "AKST": pytz.timezone("US/Alaska"),
        "AKDT": pytz.timezone("US/Alaska"),
        "AKT": pytz.timezone("US/Alaska"),
    }

    @classmethod
    def parse_datetime_range(
        cls,
        text: str,
        reference_date: Optional[datetime] = None,
    ) -> Tuple[datetime, Optional[datetime]]:
        """
        Parse a date/time string and return start and end datetimes in PST.

        Args:
            text: The date/time text to parse
            reference_date: Reference date for relative dates (defaults to today)

        Returns:
            Tuple of (start_datetime, end_datetime) both in PST
        """
        if not text:
            raise ValueError("Empty date text")

        text = cls._normalize_text(text)

        # Detect timezone in text BEFORE any modifications
        source_tz = cls._detect_timezone(text)

        # Extract time range BEFORE parsing (dateutil gets confused by time ranges)
        start_time, end_time = cls._extract_time_range(text)

        # Remove time range from text to avoid confusing dateutil
        # Pattern: removes "1:00 pm-1:50 pm" or "1:00-1:50pm" type patterns
        date_only_text = re.sub(
            r"\d{1,2}:\d{2}\s*(?:am|pm)?\s*[-–]\s*\d{1,2}:\d{2}\s*(?:am|pm)?",
            "",
            text,
            flags=re.IGNORECASE
        )
        # Also remove single times for cleaner parsing
        date_only_text = re.sub(
            r"\d{1,2}:\d{2}\s*(?:am|pm)",
            "",
            date_only_text,
            flags=re.IGNORECASE
        )

        # Try dateutil parser on cleaned text
        try:
            parsed = dateutil_parser.parse(date_only_text, fuzzy=True, tzinfos=cls.TZINFOS)
            # Start with midnight in source timezone
            start_dt = source_tz.localize(
                datetime(parsed.year, parsed.month, parsed.day, 0, 0)
            )
        except (ValueError, TypeError):
            # Fall back to manual parsing
            start_dt = cls._manual_parse_date(text, reference_date)
            if start_dt.tzinfo is None:
                start_dt = source_tz.localize(start_dt)

        # Apply extracted times in source timezone
        if start_time:
            start_dt = start_dt.replace(hour=start_time[0], minute=start_time[1])

        end_dt = None
        if end_time:
            end_dt = start_dt.replace(hour=end_time[0], minute=end_time[1])
            # Handle cases where end time is before start (crosses midnight)
            if end_dt < start_dt:
                end_dt += timedelta(days=1)

        # NOW convert to PST (after applying times in source timezone)
        start_dt = start_dt.astimezone(cls.PST)
        if end_dt:
            end_dt = end_dt.astimezone(cls.PST)

        return start_dt, end_dt

    @classmethod
    def _normalize_text(cls, text: str) -> str:
        """Normalize whitespace and common variations."""
        text = " ".join(text.split())  # Normalize whitespace
        text = text.replace("–", "-").replace("—", "-")  # Normalize dashes
        text = text.replace("\u00a0", " ")  # Replace non-breaking spaces
        return text

    @classmethod
    def _detect_timezone(cls, text: str) -> pytz.timezone:
        """Detect timezone from text, default to PST."""
        text_upper = text.upper()
        for tz_abbr, tz_name in cls.TIMEZONE_MAP.items():
            # Match timezone abbreviation as a word boundary
            if re.search(rf"\b{tz_abbr}\b", text_upper):
                return pytz.timezone(tz_name)
        return cls.PST

    @classmethod
    def _localize_to_pst(cls, dt: datetime, source_tz: pytz.timezone) -> datetime:
        """Convert datetime to PST."""
        if dt.tzinfo is None:
            dt = source_tz.localize(dt)
        return dt.astimezone(cls.PST)

    @classmethod
    def _extract_time_range(
        cls,
        text: str,
    ) -> Tuple[Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
        """
        Extract start and end times from text.
        Returns tuples of (hour, minute) in 24-hour format.
        """
        text_lower = text.lower()

        # Patterns for time extraction
        patterns = [
            # 12:00-1:00pm or 12:00pm-1:00pm
            r"(\d{1,2}):(\d{2})\s*([ap]m)?\s*[-\u2013]\s*(\d{1,2}):(\d{2})\s*([ap]m)",
            # 12:00pm
            r"(\d{1,2}):(\d{2})\s*([ap]m)",
            # 12pm-1pm or 12-1pm
            r"(\d{1,2})\s*([ap]m)?\s*[-\u2013]\s*(\d{1,2})\s*([ap]m)",
        ]

        # Pattern 1: Full time range with minutes (am/pm optional for 24-hour format)
        match = re.search(
            r"(\d{1,2}):(\d{2})\s*([ap]m)?\s*[-\u2013]\s*(\d{1,2}):(\d{2})\s*([ap]m)?",
            text_lower,
        )
        if match:
            start_hour, start_min = int(match.group(1)), int(match.group(2))
            start_ampm = match.group(3) or match.group(6)
            end_hour, end_min = int(match.group(4)), int(match.group(5))
            end_ampm = match.group(6)

            start_time = cls._convert_to_24h(start_hour, start_min, start_ampm)
            end_time = cls._convert_to_24h(end_hour, end_min, end_ampm)
            return start_time, end_time

        # Pattern 2: Single time with minutes
        match = re.search(r"(\d{1,2}):(\d{2})\s*([ap]m)", text_lower)
        if match:
            hour, minute = int(match.group(1)), int(match.group(2))
            ampm = match.group(3)
            start_time = cls._convert_to_24h(hour, minute, ampm)
            return start_time, None

        # Pattern 3: Hour range without minutes
        match = re.search(r"(\d{1,2})\s*([ap]m)?\s*[-\u2013]\s*(\d{1,2})\s*([ap]m)", text_lower)
        if match:
            start_hour = int(match.group(1))
            start_ampm = match.group(2) or match.group(4)
            end_hour = int(match.group(3))
            end_ampm = match.group(4)

            start_time = cls._convert_to_24h(start_hour, 0, start_ampm)
            end_time = cls._convert_to_24h(end_hour, 0, end_ampm)
            return start_time, end_time

        return None, None

    @classmethod
    def _convert_to_24h(
        cls, hour: int, minute: int, ampm: Optional[str]
    ) -> Tuple[int, int]:
        """Convert 12-hour time to 24-hour format."""
        if ampm:
            ampm = ampm.lower()
            if ampm == "pm" and hour != 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
        return (hour, minute)

    @classmethod
    def _manual_parse_date(
        cls,
        text: str,
        reference_date: Optional[datetime],
    ) -> datetime:
        """Manually parse date when dateutil fails."""
        if reference_date is None:
            reference_date = datetime.now(cls.PST)

        # Pattern: January 14, 2026 or Jan 14, 2026
        match = re.search(
            r"(\w+)\s+(\d{1,2}),?\s+(\d{4})", text, re.IGNORECASE
        )
        if match:
            month_str, day, year = match.groups()
            month = cls.MONTHS.get(month_str.lower()[:3])
            if month:
                return cls.PST.localize(datetime(int(year), month, int(day)))

        # Pattern: 14 January 2026
        match = re.search(
            r"(\d{1,2})\s+(\w+)\s+(\d{4})", text, re.IGNORECASE
        )
        if match:
            day, month_str, year = match.groups()
            month = cls.MONTHS.get(month_str.lower()[:3])
            if month:
                return cls.PST.localize(datetime(int(year), month, int(day)))

        # Pattern: 2026-01-14
        match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
        if match:
            year, month, day = match.groups()
            return cls.PST.localize(datetime(int(year), int(month), int(day)))

        # Pattern: 01/14/2026
        match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
        if match:
            month, day, year = match.groups()
            return cls.PST.localize(datetime(int(year), int(month), int(day)))

        # Pattern: Jan 14 (no year - assume current or next year)
        match = re.search(r"(\w{3,})\s+(\d{1,2})(?!\d)", text, re.IGNORECASE)
        if match:
            month_str, day = match.groups()
            month = cls.MONTHS.get(month_str.lower()[:3])
            if month:
                year = reference_date.year
                dt = cls.PST.localize(datetime(year, month, int(day)))
                # If date has passed, assume next year
                if dt < reference_date:
                    dt = dt.replace(year=year + 1)
                return dt

        raise ValueError(f"Could not parse date from: {text}")

    @classmethod
    def get_date_range(cls, days: int = 14) -> Tuple[datetime, datetime]:
        """Get a date range from today for the specified number of days."""
        now = datetime.now(cls.PST)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=days)
        # Set end to end of day (11:59:59 PM) so events on the last day are included
        end = end.replace(hour=23, minute=59, second=59)
        return start, end

    @classmethod
    def get_fixed_date_range(
        cls, start_str: str, end_str: str
    ) -> Tuple[datetime, datetime]:
        """Get a date range from explicit date strings (YYYY-MM-DD format)."""
        start = cls.PST.localize(datetime.strptime(start_str, "%Y-%m-%d"))
        end = cls.PST.localize(datetime.strptime(end_str, "%Y-%m-%d"))
        # Set end to end of day
        end = end.replace(hour=23, minute=59, second=59)
        return start, end
