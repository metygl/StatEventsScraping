"""
Scraper for ASA San Diego Chapter Events.
Site: https://community.amstat.org/sdasa/home
Higher Logic community platform with React rendering.
"""

import re
import asyncio
from typing import List, Optional

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class ASASanDiegoScraper(BaseScraper):
    """Scraper for ASA San Diego Chapter events."""

    SOURCE_NAME = "ASA San Diego Chapter"
    BASE_URL = "https://community.amstat.org/sdasa/home"

    async def scrape(self) -> List[Event]:
        """Scrape ASA San Diego Chapter event listings."""
        # Use domcontentloaded since it's a React SPA
        await self.page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=30000)

        # Wait for React to hydrate
        await asyncio.sleep(5)

        await self.wait_for_content("#MPContentArea, main, body", timeout=10000)

        body_text = await self.page.text_content("body") or ""

        # Parse events from the rich text content
        self._parse_events(body_text)

        return self.events

    def _parse_events(self, body_text: str):
        """Parse events from the page text."""
        # Look for date patterns with event context
        # Pattern: "When: January 22-23, 2026" or standalone dates

        # Try labeled date patterns first
        labeled = re.finditer(
            r"(?:When|Date)[:\s]+"
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2}(?:\s*[-–]\s*\d{1,2})?,?\s+\d{4})",
            body_text, re.IGNORECASE
        )

        for match in labeled:
            date_text = match.group(1)
            start_pos = max(0, match.start() - 500)

            # Find the title before this date
            context = body_text[start_pos:match.start()]
            title = self._extract_title_from_context(context)

            if not title:
                continue

            # Look for location after the date
            after_text = body_text[match.end():match.end() + 500]
            location = self._extract_location(after_text)

            # Look for registration URL
            url_match = re.search(r"(https?://[^\s]+)", after_text)
            url = url_match.group(1) if url_match else self.BASE_URL

            # Add PT timezone (San Diego is Pacific)
            if not re.search(r"\b(?:PT|PST|PDT|ET)\b", date_text, re.IGNORECASE):
                date_text = f"{date_text} PT"

            try:
                start_dt, end_dt = DateParser.parse_datetime_range(date_text)
            except Exception:
                continue

            if any(e.title == title for e in self.events):
                continue

            location_type = self.detect_location_type(f"{title} {after_text}")
            if location_type == LocationType.UNKNOWN:
                location_type = LocationType.IN_PERSON

            self.events.append(self.create_event(
                title=title,
                url=url,
                start_datetime=start_dt,
                end_datetime=end_dt,
                speakers=[],
                location_type=location_type,
                location_details=location,
                cost="",
                raw_date_text=date_text,
            ))

    def _extract_title_from_context(self, context: str) -> Optional[str]:
        """Extract event title from context text before a date."""
        lines = context.strip().split("\n")
        # Work backwards to find a substantial title line
        for line in reversed(lines):
            line = line.strip()
            if len(line) > 15 and not re.match(r"^(When|Where|Date|Time|Cost|Register)", line, re.IGNORECASE):
                # Clean the title
                line = re.sub(r"^\d+\.\s*", "", line)  # Remove numbering
                if len(line) > 15:
                    return line[:200]
        return None

    def _extract_location(self, text: str) -> Optional[str]:
        """Extract location from text after date."""
        match = re.search(
            r"(?:Where|Location)[:\s]+([^\n]+)",
            text, re.IGNORECASE
        )
        if match:
            location = match.group(1).strip()
            if len(location) > 5:
                return location[:100]
        return None
