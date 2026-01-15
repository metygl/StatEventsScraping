"""
Event data model with validation and PST normalization.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum
import pytz


class LocationType(Enum):
    VIRTUAL = "Virtual"
    IN_PERSON = "In-Person"
    HYBRID = "Hybrid"
    UNKNOWN = "Unknown"


@dataclass
class Event:
    """Represents a single event with all extracted information."""

    # Required fields
    title: str
    url: str
    source: str  # Which site this came from

    # Date/time fields
    start_datetime: datetime  # Normalized to PST
    end_datetime: Optional[datetime] = None

    # Optional details
    speakers: List[str] = field(default_factory=list)
    location_type: LocationType = LocationType.UNKNOWN
    location_details: Optional[str] = None  # City/venue for in-person
    cost: Optional[str] = None  # "free", "$50", "$100-$200"
    description: Optional[str] = None

    # Metadata
    scraped_at: datetime = field(default_factory=lambda: datetime.now(pytz.UTC))
    raw_date_text: Optional[str] = None  # Original date text for debugging

    def __post_init__(self):
        """Validate and normalize after initialization."""
        self.title = self.title.strip() if self.title else ""
        self.url = self.url.strip() if self.url else ""
        self.speakers = [s.strip() for s in self.speakers if s and s.strip()]

        # Ensure datetime is timezone-aware PST
        pst = pytz.timezone("America/Los_Angeles")
        if self.start_datetime.tzinfo is None:
            self.start_datetime = pst.localize(self.start_datetime)
        else:
            self.start_datetime = self.start_datetime.astimezone(pst)

        if self.end_datetime:
            if self.end_datetime.tzinfo is None:
                self.end_datetime = pst.localize(self.end_datetime)
            else:
                self.end_datetime = self.end_datetime.astimezone(pst)

    def format_date_range(self) -> str:
        """Format date/time for display output."""
        pst = pytz.timezone("America/Los_Angeles")
        start = self.start_datetime.astimezone(pst)

        date_str = start.strftime("%B %d, %Y")
        start_time = start.strftime("%I:%M").lstrip("0")
        start_ampm = start.strftime("%p").lower()

        if self.end_datetime:
            end = self.end_datetime.astimezone(pst)
            end_time = end.strftime("%I:%M%p").lstrip("0").lower()
            return f"{date_str}, {start_time}-{end_time} PST"
        else:
            return f"{date_str}, {start_time}{start_ampm} PST"

    def format_cost(self) -> str:
        """Format cost for display."""
        if not self.cost or self.cost.lower() in ["free", "0", "$0", "$0.00"]:
            return "free"
        return self.cost

    def format_location(self) -> str:
        """Format location for display."""
        if self.location_type == LocationType.VIRTUAL:
            return "Virtual"
        elif self.location_type == LocationType.IN_PERSON:
            return self.location_details or "In-Person"
        elif self.location_type == LocationType.HYBRID:
            return f"Hybrid - {self.location_details}" if self.location_details else "Hybrid"
        return "TBD"

    def to_display_string(self) -> str:
        """Generate the formatted output string matching the example format."""
        # Format speakers
        speakers_str = f" ({', '.join(self.speakers)})" if self.speakers else ""

        # Build the output
        lines = [
            f"\t\u2022\t{self.source}: {self.title}{speakers_str}",
            self.url,
            f"{self.format_date_range()}, {self.format_location()} ({self.format_cost()})",
        ]
        return "\n".join(lines)

    def is_within_date_range(self, start_date: datetime, end_date: datetime) -> bool:
        """Check if event falls within the specified date range."""
        pst = pytz.timezone("America/Los_Angeles")

        # Ensure comparison dates are timezone-aware
        if start_date.tzinfo is None:
            start_date = pst.localize(start_date)
        if end_date.tzinfo is None:
            end_date = pst.localize(end_date)

        return start_date <= self.start_datetime <= end_date

    def __lt__(self, other: "Event") -> bool:
        """Enable sorting by start datetime."""
        return self.start_datetime < other.start_datetime
