"""
Scraper for NESTAT (New England Statistical Society) Events.
Site: https://nestat.org/
Static HTML with Bootstrap, events spread across multiple sub-pages.
"""

import re
from typing import List, Optional

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class NESTATScraper(BaseScraper):
    """Scraper for New England Statistical Society events."""

    SOURCE_NAME = "NESTAT"
    BASE_URL = "https://nestat.org/"

    # Sub-pages that may contain upcoming events
    EVENT_PAGES = [
        "https://nestat.org/upcomingevents/",
        "https://nestat.org/events/symposium/",
        "https://nestat.org/events/nerds/",
        "https://nestat.org/events/nextgen/",
        "https://nestat.org/events/pharmads/",
    ]

    async def scrape(self) -> List[Event]:
        """Scrape NESTAT events from multiple pages."""
        for page_url in self.EVENT_PAGES:
            try:
                await self.navigate_to_page(page_url)
                await self.wait_for_content("main, body", timeout=10000)

                body_text = await self.page.text_content("body") or ""
                self._parse_events(body_text, page_url)
            except Exception as e:
                self.logger.debug(f"Failed to scrape {page_url}: {e}")

        return self.events

    def _parse_events(self, body_text: str, page_url: str):
        """Parse events from page text."""
        # Look for heading patterns with dates
        # Pattern: "38th New England Statistics Symposium (June 2-3, 2025)"
        heading_pattern = re.compile(
            r"(?:Announcing\s+)?(?:the\s+)?(.+?)\s*"
            r"\((\w+\s+\d{1,2}(?:\s*[-–]\s*\d{1,2})?,?\s+\d{4})\)",
            re.IGNORECASE
        )

        for match in heading_pattern.finditer(body_text):
            title = match.group(1).strip()
            date_text = match.group(2)

            if len(title) < 10:
                continue

            # Skip if already found
            if any(e.title == title for e in self.events):
                continue

            try:
                start_dt, end_dt = DateParser.parse_datetime_range(f"{date_text} ET")
            except Exception:
                continue

            # Find registration or detail URL near this text
            url = self._find_url_near(body_text, match.end()) or page_url

            self.events.append(self.create_event(
                title=title,
                url=url,
                start_datetime=start_dt,
                end_datetime=end_dt,
                speakers=[],
                location_type=LocationType.IN_PERSON,
                cost="",
                raw_date_text=date_text,
            ))

        # Also look for standalone date + title patterns
        date_pattern = re.compile(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2}(?:\s*[-–]\s*\d{1,2})?,?\s+\d{4})",
            re.IGNORECASE
        )

        for match in date_pattern.finditer(body_text):
            date_text = match.group(1)

            # Find title nearby
            context_start = max(0, match.start() - 200)
            context = body_text[context_start:match.start()]
            lines = context.strip().split("\n")

            title = None
            for line in reversed(lines):
                line = line.strip()
                if len(line) > 20 and not re.match(r"^(Date|When|Where|Time)", line, re.IGNORECASE):
                    title = line
                    break

            if not title or any(e.raw_date_text == date_text for e in self.events):
                continue

            try:
                start_dt, end_dt = DateParser.parse_datetime_range(f"{date_text} ET")
            except Exception:
                continue

            url = self._find_url_near(body_text, match.end()) or page_url

            self.events.append(self.create_event(
                title=title[:200],
                url=url,
                start_datetime=start_dt,
                end_datetime=end_dt,
                speakers=[],
                location_type=LocationType.IN_PERSON,
                cost="",
                raw_date_text=date_text,
            ))

    def _find_url_near(self, text: str, position: int) -> Optional[str]:
        """Find a URL near a position in the text."""
        search_area = text[position:position + 500]
        match = re.search(
            r"(https?://(?:archive\.nestat\.org|[^\s]+(?:register|learn|symposium))[^\s]*)",
            search_area, re.IGNORECASE
        )
        if match:
            return match.group(1)
        return None
