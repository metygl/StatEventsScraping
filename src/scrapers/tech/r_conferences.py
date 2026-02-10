"""
Scraper for R Conferences listing.
Site: https://www.r-project.org/conferences/
"""

import re
from typing import List, Optional

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class RConferencesScraper(BaseScraper):
    """Scraper for R project conferences page (static HTML, list-based)."""

    SOURCE_NAME = "R Conference"
    BASE_URL = "https://www.r-project.org/conferences/"

    async def scrape(self) -> List[Event]:
        """Scrape R conferences listing page."""
        await self.navigate_to_page()

        await self.wait_for_content("ul, main, body", timeout=10000)

        body_text = await self.page.text_content("body") or ""

        # R conferences are listed as <li> elements with links
        links = await self.get_all_elements("li a")

        for link in links:
            try:
                event = await self._parse_conference_link(link, body_text)
                if event and not any(e.url == event.url for e in self.events):
                    self.events.append(event)
            except Exception as e:
                self.logger.debug(f"Failed to parse R conference link: {e}")

        return self.events

    async def _parse_conference_link(self, link, body_text: str) -> Optional[Event]:
        """Parse a conference from its link element."""
        href = await self.get_href(link)
        text = await self.get_element_text(link)

        if not href or not text:
            return None

        # Conference links typically contain year: "useR! 2026"
        # Skip non-conference links
        if not re.search(r"\b20\d{2}\b", text):
            return None

        # Extract year from text
        year_match = re.search(r"\b(20\d{2})\b", text)
        if not year_match:
            return None

        year = int(year_match.group(1))

        # Only include current and future conferences
        from datetime import datetime
        if year < datetime.now().year:
            return None

        title = text.strip()

        # Get the parent <li> text for location info
        parent = await link.evaluate_handle("el => el.parentElement")
        parent_text = ""
        if parent:
            parent_text = await parent.evaluate("el => el.textContent") or ""

        # Try to extract location from parent text (after the link, usually "City, Country")
        location = self._extract_location(parent_text, title)

        # Try to extract dates from parent text
        date_text = self._extract_dates(parent_text)
        if not date_text:
            # Default to July 1 of the year (typical useR! timing)
            date_text = f"July 1, {year}"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(date_text)
        except Exception:
            return None

        return self.create_event(
            title=title,
            url=href,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=[],
            location_type=LocationType.IN_PERSON,
            location_details=location,
            cost="",
            raw_date_text=date_text,
        )

    def _extract_location(self, parent_text: str, title: str) -> Optional[str]:
        """Extract location from the parent list item text."""
        # Remove the title portion
        remaining = parent_text.replace(title, "").strip()
        # Remove "(local copy)" and similar parenthetical
        remaining = re.sub(r"\(local copy\)", "", remaining, flags=re.IGNORECASE)
        remaining = re.sub(r"\(.*?\)", "", remaining)
        # Clean up
        remaining = remaining.strip(" ,.-")
        if remaining and len(remaining) > 3:
            return remaining
        return None

    def _extract_dates(self, text: str) -> Optional[str]:
        """Extract date range from text."""
        # Pattern: "June 30 - July 4, 2026"
        match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2})\s*[-–]\s*"
            r"((?:(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+)?"
            r"\d{1,2},?\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1) + " " + match.group(2).split(",")[0].split()[-1] + ", " + re.search(r"\d{4}", match.group(2)).group()

        # Pattern: "Month DD, YYYY"
        match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)

        return None
