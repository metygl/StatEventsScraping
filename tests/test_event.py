"""
Unit tests for the Event model.
"""

import pytest
from datetime import datetime
import pytz

from src.models.event import Event, LocationType


class TestEventCreation:
    """Tests for Event object creation and initialization."""

    PST = pytz.timezone("America/Los_Angeles")

    def test_basic_event_creation(self):
        """Test creating a basic event with required fields."""
        start_dt = self.PST.localize(datetime(2026, 1, 14, 12, 0))
        event = Event(
            title="Test Event",
            url="https://example.com/event",
            source="Test Source",
            start_datetime=start_dt,
        )

        assert event.title == "Test Event"
        assert event.url == "https://example.com/event"
        assert event.source == "Test Source"
        assert event.start_datetime == start_dt

    def test_event_with_all_fields(self):
        """Test creating an event with all optional fields."""
        start_dt = self.PST.localize(datetime(2026, 1, 14, 12, 0))
        end_dt = self.PST.localize(datetime(2026, 1, 14, 13, 0))

        event = Event(
            title="Full Event",
            url="https://example.com/event",
            source="Test Source",
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=["John Doe", "Jane Smith"],
            location_type=LocationType.VIRTUAL,
            cost="free",
            description="A test event",
        )

        assert event.end_datetime == end_dt
        assert event.speakers == ["John Doe", "Jane Smith"]
        assert event.location_type == LocationType.VIRTUAL
        assert event.cost == "free"

    def test_title_whitespace_stripped(self):
        """Test that title whitespace is stripped."""
        start_dt = self.PST.localize(datetime(2026, 1, 14, 12, 0))
        event = Event(
            title="  Test Event  ",
            url="https://example.com",
            source="Test",
            start_datetime=start_dt,
        )

        assert event.title == "Test Event"

    def test_speakers_whitespace_stripped(self):
        """Test that speaker names have whitespace stripped."""
        start_dt = self.PST.localize(datetime(2026, 1, 14, 12, 0))
        event = Event(
            title="Test",
            url="https://example.com",
            source="Test",
            start_datetime=start_dt,
            speakers=["  John Doe  ", "Jane Smith", "  ", ""],
        )

        assert event.speakers == ["John Doe", "Jane Smith"]

    def test_naive_datetime_localized_to_pst(self):
        """Test that naive datetime is localized to PST."""
        naive_dt = datetime(2026, 1, 14, 12, 0)
        event = Event(
            title="Test",
            url="https://example.com",
            source="Test",
            start_datetime=naive_dt,
        )

        assert event.start_datetime.tzinfo is not None
        assert str(event.start_datetime.tzinfo) == "America/Los_Angeles"

    def test_et_datetime_converted_to_pst(self):
        """Test that ET datetime is converted to PST."""
        et = pytz.timezone("America/New_York")
        et_dt = et.localize(datetime(2026, 1, 14, 15, 0))  # 3pm ET

        event = Event(
            title="Test",
            url="https://example.com",
            source="Test",
            start_datetime=et_dt,
        )

        # 3pm ET = 12pm PST
        assert event.start_datetime.hour == 12
        assert str(event.start_datetime.tzinfo) == "America/Los_Angeles"


class TestEventFormatting:
    """Tests for Event formatting methods."""

    PST = pytz.timezone("America/Los_Angeles")

    def test_format_date_range_with_end_time(self):
        """Test date range formatting with start and end time."""
        start_dt = self.PST.localize(datetime(2026, 1, 14, 12, 0))
        end_dt = self.PST.localize(datetime(2026, 1, 14, 13, 0))

        event = Event(
            title="Test",
            url="https://example.com",
            source="Test",
            start_datetime=start_dt,
            end_datetime=end_dt,
        )

        formatted = event.format_date_range()
        assert "January 14, 2026" in formatted
        assert "12:00-1:00pm PST" in formatted

    def test_format_date_range_without_end_time(self):
        """Test date range formatting without end time."""
        start_dt = self.PST.localize(datetime(2026, 1, 14, 9, 30))

        event = Event(
            title="Test",
            url="https://example.com",
            source="Test",
            start_datetime=start_dt,
        )

        formatted = event.format_date_range()
        assert "January 14, 2026" in formatted
        assert "9:30am PST" in formatted

    def test_format_cost_free(self):
        """Test cost formatting for free events."""
        start_dt = self.PST.localize(datetime(2026, 1, 14, 12, 0))

        for cost_value in ["free", "Free", "FREE", "$0", "$0.00", "0", None]:
            event = Event(
                title="Test",
                url="https://example.com",
                source="Test",
                start_datetime=start_dt,
                cost=cost_value,
            )
            assert event.format_cost() == "free"

    def test_format_cost_paid(self):
        """Test cost formatting for paid events."""
        start_dt = self.PST.localize(datetime(2026, 1, 14, 12, 0))
        event = Event(
            title="Test",
            url="https://example.com",
            source="Test",
            start_datetime=start_dt,
            cost="$50",
        )

        assert event.format_cost() == "$50"

    def test_format_location_virtual(self):
        """Test location formatting for virtual events."""
        start_dt = self.PST.localize(datetime(2026, 1, 14, 12, 0))
        event = Event(
            title="Test",
            url="https://example.com",
            source="Test",
            start_datetime=start_dt,
            location_type=LocationType.VIRTUAL,
        )

        assert event.format_location() == "Virtual"

    def test_format_location_in_person_with_details(self):
        """Test location formatting for in-person events with details."""
        start_dt = self.PST.localize(datetime(2026, 1, 14, 12, 0))
        event = Event(
            title="Test",
            url="https://example.com",
            source="Test",
            start_datetime=start_dt,
            location_type=LocationType.IN_PERSON,
            location_details="San Francisco, CA",
        )

        assert event.format_location() == "San Francisco, CA"

    def test_format_location_hybrid(self):
        """Test location formatting for hybrid events."""
        start_dt = self.PST.localize(datetime(2026, 1, 14, 12, 0))
        event = Event(
            title="Test",
            url="https://example.com",
            source="Test",
            start_datetime=start_dt,
            location_type=LocationType.HYBRID,
            location_details="Boston, MA",
        )

        assert event.format_location() == "Hybrid - Boston, MA"


