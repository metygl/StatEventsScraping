"""
Scraper for ASA Georgia Chapter Events.
Site: https://www.amstatgeorgia.org/events
Squarespace static site with simple heading + paragraph structure.
"""

import re
from typing import List, Optional

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class ASAGeorgiaScraper(BaseScraper):
    """Scraper for ASA Georgia Chapter events."""

    SOURCE_NAME = "ASA Georgia Chapter"
    BASE_URL = "https://www.amstatgeorgia.org/events"

    async def scrape(self) -> List[Event]:
        """Scrape ASA Georgia event listings."""
        await self.navigate_to_page()

        await self.wait_for_content("main, .content, body", timeout=10000)

        body_text = await self.page.text_content("body") or ""

        # Parse events from Squarespace page structure
        # Events are under "Upcoming events" heading, each as h3 + paragraphs
        headings = await self.get_all_elements("h3")

        for heading in headings:
            try:
                title = await self.get_element_text(heading)
                if not title or len(title) < 10:
                    continue

                # Skip section headers
                if any(skip in title.lower() for skip in [
                    "upcoming event", "past event", "menu", "footer"
                ]):
                    continue

                # Get following paragraph text
                event_text = await heading.evaluate("""
                    el => {
                        let text = '';
                        let sibling = el.nextElementSibling;
                        while (sibling && sibling.tagName !== 'H3' && sibling.tagName !== 'H2') {
                            text += sibling.textContent + '\\n';
                            sibling = sibling.nextElementSibling;
                        }
                        return text;
                    }
                """)

                if not event_text:
                    continue

                event = self._parse_event(title, event_text)
                if event and not any(e.title == event.title for e in self.events):
                    self.events.append(event)

            except Exception as e:
                self.logger.debug(f"Failed to parse Georgia event: {e}")

        return self.events

    def _parse_event(self, title: str, text: str) -> Optional[Event]:
        """Parse event from title and paragraph text."""
        # Extract date from labeled fields
        date_text = self._extract_date(text)
        if not date_text:
            return None

        # Extract time
        time_text = self._extract_time(text)
        full_date = f"{date_text} {time_text}".strip()

        # Add ET timezone
        if not re.search(r"\b(?:ET|EST|EDT)\b", full_date, re.IGNORECASE):
            full_date = f"{full_date} ET"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(full_date)
        except Exception:
            return None

        # Extract speakers
        speakers = self._extract_speakers(text)

        # Detect location type
        location_type = self.detect_location_type(text)
        if location_type == LocationType.UNKNOWN:
            location_type = LocationType.VIRTUAL

        # Extract URL (zoom or registration link)
        url = self._extract_url(text) or self.BASE_URL

        return self.create_event(
            title=title.strip(),
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=location_type,
            cost="free",
            raw_date_text=full_date,
        )

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date from text with labels."""
        # Pattern: "Date: January 15, 2026"
        match = re.search(
            r"Date[:\s]+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?,?\s*"
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)

        # Standalone date
        match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)

        return None

    def _extract_time(self, text: str) -> str:
        """Extract time from text."""
        match = re.search(
            r"(?:Time[:\s]+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*[-–]\s*\d{1,2}(?::\d{2})?\s*(?:am|pm))"
            r"(?:\s*(ET|EST|EDT))?",
            text, re.IGNORECASE
        )
        if match:
            result = match.group(1)
            if match.group(2):
                result = f"{result} {match.group(2)}"
            return result
        return ""

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speakers from text."""
        speakers = []
        match = re.search(
            r"Speaker[:\s]+(?:Dr\.?\s+)?([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            text
        )
        if match:
            speakers.append(match.group(1).strip())
        return speakers

    def _extract_url(self, text: str) -> Optional[str]:
        """Extract event URL from text."""
        match = re.search(r"(https?://[^\s]+(?:zoom|register|event)[^\s]*)", text, re.IGNORECASE)
        if match:
            return match.group(1)
        return None
