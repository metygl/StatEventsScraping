"""
Scraper for ASA New Jersey Chapter Events.
Site: http://asanjchapter.org/
Very basic static HTML site with workshop listings.
"""

import re
from typing import List, Optional

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class ASANewJerseyScraper(BaseScraper):
    """Scraper for ASA New Jersey Chapter events and workshops."""

    SOURCE_NAME = "ASA New Jersey Chapter"
    BASE_URL = "http://asanjchapter.org/"

    async def scrape(self) -> List[Event]:
        """Scrape ASA NJ Chapter event listings."""
        await self.navigate_to_page()

        await self.wait_for_content("body", timeout=10000)

        body_text = await self.page.text_content("body") or ""

        # Parse events from the page
        self._parse_events(body_text)

        # Also try the events page
        try:
            await self.navigate_to_page("http://asanjchapter.org/events.html")
            events_text = await self.page.text_content("body") or ""
            self._parse_events(events_text)
        except Exception as e:
            self.logger.debug(f"Could not load events page: {e}")

        return self.events

    def _parse_events(self, body_text: str):
        """Parse events from page text."""
        # Look for workshop/event entries with dates
        # Pattern: "The Nth ASA New Jersey Chapter / Bayer Statistics Workshop Oct 10, 2025"
        # or "Month DD, YYYY" dates in the text

        lines = body_text.split("\n")

        for i, line in enumerate(lines):
            line = line.strip()

            # Look for lines with dates
            date_match = re.search(
                r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*"
                r"\s+\d{1,2},?\s+\d{4})",
                line, re.IGNORECASE
            )

            if not date_match:
                continue

            date_text = date_match.group(1)

            # The title is usually on the same line or preceding line
            title = self._extract_title_near(lines, i, line, date_text)
            if not title or len(title) < 10:
                continue

            # Add ET timezone
            full_date = f"{date_text} ET"

            try:
                start_dt, end_dt = DateParser.parse_datetime_range(full_date)
            except Exception:
                continue

            # Check if this event already exists
            if any(e.title == title for e in self.events):
                continue

            # Get nearby URL if available
            url = self._find_url_near(lines, i) or self.BASE_URL

            self.events.append(self.create_event(
                title=title,
                url=url,
                start_datetime=start_dt,
                end_datetime=end_dt,
                speakers=[],
                location_type=LocationType.IN_PERSON,
                cost="",
                raw_date_text=full_date,
            ))

    def _extract_title_near(self, lines: List[str], idx: int, line: str, date_text: str) -> Optional[str]:
        """Extract event title near a date line."""
        # If the line has text before the date, use that
        before_date = line[:line.find(date_text[:3])].strip()
        if before_date and len(before_date) > 15:
            # Clean up the title
            title = re.sub(r"\s*\(SLIDES\)\s*$", "", before_date, flags=re.IGNORECASE)
            return title.strip()

        # Otherwise look at the preceding line
        if idx > 0:
            prev = lines[idx - 1].strip()
            if prev and len(prev) > 15 and not re.match(r"^\d", prev):
                return prev

        # Use the full line minus the date
        remaining = line.replace(date_text, "").strip(" ,-")
        if remaining and len(remaining) > 15:
            remaining = re.sub(r"\s*\(SLIDES\)\s*$", "", remaining, flags=re.IGNORECASE)
            return remaining.strip()

        return None

    def _find_url_near(self, lines: List[str], idx: int) -> Optional[str]:
        """Find a URL near the given line index."""
        for i in range(max(0, idx - 2), min(len(lines), idx + 5)):
            match = re.search(r"(https?://[^\s]+)", lines[i])
            if match:
                return match.group(1)
        return None
