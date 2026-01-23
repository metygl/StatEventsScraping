"""
Tests for HTMLGenerator class, including export page functionality.
"""

import json
import pytest
import tempfile
from pathlib import Path
from datetime import datetime
import pytz

from src.output.html_generator import HTMLGenerator, days_to_time_period
from src.models.event import Event, LocationType


@pytest.fixture
def sample_events(pst_timezone):
    """Sample events for testing."""
    return [
        Event(
            title="Test Seminar on Statistics",
            url="https://example.com/event1",
            source="TestOrg",
            start_datetime=pst_timezone.localize(datetime(2026, 1, 15, 12, 0)),
            end_datetime=pst_timezone.localize(datetime(2026, 1, 15, 13, 0)),
            speakers=["John Doe", "Jane Smith"],
            location_type=LocationType.VIRTUAL,
            cost="free",
        ),
        Event(
            title="Data Science Workshop",
            url="https://example.com/event2",
            source="AnotherOrg",
            start_datetime=pst_timezone.localize(datetime(2026, 1, 16, 9, 0)),
            end_datetime=pst_timezone.localize(datetime(2026, 1, 16, 17, 0)),
            speakers=["Alice Johnson"],
            location_type=LocationType.IN_PERSON,
            location_details="San Francisco, CA",
            cost="$250",
        ),
        Event(
            title="Biostatistics Conference",
            url="https://example.com/event3",
            source="TestOrg",
            start_datetime=pst_timezone.localize(datetime(2026, 1, 14, 10, 0)),
            end_datetime=pst_timezone.localize(datetime(2026, 1, 14, 11, 0)),
            speakers=[],
            location_type=LocationType.VIRTUAL,
            cost="free",
        ),
    ]


@pytest.fixture
def html_generator():
    """HTMLGenerator instance for testing."""
    return HTMLGenerator()


class TestGenerateExportPage:
    """Tests for generate_export_page method."""

    def test_generates_export_html_file(self, html_generator, sample_events, date_range):
        """Test that export HTML file is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "export.html"
            result = html_generator.generate_export_page(
                sample_events, str(output_path), date_range
            )

            assert Path(result).exists()
            assert output_path.exists()

    def test_export_contains_event_titles(self, html_generator, sample_events, date_range):
        """Test that export page contains event titles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "export.html"
            html_generator.generate_export_page(
                sample_events, str(output_path), date_range
            )

            content = output_path.read_text()
            assert "Test Seminar on Statistics" in content
            assert "Data Science Workshop" in content
            assert "Biostatistics Conference" in content

    def test_export_contains_json_data(self, html_generator, sample_events, date_range):
        """Test that export page contains embedded JSON data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "export.html"
            html_generator.generate_export_page(
                sample_events, str(output_path), date_range
            )

            content = output_path.read_text()
            assert 'id="events-data"' in content
            assert "application/json" in content

    def test_export_json_contains_required_fields(
        self, html_generator, sample_events, date_range
    ):
        """Test that JSON data contains all required fields for export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "export.html"
            html_generator.generate_export_page(
                sample_events, str(output_path), date_range
            )

            content = output_path.read_text()

            # Extract JSON from HTML
            start_marker = '<script type="application/json" id="events-data">'
            end_marker = "</script>"
            start_idx = content.find(start_marker) + len(start_marker)
            end_idx = content.find(end_marker, start_idx)
            json_str = content[start_idx:end_idx].strip()

            events_data = json.loads(json_str)
            assert len(events_data) == 3

            # Check first event has all required fields
            first_event = events_data[0]  # Sorted by date, so Biostatistics first
            assert "title" in first_event
            assert "url" in first_event
            assert "source" in first_event
            assert "speakers" in first_event
            assert "date_range" in first_event
            assert "location" in first_event
            assert "cost" in first_event

    def test_export_events_sorted_by_date(
        self, html_generator, sample_events, date_range
    ):
        """Test that events in JSON are sorted by date."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "export.html"
            html_generator.generate_export_page(
                sample_events, str(output_path), date_range
            )

            content = output_path.read_text()

            # Extract JSON from HTML
            start_marker = '<script type="application/json" id="events-data">'
            end_marker = "</script>"
            start_idx = content.find(start_marker) + len(start_marker)
            end_idx = content.find(end_marker, start_idx)
            json_str = content[start_idx:end_idx].strip()

            events_data = json.loads(json_str)

            # First event should be Jan 14 (Biostatistics Conference)
            assert events_data[0]["title"] == "Biostatistics Conference"
            # Last event should be Jan 16 (Data Science Workshop)
            assert events_data[2]["title"] == "Data Science Workshop"

    def test_export_contains_source_filter(
        self, html_generator, sample_events, date_range
    ):
        """Test that export page contains source filter dropdown."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "export.html"
            html_generator.generate_export_page(
                sample_events, str(output_path), date_range
            )

            content = output_path.read_text()
            assert 'id="source-filter"' in content
            assert "TestOrg" in content
            assert "AnotherOrg" in content

    def test_export_contains_checkboxes(
        self, html_generator, sample_events, date_range
    ):
        """Test that export page contains checkboxes for selection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "export.html"
            html_generator.generate_export_page(
                sample_events, str(output_path), date_range
            )

            content = output_path.read_text()
            assert 'class="event-checkbox"' in content
            assert 'data-index="0"' in content
            assert 'data-index="1"' in content
            assert 'data-index="2"' in content

    def test_export_contains_action_buttons(
        self, html_generator, sample_events, date_range
    ):
        """Test that export page contains copy and download buttons."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "export.html"
            html_generator.generate_export_page(
                sample_events, str(output_path), date_range
            )

            content = output_path.read_text()
            assert 'id="copy-clipboard"' in content
            assert 'id="download-txt"' in content
            assert "Copy to Clipboard" in content
            assert "Download as .txt" in content

    def test_export_contains_select_all_none_buttons(
        self, html_generator, sample_events, date_range
    ):
        """Test that export page contains select all/none buttons."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "export.html"
            html_generator.generate_export_page(
                sample_events, str(output_path), date_range
            )

            content = output_path.read_text()
            assert 'id="select-all"' in content
            assert 'id="select-none"' in content
            assert "Select All" in content
            assert "Select None" in content

    def test_export_json_has_preformatted_fields(
        self, html_generator, sample_events, date_range
    ):
        """Test that JSON contains pre-formatted fields ready for export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "export.html"
            html_generator.generate_export_page(
                sample_events, str(output_path), date_range
            )

            content = output_path.read_text()

            # Extract JSON
            start_marker = '<script type="application/json" id="events-data">'
            end_marker = "</script>"
            start_idx = content.find(start_marker) + len(start_marker)
            end_idx = content.find(end_marker, start_idx)
            json_str = content[start_idx:end_idx].strip()

            events_data = json.loads(json_str)

            # Check pre-formatted fields match Event methods
            workshop = next(e for e in events_data if "Workshop" in e["title"])
            assert workshop["location"] == "San Francisco, CA"
            assert workshop["cost"] == "$250"
            assert "January 16, 2026" in workshop["date_range"]

    def test_export_empty_events_list(self, html_generator, date_range):
        """Test export page with empty events list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "export.html"
            html_generator.generate_export_page([], str(output_path), date_range)

            content = output_path.read_text()
            assert "No events available to export" in content

    def test_export_contains_back_link(
        self, html_generator, sample_events, date_range
    ):
        """Test that export page contains back link to events page."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "export.html"
            html_generator.generate_export_page(
                sample_events, str(output_path), date_range
            )

            content = output_path.read_text()
            assert 'href="events.html"' in content
            assert "Back to Events" in content


