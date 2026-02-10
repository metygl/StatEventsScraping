"""
Scraper for ASA Boston Chapter Events.
Site: https://community.amstat.org/bostonchapter/upcoming-events/upcoming-events
Higher Logic community platform with React hydration, rich text content.
"""

import re
import asyncio
from typing import List, Optional

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class ASABostonScraper(BaseScraper):
    """Scraper for ASA Boston Chapter events."""

    SOURCE_NAME = "ASA Boston Chapter"
    BASE_URL = "https://community.amstat.org/bostonchapter/upcoming-events/upcoming-events"

    async def scrape(self) -> List[Event]:
        """Scrape ASA Boston Chapter event listings."""
        await self.page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=30000)

        # Wait for React to hydrate
        await asyncio.sleep(5)

        await self.wait_for_content("#MPContentArea, main, body", timeout=10000)

        body_text = await self.page.text_content("body") or ""

        # Parse events from the rich text content
        self._parse_events(body_text)

        return self.events

    def _parse_events(self, body_text: str):
        """Parse events from rich text content.

        Events are separated by horizontal rules or clear visual breaks.
        Each event has a bold title, date/time, location, speaker info.
        """
        # Split on common separators
        blocks = re.split(r"(?:\n\s*[-_=]{3,}\s*\n|\n{3,})", body_text)

        for block in blocks:
            block = block.strip()
            if len(block) < 50:
                continue

            event = self._parse_event_block(block)
            if event and not any(e.title == event.title for e in self.events):
                self.events.append(event)

    def _parse_event_block(self, block: str) -> Optional[Event]:
        """Parse a single event block."""
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if len(lines) < 2:
            return None

        # Extract date
        date_text = self._extract_date(block)
        if not date_text:
            return None

        # Add ET timezone
        if not re.search(r"\b(?:ET|EST|EDT)\b", date_text, re.IGNORECASE):
            date_text = f"{date_text} ET"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(date_text)
        except Exception:
            return None

        # Extract title (first substantial line that isn't a date or label)
        title = self._extract_title(lines)
        if not title:
            return None

        # Extract speakers
        speakers = self._extract_speakers(block)

        # Extract location/type
        location_type = self.detect_location_type(block)
        if location_type == LocationType.UNKNOWN:
            location_type = LocationType.VIRTUAL

        # Extract URL (registration link)
        url = self._extract_url(block) or self.BASE_URL

        # Extract cost
        cost = "free" if "free" in block.lower() else ""

        return self.create_event(
            title=title,
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=location_type,
            cost=cost,
            raw_date_text=date_text,
        )

    def _extract_title(self, lines: List[str]) -> Optional[str]:
        """Extract event title from lines."""
        for line in lines[:5]:
            # Skip date-like lines, labels, and short text
            if re.match(r"^(?:Date|Time|Location|Speaker|Cost|Register|When|Where)[:\s]", line, re.IGNORECASE):
                continue
            if re.match(r"^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)", line, re.IGNORECASE):
                continue
            if len(line) < 10:
                continue
            # Likely a title
            return line[:200]
        return None

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date from text."""
        # Pattern: "Date/Time: Thursday, January 11, 2026, 6-7:30pm EST"
        match = re.search(
            r"(?:Date(?:/Time)?|When)[:\s]+"
            r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?,?\s*"
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})"
            r"(?:[,\s]+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*[-–]\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)))?",
            text, re.IGNORECASE
        )
        if match:
            result = match.group(1)
            if match.group(2):
                result = f"{result} {match.group(2)}"
            return result

        # Standalone date
        match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)

        return None

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speakers from text."""
        speakers = []

        match = re.search(
            r"(?:Speaker|Presenter|Dr\.)[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            text
        )
        if match:
            speakers.append(match.group(1).strip())

        return speakers

    def _extract_url(self, text: str) -> Optional[str]:
        """Extract registration URL from text."""
        match = re.search(r"(https?://(?:www\.)?eventbrite\.com/[^\s]+)", text)
        if match:
            return match.group(1)

        match = re.search(r"(https?://[^\s]+(?:register|registration|signup)[^\s]*)", text, re.IGNORECASE)
        if match:
            return match.group(1)

        return None
