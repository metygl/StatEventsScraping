"""
Static HTML and text output generation from scraped events.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import pytz
from jinja2 import Environment, FileSystemLoader

from src.models.event import Event


class HTMLGenerator:
    """Generate static HTML and text output from events."""

    def __init__(self, template_dir: str = None):
        """
        Initialize HTML generator.

        Args:
            template_dir: Path to template directory
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        self.template_dir = Path(template_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=True,
        )

    def generate(
        self,
        events: List[Event],
        output_path: str,
        date_range: tuple = None,
    ) -> str:
        """
        Generate HTML file from events.

        Args:
            events: List of Event objects
            output_path: Path to write HTML file
            date_range: Optional tuple of (start_date, end_date) for header

        Returns:
            Path to generated file
        """
        # Sort events by date
        sorted_events = sorted(events, key=lambda e: e.start_datetime)

        # Group by date for display
        grouped_events = self._group_by_date(sorted_events)

        # Prepare template context
        pst = pytz.timezone("America/Los_Angeles")
        context = {
            "events": sorted_events,
            "grouped_events": grouped_events,
            "generated_at": datetime.now(pst).strftime("%Y-%m-%d %H:%M:%S PST"),
            "total_events": len(events),
            "date_range_start": (
                date_range[0].strftime("%B %d, %Y") if date_range else None
            ),
            "date_range_end": (
                date_range[1].strftime("%B %d, %Y") if date_range else None
            ),
        }

        # Render template
        template = self.env.get_template("events.html.j2")
        html_content = template.render(**context)

        # Write to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(html_content, encoding="utf-8")

        return str(output_file)

    def generate_text_output(
        self,
        events: List[Event],
        date_range: tuple = None,
    ) -> str:
        """
        Generate plain text output matching the example format.

        Args:
            events: List of Event objects
            date_range: Optional tuple of (start_date, end_date)

        Returns:
            Formatted text string
        """
        sorted_events = sorted(events, key=lambda e: e.start_datetime)

        lines = []

        # Add header
        if date_range:
            start_str = date_range[0].strftime("%-m/%-d")
            end_str = date_range[1].strftime("%-m/%-d")
            lines.append(
                f"For your information, here are a few additional upcoming events "
                f"that will be held in the next two weeks ({start_str}-{end_str}) "
                f"which could be of interest to you."
            )
            lines.append("")

        # Add events
        for event in sorted_events:
            lines.append(event.to_display_string())
            lines.append("")

        return "\n".join(lines)

    def generate_export_page(
        self,
        events: List[Event],
        output_path: str,
        date_range: tuple = None,
    ) -> str:
        """
        Generate export HTML page with event selection and export functionality.

        Args:
            events: List of Event objects
            output_path: Path to write HTML file
            date_range: Optional tuple of (start_date, end_date) for header

        Returns:
            Path to generated file
        """
        # Sort events by date
        sorted_events = sorted(events, key=lambda e: e.start_datetime)

        # Create JSON-serializable event data for JavaScript
        events_json = json.dumps(
            [
                {
                    "title": e.title,
                    "url": e.url,
                    "source": e.source,
                    "speakers": e.speakers,
                    "date_range": e.format_date_range(),
                    "location": e.format_location(),
                    "cost": e.format_cost(),
                }
                for e in sorted_events
            ],
            ensure_ascii=False,
        )

        # Get unique sources for filter dropdown
        sources = sorted(set(e.source for e in sorted_events))

        # Prepare template context
        pst = pytz.timezone("America/Los_Angeles")
        context = {
            "events": sorted_events,
            "events_json": events_json,
            "sources": sources,
            "generated_at": datetime.now(pst).strftime("%Y-%m-%d %H:%M:%S PST"),
            "total_events": len(events),
            "date_range_start": (
                date_range[0].strftime("%B %d, %Y") if date_range else None
            ),
            "date_range_end": (
                date_range[1].strftime("%B %d, %Y") if date_range else None
            ),
        }

        # Render template
        template = self.env.get_template("export.html.j2")
        html_content = template.render(**context)

        # Write to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(html_content, encoding="utf-8")

        return str(output_file)

    def _group_by_date(self, events: List[Event]) -> Dict[str, List[Event]]:
        """Group events by date for organized display."""
        grouped = {}
        for event in events:
            date_key = event.start_datetime.strftime("%Y-%m-%d")
            if date_key not in grouped:
                grouped[date_key] = []
            grouped[date_key].append(event)
        return grouped