class TestGenerateTextOutput:
    """Tests for generate_text_output method."""

    def test_text_output_format(self, html_generator, sample_events, date_range):
        """Test that text output matches expected format."""
        result = html_generator.generate_text_output(sample_events, date_range)

        assert "For your information" in result
        assert "TestOrg:" in result
        assert "AnotherOrg:" in result

    def test_text_output_includes_speakers(
        self, html_generator, sample_events, date_range
    ):
        """Test that text output includes speaker names."""
        result = html_generator.generate_text_output(sample_events, date_range)

        assert "John Doe" in result
        assert "Jane Smith" in result
        assert "Alice Johnson" in result

    def test_text_output_sorted_by_date(
        self, html_generator, sample_events, date_range
    ):
        """Test that text output events are sorted by date."""
        result = html_generator.generate_text_output(sample_events, date_range)

        # Find positions of events - Biostatistics should come first
        bio_pos = result.find("Biostatistics Conference")
        seminar_pos = result.find("Test Seminar")
        workshop_pos = result.find("Data Science Workshop")

        assert bio_pos < seminar_pos < workshop_pos

    def test_text_output_dynamic_time_period(
        self, html_generator, sample_events, date_range
    ):
        """Test that text output uses dynamic time period based on days_ahead."""
        # Test with 21 days (three weeks)
        result = html_generator.generate_text_output(
            sample_events, date_range, days_ahead=21
        )
        assert "three weeks" in result

        # Test with 14 days (two weeks)
        result = html_generator.generate_text_output(
            sample_events, date_range, days_ahead=14
        )
        assert "two weeks" in result

        # Test with 7 days (one week)
        result = html_generator.generate_text_output(
            sample_events, date_range, days_ahead=7
        )
        assert "one week" in result


class TestDaysToTimePeriod:
    """Tests for days_to_time_period helper function."""

    def test_exact_weeks(self):
        """Test conversion for exact week multiples."""
        assert days_to_time_period(7) == "one week"
        assert days_to_time_period(14) == "two weeks"
        assert days_to_time_period(21) == "three weeks"
        assert days_to_time_period(28) == "four weeks"
        assert days_to_time_period(35) == "five weeks"
        assert days_to_time_period(42) == "six weeks"

    def test_non_week_multiples(self):
        """Test conversion for non-week multiples returns days."""
        assert days_to_time_period(10) == "10 days"
        assert days_to_time_period(15) == "15 days"
        assert days_to_time_period(20) == "20 days"

    def test_single_day(self):
        """Test conversion for single day."""
        assert days_to_time_period(1) == "one day"

    def test_few_days(self):
        """Test conversion for a few days."""
        assert days_to_time_period(3) == "3 days"
        assert days_to_time_period(5) == "5 days"


class TestExportPageTimePeriod:
    """Tests for dynamic time period in export page."""

    def test_export_page_uses_dynamic_time_period(
        self, html_generator, sample_events, date_range
    ):
        """Test that export page contains the correct dynamic time period."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "export.html"

            # Test with 21 days (three weeks)
            html_generator.generate_export_page(
                sample_events, str(output_path), date_range, days_ahead=21
            )
            content = output_path.read_text()
            assert "three weeks" in content

    def test_export_page_two_weeks(
        self, html_generator, sample_events, date_range
    ):
        """Test export page with two weeks period."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "export.html"

            html_generator.generate_export_page(
                sample_events, str(output_path), date_range, days_ahead=14
            )
            content = output_path.read_text()
            assert "two weeks" in content
