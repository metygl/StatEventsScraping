"""
Scraper for ASA Central Indiana Chapter Events.
Site: https://community.amstat.org/asacentralindiana/home
Higher Logic community platform with React hydration, announcement blocks.
"""

import re
import asyncio
from typing import List, Optional

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class ASAIndianaScraper(BaseScraper):
    """Scraper for ASA Central Indiana Chapter events."""

    SOURCE_NAME = "ASA Central Indiana"
    BASE_URL = "https://community.amstat.org/asacentralindiana/home"

    async def scrape(self) -> List[Event]:
        """Scrape ASA Central Indiana event listings from homepage announcements."""
        # Higher Logic React SPA - use domcontentloaded
        await self.page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=30000)

        # Wait for React to hydrate
        await asyncio.sleep(5)

        await self.wait_for_content("#MPContentArea, main, body", timeout=10000)

        body_text = await self.page.text_content("body") or ""

        # Parse events from announcement blocks
        self._parse_events(body_text)

        return self.events

    def _parse_events(self, body_text: str):
        """Parse events from homepage announcement blocks.

        Announcements contain labeled fields like:
        Speaker: Dr. Jane Smith
        Date: Tuesday, February 10, 2026, Noon - 1:00 ET
        Place: Virtual (Zoom)
        Cost: Free
        """
        # Find date patterns to anchor event blocks
        date_matches = list(re.finditer(
            r"(?:Date|When)[:\s]+"
            r"((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?,?\s*"
            r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4}"
            r"[^\n]*)",
            body_text, re.IGNORECASE
        ))

        for match in date_matches:
            date_text = match.group(1).strip()

            # Get surrounding context
            start_pos = max(0, match.start() - 1000)
            end_pos = min(len(body_text), match.end() + 500)
            before_text = body_text[start_pos:match.start()]
            after_text = body_text[match.end():end_pos]

            event = self._parse_event_block(date_text, before_text, after_text)
            if event and not any(e.title == event.title for e in self.events):
                self.events.append(event)

    def _parse_event_block(self, date_text: str, before_text: str, after_text: str) -> Optional[Event]:
        """Parse a single event from context around a date match."""
        # Handle "Noon" and "Midnight" in date text
        normalized_date = self._normalize_time_words(date_text)

        # Add ET timezone if not present (Indiana chapter is Eastern Time)
        if not re.search(r"\b(?:ET|EST|EDT|PT|PST|PDT|CT|CST|CDT)\b", normalized_date, re.IGNORECASE):
            normalized_date = f"{normalized_date} ET"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(normalized_date)
        except Exception:
            return None

        # Extract title from before text
        title = self._extract_title(before_text)
        if not title:
            return None

        # Extract speaker
        speakers = self._extract_speakers(before_text + after_text)

        # Extract location/type
        full_context = before_text + date_text + after_text
        location_type = self.detect_location_type(full_context)
        location_details = self._extract_location(full_context)
        if location_type == LocationType.UNKNOWN:
            location_type = LocationType.VIRTUAL  # Default for this chapter

        # Extract cost
        cost = self._extract_cost(full_context)

        # Extract registration URL
        url = self._extract_url(full_context) or self.BASE_URL

        return self.create_event(
            title=title,
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=location_type,
            location_details=location_details,
            cost=cost,
            raw_date_text=normalized_date,
        )

    def _normalize_time_words(self, text: str) -> str:
        """Convert word-based times like 'Noon' and 'Midnight' to numeric.

        Also handles 'Noon - 1:00' → '12:00pm - 1:00pm' to ensure
        the end time inherits pm when it lacks an am/pm suffix.
        """
        # Handle "Noon - H:MM" pattern (end time lacks am/pm, should be pm)
        text = re.sub(
            r"\bNoon\s*[-–]\s*(\d{1,2}:\d{2})\b(?!\s*[ap]m)",
            r"12:00pm - \1pm",
            text, flags=re.IGNORECASE
        )
        # Handle remaining standalone Noon/Midnight
        text = re.sub(r"\bNoon\b", "12:00pm", text, flags=re.IGNORECASE)
        text = re.sub(r"\bMidnight\b", "12:00am", text, flags=re.IGNORECASE)
        return text

    def _extract_title(self, before_text: str) -> Optional[str]:
        """Extract event title from text before the date.

        The title is typically labeled with 'Title:' or is the talk/presentation
        title appearing as a longer text line in the announcement.
        """
        # First try explicit "Title:" label
        match = re.search(r"Title[:\s]+(.+)", before_text, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            # Clean non-breaking spaces
            title = title.replace("\xa0", " ").strip()
            if len(title) > 10:
                return title[:300]

        lines = [l.strip() for l in before_text.split("\n") if l.strip()]

        # Work backwards from the date to find the title
        for line in reversed(lines):
            # Skip labeled fields
            if re.match(r"^(?:Speaker|Date|Time|Location|Place|Cost|Register|When|Where|Topic)[:\s]", line, re.IGNORECASE):
                continue
            # Skip short lines (navigation, labels)
            if len(line) < 15:
                continue
            # Skip lines that look like navigation or headers
            if re.match(r"^(?:Home|About|Events|Contact|Chapter|News|Upcoming)", line, re.IGNORECASE):
                continue
            # This is likely the title
            return line[:300]

        return None

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speaker names from text."""
        speakers = []

        match = re.search(
            r"(?:Speaker|Presenter)[s]?[:\s]+([^\n]+)",
            text, re.IGNORECASE
        )
        if match:
            speaker_text = match.group(1).strip()
            # Remove affiliations in parentheses
            speaker_text = re.sub(r"\s*\([^)]+\)", "", speaker_text)
            # Remove degree suffixes
            speaker_text = re.sub(r",?\s*(?:PhD|MD|MBA|JD|MS|MSc|MPH|DrPH|PharmD)\.?", "", speaker_text)
            # Split on commas, semicolons, "and"
            names = re.split(r"\s*[;,&]\s*(?:and\s+)?|\s+and\s+", speaker_text)
            for name in names:
                name = name.strip()
                if name and len(name) > 3 and any(c.isupper() for c in name):
                    speakers.append(name)

        return speakers

    def _extract_location(self, text: str) -> Optional[str]:
        """Extract location details from text."""
        match = re.search(
            r"(?:Place|Location|Where|Venue)[:\s]+([^\n]+)",
            text, re.IGNORECASE
        )
        if match:
            location = match.group(1).strip()
            if len(location) > 3:
                return location[:150]
        return None

    def _extract_cost(self, text: str) -> str:
        """Extract cost information from text."""
        match = re.search(
            r"(?:Cost|Price|Fee)[:\s]+([^\n]+)",
            text, re.IGNORECASE
        )
        if match:
            return self.normalize_cost(match.group(1))

        if "free" in text.lower():
            return "free"

        return ""

    def _extract_url(self, text: str) -> Optional[str]:
        """Extract registration or event URL from text."""
        # Look for Zoom links
        match = re.search(r"(https?://[^\s]*zoom\.us/[^\s]+)", text)
        if match:
            return match.group(1)

        # Look for registration URLs
        match = re.search(r"(https?://[^\s]+(?:register|registration|signup|rsvp)[^\s]*)", text, re.IGNORECASE)
        if match:
            return match.group(1)

        # Look for eventbrite
        match = re.search(r"(https?://(?:www\.)?eventbrite\.com/[^\s]+)", text)
        if match:
            return match.group(1)

        return None