class TestEventDisplayString:
    """Tests for to_display_string method."""

    PST = pytz.timezone("America/Los_Angeles")

    def test_display_string_format(self):
        """Test the full display string format."""
        start_dt = self.PST.localize(datetime(2026, 1, 14, 12, 0))
        end_dt = self.PST.localize(datetime(2026, 1, 14, 13, 0))

        event = Event(
            title="Test Seminar",
            url="https://example.com/seminar",
            source="Test Source",
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=["John Doe"],
            location_type=LocationType.VIRTUAL,
            cost="free",
        )

        display = event.to_display_string()

        assert "Test Source: Test Seminar (John Doe)" in display
        assert "https://example.com/seminar" in display
        assert "January 14, 2026" in display
        assert "Virtual" in display
        assert "free" in display


class TestEventDateRange:
    """Tests for is_within_date_range method."""

    PST = pytz.timezone("America/Los_Angeles")

    def test_event_within_range(self):
        """Test event within date range."""
        event_dt = self.PST.localize(datetime(2026, 1, 15, 12, 0))
        event = Event(
            title="Test",
            url="https://example.com",
            source="Test",
            start_datetime=event_dt,
        )

        start = self.PST.localize(datetime(2026, 1, 14, 0, 0))
        end = self.PST.localize(datetime(2026, 1, 28, 23, 59))

        assert event.is_within_date_range(start, end) is True

    def test_event_before_range(self):
        """Test event before date range."""
        event_dt = self.PST.localize(datetime(2026, 1, 10, 12, 0))
        event = Event(
            title="Test",
            url="https://example.com",
            source="Test",
            start_datetime=event_dt,
        )

        start = self.PST.localize(datetime(2026, 1, 14, 0, 0))
        end = self.PST.localize(datetime(2026, 1, 28, 23, 59))

        assert event.is_within_date_range(start, end) is False

    def test_event_after_range(self):
        """Test event after date range."""
        event_dt = self.PST.localize(datetime(2026, 2, 15, 12, 0))
        event = Event(
            title="Test",
            url="https://example.com",
            source="Test",
            start_datetime=event_dt,
        )

        start = self.PST.localize(datetime(2026, 1, 14, 0, 0))
        end = self.PST.localize(datetime(2026, 1, 28, 23, 59))

        assert event.is_within_date_range(start, end) is False


class TestEventSorting:
    """Tests for Event sorting."""

    PST = pytz.timezone("America/Los_Angeles")

    def test_events_sort_by_datetime(self):
        """Test that events sort by start datetime."""
        event1 = Event(
            title="Event 1",
            url="https://example.com/1",
            source="Test",
            start_datetime=self.PST.localize(datetime(2026, 1, 16, 12, 0)),
        )
        event2 = Event(
            title="Event 2",
            url="https://example.com/2",
            source="Test",
            start_datetime=self.PST.localize(datetime(2026, 1, 14, 12, 0)),
        )
        event3 = Event(
            title="Event 3",
            url="https://example.com/3",
            source="Test",
            start_datetime=self.PST.localize(datetime(2026, 1, 15, 12, 0)),
        )

        events = sorted([event1, event2, event3])

        assert events[0].title == "Event 2"
        assert events[1].title == "Event 3"
        assert events[2].title == "Event 1"
